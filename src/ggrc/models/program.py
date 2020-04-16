# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Program model."""

from sqlalchemy import orm
from werkzeug import exceptions as wzg_exceptions


from ggrc import db
from ggrc.access_control import roleable
from ggrc.fulltext import mixin as ft_mixin
from ggrc.models import comment
from ggrc.models import context
from ggrc.models import deferred
from ggrc.models import proposal
from ggrc.models import mixins
from ggrc.models import object_document
from ggrc.models import object_person
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models import review
from ggrc.models.mixins import mega
from ggrc.models.mixins import rest_handable as rest_handable_mixins
from ggrc.utils import errors


class Program(mega.Mega,
              review.Reviewable,
              mixins.CustomAttributable,
              comment.Commentable,
              object_document.PublicDocumentable,
              roleable.Roleable,
              object_person.Personable,
              relationship.Relatable,
              context.HasOwnContext,
              mixins.LastDeprecatedTimeboxed,
              rest_handable_mixins.WithDeleteHandable,
              mixins.base.ContextRBAC,
              mixins.BusinessObject,
              proposal.Proposalable,
              mixins.Folderable,
              mixins.WithWorkflowState,
              ft_mixin.Indexed,
              db.Model):
  """Representation for Program model."""
  __tablename__ = 'programs'

  KINDS = ['Directive']
  KINDS_HIDDEN = ['Company Controls Policy']
  VALID_RECIPIENTS = frozenset([
      "Program Managers",
      "Program Editors",
      "Program Readers",
      "Primary Contacts",
      "Secondary Contacts",
  ])

  kind = deferred.deferred(db.Column(db.String), 'Program')

  recipients = db.Column(
      db.String,
      nullable=True,
      default=(u"Program Managers,Program Editors,Program Readers,"
               u"Primary Contacts,Secondary Contacts"),
  )

  audits = db.relationship(
      'Audit', backref='program', cascade='all, delete-orphan')

  _api_attrs = reflection.ApiAttributes(
      'kind',
      reflection.Attribute('audits', create=False, update=False),
  )
  _include_links = []
  _aliases = {
      "documents_file": None,
      "owners": None
  }

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(Program, cls).eager_query(**kwargs)

    return cls.eager_inclusions(query, Program._include_links).options(
        orm.subqueryload('audits'),
    )

  def _check_no_audits(self):
    """Check that audit has no assessments before delete."""
    if self.audits:
      db.session.rollback()
      raise wzg_exceptions.Conflict(errors.MAPPED_AUDITS)

  def handle_delete(self):
    """Handle model_deleted signals."""
    self._check_no_audits()
