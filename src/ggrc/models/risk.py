# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for risk model."""

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models import mixins, review
from ggrc.models import proposal
from ggrc.models.comment import Commentable
from ggrc.models.deferred import deferred
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.models import reflection


class Risk(synchronizable.Synchronizable,
           synchronizable.RoleableSynchronizable,
           review.Reviewable,
           mixins.CustomAttributable,
           Relatable,
           Personable,
           PublicDocumentable,
           Commentable,
           mixins.TestPlanned,
           mixins.LastDeprecatedTimeboxed,
           mixins.base.ContextRBAC,
           mixins.BusinessObject,
           proposal.Proposalable,
           mixins.Folderable,
           Indexed,
           db.Model):
  """Basic Risk model."""
  __tablename__ = 'risks'

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
      'vulnerability'
  ]

  _api_attrs = reflection.ApiAttributes(
      'risk_type',
      'threat_source',
      'threat_event',
      'vulnerability'
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
      }
  }
