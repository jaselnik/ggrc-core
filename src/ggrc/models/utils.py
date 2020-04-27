# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Utils for ggrc models."""

from ggrc import db
from ggrc.utils import referenced_objects

from ggrc.models.exceptions import ValidationError


def validate_option(model, attribute, option, desired_role):
  """Special validation for option model."""
  if option and option.role != desired_role:
    message = ("Invalid value for attribute {}.{}. "
               "Expected option with role {}, received role {}."
               .format(model, attribute, desired_role, option.role))
    raise ValidationError(message)
  return option


class PolymorphicRelationship(object):
  """This is shortcut to generate relationships from type and id fields."""
  # pylint: disable=too-few-public-methods

  def __init__(self, id_attr, type_attr, backref_format):
    self._id_attr = id_attr
    self._type_attr = type_attr
    self._backref_format = backref_format

  def _make_backref_attr(self, obj):
    """Construct the name of backref attr from format and type field value."""
    return self._backref_format.format(getattr(obj, self._type_attr))

  def __get__(self, obj, cls):
    """Get the value of the backref attr."""
    from ggrc.models import get_model
    if obj is None:
      return self
    attr_name = self._make_backref_attr(obj)
    if not hasattr(obj, attr_name):
      instance_type = getattr(obj, self._type_attr)
      instance_id = getattr(obj, self._id_attr)
      if instance_type:
        instance = get_model(instance_type).query.get(instance_id)
        setattr(obj, attr_name, instance)
    return getattr(obj, attr_name, None)

  def __set__(self, obj, value):
    """Prepare and set the value of the backref attr."""
    if value is None:
      setattr(obj, self._id_attr, None)
      setattr(obj, self._type_attr, None)
    else:
      setattr(obj, self._id_attr, value.id)
      setattr(obj, self._type_attr, value.__class__.__name__)
      setattr(obj, self._make_backref_attr(obj), value)


class JsonPolymorphicRelationship(PolymorphicRelationship):
  """Custom relation for instance.

  Allow to setup instance over json serializaion."""
  # pylint: disable=too-few-public-methods

  INSTANCE_TYPE = None

  def __call__(self, obj, json_obj):
    for field_name, prop_instance in obj.__class__.__dict__.iteritems():
      if prop_instance is self:
        instance = referenced_objects.get(json_obj[field_name]["type"],
                                          json_obj[field_name]["id"])
        if (
            self.INSTANCE_TYPE and not
            isinstance(instance, self.INSTANCE_TYPE)
        ):
          raise ValueError(
              "{actual_obj_type} is not of {required_obj_type} type.".format(
                  actual_obj_type=instance.type,
                  required_obj_type=self.INSTANCE_TYPE.__name__,
              )
          )
        return instance
    return None


# pylint: disable=invalid-name
def json_polymorphic_relationship_factory(instance_type):
  return type(
      "{}JsonPolymorphicRelationship".format(instance_type.__name__),
      (JsonPolymorphicRelationship, ),
      {"INSTANCE_TYPE": instance_type}
  )


class FasadeProperty(object):  # pylint: disable=too-few-public-methods
  """Fasade property.

  Allow to customize json preparation for current intance field."""

  FIELD_NAME = None

  def __init__(self):
    assert self.FIELD_NAME

  def __call__(self, obj, json_obj):
    return self.prepare(json_obj)

  def prepare(self, data):  # pylint: disable=no-self-use
    return data

  def __set__(self, obj, value):
    setattr(obj, self.FIELD_NAME, value)


def person_relationship(model_name, field_name):
  """Return relationship attribute between Person model and provided model."""
  return db.relationship(
      "Person",
      primaryjoin="{0}.{1} == Person.id".format(model_name, field_name),
      foreign_keys="{0}.{1}".format(model_name, field_name),
      remote_side="Person.id",
      uselist=False,
  )
