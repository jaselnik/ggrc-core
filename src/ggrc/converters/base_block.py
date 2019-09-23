# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for handling a single import block.

Each import block should contain data for one Object type. The blocks are
separated in the csv file with empty lines.
"""

import collections
import logging

from flask import _app_ctx_stack
import sqlalchemy as sa

from ggrc import db
from ggrc import models
from ggrc import utils
from ggrc.models import exceptions
from ggrc.models import all_models
from ggrc.models import reflection
from ggrc.models import mixins
from ggrc.rbac import permissions
from ggrc.utils import benchmark
from ggrc.utils import structures
from ggrc.utils import list_chunks
from ggrc.converters import errors
from ggrc.converters import get_shared_unique_rules
from ggrc.converters import base_row
from ggrc.converters import import_helper
from ggrc.converters.block_mixins import people_cache
from ggrc.models.mixins import issue_tracker as issue_tracker_mixins
from ggrc.services import signals
from ggrc_workflows.models.cycle_task_group_object_task import \
    CycleTaskGroupObjectTask


logger = logging.getLogger(__name__)


class BlockConverter(object):
  # pylint: disable=too-many-public-methods
  # pylint: disable=too-many-instance-attributes
  """ Main block converter class for dealing with csv files and data

  Attributes:
    block_errors (list of str): list containing fatal import errors
    block_warnings (list of str): list containing blokc level import warnings
    row_errors (list of str): list containing row errors
    row_warnings (list of str): list containing row warnings
    object_ids (list of int): list containing all ids for the converted objects
    rows (list of list of str): 2D array containing csv data
    row_converters (list of RowConverter): list of row convertor objects with
      data from the coresponding row in rows attribute
    object_headers (dict): A dictionary containing object headers
    headers (dict): A dictionary containing csv headers with additional
      information. Keys are object attributes such as "title", "slug"...
      Example:
        {"slug": {
            "display_name": "Code",
            "mandatory": True,
            "default": "value or a callabe function that returns the value",
            "validator": validator_function,
            "handler": HandlerClass,
            "description": "description or function that returns description"
            "valid_values": "list of valid values"

  """

  CACHE_EXPIRY_IMPORT = 600

  def __init__(self, converter, object_class, class_name,
               operation, object_ids=None, raw_headers=None, offset=None,
               rows=None):
    # pylint: disable=too-many-instance-attributes,protected-access
    # pylint: disable=too-many-arguments
    # This class holds cache and object data for all rows and handlers below
    # it, so it is expected to hold a lot of instance attributes.
    # The protected access is a false warning for inflector access.
    self._mapping_cache = None
    self._ticket_tracker_cache = None
    self._owners_cache = None
    self._ca_definitions_cache = None
    self.converter = converter
    self.offset = offset
    self.object_class = object_class
    self.rows = rows
    self.operation = operation
    self.object_ids = object_ids if object_ids else []
    self.block_errors = []
    self.block_warnings = []
    self.row_errors = []
    self.row_warnings = []
    self.row_converters = []
    self.ignore = False
    self._has_non_importable_columns = False
    self.object_headers = {}
    self.headers = {}
    # For import contains model name from csv file.
    # For export contains 'Model.__name__' value.
    self.class_name = class_name
    self.table_singular = self.object_class._inflector.table_singular or None
    self.name = self.object_class._inflector.human_singular.title() or ""

  @property
  def ca_definitions_cache(self):
    # type: () -> Dict[Tuple(int, str), models.CustomAttributeDefinition]
    """Return custom attribute definitions used for objects in the block.

    Returns custom attribute definitions mapped to objects in the block grouped
    by ID of object definition is created for and definition title.

    Returns:
      A dict where keys are tuples containing object ID definition is created
      for and definition title, and values are custom attribute definitions
      objects.
    """
    if self._ca_definitions_cache is None:
      with benchmark("Create cache of CADs"):
        self._ca_definitions_cache = self._create_ca_definitions_cache()
    return self._ca_definitions_cache

  def _create_ca_definitions_cache(self, field_names=None):
    """Create cache for custom attribute definitions used in this block."""
    if not issubclass(self.object_class, (mixins.CustomAttributable,
                                          mixins.ExternalCustomAttributable)):
      return {}

    gca_prefix = reflection.AttributeInfo.CUSTOM_ATTR_PREFIX
    lca_prefix = reflection.AttributeInfo.OBJECT_CUSTOM_ATTR_PREFIX

    def _is_ca(field):
      """Helper function to check if field is custom attribute."""
      return field.startswith(lca_prefix) or field.startswith(gca_prefix)

    def _strip_ca_prefix(field):
      """Helper function to strip custom attribute prefix from field."""
      if field.startswith(gca_prefix):
        return field[len(gca_prefix):]
      elif field.startswith(lca_prefix):
        return field[len(lca_prefix):]
      return field

    def _get_ca_name(field):
      """Helper function to get custom attribute name from header."""
      return self.headers[field]["attr_name"]

    if not field_names and self.headers:
      field_names = map(_get_ca_name, filter(_is_ca, self.headers.keys()))
    elif field_names:
      field_names = map(_strip_ca_prefix, filter(_is_ca, field_names))

    ca_definitions = self.object_class.get_custom_attribute_definitions(
        attributable_ids=self.object_ids or None,
        field_names=field_names or None,
    )

    return {
        (cad.definition_id, cad.import_export_title): cad
        for cad in ca_definitions
    }

  def _get_relationships(self):
    """Get all relationships for any of the object in the current block."""
    relationship = models.Relationship
    with benchmark("Fetch all block relationships"):
      relationships = []
      if self.object_ids:
        relationships = db.session.query(
            relationship.source_id,
            relationship.source_type,
            relationship.destination_id,
            relationship.destination_type,
        ).filter(sa.or_(
            sa.and_(
                relationship.source_type == self.object_class.__name__,
                relationship.source_id.in_(self.object_ids),
            ),
            sa.and_(
                relationship.destination_type == self.object_class.__name__,
                relationship.destination_id.in_(self.object_ids),
            )
        )).all()
      return relationships

  def _get_identifier_mappings(self, relationships):
    """Get object and id mapping to user visible identifier."""
    object_ids = collections.defaultdict(set)
    for rel in relationships:
      if rel.source_type == self.object_class.__name__:
        object_ids[rel.destination_type].add(rel.destination_id)
      else:
        object_ids[rel.source_type].add(rel.source_id)

    id_map = {}
    for object_type, ids in object_ids.items():
      model = getattr(models.all_models, object_type, None)
      if hasattr(model, "slug"):
        id_column = getattr(model, "slug")
      elif hasattr(model, "email"):
        id_column = getattr(model, "email")
      else:
        continue
      query = db.session.query(model.id, id_column).filter(model.id.in_(ids))
      id_map[object_type] = dict(query)
    return id_map

  def _create_mapping_cache(self):
    """Create mapping cache for object in the current block."""

    with benchmark("cache for: {}".format(self.object_class.__name__)):
      relationships = self._get_relationships()
      id_map = self._get_identifier_mappings(relationships)
      with benchmark("building cache"):
        cache = collections.defaultdict(lambda: collections.defaultdict(list))
        for rel in relationships:
          if rel.source_type == self.object_class.__name__:
            identifier = id_map.get(rel.destination_type, {}).get(
                rel.destination_id)
            if identifier:
              cache[rel.source_id][rel.destination_type].append(identifier)
          else:
            identifier = id_map.get(rel.source_type, {}).get(rel.source_id)
            if identifier:
              cache[rel.destination_id][rel.source_type].append(identifier)
      return cache

  def get_mapping_cache(self):
    """Return mapping_cache attribute."""
    if self._mapping_cache is None:
      self._mapping_cache = self._create_mapping_cache()
    return self._mapping_cache

  def _create_ticket_tracker_cache(self):
    """Create ticket tracker cache for object in the current block."""
    if not issubclass(self.object_class,
                      issue_tracker_mixins.IssueTrackedWithUrl) or \
       not self.object_ids:
      return {}

    query = db.session.query(
        models.IssuetrackerIssue.object_id,
        models.IssuetrackerIssue.issue_url
    ).filter(
        models.IssuetrackerIssue.object_id.in_(self.object_ids),
        models.IssuetrackerIssue.object_type == self.object_class.__name__
    )
    return dict(query)

  def get_ticket_tracker_cache(self):
    """Return ticket tracker cache attribute."""
    if self._ticket_tracker_cache is None:
      self._ticket_tracker_cache = self._create_ticket_tracker_cache()
    return self._ticket_tracker_cache

  def check_for_duplicate_columns(self, raw_headers):
    """Check for duplicate column names in the current block.

    Having duplicate column names can happen with custom attribute names and in
    that case it is impossible to determine the correct handler for all
    columns. Blocks with duplicate names are ignored.
    """
    counter = collections.Counter(header.strip().rstrip("*").lower()
                                  for header in raw_headers)
    duplicates = [header for header, count in counter.items() if count > 1]
    if duplicates:
      self.add_errors(errors.DUPLICATE_COLUMN,
                      line=self.offset + 1,
                      duplicates=", ".join(duplicates))

  def _get_header_names(self):
    """ Get all posible user column names for current object """
    header_names = {
        v["display_name"].lower(): k for k, v in self.object_headers.items()}
    return header_names

  def _remove_column(self, index):
    """ Remove a column from all rows """
    for row in self.rows:
      if len(row) > index:
        row.pop(index)

  def clean_headers(self, raw_headers):
    """ Sanitize columns from csv file

    Clear out all the bad column headers and remove corresponding column in the
    rows data.

    Args:
      raw_headers (list of unicode): unmodified header row from csv file

    Returns:
      Ordered Dictionary containing all valid headers
    """
    clean_headers = collections.OrderedDict()
    header_names = self._get_header_names()
    removed_count = 0
    for index, raw_header in enumerate(raw_headers):
      header = self._sanitize_header(raw_header)
      if header in header_names:
        field_name = header_names[header]
        if (self.operation == 'import' and
                hasattr(self.object_class, "IMPORTABLE_FIELDS") and
                field_name not in self.object_class.IMPORTABLE_FIELDS):
          self._has_non_importable_columns = True
          self._remove_column(index - removed_count)
          removed_count += 1
          continue
        clean_headers[field_name] = self.object_headers[field_name]
      else:
        if header.startswith(("map:", "unmap:")):
          obj_a = self.name
          obj_b = header.split(":", 1)[1].title()
          self.add_warning(errors.UNSUPPORTED_MAPPING,
                           line=self.offset + 2,
                           obj_a=obj_a,
                           obj_b=obj_b,
                           column_name=header)
        else:
          self.add_warning(errors.UNKNOWN_COLUMN,
                           line=self.offset + 2,
                           column_name=header)
        self._remove_column(index - removed_count)
        removed_count += 1
    return clean_headers

  def add_errors(self, template, **kwargs):
    """Add errors for current block."""
    message = template.format(**kwargs)
    self.block_errors.append(message)
    self.ignore = True

  def add_warning(self, template, **kwargs):
    message = template.format(**kwargs)
    self.block_warnings.append(message)

  @staticmethod
  def _sanitize_header(header):
    """Sanitaze column header string.

    Since we rely on header names to get the correct handlers, we should allow
    some room in the names for special characters for mandatory columns and we
    should treat "map :  control" same as "map: control" or "map:control" to
    make the headers more user friendly.

    Args:
      header (basestring): Raw header value found in the cells of each row of
        all blocks in the imported file.

    Returs:
      String without "*" on mandatory columns and with removed extra spaces in
      the mapping columns.
    """
    header = header.strip("*").lower()
    if header.startswith("map:") or header.startswith("unmap:"):
      header = ":".join(part.strip() for part in header.split(":"))
    return header


class ImportBlockConverter(people_cache.WithPeopleCache,
                           BlockConverter):
  """Import block processing functionality."""
  def __init__(self, converter, object_class, rows, raw_headers,
               offset, class_name, csv_lines):
    # pylint: disable=too-many-arguments
    super(ImportBlockConverter, self).__init__(
        converter,
        object_class=object_class,
        raw_headers=raw_headers,
        rows=rows,
        offset=offset,
        class_name=class_name,
        operation="import"
    )
    names = {n.strip().strip("*").lower() for n in raw_headers or []} or None
    self.object_headers = import_helper.get_object_column_definitions(
        self.object_class,
        fields=names,
        include_hidden=True,
    )
    self.check_for_duplicate_columns(raw_headers)
    self.headers = self.clean_headers(raw_headers)
    self.csv_lines = csv_lines
    self.converter = converter
    self.unique_values = self.get_unique_values_dict(self.object_class)
    self.revision_ids = []
    self._import_info = self._make_empty_info()
    self._create_people_cache()

  def check_block_restrictions(self):
    """Check some block related restrictions"""
    if not self.object_class:
      self.add_errors(errors.WRONG_OBJECT_TYPE, line=self.offset + 2,
                      object_name=self.class_name)
      return
    if self.object_class is CycleTaskGroupObjectTask and \
       not permissions.is_admin():
      self.add_errors(errors.PERMISSION_ERROR, line=self.offset + 2)
      logger.error("Import failed with: Only admin can update existing "
                   "cycle-tasks via import")
    if self._has_non_importable_columns:
      importable_column_names = []
      for field_name in self.object_class.IMPORTABLE_FIELDS:
        if field_name == 'slug':
          continue
        if field_name not in self.headers:
          continue
        importable_column_names.append(
            self.headers[field_name]["display_name"])
      self.add_warning(errors.ONLY_IMPORTABLE_COLUMNS_WARNING,
                       line=self.offset + 2,
                       columns=", ".join(importable_column_names))

    # Check mandatory column "code" for slugged objects.
    if issubclass(self.object_class, models.mixins.Slugged) and \
       "slug" not in self.headers:
      self.add_errors(errors.MISSING_COLUMN,
                      column_names="Code",
                      line=self.offset + 2,
                      s="")

  def row_converters_from_csv(self):
    """ Generate a row converter object for every csv row """
    if self.ignore:
      return
    for i, row in enumerate(self.rows):
      line = self.csv_lines[i]
      yield base_row.ImportRowConverter(self, self.object_class, row=row,
                                        headers=self.headers, line=line, idx=i)

  @property
  def handle_fields(self):
    """Column definitions in correct processing order.

    Special columns which are primary keys logically or affect the valid set of
    columns go before usual columns.
    """

    return [
        # ensure that columns are ordered according to the priority list
        k for k in self.converter.priority_columns if k in self.headers
    ] + [
        k for k in self.headers if k not in self.converter.priority_columns
    ]

  def import_csv_data(self):  # noqa
    """Perform import sequence for the block."""
    try:
      for row in self.row_converters_from_csv():
        try:
          ie_status = self.converter.get_job_status()
          if ie_status and ie_status == \
             all_models.ImportExport.STOPPED_STATUS:
            raise exceptions.ImportStoppedException()
          row.process_row()
        except exceptions.ImportStoppedException:
          raise
        except ValueError as err:
          db.session.rollback()
          msg = err.message or errors.UNEXPECTED_ERROR
          row.add_error(errors.ERROR_TEMPLATE, message=msg)
          logger.exception(msg)
        except Exception:  # pylint: disable=broad-except
          db.session.rollback()
          row.add_error(errors.UNKNOWN_ERROR)
          logger.exception(errors.UNEXPECTED_ERROR)
        self._update_info(row)
        _app_ctx_stack.top.sqlalchemy_queries = []
    except exceptions.ImportStoppedException:
      raise
    except Exception:  # pylint: disable=broad-except
      logger.exception(errors.UNEXPECTED_ERROR)
    finally:
      db.session.commit_hooks_enable_flag.enable()
      is_final_commit_required = not (self.converter.dry_run or self.ignore)
      if is_final_commit_required:
        db.session.commit()

  def get_unique_values_dict(self, object_class):
    """Get the varible to storing row numbers for unique values.

    Make sure to always return the same variable for object with shared tables,
    as defined in sharing rules.
    """
    sharing_rules = get_shared_unique_rules()
    classes = sharing_rules.get(object_class, object_class)
    shared_state = self.converter.shared_state
    if classes not in shared_state:
      shared_state[classes] = collections.defaultdict(
          structures.CaseInsensitiveDict)
    return shared_state[classes]

  def store_revision_ids(self, event):
    """Store revision ids from the current event."""
    if event:
      self.revision_ids.extend(revision.id for revision in event.revisions)

  @staticmethod
  def send_collection_post_signals(new_objects):
    """Send bulk create pre-commit signals."""
    if not new_objects:
      return
    _collections = {}
    for obj in new_objects:
      _collections.setdefault(obj.__class__, []).append(obj)
    for object_class, objects in _collections.iteritems():
      signals.Restful.collection_posted.send(
          object_class,
          objects=objects,
          sources=[{} for _ in xrange(len(objects))],
      )

  def get_info(self):
    """Returns info dict for current block."""
    info = self._import_info.copy()
    info.update({
        "block_warnings": self.block_warnings,
        "block_errors": self.block_errors,
        "row_warnings": self.row_warnings,
        "row_errors": self.row_errors,
    })
    return info

  def _make_empty_info(self):
    """Empty info dict with all counts zero."""
    return {
        "name": self.name,
        "rows": 0,
        "created": 0,
        "updated": 0,
        "ignored": 0,
        "deleted": 0,
        "deprecated": 0,
        "block_warnings": [],
        "block_errors": [],
        "row_warnings": [],
        "row_errors": [],
    }

  def _update_info(self, row):
    """Update counts for info response from row metadata."""
    self._import_info["rows"] += 1
    if row.ignore:
      self._import_info["ignored"] += 1
    elif row.is_delete:
      self._import_info["deleted"] += 1
    elif row.is_new:
      self._import_info["created"] += 1
    else:
      self._import_info["updated"] += 1

    if row.is_deprecated:
      self._import_info["deprecated"] += 1


class ExportBlockConverter(BlockConverter):
  """Export block processing functionality."""

  ROW_CHUNK_SIZE = 50

  def __init__(self, converter, object_class, object_ids, fields, class_name,
               ca_cache=None):
    # pylint: disable=too-many-arguments
    super(ExportBlockConverter, self).__init__(
        converter,
        object_class=object_class,
        object_ids=object_ids,
        class_name=class_name,
        operation="export"
    )

    self._ca_definitions_cache = (
        ca_cache or self._create_ca_definitions_cache(field_names=fields)
    )

    self.object_headers = import_helper.get_object_column_definitions(
        self.object_class, ca_cache=self._ca_cache,
        for_template=self.is_template)

    raw_headers = [unicode(key) for key in self._get_header_names().keys()]
    self.headers = self.clean_headers(raw_headers)
    self.organize_fields(fields)

  @property
  def _ca_cache(self):
    """Get custom attributes definitions in ca_cache-compatible format."""
    object_name = utils.underscore_from_camelcase(self.object_class.__name__)
    if object_name in self.ca_definitions_cache:
      return self.ca_definitions_cache
    return {object_name: self.ca_definitions_cache.values()}

  @property
  def block_width(self):
    """Returns width of block (header length)."""
    return len(self.fields)

  @property
  def is_template(self):
    """Clarify if file is the template"""
    return not self.object_ids

  def organize_fields(self, fields):
    """Setup fields property."""
    if fields == "all":
      fields = self.object_headers.keys()
    self.fields = import_helper.get_column_order(fields)

  def generate_csv_header(self):
    """Generate 2D array with csv header description."""
    headers = []
    for field in self.fields:
      if field not in self.object_headers:
        # There may be cases when self.fields contains local custom attribute
        # fields passed from FE, but self.object_headers does not have them
        # since there are no such LCAs for objects being exported.
        continue
      description = self.object_headers[field]["description"]
      display_name = self.object_headers[field]["display_name"]
      if self.object_headers[field]["mandatory"]:
        display_name += "*"
      headers.append([description, display_name])
    return [list(header) for header in zip(*headers)]

  def row_converters_from_ids(self):
    """ Generate a row converter object for every csv row """
    if self.ignore or not self.object_ids:
      return
    self.row_converters = []

    for ids_pool in list_chunks(self.object_ids, self.ROW_CHUNK_SIZE):
      # sqlalchemy caches all queries and it takes a lot of memory.
      # This line clears query cache.
      _app_ctx_stack.top.sqlalchemy_queries = []

      objects = self.object_class.eager_query().filter(
          self.object_class.id.in_(ids_pool)
      ).execution_options(stream_results=True)

      for obj in objects:
        yield base_row.ExportRowConverter(self, self.object_class, obj=obj,
                                          headers=self.headers)

      # Clear all objects from session (it helps to avoid memory leak)
      for obj in db.session:
        del obj

  def generate_row_data(self):
    """Get row data from all row converters while exporting."""
    if self.ignore:
      return
    for row_converter in self.row_converters_from_ids():
      obj = row_converter.obj
      with benchmark("Create handlers for object fields"):
        row_converter.handle_obj_row_data()
      with benchmark("Load data for {} {}".format(obj.type, obj.id)):
        yield row_converter.to_array(self.fields)
