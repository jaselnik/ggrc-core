# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""GGRC Collection REST services implementation. Common to all GGRC collection
resources.
"""
# pylint: disable=too-many-lines
# pylint: disable=cyclic-import

import datetime
import collections
import hashlib
import itertools
import json
import logging
import time

from wsgiref.handlers import format_date_time
from urllib import urlencode

import flask
from flask import url_for, request, current_app, has_request_context
from flask.views import View
from flask.ext.sqlalchemy import Pagination
import sqlalchemy as sa
import sqlalchemy.orm.exc
from sqlalchemy.orm import load_only
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import (
    BadRequest,
    Forbidden,
    HTTPException,
    NotFound,
    MethodNotAllowed,
    ServiceUnavailable
)

import ggrc.builder.json
import ggrc.models
from ggrc import db
from ggrc import gdrive
from ggrc import utils
from ggrc.utils import as_json, benchmark, dump_attrs
from ggrc.utils.log_event import log_event
from ggrc.fulltext import get_indexer
from ggrc.login import get_current_user_id, get_current_user
from ggrc.login import is_external_app_user
from ggrc.models.cache import Cache
from ggrc.models.exceptions import ValidationError, translate_message
from ggrc.models.mixins.with_readonly_access import WithReadOnlyAccess
from ggrc.rbac import permissions
from ggrc.services.attribute_query import AttributeQueryBuilder
from ggrc.services import signals
from ggrc.models.background_task import BackgroundTask, create_task
from ggrc.query import utils as query_utils
from ggrc import settings
from ggrc.cache import utils as cache_utils
from ggrc.utils import errors as ggrc_errors
from ggrc.utils import format_api_error_response


# pylint: disable=invalid-name
logger = logging.getLogger(__name__)


CACHE_EXPIRY_COLLECTION = 60
MAX_AMOUNT_OF_REVISIONS = 100  # this is used on admin events page


def set_ids_for_new_custom_attributes(parent_obj):
  """
  When we are creating custom attribute values and definitions for
  POST requests, parent object ID is not yet defined. This is why we update
  custom attribute values at this point and set the correct attributable_id

  Args:
    parent_obj: parent object to be set as attributable

  Returns:
    None
  """
  if not hasattr(parent_obj, "PER_OBJECT_CUSTOM_ATTRIBUTABLE"):
    return
  for obj in get_modified_objects(db.session).new:
    if obj.type in ("CustomAttributeValue",
                    "ExternalCustomAttributeValue"):
      obj.attributable = parent_obj
    elif obj.type in ("CustomAttributeDefinition",
                      "ExternalCustomAttributeDefinition"):
      obj.definition = parent_obj


def inclusion_filter(obj):
  return permissions.is_allowed_read(obj.__class__.__name__,
                                     obj.id, obj.context_id)


def get_modified_objects(session):
  """Gets objects from cache.

  Args:
    session: Current SQLAlchemy session (db.session)
  """
  session.flush()
  cache = Cache.get_cache()
  if cache:
    return cache.copy()

  return None


def update_snapshot_index(cache):
  """Update fulltext index records for cached snapshtos."""
  from ggrc.snapshotter.indexer import reindex_snapshots
  if cache is None:
    return
  objs = itertools.chain(cache.new, cache.dirty, cache.deleted)
  reindex_snapshots_ids = [o.id for o in objs if o.type == "Snapshot"]
  get_indexer().delete_records_by_ids("Snapshot",
                                      reindex_snapshots_ids,
                                      commit=False)
  reindex_snapshots(reindex_snapshots_ids)


class ModelView(View):
  """Basic view handler for all models"""
  # pylint: disable=too-many-public-methods, protected-access
  # access to _sa_class_manager is needed for fetching the right mapper
  DEFAULT_PAGE_SIZE = 20
  MAX_PAGE_SIZE = 100
  pk = 'id'
  pk_type = 'int'

  _model = None

  # Simple accessor properties
  @property
  def request(self):
    return request

  @property
  def model(self):
    return self._model

  @property
  def modified_attr_name(self):
    return 'updated_at'

  @property
  def modified_attr(self):
    """Return the model attribute to be used for Last-Modified header and
    sorting collection elements.
    """
    return getattr(self.model, self.modified_attr_name)

  def modified_at(self, obj):
    """Returns modified_attr_name attr.

    Args:
      obj: An instance of class with modified_attr_name.
    Returns:
      Value of modified_attr_name attr.
    """
    return getattr(obj, self.modified_attr_name)

  @staticmethod
  def _get_type_where_clause(model):
    """Gets type in where clause.

    Args:
      model: Class of table model.
    """
    mapper = model._sa_class_manager.mapper
    if mapper.polymorphic_on is None:
      return True

    mappers = list(mapper.self_and_descendants)
    polymorphic_on_values = list(
        val
        for val, m in mapper.polymorphic_map.items()
        if m in mappers)
    return mapper.polymorphic_on.in_(polymorphic_on_values)

  @staticmethod
  def get_match_columns(model):
    """Gets match columns."""
    mapper = model._sa_class_manager.mapper
    columns = []
    columns.append(mapper.primary_key[0].label('id'))
    # columns.append(model.id.label('id'))
    columns.append(query_utils.get_type_select_column(model).label('type'))
    if hasattr(mapper.c, 'context_id'):
      columns.append(mapper.c.context_id.label('context_id'))
    if hasattr(mapper.c, 'updated_at'):
      columns.append(mapper.c.updated_at.label('updated_at'))
    # columns.append(self._get_polymorphic_column(model))
    return columns

  def get_collection_matches(self, model, filter_by_contexts=True):
    """Gets collection matches."""
    columns = self.get_match_columns(self.model)
    query = db.session.query(*columns).filter(
        self._get_type_where_clause(model))
    return self.filter_query_by_request(
        query, filter_by_contexts=filter_by_contexts)

  def get_resource_match_query(self, model, obj_id):
    """Gets resource match query."""
    columns = self.get_match_columns(model)
    query = db.session.query(*columns).filter(
        sa.and_(
            self._get_type_where_clause(model),
            columns[0] == obj_id))
    return query

  # Default model/DB helpers
  def get_collection(self, filter_by_contexts=True):
    """Gets collection."""
    if '__stubs_only' not in request.args and \
       hasattr(self.model, 'eager_query'):
      query = self.model.eager_query()
    else:
      query = db.session.query(self.model)
    return self.filter_query_by_request(
        query, filter_by_contexts=filter_by_contexts)

  def filter_query_by_request(self, query, filter_by_contexts=True):  # noqa
    """Returns query filter by request."""
    joinlist = []
    if request.args:
      querybuilder = AttributeQueryBuilder(self.model)
      filter_, joinlist, _ = querybuilder.collection_filters(request.args)
      if filter_ is not None:
        for j in joinlist:
          query = query.join(j)
        query = query.filter(filter_)

    if "__no_role" in request.args:
      attr = getattr(self.model, "user_roles")
      query = query.outerjoin(attr)
      user_roles_module = attr.mapper.class_
      superusers = getattr(settings, "BOOTSTRAP_ADMIN_USERS", [])
      # Filter out:
      # non superusers AND
      #   (users without user_role OR
      #    users with user_role BUT without global role:
      #    Reader, Editor, Administrator)
      subq = db.session.query(user_roles_module.person_id).filter(
          sa.or_(
              # all users that have global user_role
              user_roles_module.context_id.is_(None),
              user_roles_module.context_id == 0
          )
      ).subquery()
      filter_ = sa.and_(
          # user is not superuser
          ~self.model.email.in_(superusers),
          sa.or_(
              # user hasn't user_role in user_role table
              user_roles_module.id.is_(None),
              sa.and_(
                  # user has user_role in user_role table
                  user_roles_module.id.isnot(None),
                  # user hasn't global role
                  ~user_roles_module.person_id.in_(subq)
              )
          )
      )
      query = query.filter(filter_)

    if filter_by_contexts:
      contexts = permissions.read_contexts_for(self.model.__name__)
      resources = permissions.read_resources_for(self.model.__name__)
      if contexts is not None:
        if resources:
          query = query.filter(self.model.id.in_(resources))
        else:
          query = query.filter(sa.false())

      for j in joinlist:
        j_class = j.property.mapper.class_
        j_contexts = permissions.read_contexts_for(j_class.__name__)
        j_resources = permissions.read_resources_for(j_class.__name__)
        if resources:
          if j_contexts is None:
            query = query.filter(self.model.id.in_(resources))
          else:
            query = query.filter(self.model.id.in_(j_resources))
    if '__search' in request.args:
      terms = request.args['__search']
      indexer = get_indexer()
      search_query = indexer.get_permissions_query([self.model.__name__],
                                                   'read')
      search_query = sa.and_(search_query,
                             indexer.get_filter_query(terms, self.model))
      search_query = db.session.query(indexer.record_type.key).filter(
          search_query)
      if '__mywork' in request.args:
        search_query = indexer.search_get_owner_query(
            search_query, [self.model], get_current_user_id())
      search_subquery = search_query.subquery()
      query = query.filter(self.model.id.in_(search_subquery))
    order_properties = []
    if '__sort' in request.args:
      sort_attrs = request.args['__sort'].split(",")
      sort_desc = request.args.get('__sort_desc', False)
      for sort_attr in sort_attrs:
        attr_desc = sort_desc
        if sort_attr.startswith('-'):
          attr_desc = not sort_desc
          sort_attr = sort_attr[1:]
        order_property = getattr(self.model, sort_attr, None)
        if order_property and hasattr(order_property, 'desc'):
          if attr_desc:
            order_property = order_property.desc()
          order_properties.append(order_property)
        else:
          # Possibly throw an exception instead,
          # if sorting by invalid attribute?
          pass
    order_properties.append(self.modified_attr.desc())
    order_properties.append(self.model.id.desc())
    query = query.order_by(*order_properties)
    if '__limit' in request.args:
      try:
        limit = int(request.args['__limit'])
        query = query.limit(limit)
      except (TypeError, ValueError):
        pass
    query = query.distinct()
    return query

  def get_object(self, obj_id):
    """Gets object."""
    # This could also use `self.pk`
    # .one() is required as long as any .eager_load() adds joins using
    #   'contains_eager()' to the core query, because 'LIMIT 1' breaks up
    #   that JOIN result (e.g. Categorizable)
    try:
      return self.get_collection(
          filter_by_contexts=False).filter(self.model.id == obj_id).one()
    except sqlalchemy.orm.exc.NoResultFound:
      return None

  def get_object_without_rels(self, obj_id):
    """Get object by id without eager loading related models."""
    try:
      query = db.session.query(self.model).options(
          sa.orm.Load(self.model).load_only(
              "id", "context_id", self.modified_attr_name
          )
      )
      return query.get(obj_id)
    except sqlalchemy.orm.exc.NoResultFound:
      return None

  def not_found_message(self):
    """Generate Not Found message"""
    return '{0} not found.'.format(self.model._inflector.title_singular)

  def not_found_response(self):
    """Generate Not Found response"""
    return current_app.make_response((self.not_found_message(), 404, []))

  def collection_last_modified(self):
    """Calculate the last time a member of the collection was modified. This
    method relies on the fact that the collection table has an `updated_at` or
    other column with a relevant timestamp; services for models that don't have
    this field **MUST** override this method.
    """
    result = db.session.query(
        self.modified_attr).order_by(self.modified_attr.desc()).first()
    if result is not None:
      return self.modified_at(result)
    return datetime.datetime.utcnow()

  # Routing helpers
  @classmethod
  def endpoint_name(cls):
    """Get name of current class"""
    return cls.__name__

  @classmethod
  def url_for_preserving_querystring(cls, *args, **kwargs):
    """Gets url for preserving querystring."""
    url = cls.url_for(*args, **kwargs)
    # preserve original query string
    idx = request.url.find('?')
    querystring = '' if idx < 0 else '?' + request.url[idx + 1:]
    return url + querystring

  @classmethod
  def base_url_for(cls, _memoized_base_url=None):
    """Gets base url."""
    if _memoized_base_url is None:
      _memoized_base_url = {}

    if cls not in _memoized_base_url:
      if has_request_context():
        _memoized_base_url[cls] = url_for(cls.endpoint_name())
      else:
        _memoized_base_url[cls] = cls.generate_url()
    return _memoized_base_url[cls]

  @classmethod
  def generate_url(cls):
    """Generate relative endpoint url."""
    model = ggrc.models.get_model(cls.endpoint_name())
    plural_name = model._inflector.table_plural
    return "/api/{}".format(plural_name)

  @classmethod
  def url_for(cls, *args, **kwargs):
    """Returns url for."""
    url = cls.base_url_for()
    if args:
      arg = args[0]
      arg_id = arg if not isinstance(arg, db.Model) else arg.id
      url = '%s/%s' % (url, arg_id)
    if 'id' in kwargs:
      url = '%s/%s' % (url, kwargs['id'])
      del kwargs['id']
    if kwargs:
      url = '%s?%s' % (url, urlencode(kwargs))
    return url

  @classmethod
  def decorate_view_func(cls, view_func, decorators):
    """Decorates view func."""
    if not isinstance(decorators, (list, tuple)):
      decorators = (decorators,)
    for decorator in reversed(decorators):
      view_func = decorator(view_func)
    return view_func


# View base class for Views handling
#   - /resources (GET, POST, PATCH)
#   - /resources/<pk:pk_type> (GET, PUT, POST, DELETE)
class Resource(ModelView):
  """View base class for Views handling.  Will typically be registered with an
  application following a collection style for routes. Collection `GET` and
  `POST` will have a route like `/resources` while collection member
  resource routes will have routes like `/resources/<pk:pk_type>`.

  To register a Resource subclass FooCollection with a Flask application:

  ..

     FooCollection.add_to(app, '/foos')

  By default will only support the `application/json` content-type.
  """

  def dispatch_request(self, *args, **kwargs):  # noqa
    # pylint: disable=too-many-return-statements,arguments-differ
    # pylint: disable=too-many-branches

    with benchmark("Dispatch request"):
      with benchmark("dispatch_request > Check Headers"):
        method = request.method
        if method in ('POST', 'PUT', 'DELETE')\
           and 'X-Requested-By' not in request.headers:
          raise BadRequest('X-Requested-By header is REQUIRED.')

      with benchmark("dispatch_request > Try"):
        try:
          if method == 'GET':
            if self.pk in kwargs and kwargs[self.pk] is not None:
              return self.get(*args, **kwargs)
            return self.collection_get()
          elif method == 'HEAD':
            if self.pk in kwargs and kwargs[self.pk] is not None:
              return self.head(*args, **kwargs)
            raise MethodNotAllowed()
          elif method == 'POST':
            if self.pk in kwargs and kwargs[self.pk] is not None:
              return self.post(*args, **kwargs)
            return self.collection_post()
          elif method == 'PUT':
            return self.put(*args, **kwargs)
          elif method == 'PATCH':
            return self.patch()
          elif method == 'DELETE':
            return self.delete(*args, **kwargs)
          else:
            raise NotImplementedError()
        except (IntegrityError, ValidationError, ValueError) as err:
          logger.exception(err)
          message = translate_message(err)
          raise BadRequest(message)
        except HTTPException as error:
          logger.exception(error)
          code = error.code or 500
          # Since HTTPException may have both 4xx or 5xx codes
          alternative_message = ggrc_errors.INTERNAL_SERVER_ERROR
          if code < 500:
            alternative_message = ggrc_errors.BAD_REQUEST_MESSAGE
          message = error.description or alternative_message
          return format_api_error_response(code, message)
        except Exception as err:  # pylint: disable=broad-except
          logger.exception(err)
          err.message = ggrc_errors.INTERNAL_SERVER_ERROR
          raise
        finally:
          # When running integration tests, cache sometimes does not clear
          # correctly
          if getattr(settings, 'TESTING', False):
            cache = Cache.get_cache()
            if cache:
              cache.clear()

  def post(self, *args, **kwargs):
    """POST operation handler."""
    raise NotImplementedError()

  def get(self, id):  # pylint: disable=redefined-builtin
    """Default JSON request handlers"""
    with benchmark("Query for object"):
      obj = self.get_object(id)
    if obj is None:
      return self.not_found_response()

    accept_header = self.request.headers.get('Accept', '').strip()
    if (
        accept_header and
        accept_header != '*/*' and
        'application/json' not in accept_header
    ):
      return current_app.make_response((
          'application/json', 406, [('Content-Type', 'text/plain')]))

    with benchmark("Query read permissions"):
      if not permissions.is_allowed_read(
          self.model.__name__, obj.id, obj.context_id)\
         and not permissions.has_conditions('read', self.model.__name__):
        raise Forbidden()
      if not permissions.is_allowed_read_for(obj):
        raise Forbidden()
    with benchmark("Serialize object"):
      object_for_json = self.object_for_json(obj)

    obj_etag = etag(self.modified_at(obj), get_info(obj))
    if 'If-None-Match' in self.request.headers and \
       self.request.headers['If-None-Match'] == obj_etag:
      with benchmark("Make response"):
        return current_app.make_response(
            ('', 304, [('Etag', obj_etag)]))
    with benchmark("Make response"):
      return self.json_success_response(
          object_for_json, self.modified_at(obj), obj_etag=obj_etag)

  def head(self, id):  # pylint: disable=redefined-builtin
    """Get headers for object."""
    with benchmark("Query for object"):
      obj = self.get_object_without_rels(id)
      if not obj:
        return self.not_found_response()

    with benchmark("Query read permissions"):
      if not permissions.is_allowed_read_for(obj):
        raise Forbidden()

    obj_etag = etag(self.modified_at(obj), get_info(obj))
    with benchmark("Make response"):
      return self.json_success_response(
          {}, self.modified_at(obj), obj_etag=obj_etag
      )

  def validate_headers_for_put_or_delete(self, obj):
    """rfc 6585 defines a new status code for missing required headers"""
    required_headers = set(["If-Match", "If-Unmodified-Since"])
    missing_headers = required_headers.difference(
        set(self.request.headers.keys()))
    if missing_headers:
      return format_api_error_response(
          428,
          "Missing headers: " + ", ".join(missing_headers)
      )

    # Validate we have up to date object state according to Etag
    object_etag = etag(self.modified_at(obj), get_info(obj))
    object_timestamp = self.http_timestamp(self.modified_at(obj))
    if (request.headers["If-Match"] != object_etag or
            request.headers["If-Unmodified-Since"] != object_timestamp):

      headers = [('Last-Modified', object_timestamp),
                 ('Etag', object_etag),
                 ("Content-Type", "application/json")]
      error_message = ("The resource could not be updated due to a conflict "
                       "with the current state on the server. Please "
                       "resolve the conflict by refreshing the resource.")
      body = {"message": error_message, "code": 409}
      body.update(self.object_for_json(obj))
      return flask.make_response((as_json(body), 409, headers))
    return None

  @staticmethod
  def json_update(obj, src):
    """Update object `obj` with data from JSON `src`."""
    ggrc.builder.json.update(obj, src)

  def patch(self):
    """PATCH operation handler."""
    raise NotImplementedError()

  def _check_put_permissions(self, obj, new_context):
    """Check context and resource permissions for PUT."""
    if (not permissions.is_allowed_update(
            self.model.__name__, obj.id, obj.context_id) and
            not permissions.has_conditions('update', self.model.__name__)):
      raise Forbidden()
    if not permissions.is_allowed_update_for(obj):
      raise Forbidden()
    if (new_context != obj.context_id and
            not permissions.is_allowed_update(
                self.model.__name__, obj.id, new_context) and
            not permissions.has_conditions('update', self.model.__name__)):
      raise Forbidden()

  @staticmethod
  def _validate_readonly_access(obj, src):
    """Ensure that user can perform this request depending on readonly flag

    This method is called for POST, PUT and DELETE requests.
    It raises 405 NotAllowed if user cannot change object.

    :param obj - object with all attributes set/updated from src (POST, PUT)
                 or existing unmodified object (DELETE)
    :param src - dict from request (POST, PUT) or None (DELETE)
    """

    del src  # unused

    if not isinstance(obj, WithReadOnlyAccess):
      return

    is_external = is_external_app_user()

    if is_external and request.method in ('PUT', 'POST'):
      return

    if obj.readonly:
      raise MethodNotAllowed(
          description="The object is in a read-only mode and "
                      "is dedicated for SOX needs")

  @staticmethod
  def _validate_readonly_fields(obj, src):
    if hasattr(obj, "is_updating_readonly_fields"):
      if obj.is_updating_readonly_fields(src):
        raise Forbidden(
            description="Some fields in the object is in a read-only "
                        "mode for Assignees")

  def _validate_readonly_access_on_post(self, objects, sources):
    """Validate read-only access on POST"""

    for obj, src in zip(objects, sources):
      self._validate_readonly_access(obj, src)

  @utils.validate_mimetype("application/json")
  def put(self, id):  # pylint: disable=redefined-builtin
    """PUT operation handler."""
    with benchmark("Query for object"):
      obj = self.get_object(id)
    if obj is None:
      return self.not_found_response()

    initial_state = dump_attrs(obj)

    src = self.request.json
    header_error = self.validate_headers_for_put_or_delete(obj)
    if header_error:
      return header_error
    root_attribute = self.model._inflector.table_singular
    try:
      src = src[root_attribute]
    except KeyError:
      raise BadRequest('Required attribute "{0}" not found'.format(
          root_attribute))
    with benchmark("Set referenced_stubs"):
      flask.g.referenced_object_stubs = self._gather_referenced_objects(src)
    with benchmark("Query update permissions"):
      new_context = self.get_context_id_from_json(src)
      self._check_put_permissions(obj, new_context)

    with benchmark("Validate read-only access"):
      # check read-only access AFTER check for permissions to disallow
      # user obtain value for flag "readonly"
      self._validate_readonly_access(obj, src)

    with benchmark("Validate read-only fields access"):
      self._validate_readonly_fields(obj, src)

    with benchmark("Deserialize object"):
      self.json_update(obj, src)

    self.add_modified_object_to_session(obj)

    with benchmark("Process actions"):
      self.process_actions(obj)
    with benchmark("Validate custom attributes"):
      if hasattr(obj, "validate_custom_attributes"):
        obj.validate_custom_attributes()
    with benchmark("Validate access_control_list"):
      if hasattr(obj, "validate_acl"):
        obj.validate_acl()
    with benchmark("Send PUT event"):
      signals.Restful.model_put.send(
          obj.__class__, obj=obj, src=src, service=self)
    with benchmark("Get modified objects"):
      modified_objects = get_modified_objects(db.session)
    with benchmark("Update custom attribute values"):
      set_ids_for_new_custom_attributes(obj)
    with benchmark("Log event"):
      event = log_event(db.session, obj, force_obj=True)
    with benchmark("Update memcache before commit for collection PUT"):
      cache_utils.update_memcache_before_commit(
          self.request, modified_objects, CACHE_EXPIRY_COLLECTION)
    with benchmark("Send PUT - before commit event"):
      signals.Restful.model_put_before_commit.send(
          obj.__class__, obj=obj, src=src, service=self, event=event,
          initial_state=initial_state)
    with benchmark("Commit"):
      db.session.commit()
    with benchmark("Query for object"):
      obj = self.get_object(id)
    with benchmark("Serialize collection"):
      object_for_json = self.object_for_json(obj)
    with benchmark("Update index"):
      update_snapshot_index(modified_objects)
    with benchmark("Update memcache after commit for collection PUT"):
      cache_utils.update_memcache_after_commit(self.request)
    with benchmark("Send PUT - after commit event"):
      signals.Restful.model_put_after_commit.send(
          obj.__class__, obj=obj, src=src, service=self, event=event,
          initial_state=initial_state)
      # Note: Some data is created in listeners for model_put_after_commit
      # (like updates to snapshots), so we need to commit the changes
      with benchmark("Get modified objects"):
        modified_objects = get_modified_objects(db.session)
      with benchmark("Update memcache before commit"):
        cache_utils.update_memcache_before_commit(
            self.request, modified_objects, CACHE_EXPIRY_COLLECTION)
      db.session.commit()
      with benchmark("Update memcache after commit"):
        cache_utils.update_memcache_after_commit(self.request)
      if self.has_cache():
        self.invalidate_cache_to(obj)
    with benchmark("Send event job"):
      send_event_job(event)
    with benchmark("Make response"):
      return self.json_success_response(
          object_for_json, self.modified_at(obj),
          obj_etag=etag(self.modified_at(obj), get_info(obj)))

  def add_modified_object_to_session(self, obj):
    """Update modification metadata and add object to session."""
    obj.modified_by_id = get_current_user_id()
    obj.updated_at = datetime.datetime.utcnow()

    db.session.add(obj)

  @classmethod
  def _mark_delete_object_permissions(cls, obj):
    """Mark objects to fetch permissions on delete request."""
    if obj.type == "Relationship":
      flask.g.referenced_object_stubs = collections.defaultdict(set)
      for related_obj in (obj.source, obj.destination, obj):
        flask.g.referenced_object_stubs[related_obj.type].add(related_obj.id)
    else:
      flask.g.referenced_object_stubs = {obj.type: {obj.id}}

  def delete(self, id):  # pylint: disable=redefined-builtin
    """DELETE operation handler."""
    with benchmark("Query for object"):
      obj = self.get_object(id)
    if obj is None:
      return self.not_found_response()

    self._mark_delete_object_permissions(obj)

    with benchmark("Query delete permissions"):
      if not permissions.is_allowed_delete(
          self.model.__name__, obj.id, obj.context_id)\
         and not permissions.has_conditions("delete", self.model.__name__):
        raise Forbidden()
      if not permissions.is_allowed_delete_for(obj):
        raise Forbidden()
    header_error = self.validate_headers_for_put_or_delete(obj)
    if header_error:
      return header_error

    with benchmark("Validate read-only access"):
      # check read-only access AFTER check for permissions to disallow
      # user obtain value for flag "readonly"
      self._validate_readonly_access(obj, None)

    db.session.delete(obj)
    with benchmark("Send DELETEd event"):
      signals.Restful.model_deleted.send(
          obj.__class__, obj=obj, service=self)
    with benchmark("Get modified objects"):
      modified_objects = get_modified_objects(db.session)
    with benchmark("Log event"):
      event = log_event(db.session, obj)
    with benchmark("Update memcache before commit for collection DELETE"):
      cache_utils.update_memcache_before_commit(
          self.request, modified_objects, CACHE_EXPIRY_COLLECTION)
    with benchmark("Commit"):
      db.session.commit()
    with benchmark("Update index"):
      update_snapshot_index(modified_objects)
    with benchmark("Update memcache after commit for collection DELETE"):
      cache_utils.update_memcache_after_commit(self.request)
    with benchmark("Send DELETEd - after commit event"):
      signals.Restful.model_deleted_after_commit.send(
          obj.__class__, obj=obj, service=self, event=event)
    with benchmark("Send event job"):
      send_event_job(event)
    with benchmark("Make response"):
      result = self.json_success_response({}, datetime.datetime.utcnow())
    return result

  @staticmethod
  def has_cache():
    return cache_utils.has_memcache()

  def apply_paging(self, matches_query):
    """Apply pagination."""
    page_size = min(
        int(request.args.get('__page_size', self.DEFAULT_PAGE_SIZE)),
        self.MAX_PAGE_SIZE)
    if '__page_only' in request.args:
      page_number = int(request.args.get('__page', 0))
      matches = []
      total = matches_query.count()
    else:
      page_number = int(request.args.get('__page', 1))
      matches = matches_query\
          .limit(page_size)\
          .offset((page_number - 1) * page_size)\
          .all()
      if page_number == 1 and len(matches) < page_size:
        total = len(matches)
      else:
        total = matches_query.count()
    page = Pagination(
        matches_query, page_number, page_size, total, matches)
    collection_extras = {
        'paging': self.build_page_object_for_json(page)
    }
    return matches, collection_extras

  def get_matched_resources(self, matches):
    """Gets matched resources."""
    cache_objs = {}
    if self.has_cache():
      self.request.cache_manager = cache_utils.get_cache_manager()
      with benchmark("Query cache for resources"):
        cache_objs = self.get_resources_from_cache(matches)
      database_matches = [m for m in matches if m not in cache_objs]
    else:
      database_matches = matches

    database_objs = {}
    if database_matches:
      database_objs = self.get_resources_from_database(matches)
      if self.has_cache():
        with benchmark("Add resources to cache"):
          self.add_resources_to_cache(database_objs)
    return cache_objs, database_objs

  def collection_get(self):
    """Gets collection."""
    with benchmark("dispatch_request > collection_get > Check headers"):
      accept_header = self.request.headers.get('Accept', '').strip()
      if (
          accept_header and
          accept_header != '*/*' and
          'application/json' not in accept_header
      ):
        return current_app.make_response((
            'application/json', 406, [('Content-Type', 'text/plain')]))

    with benchmark("dispatch_request > collection_get > Collection matches"):
      # We skip querying by contexts for Creator role and relationship objects,
      # because it will filter out objects that the Creator can access.
      # We are doing a special permissions check for these objects
      # below in the filter_resource method.
      filter_by_contexts = not (
          self.model.__name__ in ("Relationship", "Revision") and _is_creator()
      )
      matches_query = self.get_collection_matches(
          self.model, filter_by_contexts)
    with benchmark("dispatch_request > collection_get > Query Data"):
      if '__page' in request.args or '__page_only' in request.args:
        with benchmark("Query matches with paging"):
          matches, extras = self.apply_paging(matches_query)
      else:
        with benchmark("Query matches"):
          matches = matches_query.all()
          extras = {}
    with benchmark("dispatch_request > collection_get > Matched resources"):
      cache_op = None
      if '__stubs_only' in request.args:
        objs = [{
            'id': m[0],
            'type': m[1],
            'href': utils.url_for(m[1], id=m[0]),
            'context_id': m[2]
        } for m in matches]

      else:
        cache_objs, database_objs = self.get_matched_resources(matches)
        objs = {}
        objs.update(cache_objs)
        objs.update(database_objs)

        objs = [objs[m] for m in matches if m in objs]
        with benchmark("Filter resources based on permissions"):
          objs = filter_resource(objs)

        cache_op = 'Hit' if cache_objs else 'Miss'
    with benchmark("dispatch_request > collection_get > Create Response"):
      # Return custom fields specified via `__fields=id,title,description` etc.
      # TODO this can be optimized by filter_resource() not retrieving
      # the other fields to being with
      if '__fields' in request.args:
        custom_fields = request.args['__fields'].split(',')
        objs = [{f: o[f] for f in custom_fields if f in o} for o in objs]
      with benchmark("Serialize collection"):
        collection = self.build_collection_representation(
            objs, extras=extras)

      if 'If-None-Match' in self.request.headers and \
         self.request.headers['If-None-Match'] == etag(collection):
        return current_app.make_response((
            '', 304, [('Etag', etag(collection))]))

      with benchmark("Make response"):
        return self.json_success_response(
            collection, self.collection_last_modified(), cache_op=cache_op)

  def get_resources_from_cache(self, matches):
    """Get resources from cache for specified matches"""
    resources = {}
    # Disable caching for background tasks
    # Setting background task status circumvents our memcache
    # invalidation logic so we have to disabling memcache.
    if self.model.__name__ == 'BackgroundTask':
      return resources
    # Skip right to memcache
    memcache_client = self.request.cache_manager.cache_object.memcache_client
    for match in matches:
      key = cache_utils.get_cache_key(None, id_=match[0], type_=match[1])
      val = memcache_client.get(key)
      if val:
        val = json.loads(val)
      else:
        val = {}
      if "selfLink" in val:
        resources[match] = val
    return resources

  def add_resources_to_cache(self, match_obj_pairs):
    """Add resources to cache if they are not blocked by DeleteOp entries"""
    # Skip right to memcache
    cache_manager = self.request.cache_manager
    memcache_client = cache_manager.cache_object.memcache_client
    for match, obj in match_obj_pairs.items():
      if obj.__class__.__name__ in cache_manager.supported_classes:
        memcache_client.add(
            cache_utils.get_cache_key(None, id_=match[0], type_=match[1]),
            as_json(obj))

  def invalidate_cache_to(self, obj):
    """Invalidate api cache for sent object."""
    memcache_client = self.request.cache_manager.cache_object.memcache_client
    memcache_client.delete(
        cache_utils.get_cache_key(None, id_=obj.id, type_=obj.type),
    )

  @staticmethod
  def json_create(obj, src):
    ggrc.builder.json.create(obj, src)

  @staticmethod
  def get_context_id_from_json(src):
    """Get context id from json."""
    context = src.get('context', None)
    if context:
      context_id = context.get('id', None)
      try:
        return int(context_id)
      except (ValueError, TypeError):
        return None
    return None

  def handle_create(self, obj, src):
    """Do NOTHING by default"""
    pass

  def _unwrap_collection_post_src(self, wrapped_src):
    """Get a valid source dict.

    Wrapped source example:
      {"policy": {"title": "A", context: None}}

    This function unwraps the first dict, returns only a dict containing
    model attributes and checks that the source contains a mandatory context
    attribute.

    Args:
      wrapped_src: dict containing a dict with all model attributes.

    Returns:
      inner dict containing only the model attributes.

    Raises:
      BadRequest if any of the required attributes are missing.
    """
    root_attribute = self.model._inflector.table_singular
    try:
      src = wrapped_src[root_attribute]
    except KeyError:
      raise BadRequest('Required attribute "{0}" not found'.format(
          root_attribute))

    if 'context' not in src:
      # context is obsolete functionality which is covered by ACL now.
      # However, this functionality cannot be completely removed because
      # it is deeply integrated into the code and requires too much effort
      # to be removed for now. FE not always adds this field,
      # but it is required by BE source code. So we add it with None value
      src['context'] = None

    return src

  def _get_relationship(self, src):
    """Get existing relationship if exists, and update updated_at"""

    relationship = self.model.get_related_query_by_type_id(
        type1=src["source"]["type"],
        id1=src["source"]["id"],
        type2=src["destination"]["type"],
        id2=src["destination"]["id"],
        strict_id=True
    ).first()

    if relationship:
      # Manually trigger relationship update in order for revisions and
      # event being created. We expect positive response when POSTing
      # an existing relationship.
      logger.info(
          "The relationship between %s %s and %s %s is already exist.",
          src["source"]["type"],
          src["source"]["id"],
          src["destination"]["type"],
          src["destination"]["id"],
      )
      relationship.updated_at = datetime.datetime.utcnow()
    return relationship

  def _get_model_instance(self, src=None):  # pylint: disable=unused-argument
    """Get a model instance.

    This function creates a new model instance and returns it. The function is
    needed for correct handling of Relationship objects. Relationship post
    request should not fail if a relationship already exists, since some
    relationships can be created with auto mappings.

    Args:
      src: dict containing new object source.

    Returns:
      obj: An instance of current model.
      needs_update: Flag shows if we need to update obj attributes.
    """
    obj = self.model()
    db.session.add(obj)
    return obj, True

  def _check_post_permissions(self, objects):
    """Check create permissions for a list of objects.append

    Args:
      objects: List of objects.

    Raises:
      Forbidden error if user does not have create permission for all objects
      in the objects list.
    """
    for obj in objects:
      if not permissions.is_allowed_create_for(obj):
        # json_create sometimes adds objects to session, so we need to
        # make sure the session is cleared
        db.session.expunge_all()
        raise Forbidden()

  def _gather_referenced_objects(self, data, accumulator=None):
    if accumulator is None:
      accumulator = collections.defaultdict(set)
    if isinstance(data, list):
      for value in data:
        self._gather_referenced_objects(value, accumulator)
    elif isinstance(data, dict):
      if "type" in data and data.get("id"):
        try:
          accumulator[data["type"]].add(data["id"])
        except TypeError:
          raise BadRequest("Either type or id are specified "
                           "incorrectly in the request payload.")
      for value in data.values():
        self._gather_referenced_objects(value, accumulator)
    return accumulator

  def _build_request_stub_cache(self, data):
    """Query objects from `data` and store them in cache."""
    objects = self._gather_referenced_objects(data)
    flask.g.referenced_objects = {}
    for class_name, ids in objects.items():
      utils.referenced_objects.mark_to_cache(class_name, ids)
    utils.referenced_objects.rewarm_cache(
        undefer=True,
    )

  def _check_post_create_options(self, body):
    """Do NOTHING by default"""
    pass

  def collection_post_loop(self, body, res, no_result):
    """Handle all posted objects.

    Args:
      body: list of dictionaries containing json object representations.
      res: List that will get responses appended to it.
      no_result: Flag for suppressing results.
    """
    with benchmark("Check create options"):
      self._check_post_create_options(body)
    with benchmark("Generate objects"):
      objects = []
      sources = []

      for wrapped_src in body:
        src = self._unwrap_collection_post_src(wrapped_src)
        obj, needs_update = self._get_model_instance(src)

        if not needs_update:
          obj.modified_by = get_current_user()
          db.session.flush()
          object_for_json = {} if no_result else self.object_for_json(obj)
          res.append((200, object_for_json))
          continue

        with benchmark("Deserialize object"):
          self.json_create(obj, src)
        with benchmark("Send model POSTed event"):
          signals.Restful.model_posted.send(
              obj.__class__, obj=obj, src=src, service=self)
        with benchmark("Update custom attribute values"):
          set_ids_for_new_custom_attributes(obj)

        obj.modified_by = get_current_user()
        objects.append(obj)
        sources.append(src)

    with benchmark("Check create permissions"):
      self._check_post_permissions(objects)

    with benchmark("Validate read-only access"):
      self._validate_readonly_access_on_post(objects, sources)

    with benchmark("Send collection POSTed event"):
      signals.Restful.collection_posted.send(
          obj.__class__, objects=objects, sources=sources)
    with benchmark("Flush posted objects"):
      db.session.flush()
    with benchmark("Validate custom attributes"):
      for obj in objects:
        if hasattr(obj, "validate_custom_attributes"):
          obj.validate_custom_attributes()
    with benchmark("Validate access_control_list"):
      for obj in objects:
        if hasattr(obj, "validate_acl"):
          obj.validate_acl()
    with benchmark("Get modified objects"):
      modified_objects = get_modified_objects(db.session)
    with benchmark("Log event for all objects"):
      event = log_event(db.session, obj, flush=False)
    with benchmark("Update memcache before commit for collection POST"):
      cache_utils.update_memcache_before_commit(
          self.request, modified_objects, CACHE_EXPIRY_COLLECTION)
    with benchmark("Serialize objects"):
      for obj in objects:
        object_for_json = {} if no_result else self.object_for_json(obj)
        res.append((201, object_for_json))
    with benchmark("Commit collection"):
      db.session.commit()
    with benchmark("Update index"):
      update_snapshot_index(modified_objects)
    with benchmark("Update memcache after commit for collection POST"):
      cache_utils.update_memcache_after_commit(self.request)

    with benchmark("Send model POSTed - after commit event"):
      for obj, src in itertools.izip(objects, sources):
        signals.Restful.model_posted_after_commit.send(
            obj.__class__, obj=obj, src=src, service=self, event=event)
        # Note: In model_posted_after_commit necessary mapping and
        # relationships are set, so need to commit the changes
      db.session.commit()
    with benchmark("Send event job"):
      # global_ac_roles may save a set of ACR objects in the session. If
      # session state is changed, all ACRs will be rerequested one by one.
      # To avoid such behavior link to ACRs objects should be removed manually.
      if hasattr(flask.g, "global_ac_roles"):
        del flask.g.global_ac_roles
      send_event_job(event)

  @staticmethod
  def _make_error_from_exception(exc):
    """Return a 400-code with the exception message."""
    message = translate_message(exc)
    logger.warning(message)
    return (400, message)

  @utils.validate_mimetype("application/json")  # noqa
  def collection_post(self):
    """Posts into collection."""
    with benchmark("collection post"):
      if 'X-GGRC-BackgroundTask' in request.headers:
        if 'X-Appengine-Taskname' not in request.headers:
          task = create_task(
              name=request.method,
              url=request.full_path,
              queued_callback=lambda _: None,
              parameters=request.data,
          )
          db.session.commit()
          if getattr(settings, 'APP_ENGINE', False):
            return self.json_success_response(
                self.object_for_json(task, 'background_task'),
                self.modified_at(task))
          body = self.request.json
        else:
          task_name = request.headers.get("X-Task-Name")
          task = BackgroundTask.query.filter_by(name=task_name).first()
          if not task:
            return current_app.make_response((
                'BackgroundTask not found. Retry later.',
                503,
                [('Content-Type', 'text/html')]
            ))
          body = json.loads(task.parameters)
        task.start()
        no_result = True
      else:
        body = self.request.json
        no_result = False
      wrap = isinstance(body, dict)
      if wrap:
        body = [body]

      # auto generation of user with Creator role if external flag is set
      if body and 'person' in body[0]:

        if not body[0]["person"].get("name") and \
           body[0]["person"].get("email"):
          body[0]["person"]["name"] = body[0]["person"]["email"].split("@")[0]

        ext_flags_passed = {p.get("person", {}).get("external", False)
                            for p in body}
        if ext_flags_passed == {True, False}:
          raise ValueError("Both external and non-external People POSTed.")

        if ext_flags_passed == {True}:
          from ggrc.utils import user_generator
          created_people = []
          created_people_response = []
          any_created = False

          for obj in body:
            person_json = obj.get("person")
            person = user_generator.find_or_create_external_user(
                person_json["email"],
                person_json["name"],
            )
            if person:
              any_created = True
            created_people.append(person)

          if any_created:
            with benchmark("person collection commit"):
              log_event(db.session)
              db.session.commit()

          for person in created_people:
            if person:
              response_part = (201, self.object_for_json(person))
            else:
              response_part = (400, {"Failed": True})
            created_people_response.append(response_part)

          if any_created:
            return self.json_success_response(created_people_response)
          return current_app.make_response(
              (self.as_json(created_people_response),
               400,
               [("Content-type", "text/plain")]),
          )

      res = []
      headers = {"Content-Type": "application/json"}
      with benchmark("collection post > body loop: {}".format(len(body))):
        with benchmark("Set referenced_stubs"):
          flask.g.referenced_object_stubs = self._gather_referenced_objects(
              body
          )
        with benchmark("Build stub query cache"):
          self._build_request_stub_cache(body)
        try:
          self.collection_post_loop(body, res, no_result)
        except (IntegrityError, ValidationError, ValueError) as error:
          res.append(self._make_error_from_exception(error))
          db.session.rollback()
        except ServiceUnavailable as error:
          res.append((503, error.description or ""))
          db.session.rollback()
        except gdrive.GdriveUnauthorized as error:
          headers["X-Expected-Error"] = True
          res.append((401, error.description or ""))
          db.session.rollback()
        except HTTPException as error:
          res.append((
              error.code or 500,
              error.description or "",
          ))
          db.session.rollback()
        except Exception as error:
          res.append((
              getattr(error, "code", 500),
              "{}: {}".format(type(error), error.message)
          ))
          logger.warning("Collection POST commit failed", exc_info=True)
          db.session.rollback()
        if hasattr(flask.g, "referenced_objects"):
          delattr(flask.g, "referenced_objects")
      with benchmark("collection post > calculate response statuses"):
        errors = []
        if wrap:
          status, res = res[0]
          if isinstance(res, dict) and len(res) == 1:
            value = res.values()[0]
            if "id" in value:
              headers['Location'] = self.url_for(id=value["id"])
        else:
          for res_status, body in res:
            if not 200 <= res_status < 300:
              errors.append((res_status, body))
          if errors:
            status = errors[0][0]
            headers[
                "X-Flash-Error"] = ' || '.join((error for _, error in errors))
          else:
            status = 200
      with benchmark("collection post > make response"):
        result = current_app.make_response(
            (self.as_json(res), status, headers))

      if 'X-GGRC-BackgroundTask' in request.headers:
        with benchmark("collection post > finish BackgroundTask"):
          if 200 <= status < 300:
            task.finish("Success", result)
          else:
            task.finish("Failure", result)
            result.status_code = 200
      return result

  @classmethod
  def add_to(cls, app, url, model_class=None, decorators=()):
    """Adds url for model."""
    if model_class:
      service_class = type(model_class.__name__, (cls,), {
          '_model': model_class,
      })
      import ggrc.services
      setattr(ggrc.services, model_class.__name__, service_class)
    else:
      service_class = cls
    view_func = service_class.as_view(service_class.endpoint_name())
    view_func = cls.decorate_view_func(view_func, decorators)
    app.add_url_rule(
        url,
        defaults={cls.pk: None},
        view_func=view_func,
        methods=['GET', 'POST', 'PATCH'])
    app.add_url_rule(
        '{url}/<{type}:{pk}>'.format(url=url, type=cls.pk_type, pk=cls.pk),
        view_func=view_func,
        methods=['GET', 'PUT', 'DELETE'])

  # Response helpers
  @classmethod
  def as_json(cls, obj, **kwargs):
    return as_json(obj, **kwargs)

  @staticmethod
  def get_properties_to_include(inclusions):
    """Gets properties to include."""
    # FIXME This needs to be improved to deal with branching paths... if that's
    # desirable or needed.
    if inclusions is not None:
      if not inclusions:
        raise BadRequest(
            'The __include query parameter requires at least one field to be '
            'included.')
      paths = inclusions.split(',')
      inclusions = []
      for p in paths:
        path = p.split('.')
        if len(path) == 1:
          inclusions.append(tuple(path))
        else:
          inclusions.append((path[0], tuple(path[1:])))
    else:
      inclusions = ()
    return inclusions

  @staticmethod
  def get_events_resources(model, ids):
    """Get events resources representation from the db.

    Returned events look like the following:
    {u'events': [{u'created_at': u'2019-01-22T13:18:26',
                  u'id': 955,
                  u'modified_by': {u'id': 2,
                                   u'type': u'Person'},
                  u'resource_type': u'Control',
                  u'revisions': [{u'description': u'New Control created'}],
                  u'revisions_count': 1,
                  u'type': u'Event'},
                  ...],
    """
    resources = {}
    events = db.session.query(
        ggrc.models.Event,
        func.count(
            ggrc.models.Revision.id
        ).label("revisions_count")
    ).join(
        ggrc.models.Revision,
        ggrc.models.Event.id ==
        ggrc.models.Revision.event_id
    ).filter(
        model.id.in_(ids.keys())
    ).group_by(
        ggrc.models.Event.id
    ).all()
    for event, revisions_count in events:
      event_resource = {
          "id": event.id,
          "resource_type": event.resource_type,
          "created_at": event.created_at,
          "modified_by": event.modified_by,
          "revisions_count": revisions_count,
          "type": "Event",
          "revisions_stub": [],
      }
      revisions = db.session.query(
          ggrc.models.Revision
      ).filter(
          ggrc.models.Revision.event_id ==
          event.id
      ).options(load_only(
          "_content",
          "action",
          "resource_type",
          "event_id")
      ).limit(MAX_AMOUNT_OF_REVISIONS)
      for revision in revisions:
        event_resource['revisions_stub'].append(
            {'description': revision.description,
             'resource_type': revision.resource_type}
        )
      resources[ids[event.id]] = event_resource
    return resources

  def build_page_object_for_json(self, paging):
    """Builds page object for json."""
    def page_url(params):
      """Gets page url."""
      return base_url + '?' + urlencode(utils.encoded_dict(params))

    def page_args(next_num, per_page):
      """Gets page args."""
      # coerce the values to be plain strings, rather than unicode
      ret = dict([(k, unicode(v)) for k, v in request.args.items()])
      ret['__page'] = next_num
      if '__page_size' in ret:
        ret['__page_size'] = per_page
      return ret
    paging_obj = {}
    base_url = self.url_for()
    if paging.has_next:
      paging_obj['next'] = page_url(
          page_args(paging.next_num, paging.per_page))
    if paging.has_prev:
      paging_obj['prev'] = page_url(
          page_args(paging.prev_num, paging.per_page))
    paging_obj['first'] = page_url(page_args(1, paging.per_page))
    paging_obj['last'] = page_url(page_args(paging.pages, paging.per_page))
    paging_obj['count'] = paging.pages
    paging_obj['total'] = paging.total
    return paging_obj

  def get_resources_from_database(self, matches):
    """Gets resources from database."""
    # FIXME: This is cheating -- `matches` should be allowed to be any model
    model = self.model
    ids = {m[0]: m for m in matches}
    if model.__name__ == "Event":
      with benchmark("Query database for events"):
        resources = self.get_events_resources(model, ids)
    else:
      with benchmark("Query database for matches"):
        query = model.eager_query(load_related=False)
        # We force the query here so that we can benchmark it
        objs = query.filter(model.id.in_(ids.keys())).all()
        with benchmark("Publish objects"):
          resources = {}
          includes = self.get_properties_to_include(
              request.args.get('__include')
          )
          for obj in objs:
            resources[ids[obj.id]] = ggrc.builder.json.publish(obj, includes)
    with benchmark("Publish representation"):
      ggrc.builder.json.publish_representation(resources)
    return resources

  def build_collection_representation(self, objs, extras=None):
    """Builds collection representation."""
    table_plural = self.model._inflector.table_plural
    collection_name = '{0}_collection'.format(table_plural)
    resource = {
        collection_name: {
            'selfLink': self.url_for_preserving_querystring(),
            table_plural: objs,
        }
    }
    if extras:
      resource[collection_name].update(extras)
    return resource

  def object_for_json(self, obj, model_name=None, properties_to_include=None):
    """Serialize obj in JSON format."""
    model_name = model_name or self.model._inflector.table_singular
    json_obj = ggrc.builder.json.publish(
        obj, properties_to_include or [], inclusion_filter)
    ggrc.builder.json.publish_representation(json_obj)
    return {model_name: json_obj}

  def build_resource_representation(self, obj, extras=None):
    """Builds resource representation."""
    table_singular = self.model._inflector.table_singular
    resource = {
        table_singular: obj,
    }
    if extras:
      resource.update(extras)
    return resource

  @staticmethod
  def http_timestamp(timestamp):
    return format_date_time(time.mktime(timestamp.utctimetuple()))

  def json_success_response(self, response_object, last_modified=None,
                            status=200, id=None, cache_op=None,
                            obj_etag=None):
    """Prepare success JSON response and set required headers."""
    # pylint: disable=redefined-builtin
    headers = [('Content-Type', 'application/json')]
    if last_modified:
      headers.append(('Last-Modified', self.http_timestamp(last_modified)))
    if obj_etag:
      headers.append(('Etag', obj_etag))
    if id is not None:
      headers.append(('Location', self.url_for(id=id)))
    if cache_op:
      headers.append(('X-GGRC-Cache', cache_op))
    return current_app.make_response(
        (self.as_json(response_object), status, headers))

  def process_actions(self, obj):
    if hasattr(obj, 'process_actions'):
      # process actionsS
      added, deleted = obj.process_actions()
      # send signals for added/deleted objects
      for _class, _objects in added.items():
        if not _objects:
          continue
        signals.Restful.collection_posted.send(
            _class, objects=_objects, service=self,
            sources=[{} for _ in xrange(len(_objects))])
        for _obj in _objects:
          signals.Restful.model_posted.send(
              _class, obj=_obj, service=self)
      for _obj in deleted:
        signals.Restful.model_deleted.send(
            _obj.__class__, obj=_obj, service=self)
      if added or deleted:
        obj.invalidate_evidence_found()


class ReadOnlyResource(Resource):

  def dispatch_request(self, *args, **kwargs):
    method = request.method

    if method == 'GET':
      return super(ReadOnlyResource, self).dispatch_request(*args, **kwargs)
    else:
      raise NotImplementedError()


class ExtendedResource(Resource):
  """Extended resource with additional command support."""

  @classmethod
  def add_to(cls, app, url, model_class=None, decorators=()):
    """Register view methods.

    This method only extends original resource add_to, with a command option
    for get requests.
    """
    if model_class:
      service_class = type(model_class.__name__, (cls,), {
          '_model': model_class,
      })
      import ggrc.services
      setattr(ggrc.services, model_class.__name__, service_class)
    else:
      service_class = cls
    view_func = service_class.as_view(service_class.endpoint_name())
    view_func = cls.decorate_view_func(view_func, decorators)
    app.add_url_rule(
        url,
        defaults={cls.pk: None},
        view_func=view_func,
        methods=['GET', 'POST'])
    app.add_url_rule(
        '{url}/<{type}:{pk}>'.format(url=url, type=cls.pk_type, pk=cls.pk),
        view_func=view_func,
        methods=['GET', 'PUT', 'DELETE'])
    app.add_url_rule(
        '{url}/<{type}:{pk}>/<command>'.format(
            url=url,
            type=cls.pk_type,
            pk=cls.pk
        ),
        view_func=view_func,
        methods=['GET']
    )

  def snapshot_counts_query(self, id):
    """Get data for audit mapped objects counts grouped by child_type."""
    # id name is used as a kw argument and can't be changed here
    # pylint: disable=invalid-name,redefined-builtin

    with benchmark("Check audit permissions"):
      obj = self.model.query.get(id)
      if not obj:
        raise NotFound()
      if not permissions.is_allowed_read_for(obj):
        raise Forbidden()

    model_name = self.model.__name__
    with benchmark("Get spanshot counts for audit grouped by child type"):
      snapshots_dest = db.session.query(
          ggrc.models.Snapshot.child_type.label("child_type"),
          ggrc.models.Snapshot.id.label("id")
      ).join(
          ggrc.models.Relationship,
          ggrc.models.Relationship.destination_id == ggrc.models.Snapshot.id
      ).filter(
          ggrc.models.Relationship.destination_type == "Snapshot",
          ggrc.models.Relationship.source_type == model_name,
          ggrc.models.Relationship.source_id == id
      )

      snapshots_source = db.session.query(
          ggrc.models.Snapshot.child_type.label("child_type"),
          ggrc.models.Snapshot.id.label("id")
      ).join(
          ggrc.models.Relationship,
          ggrc.models.Relationship.source_id == ggrc.models.Snapshot.id
      ).filter(
          ggrc.models.Relationship.source_type == "Snapshot",
          ggrc.models.Relationship.destination_type == model_name,
          ggrc.models.Relationship.destination_id == id
      )

      snapshot_counts = snapshots_dest.union(
          snapshots_source
      ).with_entities(
          ggrc.models.Snapshot.child_type,
          sa.func.count("*")
      ).group_by(
          ggrc.models.Snapshot.child_type
      )

      with benchmark("Make response"):
        result = dict(snapshot_counts)

    return self.json_success_response(result)


def filter_resource(resource, depth=0, user_permissions=None):  # noqa
  """
  Returns:
     The subset of resources which are readable based on user_permissions
  """

  if user_permissions is None:
    user_permissions = permissions.permissions_for(
        get_current_user(use_external_user=False)
    )

  if isinstance(resource, (list, tuple)):
    filtered = []
    for sub_resource in resource:
      filtered_sub_resource = filter_resource(
          sub_resource, depth=depth + 1, user_permissions=user_permissions)
      if filtered_sub_resource is not None:
        filtered.append(filtered_sub_resource)
    return filtered
  elif isinstance(resource, dict) and 'type' in resource:

    # In order to avoid loading full instances and using is_allowed_read_for,
    # we are making a special test for the Creator here. Creator can only
    # see relationship objects where he has read access on both source and
    # destination. This is defined in Creator.py:220 file, but is_allowed_read
    # can not check conditions without the full instance
    if resource['type'] == "Relationship" and _is_creator():
      # Make a check for relationship objects that are a special case
      can_read = True
      for name in ('source', 'destination'):
        if name in resource:
          inst = resource[name]
        else:
          obj_tuple = (resource[name + "_type"], resource[name + "_id"])
          obj_inst = utils.referenced_objects.get(*obj_tuple)
          if obj_inst:
            inst = utils.create_stub(obj_inst, None)
          else:
            inst = None
        if not inst:
          # If object was deleted but relationship still exists
          continue
        contexts = permissions.read_contexts_for(inst['type'])
        if contexts is None:
          # read_contexts_for returns None if the user has access to all the
          # objects of this type. If the user doesn't have access to any object
          # an empty list ([]) will be returned
          continue
        resources = permissions.read_resources_for(inst['type']) or []
        if inst['id'] in resources:
          continue
        can_read = False
      if not can_read:
        return None
    elif resource['type'] == "Revision" and _is_creator():
      if not _is_allowed_revision_read(resource, user_permissions):
        return None
    else:
      if not user_permissions.is_allowed_read(resource['type'],
                                              resource['id'], None):
        return None
    # Then, filter any typed keys
    for key, value in resource.items():
      if key in ('context', 'content'):
        # Explicitly allow `context` and `content` objects to pass through. If
        # at this point `key` contains `"content"` value, it means that user
        # has access to a revision and there is no need for further checking.
        pass
      else:
        # Apply filtering to sub-resources
        if isinstance(value, dict) and 'type' in value:
          resource[key] = filter_resource(
              value, depth=depth + 1, user_permissions=user_permissions)

    return resource
  else:
    assert False, "Non-object passed to filter_resource"


def _is_allowed_revision_read(revision, user_permissions):
  # type: (Dict[str, Any], ggrc_basic_permissions.UserPermissions) -> bool
  """Check if it is allowed to read a revision having specific permissions.

  Check if it is allowed to read `revision` revision having `user_permissions`
  permissions. Read is NOT allowed for revision if:
    - Revision's resource type does not exist anymore;
    - Instance revision was created for does not exist;
    - Read is not allowed on revision's instance OR on any snapshot a revision
      is attached to.

  Args:
    revision (Dict[str, Any]): Dictionary representing a revision.
    user_permissions (ggrc_basic_permissions.UserPermissions): User permission
      object to use when checking for read permission. If `None` is passed,
      value will be calculated for current user.

  Returns:
    `True` if it is allowed to read the revision and `False` otherwise.
  """
  if not hasattr(ggrc.models.all_models, revision['resource_type']):
    # If revision's resource type does not exist anymore, it is not allowed to
    # read such a revision.
    return False

  instance = utils.referenced_objects.get(
      revision['resource_type'],
      revision['resource_id'],
  )

  if instance is None:
    # If an instance the revision was created for does not exist anymore, it is
    # not allowed to read such a revision.
    return False

  if user_permissions is None:
    user_permissions = permissions.permissions_for(
        get_current_user(use_external_user=False)
    )

  def allowed_read_resource(instance):
    """Check if it is allowed to read `instance` for current user."""
    return user_permissions.is_allowed_read_for(instance)

  def allowed_read_snapshot(revision):
    """Check if it is allowed to read any snapshot revision is attached to."""
    snapshot_model = ggrc.models.snapshot.Snapshot
    return any(
        s and user_permissions.is_allowed_read_for(s)
        for s in snapshot_model.query.filter_by(revision_id=revision['id'])
    )

  return allowed_read_resource(instance) or allowed_read_snapshot(revision)


def _is_creator():
  """Check that current user is Creator."""
  current_user = get_current_user(use_external_user=False)
  return hasattr(current_user, 'system_wide_role') \
      and current_user.system_wide_role == "Creator"


def get_info(obj):
  """Get object info string."""
  return '%s %s' % (obj.__class__.__name__, str(obj.id))


def etag(last_modified, info=''):
  """Generate the etag given a datetime for the last time the resource was
  modified. This isn't as good as an etag generated off of a hash of the
  representation, but, it doesn't require the representation in order to be
  calculated. An alternative would be to keep an etag on the stored
  representation, but this will do for now.

  .. note::

      Using the datetime implies the need for some care - the resolution of
      the time object needs to be sufficient such that you don't end up with
      the same etag due to two updates performed in rapid succession.
  """
  return '"{0}"'.format(hashlib.sha1(str(last_modified) + info).hexdigest())


def send_event_job(event):
  """Create background job for handling new revisions."""
  from ggrc import views
  views.start_compute_attributes(event_id=event.id)
