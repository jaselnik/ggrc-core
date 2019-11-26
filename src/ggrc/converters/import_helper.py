# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

import csv
import logging
from StringIO import StringIO
import chardet

from flask import g

from ggrc.app import app
from ggrc.data_platform import computed_attributes
from ggrc.models import person
from ggrc.models.reflection import AttributeInfo
from ggrc.converters import errors
from ggrc.converters import get_exportables
from ggrc.converters import get_importables
from ggrc.converters.column_handlers import aggregate_column_handlers
from ggrc.converters.handlers import handlers


# pylint: disable=invalid-name
logger = logging.getLogger(__name__)


def get_object_column_definitions(object_class, fields=None,
                                  ca_cache=None, include_hidden=False,
                                  for_template=False):
  """Attach additional info to attribute definitions.

  Fetches the attribute info (_aliases) for the given object class and adds
  additional data (handler class, validator function, default value) needed
  for imports. For better performance consider to provide `ca_cache` argument.

  Args:
    object_class (db.Model): Model whose column definitions to get for import.
    fields (iterable): Iterable of field names of the given object class to
      include in returned attribute definitions list. If None, all fields will
      be included. Defaults to None.
    ca_cache (dict): Dictionary containing custom attribute definitions grouped
      by their definitions_type. If None, definitions will be queried from the
      DB. Defaults to None.
    include_hidden (bool): Flag which specifies if we should include column
      handlers for hidden attributes (they marked as 'hidden'
      in _aliases dict).
    for_template (bool): Flag which specifies if we should exclude column
      handlers for attributes that marked as 'ship_in_template'
      in _aliases dict.

  Returns:
    A dict of attribute definitions.
  """
  attributes = AttributeInfo.get_object_attr_definitions(
      object_class,
      ca_fields=fields,
      include_hidden=include_hidden,
      for_template=for_template,
      ca_cache=ca_cache,
  )

  column_handlers = aggregate_column_handlers(object_class)
  for key, attr in attributes.iteritems():
    handler_key = attr.get("handler_key", key)
    # check full handler keys
    handler = column_handlers.get(handler_key)
    if not handler:
      # check handler key prefixes
      handler = column_handlers.get(handler_key.split(":")[0])
    if not handler:
      # use default handler
      handler = handlers.ColumnHandler
    validator = None
    default = None
    if attr["type"] == AttributeInfo.Type.PROPERTY:
      validator = getattr(object_class, "validate_{}".format(key), None)
      default = getattr(object_class, "default_{}".format(key), None)

    attr["handler"] = attr.get("handler", handler)
    attr["validator"] = attr.get("validator", validator)
    attr["default"] = attr.get("default", default)
  return attributes


def get_column_order(columns):
  return AttributeInfo.get_column_order(columns)


def generate_csv_string(csv_data):
  """ Turn 2d string array into a string representing a csv file """
  output_buffer = StringIO()
  writer = csv.writer(output_buffer)

  csv_data = equalize_array(csv_data)
  csv_data = utf_8_encode_array(csv_data)

  for row in csv_data:
    writer.writerow(row)

  body = output_buffer.getvalue()
  output_buffer.close()
  return body


def extract_relevant_data(csv_data):
  """ Split csv data into data and metadata """
  striped_data = [[unicode.strip(c) for c in line]
                  for line in csv_data]  # noqa
  transpose_data = zip(*striped_data[1:])
  non_empty = [d for d in transpose_data if any(d)]
  data = zip(*non_empty[1:])
  column_definitions = list(data.pop(0))
  data = [list(d) for d in data]
  return column_definitions, data


def equalize_array(array):
  """ Expand all rows of 2D array to the same length """
  if len(array) == 0:
    return array
  max_length = max([len(i) for i in array])
  for row in array:
    diff = max_length - len(row)
    row.extend([""] * diff)
  return array


def split_blocks(csv_data):
  """Split array by empty lines and skip blocks shorter than 2 lines."""

  return ((offset, data_block, csv_lines)
          for offset, data_block, csv_lines in split_array(csv_data)
          if len(data_block) >= 2)


def split_array(csv_data):
  """Split array by empty lines.

  Args:
    csv_data - list of lists of strings (parsed CSV)

  Yields:

    [(offset, data_block, csv_lines)] -
        offset is the index of the starting line in the block,
        data_block is a slice of csv_data,
        csv_lines is list of line numbers in CSV for every row in data_block
  """
  current_offset = 0
  current_block = []
  current_csv_lines = []
  for offset, line in enumerate(csv_data):
    if line and line[0] == u"Object type":
      if current_block:
        yield current_offset, current_block, current_csv_lines
        current_block = []
        current_csv_lines = []
      current_offset = offset
    if any(cell for cell in line):
      current_block.append(line)
      current_csv_lines.append(offset + 1)
  if current_block:
    yield current_offset, current_block, current_csv_lines


def generate_2d_array(width, height, value=None):
  """ Generate 2D array of size width x height """
  return [[value for _ in range(width)] for _ in range(height)]


def csv_reader(csv_data, dialect=csv.excel, **kwargs):
  """ Reader for csv files """
  reader = csv.reader(utf_8_encoder(csv_data), dialect=dialect, **kwargs)
  for row in reader:
    yield [unicode(cell, 'utf-8') for cell in row]  # noqa


def read_csv_file(csv_file):
  """ Get full string representation of the csv file """
  return [row for row in csv_reader(csv_file)]


def utf_8_encode_array(array):
  """ encode 2D array to utf8 """
  return [[val.encode("utf-8") for val in line] for line in array]


def utf_8_encoder(csv_data):
  """This function is a generator that attempts to encode the string as utf-8.
  It is assumed that the data is likely to be encoded in ascii. If encoding
  fails, however, the function will attempt to guess the encoding and convert
  it to utf-8.
  Guessing is only done when a line fails to encode as there may be characters
  further in the stream that aren't valid ascii and encoding is performed per
  line yielded; guessing is the fallback on a per-line basis.
  """
  for line in csv_data:
    try:
      yield line.decode('utf-8').encode('utf-8')
    except UnicodeDecodeError:
      encoding_guess = chardet.detect(line)['encoding']
      yield line.decode(encoding_guess).encode('utf-8')


def count_objects(csv_data):
  """Count objects in csv data. Collect errors info."""

  def get_info(name, rows, **error):
    """Create new info"""
    info = {
        "name": name,
        "rows": rows,
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
    if error:
      if 'snapshot' in name.lower():
        info["block_errors"].append(
            errors.SNAPSHOT_IMPORT_ERROR.format(**error))
      else:
        info["block_errors"].append(errors.WRONG_OBJECT_TYPE.format(**error))
    return info

  exportables = get_exportables()
  exportables.update(get_importables())
  offsets_and_data_blocks = split_blocks(csv_data)
  blocks_info = []
  failed = False
  counts = {}
  for offset, data, _ in offsets_and_data_blocks:
    class_name = data[1][0].strip().lower()
    object_class = exportables.get(class_name, "")
    rows = len(data) - 2
    if 'snapshot' in class_name:
      blocks_info.append(get_info(class_name.title(), rows,
                                  line=offset + 2,
                                  object_name=class_name))
      failed = True

    elif object_class:
      object_name = object_class.__name__
      blocks_info.append(get_info(object_name, rows))
      counts[object_name] = counts.get(object_name, 0) + rows
    else:
      blocks_info.append(get_info("", rows,
                                  line=offset + 2,
                                  object_name=class_name))
      failed = True

  return counts, blocks_info, failed


def get_export_filename(objects, current_time, exportable_objects):
  """Generate export file name"""
  if exportable_objects:
    object_names = "_".join(obj['object_name']
                            for index, obj in enumerate(objects)
                            if index in exportable_objects)
  else:
    object_names = "_".join(obj['object_name'] for obj in objects)
  return "{}_{}.csv".format(object_names, current_time)


def calculate_computed_attributes(revision_ids, user_id):
  """Calculate computed attributes as deferred task."""
  with app.app_context():
    try:
      user = person.Person.query.get(user_id)
      setattr(g, '_current_user', user)
      computed_attributes.compute_attributes(revision_ids)
    except Exception as e:  # pylint: disable=broad-except
      logger.exception(
          "Calculation of computed attributes failed: %s", e.message
      )


class CsvStringBuilder(object):
  """CSV string builder."""

  def __init__(self, table_width):
    """Basic initialization."""
    self.table_width = table_width

    self.output_buffer = StringIO()
    self.csv_writer = csv.writer(self.output_buffer)

  @staticmethod
  def _utf_8_encode_line(line):
    """Encode line to utf8."""
    return [
        str(val) if isinstance(val, int) else val.encode("utf-8")
        for val in line
    ]

  def append_line(self, line):
    """Append line to CSV buffer."""
    if len(line) > self.table_width:
      raise Exception("Can't append csv line to buffer. "
                      "Line length greater than table width. ({} > {})".
                      format(len(line), self.table_width))

    line = self._utf_8_encode_line(line)
    diff = self.table_width - len(line)
    line.extend([""] * diff)
    self.csv_writer.writerow(line)

  def get_csv_string(self):
    """Returns CSV string from buffer."""
    return self.output_buffer.getvalue()
