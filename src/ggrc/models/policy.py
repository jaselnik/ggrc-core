# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for Policy object."""

import sqlalchemy as sa

from ggrc import db
from ggrc.fulltext import mixin as ft_mixins
from ggrc.models import comment
from ggrc.models import mixins
from ggrc.models import object_document
from ggrc.models import object_person
from ggrc.models import reflection
from ggrc.models import relationship


class Policy(mixins.synchronizable.Synchronizable,
             mixins.synchronizable.RoleableSynchronizable,
             mixins.WithExternalCreatedBy,
             comment.ExternalCommentable,
             mixins.BusinessObject,
             mixins.CustomAttributable,
             mixins.CycleTaskable,
             mixins.Folderable,
             mixins.LastDeprecatedTimeboxed,
             mixins.TestPlanned,
             mixins.WithWorkflowState,
             mixins.base.ContextRBAC,
             object_document.PublicDocumentable,
             object_person.Personable,
             relationship.Relatable,
             mixins.Base,
             ft_mixins.Indexed,
             db.Model):
  """Policy model."""

  __tablename__ = "policies"

  kind = db.Column(db.String)

  VALID_KINDS = (
      "Company Policy",
      "Org Group Policy",
      "Data Asset Policy",
      "Product Policy",
      "Contract-Related Policy",
      "Company Controls Policy",
  )

  _api_attrs = reflection.ApiAttributes(
      "kind",
  )

  _fulltext_attrs = [
      "kind",
  ]

  _sanitize_html = []

  _include_links = []

  _aliases = {
      "kind": {
          "display_name": "Kind/Type",
          "filter_by": "_filter_by_kind",
          "description": "Allowed values are:\n{kinds}".format(
              kinds="\n".join(sorted(VALID_KINDS)),
          ),
      },
      "documents_file": None,
  }

  @sa.orm.validates("kind")
  def validate_kind(self, key, value):
    """Validate a value set to `kind` field.

    In order to be valid, the passed value `value` should be present in
    `Policy.VALID_KINDS` class field.

    Args:
      key (str): A field name, equals to "kind".
      value (Any): A value assigned to a field.

    Returns:
      A validated value.

    Raises:
      ValueError: a `value` is an invalid value for a `key` column.
    """
    if not value:
      return None
    if value not in self.VALID_KINDS:
      message = "Invalid value '{}' for attribute {}.{}.".format(
                value, self.__class__.__name__, key)
      raise ValueError(message)
    return value

  @classmethod
  def eager_query(cls, **kwargs):
    """Return `sqlalchemy.Query` query used for object eager loading."""
    query = super(Policy, cls).eager_query(**kwargs)
    return cls.eager_inclusions(query, cls._include_links)

  @classmethod
  def indexed_query(cls):
    """Return `sqlalchemy.Query` query used for object indexing."""
    return super(Policy, cls).indexed_query().options(
        sa.orm.Load(cls).load_only(
            "kind",
        ),
    )
