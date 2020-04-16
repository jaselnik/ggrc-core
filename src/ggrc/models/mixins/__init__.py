# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Mixins to add common attributes and relationships. Note, all model classes
must also inherit from ``db.Model``. For example:
color
color
  ..

     class Market(BusinessObject, db.Model):
       __tablename__ = 'markets'

"""

# pylint: disable=no-self-argument
# All declared_attr properties that are class level as per sqlalchemy
# documentatio, are reported as false positives by pylint.

from logging import getLogger
from uuid import uuid1
import datetime
import re

from sqlalchemy import event
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from sqlalchemy.orm.session import Session

from ggrc import db

from ggrc.models import reflection
from ggrc.models import exceptions
from ggrc.models.deferred import deferred
from ggrc.models.mixins.base import Base
from ggrc.models.mixins.customattributable import CustomAttributable
from ggrc.models.mixins.notifiable import Notifiable
from ggrc.models.mixins.with_workflow_state import WithWorkflowState
from ggrc.models.mixins.with_external_created_by import WithExternalCreatedBy
from ggrc.models.utils import validate_option
from ggrc.fulltext import attributes


# pylint: disable=invalid-name
logger = getLogger(__name__)


class Titled(object):
  """Mixin that defines `title` field.

  Strips title on update and defines optional UNIQUE constraint on it.
  """

  @validates('title')
  def validate_title(self, key, value):
    """Validates and cleans Title that has leading/trailing spaces"""
    # pylint: disable=unused-argument,no-self-use

    # ensure that value is not None (value was not specified or set to null)
    # treat empty string or string with spaces as valid - it looks like
    # such case is valid - some tests check such cases, so empty title might
    # be valid in production
    if value is None:
      raise ValueError("'title' must be specified")

    return re.sub(r"\s+", " ", value).strip()

  title = db.Column(db.String, nullable=False)

  @classmethod
  def indexed_query(cls):
    return super(Titled, cls).indexed_query().options(
        orm.Load(cls).load_only("title"),
    )

  @staticmethod
  def _extra_table_args(model):
    """If model._title_uniqueness is set, apply UNIQUE constraint to title."""
    if getattr(model, '_title_uniqueness', True):
      return (
          db.UniqueConstraint(
              'title', name='uq_t_{}'.format(model.__tablename__)),
      )
    return ()

  # REST properties
  _api_attrs = reflection.ApiAttributes('title')
  _fulltext_attrs = ['title']
  _sanitize_html = ['title']
  _aliases = {
      "title": {
          "display_name": "Title",
          "mandatory": True,
      },
  }


class Described(object):
  """Mixin that defines `description` field."""

  @declared_attr
  def description(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.Text, nullable=False, default=u""),
                    cls.__name__)

  # REST properties
  _api_attrs = reflection.ApiAttributes('description')
  _fulltext_attrs = ['description']
  _sanitize_html = ['description']
  _aliases = {"description": "Description"}

  @classmethod
  def indexed_query(cls):
    return super(Described, cls).indexed_query().options(
        orm.Load(cls).load_only("description"),
    )


class Noted(object):
  """Mixin that defines `notes` field."""

  @declared_attr
  def notes(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.Text, nullable=False, default=u""),
                    cls.__name__)

  # REST properties
  _api_attrs = reflection.ApiAttributes('notes')
  _fulltext_attrs = ['notes']
  _sanitize_html = ['notes']
  _aliases = {"notes": "Notes"}

  @classmethod
  def indexed_query(cls):
    return super(Noted, cls).indexed_query().options(
        orm.Load(cls).load_only("notes"),
    )


class WithStartDate(object):
  """Mixin that defines `start_date`."""
  # REST properties
  _api_attrs = reflection.ApiAttributes('start_date')

  _aliases = {
      "start_date": "Effective Date",
  }

  _fulltext_attrs = [
      attributes.DateFullTextAttr('start_date', 'start_date'),
  ]

  @declared_attr
  def start_date(cls):
    return deferred(db.Column(db.Date), cls.__name__)

  @validates('start_date')
  def validate_date(self, _, value):
    """Validator for start_date"""
    # pylint: disable=no-self-use
    return value.date() if isinstance(value, datetime.datetime) else value

  @classmethod
  def indexed_query(cls):
    return super(WithStartDate, cls).indexed_query().options(
        orm.Load(cls).load_only("start_date"),
    )


class WithEndDate(object):
  """Mixin that defines `end_date`."""
  # REST properties
  _api_attrs = reflection.ApiAttributes('end_date')

  _aliases = {
      "end_date": "Stop Date",
  }

  _fulltext_attrs = [
      attributes.DateFullTextAttr('end_date', 'end_date'),
  ]

  @declared_attr
  def end_date(cls):
    return deferred(db.Column(db.Date), cls.__name__)

  @validates('end_date')
  def validate_date(self, _, value):
    """Validator for end_date"""
    # pylint: disable=no-self-use
    return value.date() if isinstance(value, datetime.datetime) else value

  @classmethod
  def indexed_query(cls):
    return super(WithEndDate, cls).indexed_query().options(
        orm.Load(cls).load_only("end_date"),
    )


class Timeboxed(WithStartDate, WithEndDate):
  """Mixin that defines `start_date` and `end_date` fields."""


class WithLastDeprecatedDate(object):
  """Mixin that defines `last_deprecated_date` field."""

  # pylint: disable=method-hidden ; pylint thinks that last_deprecated_date
  # is overwritten in validate_status
  @declared_attr
  def last_deprecated_date(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.Date), cls.__name__)

  # pylint: disable=unused-argument,no-self-use
  @validates('last_deprecated_date')
  def validate_date(self, key, value):
    return value.date() if isinstance(value, datetime.datetime) else value
  # pylint: enable=unused-argument,no-self-use

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('last_deprecated_date', create=False, update=False),
  )

  _aliases = {
      "last_deprecated_date": {
          "display_name": "Last Deprecated Date",
          "view_only": True,
          "description": "Automatically provided values"
      },
  }

  _fulltext_attrs = [
      attributes.DateFullTextAttr('last_deprecated_date',
                                  'last_deprecated_date'),
  ]

  @classmethod
  def indexed_query(cls):
    return super(WithLastDeprecatedDate, cls).indexed_query().options(
        orm.Load(cls).load_only("last_deprecated_date"),
    )

  AUTO_SETUP_STATUS = "Deprecated"

  @validates('status')
  def validate_status(self, key, value):
    """Autosetup current date as last_deprecated_date
      if 'Deprecated' status will setup."""
    # pylint: disable=unused-argument; key is unused but passed in by ORM
    if hasattr(super(WithLastDeprecatedDate, self), "validate_status"):
      value = super(WithLastDeprecatedDate, self).validate_status(key, value)
    if value != self.status and value == self.AUTO_SETUP_STATUS:
      self.last_deprecated_date = datetime.date.today()
    return value


class LastDeprecatedTimeboxed(Timeboxed):
  """Mixin that redefines `end_date`'s alias."""
  _aliases = {
      "end_date": {
          "display_name": "Last Deprecated Date",
          "view_only": True,
          "description": "Automatically provided values"
      },
  }

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('end_date', create=False, update=False),
  )

  AUTO_SETUP_STATUS = "Deprecated"

  @validates('status')
  def validate_status(self, key, value):
    """Autosetup current date as end date if 'Deprecated' status will setup."""
    superinstance = super(Timeboxed, self)
    if hasattr(superinstance, "validate_status"):
      value = superinstance.validate_status(key, value)
    if value != self.status and value == self.AUTO_SETUP_STATUS:
      self.end_date = datetime.date.today()
    return value


class Stateful(object):
  """Mixin that defines `status` field and status validation logic.

  TODO: unify with Statusable.
  """

  @declared_attr
  def status(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(
        db.String, default=cls.default_status, nullable=False), cls.__name__)

  _api_attrs = reflection.ApiAttributes('status')
  _fulltext_attrs = ['status']
  _aliases = {
      "status": {
          "display_name": "State",
          "mandatory": False
      }
  }

  @classmethod
  def default_status(cls):
    return cls.valid_statuses()[0]

  @classmethod
  def valid_statuses(cls):
    return cls.VALID_STATES

  @validates('status')
  def validate_status(self, key, value):
    """Use default status if value is None, check that it is in valid set."""
    # Sqlalchemy only uses one validator per status (not necessarily the
    # first) and ignores others. This enables cooperation between validators
    # since there are other mixins that want to touch 'status'.
    if hasattr(super(Stateful, self), "validate_status"):
      value = super(Stateful, self).validate_status(key, value)
    if value is None:
      value = self.default_status()
    if value not in self.valid_statuses():
      message = u"Invalid state '{}'".format(value)
      raise ValueError(message)
    return value

  @classmethod
  def indexed_query(cls):
    return super(Stateful, cls).indexed_query().options(
        orm.Load(cls).load_only("status"),
    )


class FinishedDate(object):
  """Adds 'Finished Date' which is set when status is set to a finished state.

  Requires Stateful to be mixed in as well.
  """

  NOT_DONE_STATES = None
  DONE_STATES = {}

  # pylint: disable=method-hidden
  # because validator only sets date per model instance
  @declared_attr
  def finished_date(cls):  # pylint: disable=no-self-argument
    return deferred(
        db.Column(db.DateTime, nullable=True),
        cls.__name__
    )

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('finished_date', create=False, update=False),
  )

  _aliases = {
      "finished_date": {
          "display_name": "Finished Date",
          "description": "Automatically provided values",
      }
  }

  _fulltext_attrs = [
      attributes.DatetimeFullTextAttr('finished_date', 'finished_date'),
  ]

  @validates('status')
  def validate_status(self, key, value):
    """Update finished_date given the right status change."""
    # Sqlalchemy only uses one validator per status (not necessarily the
    # first) and ignores others. This enables cooperation between validators
    # since 'status' is not defined here.
    if hasattr(super(FinishedDate, self), "validate_status"):
      value = super(FinishedDate, self).validate_status(key, value)
    # pylint: disable=unsupported-membership-test
    # short circuit
    if (value in self.DONE_STATES and
        (self.NOT_DONE_STATES is None or
         self.status in self.NOT_DONE_STATES)):
      self.finished_date = datetime.datetime.utcnow()
    elif ((self.NOT_DONE_STATES is None or
           value in self.NOT_DONE_STATES) and
            self.status in self.DONE_STATES):
      self.finished_date = None
    return value

  @classmethod
  def indexed_query(cls):
    return super(FinishedDate, cls).indexed_query().options(
        orm.Load(cls).load_only("finished_date"),
    )


class VerifiedDate(object):
  """Adds 'Verified Date' which is set when status is set to 'Verified'.

  When object is verified the status is overridden to 'Final' and the
  information about verification exposed as the 'verified' boolean.
  Requires Stateful to be mixed in as well.
  """

  VERIFIED_STATES = {u"Verified"}
  DONE_STATES = {}

  # pylint: disable=method-hidden
  # because validator only sets date per model instance
  @declared_attr
  def verified_date(cls):  # pylint: disable=no-self-argument
    return deferred(
        db.Column(db.DateTime, nullable=True),
        cls.__name__
    )

  @hybrid_property
  def verified(self):
    """Returns a boolean whether assessment is verified or not."""
    return self.verified_date != None  # noqa

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('verified', create=False, update=False),
      reflection.Attribute('verified_date', create=False, update=False),
  )

  _aliases = {
      "verified_date": {
          "display_name": "Verified Date",
          "description": "Automatically provided values",
      }
  }

  _fulltext_attrs = [
      attributes.DatetimeFullTextAttr("verified_date", "verified_date"),
      attributes.BooleanFullTextAttr(
          'verified',
          'verified',
          true_value="Yes",
          false_value="No",
      ),
  ]

  @classmethod
  def indexed_query(cls):
    return super(VerifiedDate, cls).indexed_query().options(
        orm.Load(cls).load_only("verified_date"),
    )

  @validates('status')
  def validate_status(self, key, value):
    """Update verified_date on status change, make verified status final."""
    # Sqlalchemy only uses one validator per status (not necessarily the
    # first) and ignores others. This enables cooperation between validators
    # since 'status' is not defined here.
    if hasattr(super(VerifiedDate, self), "validate_status"):
      value = super(VerifiedDate, self).validate_status(key, value)
    if (value in self.VERIFIED_STATES and
            self.status not in self.VERIFIED_STATES):
      self.verified_date = datetime.datetime.utcnow()
      value = self.FINAL_STATE
    elif (value not in self.END_STATES and
          (self.status in self.VERIFIED_STATES or
           self.status in self.DONE_STATES)):
      self.verified_date = None
    return value


class Slugged(Base):

  """Several classes make use of the common mixins and additional are
  "slugged" and have additional fields related to their publishing in the
  system.
  """

  @declared_attr
  def slug(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.String, nullable=False), cls.__name__)

  @staticmethod
  def _extra_table_args(model):
    if getattr(model, '_slug_uniqueness', True):
      return (
          db.UniqueConstraint('slug',
                              name='uq_{}'.format(model.__tablename__)),
      )
    return ()

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('slug', update=False)
  )
  _fulltext_attrs = ['slug']
  _sanitize_html = ['slug']
  _aliases = {
      "slug": {
          "display_name": "Code",
          "description": ("Must be unique. Can be left empty for "
                          "auto generation. If updating or deleting, "
                          "code is required"),
      }
  }

  @classmethod
  def indexed_query(cls):
    return super(Slugged, cls).indexed_query().options(
        orm.Load(cls).load_only("slug"),
    )

  @classmethod
  def generate_slug_for(cls, obj):
    """Generate unique Slug among the objects of the current class"""
    _id = getattr(obj, 'id', uuid1())
    obj.slug = "{0}-{1}".format(cls.generate_slug_prefix(), _id)
    # We need to make sure the generated slug is not already present in the
    # database. If it is, we increment the id until we find a slug that is
    # unique.
    # A better approach would be to query the database for slug uniqueness
    # only if the there was a conflict, but because we can't easily catch a
    # session rollback at this point we are sticking with a
    # suboptimal solution for now.
    INCREMENT = 1000
    while db.session.query(
            cls.query.filter(cls.slug == obj.slug).exists()).scalar():
      _id += INCREMENT
      obj.slug = "{0}-{1}".format(cls.generate_slug_prefix(), _id)

  @classmethod
  def generate_slug_prefix(cls):
    return cls.__name__.upper()

  @validates("slug")
  def validate_slug(self, _, value):
    """Validates slug for presence of forbidden symbols"""
    # pylint: disable=no-self-use
    if value:
      new_value = value.strip()
      if new_value != value:
        logger.warning("Slug \"%s\" contains unsupported leading or trailing "
                       "whitespace. Slug will be trimmed.", value)
        value = new_value
    if value and "*" in value:
      raise exceptions.ValidationError(
          "Field 'Code' contains unsupported symbol '*'"
      )
    return value

  @classmethod
  def ensure_slug_before_flush(cls, session, flush_context, instances):
    """Set the slug to a default string so we don't run afoul of the NOT NULL
    constraint.
    """
    # pylint: disable=unused-argument
    for o in session.new:
      if isinstance(o, Slugged) and (o.slug is None or o.slug == ''):
        o.slug = str(uuid1())
        o._replace_slug = True  # pylint: disable=protected-access

  @classmethod
  def ensure_slug_after_flush_postexec(cls, session, flush_context):
    """Replace the placeholder slug with a real slug that will be set on the
    next flush/commit.
    """
    # pylint: disable=unused-argument
    for o in session.identity_map.values():
      if isinstance(o, Slugged) and hasattr(o, '_replace_slug'):
        o.generate_slug_for(o)
        delattr(o, '_replace_slug')


event.listen(Session, 'before_flush', Slugged.ensure_slug_before_flush)
event.listen(
    Session, 'after_flush_postexec', Slugged.ensure_slug_after_flush_postexec)


class WithContact(object):
  """Mixin that defines `contact` and `secondary_contact` fields."""

  @declared_attr
  def contact_id(cls):  # pylint: disable=no-self-argument
    return deferred(
        db.Column(db.Integer, db.ForeignKey('people.id')), cls.__name__)

  @declared_attr
  def secondary_contact_id(cls):  # pylint: disable=no-self-argument
    return deferred(
        db.Column(db.Integer, db.ForeignKey('people.id')), cls.__name__)

  @declared_attr
  def contact(cls):  # pylint: disable=no-self-argument
    return db.relationship(
        'Person',
        uselist=False,
        foreign_keys='{}.contact_id'.format(cls.__name__))

  @declared_attr
  def secondary_contact(cls):  # pylint: disable=no-self-argument
    return db.relationship(
        'Person',
        uselist=False,
        foreign_keys='{}.secondary_contact_id'.format(cls.__name__))

  @staticmethod
  def _extra_table_args(model):
    return (
        db.Index('fk_{}_contact'.format(model.__tablename__), 'contact_id'),
        db.Index('fk_{}_secondary_contact'.format(
            model.__tablename__), 'secondary_contact_id'),
    )

  _api_attrs = reflection.ApiAttributes('contact', 'secondary_contact')
  _fulltext_attrs = [
      attributes.FullTextAttr(
          "contact",
          "contact",
          ["email", "name"]
      ),
      attributes.FullTextAttr(
          'secondary_contact',
          'secondary_contact',
          ["email", "name"]),
  ]

  @classmethod
  def indexed_query(cls):
    return super(WithContact, cls).indexed_query().options(
        orm.Load(cls).joinedload(
            "contact"
        ).load_only(
            "name",
            "email",
            "id"
        ),
        orm.Load(cls).joinedload(
            "secondary_contact"
        ).load_only(
            "name",
            "email",
            "id"
        ),
    )

  _aliases = {
      "contact": "Primary Contact",
      "secondary_contact": "Secondary Contact",
  }


class BusinessObject(Stateful, Noted, Described, Titled, Slugged):
  """Mixin that groups most commonly-used mixins into one."""
  DRAFT = 'Draft'
  ACTIVE = 'Active'
  DEPRECATED = 'Deprecated'

  VALID_STATES = (DRAFT, ACTIVE, DEPRECATED, )

  _aliases = {
      "status": {
          "display_name": "State",
          "mandatory": False,
          "description": "Allowed values are:\n{}".format(
              '\n'.join(VALID_STATES))}
  }


class ScopeObject(WithExternalCreatedBy, BusinessObject):
  """Mixin that re-name status attribute"""

  _fulltext_attrs = [
      attributes.FullTextAttr("Launch Status", "status")
  ]
  _aliases = {
      "status": {
          "display_name": "Launch Status",
          "mandatory": False,
          "description": "Options are:\n{}".format(
              "\n".join(BusinessObject.VALID_STATES)
          )
      }
  }

# This class is just a marker interface/mixin to indicate that a model type
# supports custom attributes.


class TestPlanned(object):
  """Mixin that defines `test_plan` field."""

  @declared_attr
  def test_plan(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.Text, nullable=False, default=u""),
                    cls.__name__)

  # REST properties
  _api_attrs = reflection.ApiAttributes('test_plan')
  _fulltext_attrs = ['test_plan']
  _sanitize_html = ['test_plan']
  _aliases = {"test_plan": "Assessment Procedure"}

  @classmethod
  def indexed_query(cls):
    return super(TestPlanned, cls).indexed_query().options(
        orm.Load(cls).load_only("test_plan"),
    )


# pylint: disable=too-few-public-methods
class WithProtectedAttributes(object):
  """Mixin that check if attributes can be setted by external user."""

  # Set of protected attributes
  PROTECTED_ATTRIBUTES = set()

  @classmethod
  def get_protected_attributes(cls):
    """Get set of protected attributes for external user."""
    protected_attributes = set()

    for base in cls.mro():
      if hasattr(base, "PROTECTED_ATTRIBUTES"):
        protected_attributes.update(base.PROTECTED_ATTRIBUTES)

    return protected_attributes


class Folderable(WithProtectedAttributes):
  """Mixin adding the ability to attach folders to an object"""

  @declared_attr
  def folder(cls):
    return deferred(db.Column(db.Text, nullable=False, default=""),
                    cls.__name__)

  @classmethod
  def indexed_query(cls):
    return super(Folderable, cls).indexed_query().options(
        orm.Load(cls).load_only("folder"),
    )

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('folder', update=False),
  )
  _fulltext_attrs = ['folder']
  _aliases = {
      "folder": {
          "display_name": "GDrive Folder ID",
          "description": ("Add 'GDrive Folder ID' that is part of "
                          "drive link to a folder "
                          "'https://drive.google.com/corp/drive/folders/XXX', "
                          "where XXX is a 'GDrive Folder ID'")
      }
  }
  PROTECTED_ATTRIBUTES = {"folder"}


class WithNetworkZone(object):
  """Mixin that add network zone option."""

  network_zone_id = db.Column(db.Integer, nullable=True)

  @declared_attr
  def network_zone(cls):  # pylint: disable=no-self-argument
    return db.relationship(
        "Option",
        primaryjoin="and_(foreign({}.network_zone_id) == Option.id, "
                    "Option.role == 'network_zone')".format(cls.__name__),
        uselist=False,
    )

  _api_attrs = reflection.ApiAttributes(
      "network_zone",
  )
  _fulltext_attrs = [
      "network_zone",
  ]
  NZ_OPTIONS = ("Service",
                "Core",
                "3rd Party",
                "Prod",
                "Corp")
  _aliases = {
      "network_zone": {
          "display_name": "Network Zone",
          "description": "Allowed values are:\n{}".format(
              "\n".join(NZ_OPTIONS)),
      },
  }

  @orm.validates("network_zone")
  def validate_network_zone(self, key, option):
    return validate_option(
        self.__class__.__name__, key, option, 'network_zone')

  @classmethod
  def eager_query(cls, **kwargs):
    """Eager query."""
    query = super(WithNetworkZone, cls).eager_query(**kwargs)
    return query.options(
        orm.joinedload(
            "network_zone"
        ).undefer_group(
            "Option_complete",
        )
    )

  @classmethod
  def indexed_query(cls):
    """Indexed query."""
    query = super(WithNetworkZone, cls).indexed_query()
    return query.options(
        orm.joinedload(
            "network_zone",
        ).undefer_group(
            "Option_complete",
        )
    )


def person_relation_factory(relation_name, fulltext_attr=None, api_attr=None):
  """Factory that will generate person  """

  def field_declaration(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.Integer,
                              db.ForeignKey('people.id'),
                              nullable=True),
                    cls.__name__)

  def attr_declaration(cls):
    return db.relationship(
        'Person',
        primaryjoin='{0}.{1}_id == Person.id'.format(cls.__name__,
                                                     relation_name),
        foreign_keys='{0}.{1}_id'.format(cls.__name__,
                                         relation_name),
        remote_side='Person.id',
        uselist=False,
    )

  gen_fulltext_attr = (
      fulltext_attr or attributes.FullTextAttr(relation_name,
                                               relation_name,
                                               ["email", "name"]))
  api_attr = api_attr or reflection.Attribute(relation_name)

  # pylint: disable=too-few-public-methods,missing-docstring
  class DecoratedClass(object):

    _api_attrs = reflection.ApiAttributes(api_attr)
    fulltext_attr = [gen_fulltext_attr]

    @classmethod
    def indexed_query(cls):
      return super(DecoratedClass, cls).indexed_query().options(
          orm.Load(cls).joinedload(
              relation_name
          ).load_only(
              "name", "email", "id"
          ),
      )

  return type(
      "{}_mixin".format(relation_name),
      (DecoratedClass, ),
      {
          "{}_id".format(relation_name): declared_attr(field_declaration),
          relation_name: declared_attr(attr_declaration),
      })


def datetime_mixin_factory(relation_name, fulltext_attr=None, api_attr=None):
  """Factory responsible for datetime mixin generation."""

  def field_declaration(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.DateTime, nullable=True), cls.__name__)

  return type(
      "{}_mixin".format(relation_name),
      (object, ),
      {
          relation_name: declared_attr(field_declaration),
          "_api_attrs": reflection.ApiAttributes(api_attr or relation_name),
          "fulltext_attr": [fulltext_attr or relation_name],
      },
  )


__all__ = [
    "Base",
    "BusinessObject",
    "CustomAttributable",
    "Described",
    "FinishedDate",
    "Noted",
    "Notifiable",
    "Slugged",
    "Stateful",
    "ScopeObject",
    "TestPlanned",
    "WithStartDate",
    "WithEndDate",
    "Timeboxed",
    "Titled",
    "VerifiedDate",
    "WithContact",
    "Folderable",
    "WithWorkflowState",
]
