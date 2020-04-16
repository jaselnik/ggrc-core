# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for risk model."""

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates

from ggrc import db
from ggrc import utils as ggrc_utils
from ggrc.fulltext import attributes
from ggrc.fulltext.mixin import Indexed
from ggrc.models import comment
from ggrc.models import exceptions
from ggrc.models import mixins
from ggrc.models import reflection
from ggrc.models import utils
from ggrc.models.deferred import deferred
from ggrc.models.mixins import synchronizable
from ggrc.models.mixins import with_external_created_by
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.relationship import Relatable


class Risk(with_external_created_by.WithExternalCreatedBy,
           synchronizable.Synchronizable,
           synchronizable.RoleableSynchronizable,
           mixins.CustomAttributable,
           Relatable,
           PublicDocumentable,
           comment.ExternalCommentable,
           mixins.TestPlanned,
           mixins.LastDeprecatedTimeboxed,
           mixins.base.ContextRBAC,
           mixins.BusinessObject,
           mixins.Folderable,
           mixins.WithWorkflowState,
           Indexed,
           db.Model):
  """Basic Risk model."""
  __tablename__ = 'risks'

  # GGRCQ attributes
  external_id = db.Column(db.Integer, nullable=False)
  due_date = db.Column(db.Date, nullable=True)
  review_status = deferred(db.Column(db.String, nullable=True), "Risk")
  review_status_display_name = deferred(db.Column(db.String, nullable=True),
                                        "Risk")

  last_submitted_at = db.Column(db.DateTime, nullable=True)
  last_submitted_by_id = db.Column(db.Integer, nullable=True)

  # pylint: disable=no-self-argument
  @declared_attr
  def last_submitted_by(cls):
    """Relationship to user referenced by last_submitted_by_id."""
    return utils.person_relationship(cls.__name__,
                                     "last_submitted_by_id")

  last_verified_at = db.Column(db.DateTime, nullable=True)
  last_verified_by_id = db.Column(db.Integer, nullable=True)

  # pylint: disable=no-self-argument
  @declared_attr
  def last_verified_by(cls):
    """Relationship to user referenced by last_verified_by_id."""
    return utils.person_relationship(cls.__name__,
                                     "last_verified_by_id")

  # Overriding mixin to make mandatory
  @declared_attr
  def description(cls):
    #  pylint: disable=no-self-argument
    return deferred(db.Column(db.Text, nullable=False, default=u""),
                    cls.__name__)

  risk_type = db.Column(db.Text, nullable=True)
  threat_source = db.Column(db.Text, nullable=True)
  threat_event = db.Column(db.Text, nullable=True)
  vulnerability = db.Column(db.Text, nullable=True)

  @validates('review_status')
  def validate_review_status(self, _, value):
    """Add explicit non-nullable validation."""
    # pylint: disable=no-self-use

    if value is None:
      raise exceptions.ValidationError(
          "Review status for the object is not specified")

    return value

  @validates('review_status_display_name')
  def validate_review_status_display_name(self, _, value):
    """Add explicit non-nullable validation."""
    # pylint: disable=no-self-use
    # pylint: disable=invalid-name

    if value is None:
      raise exceptions.ValidationError(
          "Review status display for the object is not specified")

    return value

  _sanitize_html = [
      'risk_type',
      'threat_source',
      'threat_event',
      'vulnerability'
  ]

  _fulltext_attrs = [
      'risk_type',
      'threat_source',
      'threat_event',
      'vulnerability',
      'review_status_display_name',

      attributes.DateFullTextAttr(
          'due_date',
          'due_date',
      ),
      attributes.DatetimeFullTextAttr(
          'last_submitted_at',
          'last_submitted_at',
      ),
      attributes.FullTextAttr(
          "last_submitted_by",
          "last_submitted_by",
          ["email", "name"]
      ),
      attributes.DatetimeFullTextAttr(
          'last_verified_at',
          'last_verified_at',
      ),
      attributes.FullTextAttr(
          "last_verified_by",
          "last_verified_by",
          ["email", "name"]
      )
  ]

  _custom_publish = {
      'last_submitted_by': ggrc_utils.last_submitted_by_stub,
      'last_verified_by': ggrc_utils.last_verified_by_stub,
  }

  _api_attrs = reflection.ApiAttributes(
      'risk_type',
      'threat_source',
      'threat_event',
      'vulnerability',
      'external_id',
      'due_date',
      reflection.ExternalUserAttribute('last_submitted_by',
                                       force_create=True),
      reflection.ExternalUserAttribute('last_verified_by',
                                       force_create=True),
      'last_submitted_at',
      'last_verified_at',
      'external_slug',
      'review_status',
      'review_status_display_name',
  )

  _aliases = {
      "description": {
          "display_name": "Description",
          "mandatory": True
      },
      "risk_type": {
          "display_name": "Risk Type",
          "mandatory": False
      },
      "threat_source": {
          "display_name": "Threat Source",
          "mandatory": False
      },
      "threat_event": {
          "display_name": "Threat Event",
          "mandatory": False
      },
      "vulnerability": {
          "display_name": "Vulnerability",
          "mandatory": False
      },
      "documents_file": None,
      "status": {
          "display_name": "State",
          "mandatory": False,
          "description": "Options are: \n {}".format('\n'.join(
              mixins.BusinessObject.VALID_STATES))
      },
      "review_status": {
          "display_name": "Review State",
          "mandatory": False,
          "filter_only": True,
      },
      "review_status_display_name": {
          "display_name": "Review Status",
          "mandatory": False,
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

  def log_json(self):
    res = super(Risk, self).log_json()
    res["last_submitted_by"] = ggrc_utils.last_submitted_by_stub(self)
    res["last_verified_by"] = ggrc_utils.last_verified_by_stub(self)
    return res
