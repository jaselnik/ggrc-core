# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base objects for csv file converters."""

import collections
import logging

from google.appengine.ext import deferred
import sqlalchemy as sa

from ggrc import db
from ggrc import login
from ggrc import settings
from ggrc.cache import utils as cache_utils
from ggrc.cache.utils import clear_memcache
from ggrc.converters import base_block
from ggrc.converters import get_exportables
from ggrc.converters import get_importables
from ggrc.converters import import_helper
from ggrc.converters import snapshot_block
from ggrc.fulltext import get_indexer
from ggrc.models import exceptions
from ggrc.models import all_models
from ggrc.utils import benchmark
from ggrc.utils import structures


logger = logging.getLogger(__name__)


class BaseConverter(object):
  """Base class for csv converters."""
  # pylint: disable=too-few-public-methods
  def __init__(self, ie_job):
    self.new_objects = collections.defaultdict(structures.CaseInsensitiveDict)
    self.shared_state = {}
    self.response_data = []
    self.cache_manager = cache_utils.get_cache_manager()
    self.ie_job = ie_job
    self.exportable = get_exportables()

  def get_info(self):
    raise NotImplementedError()

  def _add_ie_status_to_cache(self, status):
    """Add export job status to memcache"""
    cache_key = cache_utils.get_ie_cache_key(self.ie_job)
    self.cache_manager.cache_object.memcache_client.add(cache_key, status)

  def get_job_status(self):
    """Get export job status from cache if exists and from DB otherwise"""
    if not self.ie_job:
      return None
    status = self._get_ie_status_from_cache()
    if not status:
      status = self._get_ie_status_from_db()
      self._add_ie_status_to_cache(status)
    return status

  def _get_ie_status_from_cache(self):
    """Get export job status from memcache if exists, from DB otherwise."""
    if not self.ie_job:
      return None
    cache_key = cache_utils.get_ie_cache_key(self.ie_job)
    ie_status = self.cache_manager.cache_object.memcache_client.get(cache_key)
    return ie_status

  def _get_ie_status_from_db(self):
    """Get status of current ImportExport job."""
    if not self.ie_job:
      return None
    return db.engine.execute(
        sa.text("""
                SELECT status
                FROM import_exports
                WHERE id = :ie_id
        """),
        {"ie_id": self.ie_job.id},
    ).fetchone()[0]


class ImportConverter(BaseConverter):
  # pylint:disable=too-many-instance-attributes
  """Import Converter.

  This class contains and handles all block converters and makes sure that
  blocks and columns are handled in the correct order.
  """

  priority_columns = [
      "email",
      "slug",
      "readonly",
      "delete",
      "task_type",
      "audit",
      "assessment_template",
      "title",
      "status",
  ]

  def __init__(self, ie_job, dry_run=True, csv_data=None, bulk_import=False):
    self.user = login.get_current_user()
    self.dry_run = dry_run
    self.csv_data = csv_data or []
    self._bulk_import = bulk_import
    self.indexer = get_indexer()
    self.comment_created_notif_type = all_models.NotificationType.query. \
        filter_by(name="comment_created").one().id
    super(ImportConverter, self).__init__(ie_job)
    self.exportable.update(get_importables())
    self.bulk_import = bulk_import
    self.failed_slugs = []

  def get_info(self):
    return self.response_data

  def is_bulk_import(self):
    return self._bulk_import

  def initialize_block_converters(self):
    """Initialize block converters."""
    offsets_and_data_blocks = import_helper.split_blocks(self.csv_data)
    for offset, data, csv_lines in offsets_and_data_blocks:
      class_name = data[1][0].strip().lower()
      object_class = self.exportable.get(class_name)
      raw_headers, rows = import_helper.extract_relevant_data(data)
      block_converter = base_block.ImportBlockConverter(
          self,
          object_class=object_class,
          rows=rows,
          raw_headers=raw_headers,
          offset=offset,
          class_name=class_name,
          csv_lines=csv_lines[2:],  # Skip 2 header lines
      )
      block_converter.check_block_restrictions()
      yield block_converter

  def import_csv_data(self):
    """Process import and post import jobs."""

    revision_ids = []
    for converter in self.initialize_block_converters():
      if not converter.ignore:
        try:
          converter.import_csv_data()
        except exceptions.ImportStoppedException:
          raise
        revision_ids.extend(converter.revision_ids)
      self.response_data.append(converter.get_info())
    self._start_compute_attributes_job(revision_ids)
    if not self.dry_run and settings.ISSUE_TRACKER_ENABLED:
      self._start_issuetracker_update(revision_ids)
    self.drop_cache()

  def _start_issuetracker_update(self, revision_ids):
    """Create or update issuetracker tickets for all imported instances."""

    arg_list = {"revision_ids": revision_ids}

    filename = getattr(self.ie_job, "title", '')
    user_email = getattr(self.user, "email", '')
    mail_data = {
        "filename": filename,
        "user_email": user_email,
    }

    arg_list["mail_data"] = mail_data

    from ggrc import views
    views.background_update_issues(parameters=arg_list)

  @staticmethod
  def _start_compute_attributes_job(revision_ids):
    """Starts deferred task to calculate computed attributes."""
    if revision_ids:
      cur_user = login.get_current_user()
      deferred.defer(
          import_helper.calculate_computed_attributes,
          revision_ids,
          cur_user.id
      )

  @classmethod
  def drop_cache(cls):
    clear_memcache()


class ExportConverter(BaseConverter):
  """Export Converter.

  This class contains and handles all block converters and makes sure that
  blocks and columns are handled in the correct order.
  """

  def __init__(self, ids_by_type, exportable_queries=None, ie_job=None,
               ca_cache=None):
    super(ExportConverter, self).__init__(ie_job)
    self.dry_run = True  # TODO: fix ColumnHandler to not use it for exports
    self.block_converters = []
    self.ids_by_type = ids_by_type
    self.exportable_queries = exportable_queries or []
    self._ca_cache = ca_cache

  def get_object_names(self):
    return [c.name for c in self.block_converters]

  def get_info(self):
    for converter in self.block_converters:
      self.response_data.append(converter.get_info())
    return self.response_data

  def initialize_block_converters(self):
    """Generate block converters.

    Generate block converters from a list of tuples with an object name and
    ids and store it to an instance variable.
    """
    object_map = {o.__name__: o for o in self.exportable.values()}
    exportable_queries = self._get_exportable_queries()
    for object_data in exportable_queries:
      class_name = object_data["object_name"]
      object_class = object_map[class_name]
      object_ids = object_data.get("ids", [])
      fields = object_data.get("fields", "all")
      if class_name == "Snapshot":
        self.block_converters.append(
            snapshot_block.SnapshotBlockConverter(self, object_ids,
                                                  fields=fields),
        )
      else:
        block_converter = base_block.ExportBlockConverter(
            self,
            object_class=object_class,
            fields=fields,
            object_ids=object_ids,
            class_name=class_name,
            ca_cache=self._ca_cache
        )
        self.block_converters.append(block_converter)

  def export_csv_data(self):
    """Export csv data."""
    with benchmark("Initialize block converters."):
      self.initialize_block_converters()
    with benchmark("Build csv data."):
      try:
        return self.build_csv_from_row_data()
      except ValueError:
        return ""

  def build_csv_from_row_data(self):
    """Export each block separated by empty lines."""
    table_width = max([converter.block_width
                       for converter in self.block_converters])
    table_width += 1  # One line for 'Object line' column

    csv_string_builder = import_helper.CsvStringBuilder(table_width)
    for block_converter in self.block_converters:
      with benchmark("Generate export file header"):
        csv_header = block_converter.generate_csv_header()
        csv_header[0].insert(0, "Object type")
        csv_header[1].insert(0, block_converter.name)

        csv_string_builder.append_line(csv_header[0])
        csv_string_builder.append_line(csv_header[1])

      for line in block_converter.generate_row_data():
        ie_status = self.get_job_status()
        if ie_status and ie_status == \
           all_models.ImportExport.STOPPED_STATUS:
          raise exceptions.ExportStoppedException()
        line.insert(0, "")
        csv_string_builder.append_line(line)

      csv_string_builder.append_line([])
      csv_string_builder.append_line([])

    return csv_string_builder.get_csv_string()

  def _get_exportable_queries(self):
    """Get a list of filtered object queries regarding exportable items.

    self.ids_by_type should contain a list of object queries.

    self.exportable_queries should contain indexes of exportable queries
    regarding self.ids_by_type

    Returns:
      list of dicts: filtered object queries regarding self.exportable_queries
    """
    if self.exportable_queries:
      queries = [
          object_query
          for index, object_query in enumerate(self.ids_by_type)
          if index in self.exportable_queries
      ]
    else:
      queries = self.ids_by_type
    return queries
