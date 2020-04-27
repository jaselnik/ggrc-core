# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Review model."""

import datetime

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.orm import validates

from ggrc import db
from ggrc import builder
from ggrc import utils
from ggrc.access_control import role
from ggrc.access_control import roleable
from ggrc.login import get_current_user
from ggrc.models import mixins
from ggrc.models import exceptions
from ggrc.models import comment
from ggrc.models import inflector
from ggrc.models import utils as model_utils
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models.mixins import issue_tracker
from ggrc.models.mixins import rest_handable
from ggrc.models.mixins import with_proposal_handable
from ggrc.models.mixins import with_mappimg_via_import_handable
from ggrc.models.mixins import synchronizable
from ggrc.models.mixins import with_comment_created
from ggrc.notifications import add_notification


def handle_recipients_attr(attr, changed):
  """Add attr to changed if it was changed
    Args:
      attr: db.inspect().attr object
      changed: set of changed attrs
  """
  history = attr.load_history()
  if utils.ordered_string_changed(history):
    changed.add(attr.key)


class Reviewable(rest_handable.WithPutHandable,
                 rest_handable.WithRelationshipsHandable,
                 with_proposal_handable.WithProposalHandable,
                 with_mappimg_via_import_handable.WithMappingImportHandable):
  """Mixin to setup object as reviewable."""

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute("review", create=False, update=False),
      reflection.Attribute("review_status", create=False, update=False),
      reflection.Attribute("review_issue_link", create=False, update=False),
  )

  _fulltext_attrs = ["review_status", "review_issue_link"]

  _aliases = {
      "review_status": {
          "display_name": "Review State",
          "mandatory": False,
          "skip_in_template": True,
      },
      "reviewers": {
          "display_name": "Reviewers",
          "mandatory": False,
          "skip_in_template": True,
      }
  }

  @builder.simple_property
  def review_status(self):
    return self.review.status if self.review else Review.STATES.UNREVIEWED

  @builder.simple_property
  def reviewers(self):
    """Return list of reviewer persons"""
    if self.review:
      return self.review.get_persons_for_rolename('Reviewers')
    return []

  @builder.simple_property
  def review_issue_link(self):
    """Returns review issue link for reviewable object."""
    if not self.review:
      return None
    if not self.review.issuetracker_issue:
      return None
    notification_type = self.review.notification_type
    if notification_type != Review.NotificationTypes.ISSUE_TRACKER:
      return None
    return self.review.issuetracker_issue.issue_url

  @sa.ext.declarative.declared_attr
  def review(cls):  # pylint: disable=no-self-argument
    """Declare review relationship for reviewable object."""

    def join_function():
      return sa.and_(sa.orm.foreign(Review.reviewable_type) == cls.__name__,
                     sa.orm.foreign(Review.reviewable_id) == cls.id)

    return sa.orm.relationship(
        Review,
        primaryjoin=join_function,
        backref=Review.REVIEWABLE_TMPL.format(cls.__name__),
        uselist=False,
    )

  @classmethod
  def eager_query(cls, **kwargs):
    return super(Reviewable, cls).eager_query(**kwargs).options(
        sa.orm.joinedload("review")
    )

  @classmethod
  def indexed_query(cls):
    return super(Reviewable, cls).indexed_query().options(
        sa.orm.Load(cls).subqueryload(
            "review"
        ).load_only(
            "status",
            "notification_type",
        ),
        sa.orm.Load(cls).subqueryload(
            "review"
        ).joinedload(
            "issuetracker_issue"
        ).load_only(
            "issue_url",
        ),
    )

  def log_json(self):
    """Serialize to JSON"""
    out_json = super(Reviewable, self).log_json()
    out_json["review_status"] = self.review_status

    # put proper review stub to have it in the revision content
    review_stub = None
    if self.review:
      review_stub = utils.create_stub(self.review, self.review.context_id)
    out_json["review"] = review_stub

    out_json["review_issue_link"] = self.review_issue_link
    return out_json

  ATTRS_TO_IGNORE = {"review", "updated_at", "modified_by", "modified_by_id",
                     "slug", "_access_control_list", "folder", "recipients"}

  SPECIAL_ATTRS_HANDLERS = {
      'recipients': handle_recipients_attr,
  }

  def _update_status_on_attr(self):
    """Update review status when reviewable attrs are changed"""
    if (self.review and
            self.review.status != Review.STATES.UNREVIEWED):
      changed = set()
      attrs = [attr for attr in db.inspect(self).attrs
               if attr.history.has_changes()]
      for attr in attrs:
        if attr.key in self.SPECIAL_ATTRS_HANDLERS:
          self.SPECIAL_ATTRS_HANDLERS[attr.key](attr, changed)
        else:
          changed.add(attr.key)

      if changed - self.ATTRS_TO_IGNORE:
        self._set_review_status_unreviewed()

  def _update_status_on_custom_attrs(self):
    """Update review status when reviewable custom attrs are changed"""
    if not hasattr(self, "custom_attribute_values"):
      return
    if (self.review and
            self.review.status != Review.STATES.UNREVIEWED):
      if self._has_custom_attr_changes():
        self._set_review_status_unreviewed()

  def _has_custom_attr_changes(self):
    """Check if any custom attribute changed based on history"""
    for value in self.custom_attribute_values:
      for attr_name in ("attribute_value", "attribute_object_id"):
        history = db.inspect(
            value).attrs.get(attr_name).history
        if history.has_changes():
          return True
    return False

  def add_email_notification(self):
    """Add email notification of type STATUS_UNREVIEWED"""
    if isinstance(self, synchronizable.Synchronizable):
      # External objects should not be notified.
      return

    review_notif_type = self.review.notification_type
    if review_notif_type == Review.NotificationTypes.EMAIL_TYPE:
      add_notification(self.review,
                       Review.NotificationObjectTypes.STATUS_UNREVIEWED)

  def _update_status_on_mapping(self, counterparty):
    """Update review status on mapping to reviewable"""
    if self.review_status != Review.STATES.UNREVIEWED:
      if self._is_counterparty_snapshottable(counterparty):
        self._set_review_status_unreviewed()

  def _set_review_status_unreviewed(self):
    """Set review status -> unreviewed"""
    if self.review:
      self.review.status = Review.STATES.UNREVIEWED
      self.add_email_notification()

  @staticmethod
  def _is_counterparty_snapshottable(counterparty):
    """Check that counterparty is snapshottable."""
    from ggrc.snapshotter.rules import Types
    return bool(counterparty.type in Types.all)

  def handle_put(self, initial_state):
    self._update_status_on_attr()
    self._update_status_on_custom_attrs()

  def handle_relationship_post(self, counterparty):
    self._update_status_on_mapping(counterparty)

  def handle_relationship_delete(self, counterparty):
    self._update_status_on_mapping(counterparty)

  def handle_proposal_applied(self):
    self._update_status_on_attr()
    self._update_status_on_custom_attrs()

  def handle_mapping_via_import_created(self, counterparty):
    if self._is_counterparty_snapshottable(counterparty):
      self._set_review_status_unreviewed()


class Review(mixins.person_relation_factory("last_reviewed_by"),
             mixins.person_relation_factory("created_by"),
             mixins.datetime_mixin_factory("last_reviewed_at"),
             mixins.Stateful,
             rest_handable.WithPostHandable,
             rest_handable.WithPutHandable,
             rest_handable.WithPostAfterCommitHandable,
             rest_handable.WithPutAfterCommitHandable,
             with_comment_created.WithCommentCreated,
             comment.CommentInitiator,
             roleable.Roleable,
             issue_tracker.IssueTracked,
             relationship.Relatable,
             mixins.base.ContextRBAC,
             mixins.Base,
             db.Model):
  """Review object"""
  # pylint: disable=too-few-public-methods
  __tablename__ = "reviews"

  REVIEWER_ROLE_NAME = "Reviewer"

  class STATES(object):
    """Review states container """
    REVIEWED = "Reviewed"
    UNREVIEWED = "Unreviewed"

  VALID_STATES = [STATES.UNREVIEWED, STATES.REVIEWED]

  class NotificationTypes(object):
    """Notification types container """
    EMAIL_TYPE = "email"
    ISSUE_TRACKER = "issue_tracker"

  class NotificationObjectTypes(object):
    """Review Notification Object types container """
    STATUS_UNREVIEWED = "review_status_unreviewed"
    REVIEW_CREATED = "review_request_created"

  reviewable_id = db.Column(db.Integer, nullable=False)
  reviewable_type = db.Column(db.String, nullable=False)

  REVIEWABLE_TMPL = "{}_reviewable"

  reviewable = model_utils.JsonPolymorphicRelationship(
      "reviewable_id",
      "reviewable_type",
      REVIEWABLE_TMPL,
  )

  notification_type = db.Column(
      sa.types.Enum(NotificationTypes.EMAIL_TYPE,
                    NotificationTypes.ISSUE_TRACKER),
      nullable=False,
  )
  email_message = db.Column(db.Text, nullable=False, default=u"")

  _api_attrs = reflection.ApiAttributes(
      "notification_type",
      "email_message",
      reflection.Attribute("reviewable", update=False),
      reflection.Attribute("last_reviewed_by", create=False, update=False),
      reflection.Attribute("last_reviewed_at", create=False, update=False),
      "issuetracker_issue",
      "status",
  )

  def validate_acl(self):
    """Reviewer is mandatory Role"""
    super(Review, self).validate_acl()
    review_global_roles = role.get_ac_roles_data_for("Review").values()
    mandatory_role_ids = {acr[0] for acr in review_global_roles if acr[3]}
    passed_acr_ids = {acl.ac_role_id for _, acl in self.access_control_list}
    missed_mandatory_roles = mandatory_role_ids - passed_acr_ids
    if missed_mandatory_roles:
      raise exceptions.ValidationError("{} roles are mandatory".format(
          ",".join(missed_mandatory_roles))
      )

  def _add_comment_about(self, text):
    """Create comment about proposal for reason with required text."""
    if not isinstance(self.reviewable, comment.Commentable):
      return

    text = self.clear_text(text)

    # pylint: disable=not-an-iterable
    existing_people = set(acp.person.email
                          for acl in self._access_control_list
                          for acp in acl.access_control_people)
    comment_text = (
        u"<p>Review requested from</p><p>{people}</p>"
        u"<p>with a comment: {text}</p>"
    ).format(
        people=', '.join(existing_people),
        text=text,
    )
    self.add_comment(
        comment_text,
        source=self.reviewable,
        initiator_object=self
    )

  def handle_post(self):
    """Handle POST request."""
    if self.email_message:
      self._add_comment_about(self.email_message)
    self._create_relationship()
    self._update_new_reviewed_by()
    if (self.notification_type == Review.NotificationTypes.EMAIL_TYPE and
        self.status == Review.STATES.UNREVIEWED and
            not isinstance(self.reviewable, synchronizable.Synchronizable)):
      add_notification(self, Review.NotificationObjectTypes.REVIEW_CREATED)

  def is_status_changed(self):
    """Checks whether the status has changed."""
    return inspect(self).attrs.status.history.has_changes()

  def handle_put(self, initial_state):
    """Handle PUT request."""
    if not self.is_status_changed() and self.email_message:
      self._add_comment_about(self.email_message)
    self._update_reviewed_by()

  def handle_posted_after_commit(self, event):
    """Handle POST after commit."""
    self.apply_mentions_comment(obj=self.reviewable, event=event)

  def handle_put_after_commit(self, event):
    """Handle PUT after commit."""
    self.apply_mentions_comment(obj=self.reviewable, event=event)

  def _create_relationship(self):
    """Create relationship for newly created review (used for ACL)"""
    if self in db.session.new:
      db.session.add(
          relationship.Relationship(source=self.reviewable, destination=self)
      )

  def _update_new_reviewed_by(self):
    """When create new review with state REVIEWED set last_reviewed_by"""
    # pylint: disable=attribute-defined-outside-init
    if self.status == Review.STATES.REVIEWED:
      self.last_reviewed_by = get_current_user()
      self.last_reviewed_at = datetime.datetime.utcnow()

  def _update_reviewed_by(self):
    """Update last_reviewed_by, last_reviewed_at"""
    # pylint: disable=attribute-defined-outside-init
    if not db.inspect(self).attrs["status"].history.has_changes():
      return

    self.reviewable.updated_at = datetime.datetime.utcnow()

    if self.status == Review.STATES.REVIEWED:
      self.last_reviewed_by = self.modified_by
      self.last_reviewed_at = datetime.datetime.utcnow()

  # pylint: disable=no-self-use
  @validates("reviewable_type")
  def validate_reviewable_type(self, _, reviewable_type):
    """Validate reviewable_type attribute.

    We preventing creation of reviews for external models.
    """
    reviewable_class = inflector.get_model(reviewable_type)

    if issubclass(reviewable_class, synchronizable.Synchronizable):
      raise ValueError("Trying to create review for external model.")

    return reviewable_type
