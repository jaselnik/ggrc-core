# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module contains object generation utilities."""

import datetime
import functools
import random

import names

from ggrc import db
from ggrc import models
from ggrc.app import app
from ggrc.models import all_models
from ggrc.models.mixins.synchronizable import Synchronizable
from ggrc.services import common
from ggrc_basic_permissions import models as permissions_models
from integration.ggrc import api_helper
from integration.ggrc.models import factories


class Generator(object):
  """Generator base class."""

  def __init__(self, fail_no_json=True):
    self.api = api_helper.Api()
    self.resource = common.Resource()
    self._fail_no_json = fail_no_json

  @staticmethod
  def random_date(start=datetime.date.today(), end=None):
    """Generate a random date between start and end."""
    if not end or start > end:
      end = start + datetime.timedelta(days=7)
    return start + datetime.timedelta(
        seconds=random.randint(0, int((end - start).total_seconds())))

  @staticmethod
  def get_header():
    """Get base GGRC headers."""
    return {
        "Content-Type": "application/json",
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def generate(self, obj_class, obj_name=None, data=None,
               with_background_tasks=False):
    """Generate `obj_class` instance with fields populated from `data`."""
    if obj_name is None:
      # pylint: disable=protected-access
      obj_name = obj_class._inflector.table_plural
      # pylint: enable=protected-access
    if data is None:
      data = {}

    headers = {}
    if with_background_tasks:
      headers.update({"X-GGRC-BackgroundTask": "true"})
    response = self.api.send_request(
        self.api.client.post, obj=obj_class, data=data, headers=headers,
    )

    response_obj = None
    if response.status_code == 201 and response.json:
      try:
        response_obj = obj_class.query.get(response.json[obj_name]['id'])
      except TypeError:
        if self._fail_no_json:
          raise Exception("Invalid response.\nResponse: {}\nError: {}".format(
              response,
              response.data
          ))
        response_obj = None
    return response, response_obj

  @staticmethod
  def get_object_from_response(response, obj_class, obj_name):
    """Try to get the object from response.

    If response does not contain the object, return None
    """
    try:
      return obj_class.query.get(response.json[obj_name]['id'])
    except KeyError:
      return None

  def modify(self, obj, obj_name, data):
    """Make a PUT request to modify `obj` with new fields in `data`."""
    obj_class = obj.__class__
    response = self.api.put(obj, data)
    response_obj = None
    if response.status_code == 200 and response.json:
      response_obj = self.get_object_from_response(response, obj_class,
                                                   obj_name)
    return response, response_obj

  def obj_to_dict(self, obj, model_name=None):
    with app.app_context():
      return self.resource.object_for_json(obj, model_name)


class ObjectGenerator(Generator):
  """Main object generator class.

  This class is used as a helper for generating ggrc objects via the API. This
  is used for writing integration tests on thigs that attach on api callbacs,
  such as model_posted, model_put and model_deleted.
  """

  def _singledispatchmethod(func):  # pylint: disable=no-self-argument
    """Call specific method based on second (1st is self) attr's type."""
    registry = {}

    def dispatch(cls):
      """Get specific method based on type."""
      return registry.get(cls, func)

    def register(cls, func=None):
      """Register method as handler for specific type."""
      if func is None:
        return lambda f: register(cls, f)
      registry[cls] = func
      return func

    def wrapper(*args, **kwargs):
      """Call method based on second argument type."""
      return dispatch(args[1])(*args, **kwargs)

    registry[object] = func
    wrapper.register = register
    wrapper.dispatch = dispatch
    wrapper.registry = registry
    functools.update_wrapper(wrapper, func)
    return wrapper

  @staticmethod
  def create_stub(obj):
    """Create object stub (dict with id and type information)."""
    # pylint: disable=protected-access
    return {
        "id": obj.id,
        "href": "/api/{}/{}".format(obj._inflector.table_name, obj.id),
        "type": obj.type,
    }

  @staticmethod
  def _get_synchronizable_obj_dict():
    """Return dict with fileds which extend Synchronizable object"""

    return {
        'external_id': factories.SynchronizableExternalId.next(),
        'external_slug': factories.random_str(),
    }

  @_singledispatchmethod
  def generate_object(self, obj_class, data=None, add_fields=True,
                      with_background_tasks=False):
    """Generate an object of `obj_class` with fields from `data`.

    This generator is used for creating objects with data. By default it will
    add the first user in the DB as the object owner and it will create a
    random title.

    Args:
      obj_class: Model that we want to generate.
      add_fields: Flag for adding owners and title default field values. If
        these are present in the data, default values will be overridden.
      data: Dict containing generation data for the object.
      with_background_tasks: Flag for executing background tasks on object
        creation.

    Returns:
      Tuple containing server response and the generated object.
    """
    if data is None:
      data = {}
    # pylint: disable=protected-access
    obj_name = obj_class._inflector.table_singular
    # pylint: enable=protected-access
    obj = obj_class()
    obj_dict = self.obj_to_dict(obj, obj_name)
    if add_fields:
      obj_dict[obj_name].update({
          "owners": [self.create_stub(models.Person.query.first())],
          "title": factories.random_str(),
      })
      if issubclass(obj_class, Synchronizable):
        obj_dict[obj_name].update(self._get_synchronizable_obj_dict())

    obj_dict[obj_name].update(data[obj_name] if obj_name in data else data)
    return self.generate(obj_class, obj_name=obj_name, data=obj_dict,
                         with_background_tasks=with_background_tasks)

  @generate_object.register(models.Control)
  def _(self, obj_class, data=None, add_fields=True,
        with_background_tasks=False):
    """Handle generation of `Control` objects."""
    data = data if data is not None else {}
    # pylint: disable=protected-access
    obj_name = models.Control._inflector.table_singular
    # pylint: enable=protected-access
    obj_dict = self.obj_to_dict(models.Control(), obj_name)

    defaults = {
        obj_name: {
            "title": factories.random_str(),
            "context": None,
            "recipients": "Admin,Control Operators,Control Owners",
            "send_by_default": 0,
            "assertions": '["test assertion"]',
            "review_status": all_models.Review.STATES.UNREVIEWED,
            "review_status_display_name": "some status",
        }
    }

    obj_dict[obj_name].update(defaults[obj_name])

    if issubclass(obj_class, Synchronizable):
      obj_dict[obj_name].update(self._get_synchronizable_obj_dict())

    obj_dict[obj_name].update(data[obj_name] if obj_name in data else data)
    return self.generate(models.Control, obj_name=obj_name, data=obj_dict,
                         with_background_tasks=with_background_tasks)

  @generate_object.register(models.Risk)
  def __(self, data=None, with_background_tasks=False):
    """Handle generation of `Risk` objects."""
    data = data if data is not None else {}
    # pylint: disable=protected-access
    obj_name = models.Risk._inflector.table_singular
    # pylint: enable=protected-access
    obj_dict = self.obj_to_dict(models.Risk(), obj_name)

    defaults = {
        obj_name: {
            "title": factories.random_str(),
            "context": None,
            "recipients": "Admin,Other Contacts,Risk Owners",
            "risk_type": "Some type",
            "review_status": all_models.Review.STATES.UNREVIEWED,
            "review_status_display_name": "some status",
        }
    }

    obj_dict[obj_name].update(defaults[obj_name])
    obj_dict[obj_name].update(self._get_synchronizable_obj_dict())

    return self.generate(models.Risk, obj_name=obj_name, data=obj_dict,
                         with_background_tasks=with_background_tasks)

  def generate_relationship(self, source, destination, context=None, **kwargs):
    """Create relationship between two objects.

    Args:
      source (db.Model): source model of the relationship.
      destination (db.Model): destination model of the relationship.
      context (Context): context of the relationship. Usually a context of one
        of the related objects.
      kwargs (dict): various arguments for the given relationship, such as
        relationship attributes.

    Returns:
      response object and the actual relationship that was created.
    """
    if context:
      context = self.create_stub(context)
    data = {
        "source": self.create_stub(source),
        "destination": self.create_stub(destination),
        "context": context,
        "is_external": False,
    }
    data.update(kwargs)
    return self.generate_object(
        models.Relationship, add_fields=False, data=data)

  def generate_comment(self, commentable, assignee_type, description,
                       **kwargs):
    """Create a comment on a commentable object.

    This function creates a comment for a given object and generates the
    correct relationship to that object. The result of generating the
    relationship is discarded and the user will only see if a comment is
    created.

    Args:
      commentable (db.Model): Model that is commentable such as Assessment.
      assignee_type (string): Assignee type of the person creating the comment.
      description (string): Comment content.
      kwargs (dict): Any additional data added to the comments.

    Returns:
      Server response and the generated comment.
    """
    data = {
        "description": description,
        "assignee_type": assignee_type,
        "context": self.create_stub(commentable),
    }
    data.update(kwargs)
    response, comment_ = self.generate_object(
        models.Comment, add_fields=False, data=data)
    # Refresh the object after an API call.
    commentable = commentable.__class__.query.get(commentable.id)
    self.generate_relationship(commentable, comment_, commentable.context)
    return response, comment_

  def generate_user_role(self, person, role, context=None):
    """Generate a mapping between `role` and `person`."""
    if context:
      context = self.create_stub(context)
    data = {
        "user_role": {
            "context": context,
            "person": self.create_stub(person),
            "role": self.create_stub(role),
        }
    }
    return self.generate(permissions_models.UserRole, "user_role", data)

  def generate_person(self, data=None, user_role=None):
    """Generate a person with fields from `data` and with an optional role."""
    if data is None:
      data = {}
    obj_name = 'person'
    name = names.get_full_name()
    default = {
        obj_name: {
            "context": None,
            "name": name,
            "email": "%s@test.com" % name.replace(" ", ".").lower(),
        }
    }
    default[obj_name].update(data)
    response, person = self.generate(models.Person, obj_name, default)

    if person and user_role:
      role = db.session.query(permissions_models.Role).filter(
          permissions_models.Role.name == user_role).first()
      self.generate_user_role(person, role)

    return response, person

  def generate_random_objects(self, count=5):
    """Generate `count` objects of random types."""
    random_objects = []
    classes = [
        models.Standard,
    ]
    for _ in range(count):
      obj_class = random.choice(classes)
      obj = self.generate_object(obj_class)[1]
      random_objects.append(obj)
    return random_objects

  def generate_random_people(self, count=5, **kwargs):
    """Generate `count` random people."""
    random_people = []
    for _ in range(count):
      _, person = self.generate_person(**kwargs)
      if person:
        random_people.append(person)
    return random_people

  def generate_notification_setting(self, user_id, notif_type, enable_flag):
    """Generate notification setting for user `user_id` of `notif_type`."""
    obj_name = "notification_config"
    data = {
        obj_name: {
            "person_id": user_id,
            "notif_type": notif_type,
            "enable_flag": enable_flag,
            "context": None,
            "type": "NotificationConfig",
        }
    }
    return self.generate(models.NotificationConfig, obj_name, data)

  def generate_custom_attribute(self, definition_type, **kwargs):
    """Generate a CA definition of `definition_type`."""
    obj_name = "custom_attribute_definition"
    data = {
        obj_name: {
            "title": kwargs.get("title", factories.random_str()),
            "custom_attribute_definitions": [],
            "custom_attributes": {},
            "definition_type": definition_type,
            "modal_title": kwargs.get("modal_title", factories.random_str()),
            "attribute_type": kwargs.get("attribute_type", "Text"),
            "mandatory": kwargs.get("mandatory", False),
            "helptext": kwargs.get("helptext", None),
            "placeholder": kwargs.get("placeholder", None),
            "context": {"id": None},
            "multi_choice_options": kwargs.get("options", None),
        }
    }
    data[obj_name].update(kwargs)
    return self.generate(models.CustomAttributeDefinition, obj_name, data)
