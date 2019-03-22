# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test api helper.

This module contains an api helper that is used for simulating api calls to our
app. This api helper is used instead of the TestCase.client in cases where we
need to access the API during the class setup stage, when the default flaks
test client is not yet ready.

This api helper also helps with delete and put requests where it fetches the
latest etag needed for such requests.
"""
import logging
from contextlib import contextmanager
from email import utils as email_utils
import json
from urllib import urlencode

import flask

from ggrc import db
from ggrc import builder
from ggrc import utils
from ggrc import settings
from ggrc.app import app
from ggrc.services.common import Resource


def wrap_client_calls(client):
  """Wrap all client api calls with app_context."""
  def wrapper(func):
    """Wrapper function for api client calls."""
    def new_call(*args, **kwargs):
      with app.app_context():
        return func(*args, **kwargs)
    return new_call

  client.get = wrapper(client.get)
  client.post = wrapper(client.post)
  client.put = wrapper(client.put)
  client.delete = wrapper(client.delete)
  client.head = wrapper(client.head)


class Api(object):
  """Test api class."""

  def __init__(self):
    self.client = app.test_client()
    wrap_client_calls(self.client)
    self.client.get("/login")
    self.resource = Resource()
    self.headers = {'Content-Type': 'application/json',
                    "X-Requested-By": "GGRC"
                    }
    self.user_headers = {}
    self.person_name = None
    self.person_email = None

  def set_user(self, person=None):
    """Set user for current api instance.

    All api calls will run as login user.
    If user is empty, they will run as superuser."""
    # Refresh the person instance from the db:
    if person:
      person = person.__class__.query.get(person.id)
      self.user_headers = {
          "X-ggrc-user": self.resource.as_json({
              "name": person.name,
              "email": person.email,
          })
      }
      self.person_name, self.person_email = person.name, person.email
      db.session.expunge(person)
    else:
      self.user_headers = {}
      self.person_name, self.person_email = None, None

    self.client.get("/logout")
    self.client.get("/login", headers=self.user_headers)
    db.session.commit()
    db.session.flush()

  def login_as_external(self, external_user=None):
    """Login API client as external app user."""
    _, user_email = email_utils.parseaddr(settings.EXTERNAL_APP_USER)
    self.user_headers = {
        "X-GGRC-user": "{\"email\": \"%s\"}" % user_email
    }

    if external_user:
      self.user_headers["X-EXTERNAL-USER"] = json.dumps(external_user)

    self.client.get("/logout")
    self.client.get("/login", headers=self.user_headers)

  def login_as_normal(self):
    """Login API client as internal user."""
    if "X-GGRC-user" in self.user_headers:
      del self.user_headers["X-GGRC-user"]

    self.client.get("/logout")
    self.client.get("/login")

  @contextmanager
  def as_external(self):
    self.login_as_external()
    yield
    self.login_as_normal()

  @staticmethod
  def api_link(obj, obj_id=None):
    """return API link to the object with ID"""
    obj_id = "" if obj_id is None else "/" + str(obj_id)
    return "/api/%s%s" % (obj._inflector.table_plural, obj_id)

  @staticmethod
  def data_to_json(response):
    """ add docoded json to response object """
    try:
      response.json = flask.json.loads(response.data)
    except StandardError:
      response.json = None
    return response

  # pylint: disable=too-many-arguments
  def send_request(self, request,
                   obj=None, data=None, headers=None, api_link=None):
    """Send an API request."""
    headers = headers or {}
    data = data or {}
    if api_link is None:
      if obj is not None:
        api_link = self.api_link(obj)

    headers.update(self.headers)
    headers.update(self.user_headers)

    json_data = self.resource.as_json(data)
    logging.info("request json: %s", json_data)
    response = request(api_link, data=json_data, headers=headers.items())
    if response.status_code == 401:
      self.set_user()
      response = request(api_link, data=json_data, headers=headers.items())

    if hasattr(flask.g, "referenced_object_stubs"):
      del flask.g.referenced_object_stubs

    return self.data_to_json(response)

  def put(self, obj, data=None, not_send_fields=None):
    """Simple put request."""
    name = obj._inflector.table_singular
    response = self.get(obj, obj.id)
    data = data or {}
    not_send_fields = not_send_fields or []
    if response.status_code == 403:
      return response
    headers = {
        "If-Match": response.headers.get("Etag"),
        "If-Unmodified-Since": response.headers.get("Last-Modified")
    }
    api_link = response.json[name]["selfLink"]
    if name not in data:
      response.json[name].update(data)
      data = response.json

    for field in not_send_fields:
      del data[name][field]

    return self.send_request(
        self.client.put, obj, data, headers=headers, api_link=api_link)

  def post(self, obj, data):
    return self.send_request(self.client.post, obj, data)

  def patch(self, model, data):
    return self.send_request(self.client.patch, data=data,
                             api_link=self.api_link(model))

  def get(self, obj, id_):
    return self.data_to_json(self.client.get(self.api_link(obj, id_)))

  def head(self, obj, id_):
    return self.data_to_json(self.client.head(self.api_link(obj, id_)))

  def get_collection(self, obj, ids):
    return self.data_to_json(self.client.get(
        "{}?ids={}".format(self.api_link(obj), ids)))

  def get_query(self, obj, query):
    return self.data_to_json(self.client.get(
        "{}?{}".format(self.api_link(obj), query)))

  def modify_object(self, obj, data=None):
    """Make a put call for a given object.

    Args:
      obj (db.Model): Object that should be modified, and it can also contain
        the changes that should be made.
      data (dict): dictionary containing the changed values for the object.
        This is not mandatory if the object itself has the given changes.

    Returns:
      response, db.Model: The put response from the server and the modified
        object if the put request was successful.
    """
    if data is None:
      data = {}
    obj_dict = builder.json.publish(obj)
    builder.json.publish_representation(obj_dict)
    obj_dict = flask.json.loads(utils.as_json(obj_dict))
    obj_dict.update(data)
    data = {obj._inflector.table_singular: obj_dict}
    return self.put(obj, data)

  def delete(self, obj, id_=None, args=None):
    """Delete api call helper.

    This function helps creating delete calls for a specific object by fetching
    the data and setting the appropriate etag needed for the delete api calls.

    Args:
      obj (sqlalchemy model): object that we wish to delete.

    Returns:
      Server response.
    """
    id_ = id_ or obj.id
    response = self.get(obj, id_)
    headers = {
        "If-Match": response.headers.get("Etag"),
        "If-Unmodified-Since": response.headers.get("Last-Modified")
    }
    headers.update(self.headers)
    api_link = self.api_link(obj, id_)
    if args:
      args_str = ",".join("{}={}".format(k, v) for k, v in args.items())
      api_link = "{}?{}".format(api_link, args_str)
    return self.client.delete(api_link, headers=headers)

  def search(self, types, query="", counts=False, relevant_objects=None,
             extra_params=None, extra_columns=None):
    """Api search call."""

    params = {
        'q': query,
        'types': types,
        'counts_only': str(counts)
    }

    if extra_params is not None:
      params['extra_params'] = extra_params

    if extra_columns is not None:
      params['extra_columns'] = extra_columns

    if relevant_objects is not None:
      params['relevant_objects'] = relevant_objects

    link = "/search?{}".format(urlencode(params))

    return self.client.get(link), self.headers
