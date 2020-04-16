# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Module for Directive, Contract, Policy, Regulation, Standard model."""

from sqlalchemy import orm
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext.mixin import Indexed
from ggrc.models import reflection, review
from ggrc.models.comment import Commentable
from ggrc.models.deferred import deferred
from ggrc.models import mixins
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.models.utils import validate_option


# NOTE: The PublicDocumentable mixin is not applied directly to the Directive
# base class, but instead to all of its specialized subclasses. The reason for
# this is the PublicDocumentable's declared attribute `documents` that builds a
# dynamic DB relationship based on the class name, and thus the attribute needs
# to be run in the context of each particular subclass.
# (of course, if there is a nice way of overriding/customizing declared
# attributes in subclasses, we might want to use that approach)
class Directive(mixins.LastDeprecatedTimeboxed,
                Commentable,
                mixins.TestPlanned,
                mixins.base.ContextRBAC,
                mixins.BusinessObject,
                mixins.Folderable,
                mixins.WithWorkflowState,
                db.Model):
  """Directive model"""

  __tablename__ = 'directives'

  version = deferred(db.Column(db.String), 'Directive')
  organization = deferred(db.Column(db.String), 'Directive')
  scope = deferred(db.Column(db.Text, nullable=False, default=u""),
                   'Directive')
  kind_id = deferred(db.Column(db.Integer), 'Directive')
  audit_start_date = deferred(db.Column(db.DateTime), 'Directive')
  audit_frequency_id = deferred(db.Column(db.Integer), 'Directive')
  audit_duration_id = deferred(db.Column(db.Integer), 'Directive')
  meta_kind = db.Column(db.String)
  kind = deferred(db.Column(db.String), 'Directive')

  # TODO: FIX jost!
  # requirements = db.relationship(
  #     'Requirement', backref='directive',
  #     order_by='Requirement.slug', cascade='all, delete-orphan')
  controls = db.relationship(
      'Control', backref='directive', order_by='Control.slug')
  audit_frequency = db.relationship(
      'Option',
      primaryjoin='and_(foreign(Directive.audit_frequency_id) == Option.id, '
                  'Option.role == "audit_frequency")',
      uselist=False,
  )
  audit_duration = db.relationship(
      'Option',
      primaryjoin='and_(foreign(Directive.audit_duration_id) == Option.id, '
                  'Option.role == "audit_duration")',
      uselist=False,
  )

  __mapper_args__ = {
      'polymorphic_on': meta_kind
  }

  _api_attrs = reflection.ApiAttributes(
      'audit_start_date',
      'audit_frequency',
      'audit_duration',
      'controls',
      'kind',
      'organization',
      'scope',
      'version',
  )

  _fulltext_attrs = [
      'audit_start_date',
      'audit_frequency',
      'audit_duration',
      'controls',
      'kind',
      'organization',
      'scope',
      'version',
  ]

  @classmethod
  def indexed_query(cls):
    return super(Directive, cls).indexed_query().options(
        orm.Load(cls).joinedload('audit_frequency'),
        orm.Load(cls).joinedload('audit_duration'),
        orm.Load(cls).subqueryload('controls'),
        orm.Load(cls).load_only(
            'audit_start_date',
            'kind',
            'organization',
            'scope',
            'version',
        ),
    )

  _sanitize_html = [
      'organization',
      'scope',
      'version',
  ]

  _include_links = []

  _aliases = {
      'kind': "Kind/Type",
      "documents_file": None,
  }

  @validates('kind')
  def validate_kind(self, key, value):
    if not value:
      return None
    if value not in self.VALID_KINDS:
      message = "Invalid value '{}' for attribute {}.{}.".format(
                value, self.__class__.__name__, key)
      raise ValueError(message)
    return value

  @validates('audit_duration', 'audit_frequency')
  def validate_directive_options(self, key, option):
    return validate_option(self.__class__.__name__, key, option, key)

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(Directive, cls).eager_query(**kwargs)
    return cls.eager_inclusions(query, Directive._include_links).options(
        orm.joinedload('audit_frequency'),
        orm.joinedload('audit_duration'),
        orm.subqueryload('controls'))

  @staticmethod
  def _extra_table_args(cls):
    return (
        db.Index('ix_{}_meta_kind'.format(cls.__tablename__), 'meta_kind'),
    )


# FIXME: For subclasses, restrict kind
class Policy(review.Reviewable,
             Roleable,
             mixins.CustomAttributable,
             Relatable,
             Personable,
             PublicDocumentable,
             Directive,
             Indexed):
  __mapper_args__ = {
      'polymorphic_identity': 'Policy'
  }

  _table_plural = 'policies'

  VALID_KINDS = frozenset([
      "Company Policy", "Org Group Policy", "Data Asset Policy",
      "Product Policy", "Contract-Related Policy", "Company Controls Policy"
  ])

  POLICY_OPTIONS = ("Company Policy",
                    "Org Group Policy",
                    "Data Asset Policy",
                    "Product Policy",
                    "Contract-Related Policy",
                    "Company Controls Policy"
                    )

  _aliases = {
      "documents_file": None,
      "kind": {
          "display_name": "Kind/Type",
          "filter_by": "_filter_by_kind",
          "description": "Allowed values are:\n{}".format(
              "\n".join(POLICY_OPTIONS))
      },
  }

  # pylint: disable=unused-argument
  @validates('meta_kind')
  def validates_meta_kind(self, key, value):
    return 'Policy'


class Regulation(review.Reviewable,
                 Roleable,
                 mixins.CustomAttributable,
                 Relatable,
                 Personable,
                 PublicDocumentable,
                 Directive,
                 Indexed):
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
  @validates('meta_kind')
  def validates_meta_kind(self, key, value):
    return 'Regulation'


class Standard(review.Reviewable,
               Roleable,
               mixins.CustomAttributable,
               Relatable,
               Personable,
               PublicDocumentable,
               Directive,
               Indexed):
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
  @validates('meta_kind')
  def validates_meta_kind(self, key, value):
    return 'Standard'


class Contract(review.Reviewable,
               Roleable,
               mixins.CustomAttributable,
               Relatable,
               Personable,
               PublicDocumentable,
               Directive,
               Indexed):
  __mapper_args__ = {
      'polymorphic_identity': 'Contract'
  }

  _table_plural = 'contracts'

  VALID_KINDS = ("Contract",)

  _aliases = {
      "kind": None,
      "documents_file": None,
  }

  # pylint: disable=unused-argument
  @validates('meta_kind')
  def validates_meta_kind(self, key, value):
    return 'Contract'
