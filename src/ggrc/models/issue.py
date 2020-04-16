# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Issue Model."""

import itertools

from sqlalchemy import orm

from ggrc import db
from ggrc import builder
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext import attributes
from ggrc.models.comment import Commentable
from ggrc.models.deferred import deferred
from ggrc.models import audit
from ggrc.models import mixins
from ggrc.models.mixins import issue_tracker
from ggrc.models.mixins.audit_relationship import AuditRelationship
from ggrc.models.mixins.with_action import WithAction
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.models import reflection
from ggrc.fulltext.mixin import Indexed
from ggrc.integrations import constants


class Issue(Roleable,
            mixins.TestPlanned,
            mixins.CustomAttributable,
            PublicDocumentable,
            Personable,
            mixins.LastDeprecatedTimeboxed,
            Relatable,
            Commentable,
            AuditRelationship,
            WithAction,
            issue_tracker.IssueTrackedWithUrl,
            mixins.base.ContextRBAC,
            mixins.BusinessObject,
            mixins.Folderable,
            mixins.WithWorkflowState,
            Indexed,
            db.Model):
  """Issue Model."""

  __tablename__ = 'issues'

  FIXED = "Fixed"
  FIXED_AND_VERIFIED = "Fixed and Verified"

  VALID_STATES = mixins.BusinessObject.VALID_STATES + (
      FIXED,
      FIXED_AND_VERIFIED,
  )

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute("audit",
                           create=False,
                           update=False),
      reflection.Attribute("allow_map_to_audit",
                           create=False,
                           update=False),
      reflection.Attribute("allow_unmap_from_audit",
                           create=False,
                           update=False),
      reflection.Attribute("due_date"),
  )

  _aliases = {
      "due_date": {
          "display_name": "Due Date",
          "mandatory": True,
      },
      "test_plan": {
          "display_name": "Remediation Plan"
      },
      "issue_tracker": {
          "display_name": "Ticket Tracker",
          "view_only": True,
          "mandatory": False,
      },
      "status": {
          "display_name": "State",
          "mandatory": False,
          "description": "Allowed values are:\n{} ".format(
              '\n'.join(VALID_STATES))
      },
      "audit": None,
      "documents_file": None,
      "issue_priority": {
          "display_name": "Priority",
          "description": "Allowed values are:\n{}".format(
              '\n'.join(constants.AVAILABLE_PRIORITIES)),
          "mandatory": False
      },
  }

  _fulltext_attrs = [
      attributes.DateFullTextAttr('due_date', 'due_date'),
  ]

  _custom_publish = {
      'audit': audit.build_audit_stub,
  }

  audit_id = deferred(
      db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=True),
      'Issue')
  due_date = db.Column(db.Date)

  @builder.simple_property
  def allow_map_to_audit(self):
    """False if self.audit or self.audit_id is set, True otherwise."""
    return self.audit_id is None and self.audit is None

  @builder.simple_property
  def allow_unmap_from_audit(self):
    """False if Issue is mapped to any Assessment/Snapshot, True otherwise."""
    from ggrc.models import all_models

    restricting_types = {all_models.Assessment, all_models.Snapshot}
    restricting_types = set(m.__name__.lower() for m in restricting_types)

    # pylint: disable=not-an-iterable
    restricting_srcs = (rel.source_type.lower() in restricting_types
                        for rel in self.related_sources
                        if rel not in db.session.deleted)
    restricting_dsts = (rel.destination_type.lower() in restricting_types
                        for rel in self.related_destinations
                        if rel not in db.session.deleted)
    return not any(itertools.chain(restricting_srcs, restricting_dsts))

  def log_json(self):
    out_json = super(Issue, self).log_json()
    out_json["folder"] = self.folder
    return out_json

  @classmethod
  def _populate_query(cls, query):
    return query.options(
        orm.Load(cls).joinedload("audit").undefer_group("Audit_complete"),
    )

  @classmethod
  def indexed_query(cls):
    return super(Issue, cls).indexed_query().options(
        orm.Load(cls).load_only("due_date"),
    )

  @classmethod
  def eager_query(cls, **kwargs):
    # Ensure that related_destinations and related_sources will be loaded
    # in subquery. It allows reduce a number of requests to DB when these attrs
    # are used
    kwargs['load_related'] = True

    return cls._populate_query(super(Issue, cls).eager_query(**kwargs))

  @orm.validates("due_date")
  def validate_due_date(self, _, value):  # pylint: disable=no-self-use
    """Validate due date"""
    if not value:
      raise ValueError("Due Date for the issue is not specified")
    return value
