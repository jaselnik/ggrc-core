# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Module for ExternalDirective, Regulation, Standard model."""


from sqlalchemy import orm
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext.mixin import Indexed
from ggrc.models import reflection
from ggrc.models.comment import ExternalCommentable
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class ExternalDirective(synchronizable.Synchronizable,
                        mixins.WithExternalCreatedBy,
                        mixins.WithWorkflowState,
                        mixins.LastDeprecatedTimeboxed,
                        mixins.base.ContextRBAC,
                        mixins.BusinessObject,
                        mixins.Folderable,
                        ExternalCommentable,
                        Indexed,
                        mixins.Slugged,
                        mixins.Base,
                        db.Model):
  """Class for ExternalDirective model"""

  __tablename__ = "external_directives"

  id = db.Column(db.Integer, primary_key=True, autoincrement=False)
  kind = db.Column(db.String, nullable=False)
  test_plan = db.Column(db.String, nullable=True)

  _api_attrs = reflection.ApiAttributes(
      'kind',
  )

  _fulltext_attrs = [
      'kind',
  ]

  _include_links = []

  @classmethod
  def indexed_query(cls):
    return super(ExternalDirective, cls).indexed_query().options(
        orm.Load(cls).load_only('kind'),
    )

  _aliases = {
      'kind': "Kind/Type",
      "documents_file": None,
  }

  @validates('kind')
  def validate_kind(self, key, value):
    """Validator for 'kind' attribute"""
    if not value:
      return None
    if value not in self.VALID_KINDS:
      message = "Invalid value '{}' for attribute {}.{}.".format(
          value, self.__class__.__name__, key)
      raise ValueError(message)
    return value

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(ExternalDirective, cls).eager_query(**kwargs)
    return cls.eager_inclusions(query, ExternalDirective._include_links)


class Regulation(Roleable,
                 mixins.CustomAttributable,
                 Relatable,
                 Personable,
                 PublicDocumentable,
                 ExternalDirective,
                 Indexed):
  """Class for Regulation model"""

  __mapper_args__ = {
      'polymorphic_identity': 'Regulation'
  }

  _table_plural = 'regulations'

  VALID_KINDS = ("Regulation",)

  _aliases = {
      "kind": None,
      "documents_file": None,
  }

  # pylint: disable=unused-argument
  @validates('kind')
  def validates_kind(self, key, value):
    return 'Regulation'


class Standard(Roleable,
               mixins.CustomAttributable,
               Relatable,
               Personable,
               PublicDocumentable,
               ExternalDirective,
               Indexed):
  """Class for Standard model"""

  __mapper_args__ = {
      'polymorphic_identity': 'Standard'
  }

  _table_plural = 'standards'

  VALID_KINDS = ("Standard",)

  _aliases = {
      "kind": None,
      "documents_file": None,
  }

  # pylint: disable=unused-argument
  @validates('kind')
  def validates_kind(self, key, value):
    return 'Standard'
