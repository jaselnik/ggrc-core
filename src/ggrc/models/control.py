# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for Control model."""

from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates

from ggrc import db
from ggrc import utils as ggrc_utils
from ggrc.models import comment
from ggrc.models.mixins.with_similarity_score import WithSimilarityScore
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.mixins import base, categorizable
from ggrc.models.mixins import synchronizable
from ggrc.models.mixins import with_external_created_by
from ggrc.models import mixins, utils
from ggrc.models.mixins.with_last_assessment_date import WithLastAssessmentDate
from ggrc.models.deferred import deferred
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.fulltext.mixin import Indexed
from ggrc.fulltext import attributes
from ggrc.models import reflection
from ggrc.models.exceptions import ValidationError


class Control(with_external_created_by.WithExternalCreatedBy,
              synchronizable.Synchronizable,
              categorizable.Categorizable,
              WithLastAssessmentDate,
              synchronizable.RoleableSynchronizable,
              Relatable,
              mixins.CustomAttributable,
              Personable,
              PublicDocumentable,
              mixins.LastDeprecatedTimeboxed,
              mixins.TestPlanned,
              comment.ExternalCommentable,
              WithSimilarityScore,
              base.ContextRBAC,
              mixins.BusinessObject,
              mixins.WithWorkflowState,
              Indexed,
              mixins.Folderable,
              db.Model):
  """Control model definition."""
  __tablename__ = 'controls'

  company_control = deferred(db.Column(db.Boolean), 'Control')
  directive_id = deferred(
      db.Column(db.Integer, db.ForeignKey('directives.id')), 'Control')
  version = deferred(db.Column(db.String), 'Control')
  fraud_related = deferred(db.Column(db.Boolean), 'Control')
  key_control = deferred(db.Column(db.Boolean), 'Control')
  active = deferred(db.Column(db.Boolean), 'Control')
  kind = deferred(db.Column(db.String), "Control")
  means = deferred(db.Column(db.String), "Control")
  verify_frequency = deferred(db.Column(db.String), "Control")
  review_status = deferred(db.Column(db.String, nullable=True), "Control")
  review_status_display_name = deferred(db.Column(db.String, nullable=True),
                                        "Control")

  # GGRCQ attributes
  due_date = db.Column(db.Date, nullable=True)
  last_submitted_at = db.Column(db.DateTime, nullable=True)
  last_submitted_by_id = db.Column(db.Integer, nullable=True)

  # pylint: disable=no-self-argument
  @declared_attr
  def last_submitted_by(cls):
    """Relationship to user referenced by last_submitted_by_id."""
    return utils.person_relationship(cls.__name__, "last_submitted_by_id")

  last_verified_at = db.Column(db.DateTime, nullable=True)
  last_verified_by_id = db.Column(db.Integer, nullable=True)

  # pylint: disable=no-self-argument
  @declared_attr
  def last_verified_by(cls):
    """Relationship to user referenced by last_verified_by_id."""
    return utils.person_relationship(cls.__name__, "last_verified_by_id")

  _title_uniqueness = False

  _custom_publish = {
      'last_submitted_by': ggrc_utils.last_submitted_by_stub,
      'last_verified_by': ggrc_utils.last_verified_by_stub,
  }

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'active',
      'company_control',
      'directive',
      'fraud_related',
      'key_control',
      'kind',
      'means',
      'verify_frequency',
      'version',
      'review_status',
      'review_status_display_name',
      'due_date',
      'last_submitted_at',
      reflection.ExternalUserAttribute('last_submitted_by',
                                       force_create=True),
      'last_verified_at',
      reflection.ExternalUserAttribute('last_verified_by',
                                       force_create=True),
  )

  _fulltext_attrs = [
      'active',
      'company_control',
      'directive',
      attributes.BooleanFullTextAttr(
          'fraud_related',
          'fraud_related',
          true_value="yes", false_value="no"),
      attributes.BooleanFullTextAttr(
          'key_control',
          'key_control',
          true_value="key", false_value="non-key"),
      'kind',
      'means',
      'verify_frequency',
      'version',
      'review_status_display_name',

      attributes.DateFullTextAttr(
          "due_date",
          "due_date",
      ),
      attributes.DatetimeFullTextAttr(
          "last_submitted_at",
          "last_submitted_at",
      ),
      attributes.FullTextAttr(
          "last_submitted_by",
          "last_submitted_by",
          ["email", "name"],
      ),
      attributes.DatetimeFullTextAttr(
          "last_verified_at",
          "last_verified_at",
      ),
      attributes.FullTextAttr(
          "last_verified_by",
          "last_verified_by",
          ["email", "name"],
      )
  ]

  _sanitize_html = [
      'version',
  ]

  @classmethod
  def indexed_query(cls):
    return super(Control, cls).indexed_query().options(
        orm.Load(cls).undefer_group(
            "Control_complete"
        ),
        orm.Load(cls).joinedload(
            "directive"
        ).undefer_group(
            "Directive_complete"
        ),
    )

  _include_links = []

  _aliases = {
      "kind": "Kind/Nature",
      "means": "Type/Means",
      "verify_frequency": "Frequency",
      "fraud_related": "Fraud Related",
      "key_control": {
          "display_name": "Significance",
          "description": "Allowed values are:\nkey\nnon-key\n---",
      },
      "test_plan": "Assessment Procedure",
      "review_status": {
          "display_name": "Review State",
          "mandatory": False,
          "filter_only": True
      },
      "review_status_display_name": {
          "display_name": "Review Status",
          "mandatory": False
      },

      "due_date": {
          "display_name": "Due Date",
          "mandatory": False,
      },
      "last_submitted_at": {
          "display_name": "Last Owner Reviewed Date",
          "mandatory": False,
      },
      "last_submitted_by": {
          "display_name": "Last Owner Reviewed By",
          "mandatory": False,
      },
      "last_verified_at": {
          "display_name": "Last Compliance Reviewed Date",
          "mandatory": False,
      },
      "last_verified_by": {
          "display_name": "Last Compliance Reviewed By",
          "mandatory": False,
      },
  }

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(Control, cls).eager_query(**kwargs)
    return cls.eager_inclusions(query, Control._include_links).options(
        orm.joinedload('directive'),
    )

  def log_json(self):
    out_json = super(Control, self).log_json()
    out_json["last_submitted_by"] = ggrc_utils.last_submitted_by_stub(self)
    out_json["last_verified_by"] = ggrc_utils.last_verified_by_stub(self)
    # so that event log can refer to deleted directive
    if self.directive:
      out_json["mapped_directive"] = self.directive.display_name
    return out_json

  @validates('review_status')
  def validate_review_status(self, _, value):  # pylint: disable=no-self-use
    """Add explicit non-nullable validation."""
    if value is None:
      raise ValidationError("review_status for the object is not specified")

    return value

  # pylint: disable=invalid-name
  @validates('review_status_display_name')
  def validate_review_status_display_name(self, _, value):
    """Add explicit non-nullable validation."""
    # pylint: disable=no-self-use,invalid-name

    if value is None:
      raise ValidationError(
          "review_status_display_name for the object is not specified")

    return value
