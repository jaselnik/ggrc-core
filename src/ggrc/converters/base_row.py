# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module is used for handling a single line from a csv file.
"""

import collections
from logging import getLogger

from sqlalchemy import exc
from sqlalchemy.orm.exc import UnmappedInstanceError

import ggrc.services
from ggrc import db
from ggrc.converters import errors
from ggrc.converters import get_importables
from ggrc.converters import pre_commit_checks
from ggrc.converters.handlers import acl
from ggrc.converters.handlers import handlers
from ggrc.login import get_current_user_id
from ggrc.models import all_models
from ggrc.models import cache
from ggrc.models.exceptions import StatusValidationError
from ggrc.models.mixins import issue_tracker
from ggrc.models.mixins import synchronizable
from ggrc.models.mixins.with_readonly_access import WithReadOnlyAccess
from ggrc.rbac import permissions
from ggrc.services import signals
from ggrc.snapshotter import create_snapshots
from ggrc.utils import dump_attrs, benchmarks

from ggrc.models.reflection import AttributeInfo
from ggrc.services.common import get_modified_objects
from ggrc.services.common import update_snapshot_index
from ggrc.cache import utils as cache_utils
from ggrc.utils.log_event import log_event

logger = getLogger(__name__)


_ALLOWED_ATTRS_FOR_READONLY_ACCESS = (
    'slug',
    'email',
    'comments',
    'readonly',
)


class RowConverter(object):
  """Base class for handling row data."""
  # pylint: disable=too-few-public-methods,too-many-instance-attributes
  def __init__(self, block_converter, object_class, headers, options):
    self.block_converter = block_converter
    self.object_class = object_class
    self.headers = headers
    self.idx = options.get("idx")
    self.obj = options.get("obj")
    self.attrs = collections.OrderedDict()
    self.objects = collections.OrderedDict()
    self.old_values = {}
    self.issue_tracker = {}
    self.comments = []


class ImportRowConverter(RowConverter):
  """Class for handling row data for import"""
  # pylint: disable=too-many-public-methods,too-many-instance-attributes
  def __init__(self, block_converter, object_class, headers, line, **options):
    super(ImportRowConverter, self).__init__(block_converter, object_class,
                                             headers, options)
    self.is_new = True
    self.is_delete = False
    self.is_deprecated = False
    self.ignore = False
    self.row = options.get("row", [])
    self.id_key = ""
    self.line = line
    self.initial_state = None
    self.is_new_object_set = False
    self._is_obj_readonly = False
    self.status_changing = False

  def _is_allowed_for_readonly_obj(self, attr_name, handler):
    """Return whether attr is allowed for readonly objects"""
    if not self._is_obj_readonly:
      return True

    # Allow processing of all columns if object is read-only and user wants
    # to unset readonly flag
    # Note: if user doesn't have permission to change flag readonly,
    # parsed value of column handler is set to None.
    # In this case this function works as if readonly=True
    readonly_handler = self.attrs.get('readonly')
    if readonly_handler and readonly_handler.value is False:
      return True

    if attr_name in _ALLOWED_ATTRS_FOR_READONLY_ACCESS:
      return True

    if isinstance(handler, handlers.MappingColumnHandler):
      return True

    return False

  def handle_raw_cell(self, attr_name, idx, header_dict):
    """Process raw value from self.row[idx] for attr_name.

    This function finds and instantiates the correct handler class and handles
    special logic for deprecated status and primary key attributes, as well as
    value uniqueness.
    """
    handler_cls = header_dict["handler"]
    item = handler_cls(self, attr_name, raw_value=self.row[idx], **header_dict)

    if self._is_allowed_for_readonly_obj(attr_name, item):
      item.set_value()
    else:
      item.ignore = True

    if header_dict.get("type") == AttributeInfo.Type.PROPERTY:
      self.attrs[attr_name] = item
    else:
      self.objects[attr_name] = item
    if attr_name == "status" and hasattr(self.obj, "DEPRECATED"):
      self.is_deprecated = (
          self.obj.DEPRECATED == item.value != self.obj.status
      )
    if attr_name in ("slug", "email"):
      self.id_key = attr_name
      self.obj = self.get_or_generate_object(attr_name)
      item.set_obj_attr()
    if header_dict["unique"]:
      value = self.get_value(attr_name)
      if value:
        unique_values = self.block_converter.unique_values
        if unique_values[attr_name].get(value) is not None:
          self.add_error(
              errors.DUPLICATE_VALUE_IN_CSV.format(
                  line=self.line,
                  processed_line=unique_values[attr_name][value],
                  column_name=header_dict["display_name"],
                  value=value,
              ),
          )
          item.is_duplicate = True
        else:
          self.block_converter.unique_values[attr_name][value] = self.line
    item.check_unique_consistency()

  def _handle_raw_data(self):
    """Pass raw values into column handlers for all cell in the row."""

    row_headers = {attr_name: (idx, header_dict)
                   for idx, (attr_name, header_dict)
                   in enumerate(self.headers.iteritems())}
    if self.object_class == all_models.Comment:
      self.obj = all_models.Comment(
          modified_by_id=get_current_user_id()
      )

    for attr_name in self.block_converter.handle_fields:
      if attr_name not in row_headers or self.is_delete:
        continue
      idx, header_dict = row_headers[attr_name]
      self.handle_raw_cell(attr_name, idx, header_dict)

  def _update_new_obj_cache(self):
    """Update local cache with newly created objects."""
    if not self.is_new or not getattr(self.obj, self.id_key):
      return
    self.is_new_object_set = True
    self.block_converter.converter.new_objects[
        self.obj.__class__
    ][
        getattr(self.obj, self.id_key)
    ] = self.obj

  def _update_new_comment_cache(self):
    """Update local cache with newly created comment object."""
    if not self.is_new:
      return
    self.is_new_object_set = True
    self.block_converter.converter.new_objects[
        self.obj.__class__
    ] = self.obj

  def add_error_slug(self, key=None):
    """Add failed to complete assessment slug to list for bulk operations"""
    if not key:
      key = self.get_value(self.id_key)

    if key and self.block_converter.converter.bulk_import:
      self.block_converter.converter.failed_slugs.append(key)

  def add_error(self, template, **kwargs):
    """Add error for current row.

    Add an error entry for the current row and mark it as ignored. If the error
    occurred on a new object, it gets removed from the new object cache dict.

    Args:
      template: String template.
      **kwargs: Arguments needed to format the string template.
    """
    message = template.format(line=self.line, **kwargs)
    self.block_converter.row_errors.append(message)
    key = self.get_value(self.id_key)

    self.add_error_slug(key)

    if self.is_new_object_set:
      new_objects = self.block_converter.converter.new_objects[
          self.object_class
      ]
      key = self.get_value(self.id_key)
      if key in new_objects:
        del new_objects[key]
      self.is_new_object_set = False
    self.ignore = True

  def add_warning(self, template, **kwargs):
    message = template.format(line=self.line, **kwargs)
    self.block_converter.row_warnings.append(message)

  def _check_mandatory_fields(self):
    """Check if the new object contains all mandatory columns."""
    if not self.is_new or self.is_delete or self.ignore:
      return
    headers = self.block_converter.object_headers
    mandatory = [key for key, header in headers.items() if header["mandatory"]]
    missing_keys = set(mandatory).difference(set(self.headers.keys()))
    # TODO: fix mandatory checks for individual rows based on object level
    # custom attributes.
    missing = [headers[key]["display_name"] for key in missing_keys if
               headers[key]["type"] != AttributeInfo.Type.OBJECT_CUSTOM]
    if self.block_converter.class_name.lower() == "lca comment":
      return
    if missing:
      self.add_error(errors.MISSING_COLUMN,
                     s="s" if len(missing) > 1 else "",
                     column_names=", ".join(missing))

  def find_by_key(self, key, value):
    return self.object_class.query.filter_by(**{key: value}).first()

  def get_value(self, key):
    """Get the value for the row object key."""
    item = self.attrs.get(key) or self.objects.get(key)
    if item:
      return item.value
    return None

  def set_ignore(self, ignore=True):
    self.ignore = ignore

  def get_or_generate_object(self, attr_name):
    """Fetch an existing object if possible or create and return a new one.

    Note: Person object is the only exception here since it does not have a
    slug field.
    """
    value = self.get_value(attr_name)
    new_objects = self.block_converter.converter.new_objects[self.object_class]
    if value in new_objects and new_objects[value]:
      return new_objects[value]
    obj = self.get_object_by_key(attr_name)
    if value:
      new_objects[value] = obj
    obj.modified_by_id = get_current_user_id()
    return obj

  def _has_readonly_access(self, obj):
    """Return True if new obj has type WithReadOnlyAccess and readonly=True"""

    if self.is_new or not isinstance(obj, WithReadOnlyAccess):
      return False

    return obj.readonly

  def get_object_by_key(self, key="slug"):
    """ Get object if the slug is in the system or return a new object """
    value = self.get_value(key)
    self.is_new = False

    if value:
      obj = self.find_by_key(key, value)

    if not value or not obj:
      # We assume that 'get_importables()' returned value contains
      # names of the objects that cannot be created via import but
      # can be updated.
      if self.block_converter.class_name.lower() not in get_importables() and \
              not self._check_object_is_external():
        self.add_error(errors.CREATE_INSTANCE_ERROR)
      obj = self.object_class()
      self.is_new = True
    elif not permissions.is_allowed_update_for(obj):
      self.ignore = True
      self.add_error(errors.PERMISSION_ERROR)
    elif self._has_readonly_access(obj):
      self._is_obj_readonly = True

    self.initial_state = dump_attrs(obj)
    return obj

  def setup_secondary_objects(self):
    """Import non-acl secondary objects.

    This function creates and stores all secondary objects except acl such as
    relationships and any linked object that need the original object to be
    saved before they can be processed. This is usually due to needing the id
    of the original object that is created with a csv import.
    """
    if not self.obj or self.ignore or self.is_delete:
      return
    for mapping in self.objects.values():
      if not mapping.ignore and not isinstance(
          mapping,
          acl.AccessControlRoleColumnHandler
      ):
        mapping.set_obj_attr()
    self._setup_secondary_objects()

  def setup_acl_secondary_objects(self):
    """Import acl secondary objects.

    This function creates and stores only acl secondary objects such as
    relationships and any linked object that need the original object to
    be saved before they can be processed. This is usually due to needing the
    id of the original object that is created with a csv import.
    """
    if not self.obj or self.ignore or self.is_delete:
      return
    for mapping in self.objects.values():
      if not mapping.ignore and isinstance(
          mapping,
          acl.AccessControlRoleColumnHandler
      ):
        mapping.set_obj_attr()
    self._setup_secondary_objects(acl_only=True)

  def _setup_secondary_objects(self, acl_only=False):
    """Import all secondary objects.

    This function creates and stores all secondary object such as relationships
    and any linked object that need the original object to be saved before they
    can be processed. This is usually due to needing the id of the original
    object that is created with a csv import.
    """
    if hasattr(self.obj, "validate_role_limit"):
      results = self.obj.validate_role_limit(_import=True)
      for role, msg in results:
        self.add_error(errors.VALIDATION_ERROR,
                       column_name=role,
                       message=msg)
    # Need to proceed only after acl objects were added to the session
    if acl_only:
      self._check_secondary_objects()
    if self.dry_run:
      return
    try:
      if acl_only:
        self.insert_acl_secondary_objects()
      else:
        self.insert_secondary_objects()
    except exc.SQLAlchemyError as err:
      db.session.rollback()
      logger.exception("Import failed with: %s", err.message)
      self.add_error(errors.UNKNOWN_ERROR)

  def _check_ignored_columns(self):
    """Add warning if some columns were ignored"""
    ignored_names = list(handler.display_name
                         for handler in self.attrs.values()
                         if handler.ignore)
    ignored_names.extend(handler.display_name
                         for handler in self.objects.values()
                         if handler.ignore)

    if not ignored_names:
      return

    columns_str = ', '.join("'{}'".format(name)
                            for name in sorted(ignored_names))

    self.add_warning(errors.READONLY_ACCESS_WARNING, columns=columns_str)

  @property
  def dry_run(self):
    return self.block_converter.converter.dry_run

  def _get_assessment_template(self):
    """Get asmt template object which is referenced by current row if exists"""
    tmpl_handler = self.objects.get("assessment_template")
    if not tmpl_handler:
      return None

    items = tmpl_handler.parse_item()
    if not items:
      return None

    return items[0]

  def _update_issue_tracker_to_import(self):
    """Make importable data available in import background task"""

    if self.dry_run:
      return

    if not isinstance(self.obj, issue_tracker.IssueTracked):
      return

    self.obj.is_import = True

    if self.is_new and isinstance(self.obj, all_models.Assessment):
      # Assessment template is available only for new assessment objects
      asmt_tmpl = self._get_assessment_template()
      if asmt_tmpl:
        # Format have to be the same as issue_tracker dict in POST request
        self.obj.issue_tracker_to_import['template'] = {
            'type': asmt_tmpl.__class__.__name__,
            'id': asmt_tmpl.id
        }

    self.obj.issue_tracker_to_import['issue_tracker'] = self.issue_tracker

  def process_row(self):
    """Parse, set, validate and commit data specified in self.row."""
    self._check_object_class()
    self._handle_raw_data()
    self._check_ignored_columns()
    self._check_mandatory_fields()
    if self.ignore:
      db.session.rollback()
      return
    if self.object_class == all_models.Comment:
      self._update_new_comment_cache()
    else:
      self._update_new_obj_cache()
    self._setup_object()
    self._check_object()
    try:
      if self.ignore and self.obj in db.session:
        db.session.expunge(self.obj)
    except UnmappedInstanceError:
      return
    if self.block_converter.ignore:
      return

    self._update_issue_tracker_to_import()

    self.flush_object()
    self.setup_secondary_objects()
    self.setup_acl_secondary_objects()
    self.commit_object()

  def _check_object_class(self):
    """Validate if object class is external."""
    if self._check_object_is_external():
      self.add_error(errors.EXTERNAL_MODEL_IMPORT_RESTRICTION,
                     external_model_name=self.object_class.__name__)

  def _check_object_is_external(self):
    """Check if object class is external."""
    return issubclass(self.object_class, synchronizable.Synchronizable)

  def _check_object(self):
    """Check object if it has any pre commit checks.

    The check functions can mutate the row_converter object and mark it
    to be ignored if there are any errors detected.

    Args:
        row_converter: Row converter for the row we want to check.
    """
    checker = pre_commit_checks.CHECKS.get(type(self.obj).__name__)
    if checker and callable(checker):
      checker(self)

  def _check_secondary_objects(self):
    """Check object if it has any pre commit checks
    after setup of secondary objects.

    The check functions can mutate the row_converter object and mark it
    to be ignored if there are any errors detected.

    Args:
        row_converter: Row converter for the row we want to check.
    """
    checker = pre_commit_checks.SECONDARY_CHECKS.get(type(self.obj).__name__)
    if checker and callable(checker):
      checker(self)

  def flush_object(self):
    """Flush dirty data related to the current row."""
    if self.dry_run or self.ignore or not self.is_new:
      return
    self.send_pre_commit_signals()
    try:
      if self.object_class == all_models.Audit and self.is_new:
        # This hack is needed only for snapshot creation
        # for audit during import, this is really bad and
        # need to be refactored
        import_event = log_event(db.session, None)
      self.insert_object()
      db.session.flush()
      if self.object_class == all_models.Audit and self.is_new:
        # This hack is needed only for snapshot creation
        # for audit during import, this is really bad and
        # need to be refactored
        create_snapshots(self.obj, import_event)
    except exc.SQLAlchemyError as err:
      db.session.rollback()
      logger.exception("Import failed with: %s", err.message)
      self.add_error(errors.UNKNOWN_ERROR)
      return
    if not self.ignore:
      self.block_converter.send_collection_post_signals([self.obj])

  def commit_object(self):
    """Commit the row.

    This method also calls pre-and post-commit signals and handles failures.
    """
    if self.dry_run or self.ignore:
      return
    try:
      if not self.is_new:
        cache.Cache.add_to_cache(self.obj)
        self.send_pre_commit_signals()
      modified_objects = get_modified_objects(db.session)
      import_event = log_event(db.session, None)
      cache_utils.update_memcache_before_commit(
          self.block_converter,
          modified_objects,
          self.block_converter.CACHE_EXPIRY_IMPORT,
      )
      try:
        self.send_before_commit_signals(import_event)
      except StatusValidationError as exp:
        status_alias = self.headers.get("status", {}).get("display_name")
        self.add_error(errors.VALIDATION_ERROR,
                       column_name=status_alias,
                       message=exp.message)
      db.session.commit_hooks_enable_flag.disable()
      db.session.commit()
      if not self.ignore:
        self.block_converter.store_revision_ids(import_event)
      cache_utils.update_memcache_after_commit(self.block_converter)
      update_snapshot_index(modified_objects)
    except exc.SQLAlchemyError as err:
      db.session.rollback()
      logger.exception("Import failed with: %s", err.message)
      self.block_converter.add_errors(errors.UNKNOWN_ERROR,
                                      line=self.block_converter.offset)
    else:
      self.create_comment_notifications()
      self.send_comment_notifications()
      self.send_post_commit_signals(event=import_event)

  def _setup_object(self):
    """ Set the object values or relate object values

    Set all object attributes to the value specified in attrs. If the value
    is in some related object such as "UserRole" it should be added there and
    handled by the handler defined in attrs.
    """
    if self.ignore:
      return

    for item_handler in self.attrs.values():
      if not item_handler.view_only and not item_handler.ignore:
        item_handler.set_obj_attr()

  def send_comment_notifications(self):
    """Send comment people mentions notifications."""
    from ggrc.notifications import people_mentions

    if self.comments:
      people_mentions.handle_comment_mapped(obj=self.obj,
                                            comments=self.comments)

  def _get_comment_created_notif_type(self):
    """Get comment created notification type id"""
    return self.block_converter.converter.comment_created_notif_type

  def create_comment_notifications(self):
    """Create comment notifications."""
    import datetime

    if self.comments:
      for comment in self.comments:
        notification = all_models.Notification(
            object=comment,
            send_on=datetime.datetime.utcnow(),
            notification_type_id=self._get_comment_created_notif_type(),
        )
        db.session.add(notification)

  def send_post_commit_signals(self, event=None):
    """Send after commit signals for all objects

    This function sends proper signals for all objects depending if the object
    was created, updated or deleted.
    Note: signals are only sent for the row objects. Secondary objects such as
    Relationships do not get any signals triggered.
    ."""
    if self.ignore:
      return
    service_class = getattr(ggrc.services, self.object_class.__name__)
    service_class.model = self.object_class
    if self.is_delete:
      signals.Restful.model_deleted_after_commit.send(
          self.object_class, obj=self.obj, service=service_class, event=event)
    elif self.is_new:
      signals.Restful.model_posted_after_commit.send(
          self.object_class, obj=self.obj, src={}, service=service_class,
          event=event)
    else:
      signals.Restful.model_put_after_commit.send(
          self.object_class, obj=self.obj, src={}, service=service_class,
          event=event)

  def send_before_commit_signals(self, event=None):
    """Send before commit signals for all objects.

    Currently we have only one before commit signal type:
    model_put_before_commit. It should be sent for all changed objects via
    import.
    Note: signals are only sent for the row objects. Secondary objects such as
    Relationships do not get any signals triggered.
    """
    if self.ignore or self.is_new or self.is_delete:
      return
    service_class = getattr(ggrc.services, self.object_class.__name__)
    service_class.model = self.object_class
    signals.Restful.model_put_before_commit.send(
        self.object_class, obj=self.obj, src={}, service=service_class,
        event=event, initial_state=self.initial_state)

  def send_pre_commit_signals(self):
    """Send before commit signals for all objects.

    This function sends proper signals for all objects depending if the object
    was created, updated or deleted.
    Note: signals are only sent for the row objects. Secondary objects such as
    Relationships do not get any signals triggered.
    """
    if self.ignore:
      return
    service_class = getattr(ggrc.services, self.object_class.__name__)
    service_class.model = self.object_class
    if self.is_delete:
      signals.Restful.model_deleted.send(
          self.object_class, obj=self.obj, service=service_class)
    elif self.is_new:
      signals.Restful.model_posted.send(
          self.object_class, obj=self.obj, src={}, service=service_class)
    else:
      signals.Restful.model_put.send(
          self.object_class, obj=self.obj, src={}, service=service_class)

  def insert_object(self):
    """Add the row object to the current database session."""
    if self.ignore or self.is_delete:
      return

    if self.is_new:
      db.session.add(self.obj)
    for handler in self.attrs.values():
      if not handler.ignore:
        handler.insert_object()

  def insert_secondary_objects(self):
    """Add non-acl additional objects to the current database session.

    This is used for adding non-acl extra created objects such as
    Relationships, to the current session to be committed.
    """
    if not self.obj or self.ignore or self.is_delete:
      return

    for handler in self.objects.values():
      if not handler.ignore and not isinstance(
          handler,
          acl.AccessControlRoleColumnHandler
      ):
        handler.insert_object()

  def insert_acl_secondary_objects(self):
    """Add acl additional objects to the current database session.

    This is used for adding acl extra created objects such as Relationships, to
    the current session to be committed.
    """
    if not self.obj or self.ignore or self.is_delete:
      return

    for handler in self.objects.values():
      if not handler.ignore and isinstance(
          handler,
          acl.AccessControlRoleColumnHandler
      ):
        handler.insert_object()

    self._update_issue_tracker_object()

  def _update_issue_tracker_object(self):
    """Update IssueTrackerIssue for object update requests.

    The functionality to update IssueTrackerIssue for new objects
    is moved to import background task.
    """

    if self.is_new:
      return

    if issubclass(self.obj.__class__, issue_tracker.IssueTracked):
      if not self.issue_tracker:
        self.issue_tracker = self.obj.issue_tracker
      all_models.IssuetrackerIssue.create_or_update_from_dict(
          self.obj, self.issue_tracker
      )


class ExportRowConverter(RowConverter):
  """Class for handling row data for export"""
  def __init__(self, block_converter, object_class, headers, **options):
    super(ExportRowConverter, self).__init__(block_converter, object_class,
                                             headers, options)
    if issubclass(type(self.obj), issue_tracker.IssueTracked):
      self.issue_tracker = self.obj.issue_tracker

  def handle_obj_row_data(self):
    """Create handlers for cells in the current row."""
    for attr_name, header_dict in self.headers.items():
      handler = header_dict["handler"]
      item = handler(self, attr_name, **header_dict)
      if header_dict.get("type") == AttributeInfo.Type.PROPERTY:
        self.attrs[attr_name] = item
      else:
        self.objects[attr_name] = item

  def to_array(self, fields):
    """Get an array representation of the current row.

    Filter the values to match the fields array and return the string
    representation of the values.

    Args:
      fields (list of strings): A list of columns that will be included in the
        output array. This is basically a filter of all possible fields that
        this row contains.

    Returns:
      list of strings where each cell contains a string value of the
      corresponding field.
    """
    benchmark_manager = benchmarks.BenchmarkLongestManager(5)
    row = []
    for field in fields:
      with benchmark_manager.benchmark(u"Process '{}' field".format(field)):
        field_type = self.headers.get(field, {}).get("type")
        if field_type == AttributeInfo.Type.PROPERTY:
          field_handler = self.attrs.get(field)
        else:
          field_handler = self.objects.get(field)
        value = field_handler.get_value() if field_handler else ""
        row.append(value or "")
    benchmark_manager.print_benchmaks()
    return row
