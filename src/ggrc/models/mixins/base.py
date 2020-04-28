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

from datetime import datetime

from logging import getLogger

from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr

from ggrc import builder
from ggrc import db
from ggrc.models import reflection
from ggrc.models.inflector import ModelInflectorDescriptor
from ggrc.models.reflection import AttributeInfo
from ggrc.utils import create_stub
from ggrc.fulltext import attributes


# pylint: disable=invalid-name
logger = getLogger(__name__)


def is_attr_of_type(object_, attr_name, mapped_class):
  """Check if relationship property points to mapped_class"""
  cls = object_.__class__

  if isinstance(attr_name, basestring):
    if hasattr(cls, attr_name):
      cls_attr = getattr(cls, attr_name)
      if (hasattr(cls_attr, "property") and
          isinstance(cls_attr.property,
                     orm.properties.RelationshipProperty) and
              cls_attr.property.mapper.class_ == mapped_class):
        return True
  return False


class Identifiable(object):

  """A model with an ``id`` property that is the primary key."""
  id = db.Column(db.Integer, primary_key=True)  # noqa

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('id', create=False, update=False),
      reflection.Attribute('type', create=False, update=False),
  )

  _inflector = ModelInflectorDescriptor()

  @builder.simple_property
  def type(self):
    return self.__class__.__name__

  @classmethod
  def eager_query(cls, **kwargs):  # pylint: disable=unused-argument
    """Sub-query for eager loading."""

    mapper_class = cls._sa_class_manager.mapper.base_mapper.class_
    return db.session.query(cls).options(
        db.Load(mapper_class).undefer_group(
            mapper_class.__name__ + '_complete'),
    )

  @classmethod
  def eager_inclusions(cls, query, include_links):
    """Load related items listed in include_links eagerly."""
    options = []
    for include_link in include_links:
      inclusion_class = getattr(cls, include_link).property.mapper.class_
      options.append(
          orm.subqueryload(include_link)
          .undefer_group(inclusion_class.__name__ + '_complete'))
    return query.options(*options)

  @declared_attr
  def __table_args__(cls):  # pylint: disable=no-self-argument
    if getattr(cls, '__abstract_table__', False):
      return None
    extra_table_args = AttributeInfo.gather_attrs(cls, '_extra_table_args')
    table_args = []
    table_dict = {}
    for table_arg in extra_table_args:
      if callable(table_arg):
        table_arg = table_arg()
      if isinstance(table_arg, (list, tuple, set)):
        if isinstance(table_arg[-1], (dict,)):
          table_dict.update(table_arg[-1])
          table_args.extend(table_arg[:-1])
        else:
          table_args.extend(table_arg)
      elif isinstance(table_arg, (dict,)):
        table_dict.update(table_arg)
      else:
        table_args.append(table_arg)
    if table_dict:
      table_args.append(table_dict)
    return tuple(table_args,)


class ContextRBAC(object):
  """Defines `context` relationship for Context-based access control."""

  @declared_attr
  def context_id(cls):  # pylint: disable=no-self-argument
    return db.Column(db.Integer, db.ForeignKey('contexts.id'))

  @declared_attr
  def context(cls):  # pylint: disable=no-self-argument
    return db.relationship('Context', uselist=False)

  @staticmethod
  def _extra_table_args(model):
    return (
        db.Index('fk_{}_contexts'.format(model.__tablename__), 'context_id'),
    )

  _api_attrs = reflection.ApiAttributes('context')

  @classmethod
  def indexed_query(cls):
    return super(ContextRBAC, cls).indexed_query().options(
        orm.Load(cls).load_only("context_id"),
    )


class CreationTimeTracked(object):
  """
    Mixing for created_at column support.

    `created_at` column will keep track of db record
    creation time.
  """

  @declared_attr
  def created_at(self):
    """
        Date of creation. Set to current time on object creation.
    """
    column = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.utcnow().replace(microsecond=0).isoformat(),
    )

    return column

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('created_at', create=False, update=False),
  )

  _fulltext_attrs = [
      attributes.DatetimeFullTextAttr('created_at', 'created_at'),
  ]

  _filterable_attrs = [
      "created_at",
  ]

  _aliases = {
      "created_at": {
          "display_name": "Created Date",
          "mandatory": False,
          "description": "Automatically provided values"
      },
  }

  @classmethod
  def indexed_query(cls):
    return super(CreationTimeTracked, cls).indexed_query().options(
        orm.Load(cls).load_only("created_at"),
    )


class ChangeTracked(CreationTimeTracked):

  """A model with fields to tracked the last user to modify the model, the
  creation time of the model, and the last time the model was updated.
  """
  @declared_attr
  def modified_by_id(cls):  # pylint: disable=no-self-argument
    """Id of user who did the last modification of the object."""
    return db.Column(db.Integer)

  @declared_attr
  def updated_at(cls):  # pylint: disable=no-self-argument
    """Date of last update. Set to current time on object creation/update."""
    column = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.utcnow().replace(microsecond=0).isoformat(),
        onupdate=lambda: datetime.utcnow().replace(microsecond=0).isoformat(),
    )
    return column

  @declared_attr
  def modified_by(cls):  # pylint: disable=no-self-argument
    """Relationship to user referenced by modified_by_id."""
    return db.relationship(
        'Person',
        primaryjoin='{0}.modified_by_id == Person.id'.format(cls.__name__),
        foreign_keys='{0}.modified_by_id'.format(cls.__name__),
        remote_side='Person.id',
        uselist=False,
    )

  @staticmethod
  def _extra_table_args(model):
    """Apply extra table args (like indexes) to model definition."""
    return (
        db.Index('ix_{}_updated_at'.format(model.__tablename__), 'updated_at'),
    )

  # TODO Add a transaction id, this will be handy for generating etags
  # and for tracking the changes made to several resources together.
  # transaction_id = db.Column(db.Integer)

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('modified_by', create=False, update=False),
      reflection.Attribute('updated_at', create=False, update=False),
  )

  _fulltext_attrs = [
      attributes.DatetimeFullTextAttr('updated_at', 'updated_at'),
      attributes.FullTextAttr(
          "modified_by", "modified_by", ["email", "name"]
      ),
  ]

  _filterable_attrs = [
      "updated_at",
  ]

  _aliases = {
      "updated_at": {
          "display_name": "Last Updated Date",
          "mandatory": False,
          "description": "Automatically provided values"
      },
      "modified_by": {
          "display_name": "Last Updated By",
          "mandatory": False,
          "description": "Automatically provided values"
      },
  }

  @classmethod
  def indexed_query(cls):
    """Sub-query for indexed query."""

    return super(ChangeTracked, cls).indexed_query().options(
        orm.Load(cls).load_only("updated_at"),
        orm.Load(cls).joinedload(
            "modified_by"
        ).load_only(
            "name", "email", "id"
        ),
    )


class Dictable(object):
  # pylint: disable=too-few-public-methods

  """
    Add support for model serialization to dict.
    This allow using ggrc.utils.as_json for model
    serialization to json (see utils.GrcEncoder).
  """
  def to_dict(self):
    return {
        column.name: getattr(self, column.name)
        for column in self.__table__.columns
        if hasattr(self, column.name)
    }


class Base(Dictable, ChangeTracked, Identifiable):

  """Several of the models use the same mixins. This class covers that common
  case.
  """
  _people_log_mappings = [
      "contact_id",
      "secondary_contact_id",
      "modified_by_id",
      "attribute_objects_id",  # used for person mapping CA
  ]

  @staticmethod
  def _person_stub(id_):
    return {
        'type': u"Person",
        'id': id_,
        'context_id': None,
        'href': u"/api/people/{}".format(id_),
    }

  def log_json_base(self):
    """Get a dict with attributes of self that is easy to serialize to json.

    This method lists only first-class attributes.
    """
    res = {
        "type": self.type,
    }

    res.update(self.to_dict())

    res["display_name"] = self.display_name

    return res

  def log_json(self):
    """Get a dict with attributes and related objects of self.

    This method converts additionally person-mapping attributes and owners
    to person stubs.
    """
    from ggrc import models

    res = self.log_json_base()

    for attr in self._people_log_mappings:
      if hasattr(self, attr):
        value = getattr(self, attr)

        if value and isinstance(value, list):
          json_repr = [self._person_stub(v) for v in value]
        elif value:
          json_repr = self._person_stub(value)
        else:
          json_repr = None

        # hardcoded [:-3] is used to strip "_id" suffix
        res[attr[:-3]] = json_repr

    for attr_name in AttributeInfo.gather_publish_attrs(self.__class__):
      if is_attr_of_type(self, attr_name, models.Option):
        attr = getattr(self, attr_name)
        if attr:
          stub = create_stub(attr)
          stub["title"] = attr.title
        else:
          stub = None
        res[attr_name] = stub
    return res

  @builder.simple_property
  def display_name(self):
    """Returns display name of current class object."""

    try:
      return self._display_name()
    except:  # pylint: disable=bare-except
      logger.warning("display_name error in %s", type(self), exc_info=True)
      return ""

  def _display_name(self):
    return getattr(self, "title", None) or getattr(self, "name", "")

  def copy_into(self, target_object, columns, **kwargs):
    """Copy current object values into a target object.

    Copy all values listed in columns from current class to target class and
    use kwargs as defaults with precedence. Note that this is a shallow copy
    and any mutable values will be shared between current and target objects.

    Args:
      target_object: object to which we want to copy current values. This
        function will mutate the target_object parameter if it is set.
      columns: list with all attribute names that we want to set in the
        target_object.
      kwargs: additional default values.

    Returns:
      target_object with all values listed in columns set.
    """
    target = target_object or type(self)()

    columns = set(columns).union(kwargs.keys())
    for name in columns:
      if name in kwargs:
        value = kwargs[name]
      else:
        value = getattr(self, name)
      setattr(target, name, value)

    return target

  CACHED_ATTRIBUTE_MAP = None

  @classmethod
  def attributes_map(cls):
    """Get class attributes map"""
    if cls.CACHED_ATTRIBUTE_MAP:
      return cls.CACHED_ATTRIBUTE_MAP
    aliases = AttributeInfo.gather_aliases(cls)
    cls.CACHED_ATTRIBUTE_MAP = {}
    for key, value in aliases.items():
      if isinstance(value, dict):
        name = value["display_name"]
        filter_by = None
        if value.get("filter_by"):
          filter_by = getattr(cls, value["filter_by"], None)
      else:
        name, filter_by = value, None
      if not name:
        continue
      if name.lower() not in getattr(cls, 'IGNORE_TEMPLATE_ATTRIBUTES', []):
        tmp = getattr(cls, "PROPERTY_TEMPLATE", "{}")
        name = tmp.format(name)
        key = tmp.format(key)
      cls.CACHED_ATTRIBUTE_MAP[name.lower()] = (key.lower(), filter_by)
    return cls.CACHED_ATTRIBUTE_MAP
