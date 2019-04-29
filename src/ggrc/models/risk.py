# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for risk model."""

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models import mixins, comment, utils, exceptions
from ggrc.models.deferred import deferred
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.models import reflection
from ggrc.utils import create_stub


class Risk(synchronizable.Synchronizable,
           synchronizable.RoleableSynchronizable,
           mixins.CustomAttributable,
           Relatable,
           Personable,
           PublicDocumentable,
           comment.ExternalCommentable,
           mixins.TestPlanned,
           mixins.LastDeprecatedTimeboxed,
           mixins.base.ContextRBAC,
           mixins.BusinessObject,
           mixins.Folderable,
           Indexed,
           db.Model):
  """Basic Risk model."""
  __tablename__ = 'risks'

  # GGRCQ attributes
  external_id = db.Column(db.Integer, nullable=False)
  due_date = db.Column(db.Date, nullable=True)
  created_by_id = db.Column(db.Integer, nullable=False)
  review_status = deferred(db.Column(db.String, nullable=True), "Risk")
  review_status_display_name = deferred(db.Column(db.String, nullable=True),
                                        "Risk")

  # pylint: disable=no-self-argument
  @declared_attr
  def created_by(cls):
    """Relationship to user referenced by created_by_id."""
    return utils.person_relationship(cls.__name__, "created_by_id")

  last_submitted_at = db.Column(db.DateTime, nullable=True)
  last_submitted_by_id = db.Column(db.Integer, nullable=True)

  @declared_attr
  def last_submitted_by(cls):
    """Relationship to user referenced by last_submitted_by_id."""
    return utils.person_relationship(cls.__name__,
                                     "last_submitted_by_id")

  last_verified_at = db.Column(db.DateTime, nullable=True)
  last_verified_by_id = db.Column(db.Integer, nullable=True)

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

  risk_type = db.Column(db.Text, nullable=False)
  threat_source = db.Column(db.Text, nullable=True)
  threat_event = db.Column(db.Text, nullable=True)
  vulnerability = db.Column(db.Text, nullable=True)

  @validates("risk_type")
  def validate_risk_type(self, key, value):
    """Validate risk_type"""
    #  pylint: disable=unused-argument,no-self-use
    if value:
      return value
    else:
      raise ValueError("Risk Type value shouldn't be empty")

  @validates('review_status')
  def validate_review_status(self, _, value):
    """Add explicit non-nullable validation."""
    if value is None:
      raise exceptions.ValidationError(
          "Review status for the object is not specified")

    return value

  @validates('review_status_display_name')
  def validate_review_status_display_name(self, _, value):
    """Add explicit non-nullable validation."""
    # pylint: disable=no-self-use

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
      'review_status_display_name'
  ]

  _api_attrs = reflection.ApiAttributes(
      'risk_type',
      'threat_source',
      'threat_event',
      'vulnerability',
      'external_id',
      'due_date',
      reflection.ExternalUserAttribute('created_by',
                                       force_create=True),
      reflection.ExternalUserAttribute('last_submitted_by',
                                       force_create=True),
      reflection.ExternalUserAttribute('last_verified_by',
                                       force_create=True),
      'last_submitted_at',
      'last_verified_at',
      'external_slug',
      'review_status',
      'review_status_display_name'
  )

  _aliases = {
      "description": {
          "display_name": "Description",
          "mandatory": True
      },
      "risk_type": {
          "display_name": "Risk Type",
          "mandatory": True
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
          "display_name": "Review State",
          "mandatory": False,
      },
  }

  def log_json(self):
    res = super(Risk, self).log_json()
    res["created_by"] = create_stub(self.created_by)
    res["last_submitted_by"] = self.last_submitted_by
    res["last_verified_by"] = self.last_verified_by
    return res
