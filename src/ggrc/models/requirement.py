# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module with Requirement model."""

import sqlalchemy as sa

from ggrc import db
from ggrc.access_control import roleable
from ggrc.fulltext import mixin as ft_mixins
from ggrc.models.deferred import deferred
from ggrc.models import comment
from ggrc.models import directive
from ggrc.models import mixins
from ggrc.models import object_document
from ggrc.models import object_person
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models import review


class Requirement(mixins.synchronizable.Synchronizable,
                  mixins.WithExternalCreatedBy,
                  comment.ExternalCommentable,
                  roleable.Roleable,
                  review.Reviewable,
                  mixins.CustomAttributable,
                  mixins.WithStartDate,
                  mixins.WithLastDeprecatedDate,
                  object_person.Personable,
                  relationship.Relatable,
                  mixins.TestPlanned,
                  object_document.PublicDocumentable,
                  mixins.base.ContextRBAC,
                  mixins.BusinessObject,
                  mixins.Folderable,
                  mixins.WithWorkflowState,
                  ft_mixins.Indexed,
                  db.Model):
  """Requirement model."""

  __tablename__ = 'requirements'
  _table_plural = 'requirements'
  _aliases = {
      "documents_file": None,
      "description": "Description",
      "directive": {
          "display_name": "Policy / Regulation / Standard / Contract",
          "type": reflection.AttributeInfo.Type.MAPPING,
          "filter_by": "_filter_by_directive",
      }
  }

  notes = deferred(db.Column(db.Text, nullable=False, default=u""),
                   'Requirements')

  _api_attrs = reflection.ApiAttributes('notes')
  _sanitize_html = ['notes']
  _include_links = []

  @classmethod
  def eager_query(cls, **kwargs):
    """Define fields to be loaded eagerly to lower the count of DB queries."""
    query = super(Requirement, cls).eager_query(**kwargs)
    return query.options(sa.orm.undefer('notes'))

  @classmethod
  def _filter_by_directive(cls, predicate):
    """Apply predicate to the object referenced by directive field."""
    types = ["Policy", "Regulation", "Standard", "Contract"]
    rel_model = relationship.Relationship
    directve_model = directive.Directive

    dst = rel_model.query.filter(
        rel_model.source_id == cls.id,
        rel_model.source_type == cls.__name__,
        rel_model.destination_type.in_(types),
    ).join(
        directve_model,
        directve_model.id == rel_model.destination_id,
    ).filter(
        sa.or_(
            predicate(directve_model.slug),
            predicate(directve_model.title),
        ),
    ).exists()

    src = rel_model.query.filter(
        rel_model.destination_id == cls.id,
        rel_model.destination_type == cls.__name__,
        rel_model.source_type.in_(types),
    ).join(
        directve_model,
        directve_model.id == rel_model.source_id,
    ).filter(
        sa.or_(
            predicate(directve_model.slug),
            predicate(directve_model.title),
        ),
    ).exists()
    return dst | src
