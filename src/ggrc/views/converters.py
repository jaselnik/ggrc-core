# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Main view functions for import and export pages.

This module handles all view related function to import and export pages
including the import/export api endponts.
"""

# pylint: disable=inconsistent-return-statements
# TODO: Remove this suppression after pylint update to v.1.8.3 or higher.

import re

from functools import wraps
from logging import getLogger
from StringIO import StringIO
from datetime import datetime

from googleapiclient import errors

import flask
from flask import current_app
from flask import json
from flask import render_template
from flask import request
from sqlalchemy import exc as sa_exc
from werkzeug import exceptions as wzg_exceptions


from ggrc import converters
from ggrc import db
from ggrc import login
from ggrc import settings
from ggrc import utils
from ggrc.app import app
from ggrc.cache import utils as cache_utils
from ggrc.cloud_api import task_queue
from ggrc.converters import base
from ggrc.converters import import_helper
from ggrc.gdrive import file_actions as fa
from ggrc.models import all_models
from ggrc.models import background_task
from ggrc.models import exceptions as models_exceptions
from ggrc.models import import_export
from ggrc.notifications import job_emails
from ggrc.query import builder
from ggrc.query import exceptions as query_exceptions
from ggrc.utils import benchmark
from ggrc.utils import errors as app_errors
from ggrc.utils import objects_cache


IMPORTABLES_MAP = {importable.__name__: importable for importable
                   in converters.get_importables().values()}


IGNORE_FIELD_IN_TEMPLATE = {
    "Assessment": {"evidences_file",
                   "end_date"},
    "Audit": {"evidences_file"},
}

# pylint: disable=invalid-name
logger = getLogger(__name__)


def check_required_headers(required_headers):
  """Check required headers to the current request"""
  headers_errors = []
  for header, valid_values in required_headers.items():
    if header not in request.headers:
      headers_errors.append(
          "Missing required header '{}'".format(header))
    elif request.headers[header] not in valid_values:
      headers_errors.append(
          "Invalid header value for '{}'".format(header))

  if headers_errors:
    raise wzg_exceptions.BadRequest("\n".join(headers_errors))


def parse_export_request():
  """ Check if request contains all required fields """
  required_headers = {
      "X-Requested-By": ["GGRC"],
      "Content-Type": ["application/json"],
      "X-export-view": ["blocks", "grid"],
  }
  check_required_headers(required_headers)
  return request.json


def export_file(export_to, filename, csv_string=None):
  """Export file to csv file or gdrive file"""
  if export_to == "gdrive":
    gfile = fa.create_gdrive_file(csv_string, filename)
    headers = [('Content-Type', 'application/json'), ]
    return current_app.make_response((json.dumps(gfile), 200, headers))
  if export_to == "csv":
    headers = [
        ("Content-Type", "text/csv"),
        ("Content-Disposition", "attachment"),
    ]
    return current_app.make_response((csv_string, 200, headers))
  raise wzg_exceptions.BadRequest(app_errors.BAD_PARAMS)


def handle_export_request_error(handle_function):
  """Decorator for handle exceptions during exporting"""
  @wraps(handle_function)
  def handle_wrapper(*args, **kwargs):
    """Wrapper for handle exceptions during exporting"""
    try:
      return handle_function(*args, **kwargs)
    except query_exceptions.BadQueryException as exception:
      raise wzg_exceptions.BadRequest(exception.message)
    except wzg_exceptions.Unauthorized as ex:
      raise wzg_exceptions.Unauthorized("%s %s" % (ex.message,
                                                   app_errors.RELOAD_PAGE))
    except errors.HttpError as e:
      message = json.loads(e.content).get("error").get("message")
      if e.resp.code == 401:
        raise wzg_exceptions.Unauthorized("%s %s" % (message,
                                                     app_errors.RELOAD_PAGE))
      raise wzg_exceptions.InternalServerError(message)
    except Exception as e:  # pylint: disable=broad-except
      logger.exception(e.message)
      if settings.TESTING:
        raise
      raise wzg_exceptions.InternalServerError(
          app_errors.INTERNAL_SERVER_ERROR.format(job_type="Export"))
  return handle_wrapper


@handle_export_request_error
def handle_export_request():
  """Export request handler"""
  # pylint: disable=too-many-locals
  with benchmark("handle export request data"):
    data = parse_export_request()
    objects = data.get("objects")
    exportable_objects = data.get("exportable_objects", [])
    export_to = data.get("export_to")
    current_time = data.get("current_time")
  with benchmark("Generate CSV string"):
    csv_string, object_names = make_export(objects, exportable_objects)
  with benchmark("Make response."):
    filename = "{}_{}.csv".format(object_names, current_time)
    return export_file(export_to, filename, csv_string)


def _check_if_import_allowed_for(object_data):
  """Check if import is allowed for passed objects.

  Args:
    object_data (List[dict]): A list of dictionaries containing object info.
      List items are {"object_name": <str>, ...} dictionaries.

  Raises:
    wzg_exceptions.Forbidden: Import of at least one object from `object_data`
      is not allowed.
  """
  if any(item["object_name"] not in IMPORTABLES_MAP for item in object_data):
    raise wzg_exceptions.Forbidden()


def get_csv_template(objects):
  """Make csv template"""
  _check_if_import_allowed_for(objects)
  ca_cache = {}
  for object_data in objects:
    class_name = object_data["object_name"]
    template_ids = tuple(object_data.get("template_ids") or [])

    object_class = IMPORTABLES_MAP[class_name]
    ignore_fields = IGNORE_FIELD_IN_TEMPLATE.get(class_name, [])

    class_name = utils.underscore_from_camelcase(class_name)
    ca_cache[class_name] = (
        objects_cache.related_cads_for_object_type(
            class_name,
            template_ids
        )
    )

    filtered_fields = [
        field for field in
        import_helper.get_object_column_definitions(
            object_class,
            ca_cache=ca_cache,
        )
        if field not in ignore_fields
    ]
    object_data["fields"] = filtered_fields
  return make_export(objects, ca_cache=ca_cache)


@handle_export_request_error
def handle_export_csv_template_request():
  """Export template request handler"""
  data = parse_export_request()
  objects = data.get("objects")
  export_to = data.get("export_to")
  csv_string, object_names = get_csv_template(objects)
  filename = "{}_template.csv".format(object_names)
  return export_file(export_to, filename, csv_string)


def make_export(objects, exportable_objects=None, ie_job=None, ca_cache=None):
  """Make export"""
  query_helper = builder.QueryHelper(objects)
  ids_by_type = query_helper.get_ids()
  converter = base.ExportConverter(
      ids_by_type=ids_by_type,
      exportable_queries=exportable_objects,
      ie_job=ie_job,
      ca_cache=ca_cache
  )
  csv_data = converter.export_csv_data()
  object_names = "_".join(converter.get_object_names())
  return csv_data, object_names


def check_import_file():
  """Check if imported file format and type is valid"""
  if "file" not in request.files or not request.files["file"]:
    raise wzg_exceptions.BadRequest(app_errors.MISSING_FILE)
  csv_file = request.files["file"]
  if not csv_file.filename.lower().endswith(".csv"):
    raise wzg_exceptions.BadRequest(app_errors.WRONG_FILE_TYPE)
  return csv_file


def parse_import_request():
  """ Check if request contains all required fields """
  required_headers = {
      "X-Requested-By": ["GGRC"],
      "X-test-only": ["true", "false"],
  }
  check_required_headers(required_headers)
  try:
    file_data = request.json
    dry_run = request.headers["X-test-only"] == "true"
    return dry_run, file_data
  except:  # pylint: disable=bare-except
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Export"))


def handle_import_request():
  """Import request handler"""
  dry_run, file_data = parse_import_request()
  csv_data = fa.get_gdrive_file(file_data)
  return make_response(make_import(csv_data, dry_run)["data"])


def make_response(data):
  """Make response"""
  response_json = json.dumps(data)
  headers = [("Content-Type", "application/json")]
  return current_app.make_response((response_json, 200, headers))


def make_import(csv_data, dry_run, ie_job=None, bulk_import=False,
                custom_messages=None):

  """Make import"""
  try:
    converter = base.ImportConverter(
        ie_job,
        dry_run=dry_run,
        csv_data=csv_data,
        bulk_import=bulk_import,
        custom_messages=custom_messages,
    )

    converter.import_csv_data()

    return {"data": converter.get_info(),
            "failed_slugs": converter.failed_slugs}

  except models_exceptions.ImportStoppedException:
    raise
  except Exception as e:  # pylint: disable=broad-except
    logger.exception("Import failed: %s", e.message)
    if settings.TESTING:
      raise
    raise wzg_exceptions.BadRequest("{} {}".format(
        app_errors.INTERNAL_SERVER_ERROR.format(job_type="Import"), e.message
    ))


@app.route("/_background_tasks/run_export", methods=["POST"])
@background_task.queued_task
def run_export(task):
  """Run export"""
  info = {'errors': [], 'warnings': []}
  user = login.get_current_user()
  ie_id = task.parameters.get("ie_id")
  objects = task.parameters.get("objects")
  exportable_objects = task.parameters.get("exportable_objects")

  try:
    ie_job = import_export.get(ie_id)
    content, _ = make_export(objects, exportable_objects, ie_job)
    db.session.refresh(ie_job)
    if ie_job.status == "Stopped":
      return utils.make_simple_response()
    ie_job.results = json.dumps(info)
    ie_job.status = "Finished"
    ie_job.end_at = datetime.utcnow()
    ie_job.content = content
    db.session.commit()

    job_emails.send_email(job_emails.EXPORT_COMPLETED, user.email,
                          ie_job.title, ie_id)
  except models_exceptions.ExportStoppedException:
    logger.info("Export was stopped by user.")
  except sa_exc.OperationalError as e:
    db.session.rollback()
    logger.exception("Export failed: %s", e.message)
    ie_job = import_export.get(ie_id)
    ie_job.status = "Failed"
    info['errors'].append('Too many items. The export cannot be processed. '
                          'Please contact our support team.')
    ie_job.results = json.dumps(info)
    ie_job.end_at = datetime.utcnow()
    db.session.commit()
    job_emails.send_email(job_emails.EXPORT_CRASHED_TOO_MANY_ITEMS, user.email)
    return utils.make_simple_response(e.message)
  except Exception as e:  # pylint: disable=broad-except
    logger.exception("Export failed: %s", e.message)
    ie_job = import_export.get(ie_id)
    try:
      ie_job.status = "Failed"
      ie_job.end_at = datetime.utcnow()
      db.session.commit()
      job_emails.send_email(job_emails.EXPORT_CRASHED, user.email)
      return utils.make_simple_response(e.message)
    except Exception as e:  # pylint: disable=broad-except
      logger.exception("%s: %s", app_errors.STATUS_SET_FAILED, e.message)
      return utils.make_simple_response(e.message)

  return utils.make_simple_response()


@app.route("/_background_tasks/run_import_phases", methods=["POST"])  # noqa: ignore=C901
@background_task.queued_task
def run_import_phases(task):
  """Execute import phases"""
  # pylint: disable=too-many-return-statements
  # pylint: disable=too-many-branches
  # pylint: disable=too-many-statements
  ie_id = task.parameters.get("ie_id")
  user = login.get_current_user()
  try:
    ie_job = import_export.get(ie_id)
    if ie_job.title is not None:
      ie_job.title = ie_job.title.encode("utf-8")
    csv_data = import_helper.read_csv_file(
        StringIO(ie_job.content.encode("utf-8"))
    )

    if ie_job.status == "Analysis":
      info = make_import(csv_data, True, ie_job)["data"]
      db.session.rollback()
      db.session.refresh(ie_job)
      if ie_job.status == "Stopped":
        return utils.make_simple_response()
      ie_job.results = json.dumps(info)
      for block_info in info:
        if block_info["block_errors"] or block_info["row_errors"]:
          ie_job.status = "Analysis Failed"
          ie_job.end_at = datetime.utcnow()
          db.session.commit()
          job_emails.send_email(job_emails.IMPORT_FAILED, user.email,
                                ie_job.title)
          return utils.make_simple_response()
      for block_info in info:
        if block_info["block_warnings"] or block_info["row_warnings"]:
          ie_job.status = "Blocked"
          db.session.commit()
          job_emails.send_email(job_emails.IMPORT_BLOCKED, user.email,
                                ie_job.title)
          return utils.make_simple_response()
      ie_job.status = "In Progress"
      db.session.commit()

    if ie_job.status == "In Progress":
      info = make_import(csv_data, False, ie_job)["data"]
      if ie_job.status == "Stopped":
        return utils.make_simple_response()
      ie_job.results = json.dumps(info)
      for block_info in info:
        if block_info["block_errors"] or block_info["row_errors"]:
          ie_job.status = "Analysis Failed"
          ie_job.end_at = datetime.utcnow()
          job_emails.send_email(job_emails.IMPORT_FAILED, user.email,
                                ie_job.title)
          db.session.commit()
          return utils.make_simple_response()
      ie_job.status = "Finished"
      ie_job.end_at = datetime.utcnow()
      db.session.commit()
      job_emails.send_email(job_emails.IMPORT_COMPLETED, user.email,
                            ie_job.title)
  except models_exceptions.ImportStoppedException:
    ie_job = import_export.get(ie_id)
    job_emails.send_email(job_emails.IMPORT_STOPPED, user.email,
                          ie_job.title)
    logger.info("Import was stopped by user.")
  except Exception as e:  # pylint: disable=broad-except
    logger.exception(e.message)
    ie_job = import_export.get(ie_id)
    try:
      ie_job.status = "Failed"
      ie_job.end_at = datetime.utcnow()
      db.session.commit()
      job_emails.send_email(job_emails.IMPORT_FAILED, user.email,
                            ie_job.title)
      return utils.make_simple_response(e.message)
    except Exception as e:  # pylint: disable=broad-except
      logger.exception("%s: %s", app_errors.STATUS_SET_FAILED, e.message)
      return utils.make_simple_response(e.message)

  return utils.make_simple_response()


def init_converter_views():
  """Initialize views for import and export."""

  # pylint: disable=unused-variable
  # The view function trigger a false unused-variable.
  @app.route("/_service/export_csv", methods=["POST"])
  @login.login_required
  def handle_export_csv():
    """Calls export handler"""
    with benchmark("handle export request"):
      return handle_export_request()

  @app.route("/_service/export_csv_template", methods=["POST"])
  @login.login_required
  def handle_export_csv_template():
    """Calls export csv template handler"""
    with benchmark("handle export csv template"):
      return handle_export_csv_template_request()

  @app.route("/_service/import_csv", methods=["POST"])
  @login.login_required
  def handle_import_csv():
    """Calls import handler"""
    with benchmark("handle import request"):
      return handle_import_request()

  @app.route("/import")
  @login.login_required
  def import_view():
    """Get import view"""
    return render_template("import_export/import.haml")

  @app.route("/export")
  @login.login_required
  def export_view():
    """Get export view"""
    return render_template("import_export/export.haml")


def check_import_export_headers():
  """Check headers"""
  required_headers = {
      "X-Requested-By": ["GGRC"],
  }
  check_required_headers(required_headers)


def make_import_export_response(data):
  """Make response"""
  response_json = json.dumps(data)
  headers = [("Content-Type", "application/json")]
  return current_app.make_response((response_json, 200, headers))


def handle_start(ie_job):
  """Handle import start command"""
  if ie_job.status == "Not Started":
    ie_job.status = "Analysis"
  elif ie_job.status == "Blocked":
    ie_job.status = "In Progress"
  else:
    raise wzg_exceptions.BadRequest(app_errors.WRONG_STATUS)
  try:
    ie_job.start_at = datetime.utcnow()
    db.session.commit()
    run_background_import(ie_job.id)
    return make_import_export_response(ie_job.log_json())
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.JOB_FAILED.format(job_type="Import")
    )


def run_background_import(ie_job_id):
  """Run import job in background task."""
  background_task.create_task(
      name="import",
      url=flask.url_for(run_import_phases.__name__),
      parameters={
          "ie_id": ie_job_id,
          "parent": {
              "type": "ImportExport",
              "id": ie_job_id,
          }
      },
      queue="ggrcImport",
      queued_callback=run_import_phases,
      operation_type=all_models.ImportExport.IMPORT_JOB_TYPE.lower(),
  )
  db.session.commit()


def handle_import_put(**kwargs):
  """Handle import put"""
  command = kwargs.get("command2")
  ie_id = kwargs.get("id2")
  user = login.get_current_user()
  if user.system_wide_role == 'No Access':
    raise wzg_exceptions.Forbidden()
  if not ie_id or not command or command not in ("start", "stop"):
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Import"))
  try:
    ie_job = import_export.get(ie_id)
  except (wzg_exceptions.Forbidden, wzg_exceptions.NotFound):
    raise
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Import"))
  if command == 'start':
    return handle_start(ie_job)
  elif command == "stop":
    return handle_import_stop(**kwargs)
  raise wzg_exceptions.BadRequest(app_errors.BAD_PARAMS)


def handle_import_get(**kwargs):
  """Handle import get"""
  return handle_get(kwargs.get("id2"), kwargs.get("command2"), "Import")


def handle_get(id2, command, job_type):
  """Handle simple get and collection get"""
  check_import_export_headers()
  if command:
    if command != "download":
      wzg_exceptions.BadRequest("Unknown command")
    return handle_file_download(id2)
  try:
    if id2:
      res = import_export.get(id2).log_json()
    else:
      ids = request.args.get("id__in")
      res = import_export.get_jobs(job_type, ids.split(",") if ids else None)
  except (wzg_exceptions.Forbidden, wzg_exceptions.NotFound):
    raise
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type=job_type))

  return make_import_export_response(res)


def check_import_filename(filename):
  """Check filename has no special symbols"""
  spec_symbols = r'\\#?'
  if re.search('[{}]+'.format(spec_symbols), filename):
    raise wzg_exceptions.BadRequest(r"""
        The file name should not contain special symbols \#?. Please correct
        the file name and import a Google sheet or a file again.
    """)


def handle_import_post(**kwargs):
  """ Handle import post """
  # pylint: disable=unused-argument
  check_import_export_headers()
  import_export.delete_previous_imports()
  file_meta = request.json
  csv_data, csv_content, filename = fa.get_gdrive_file_data(file_meta)
  check_import_filename(filename)
  try:
    objects, results, failed = import_helper.count_objects(csv_data)
    ie = import_export.create_import_export_entry(
        content=csv_content,
        gdrive_metadata=file_meta,
        title=filename,
        status="Not Started" if not failed else "Analysis Failed",
        results=results)
    return make_import_export_response({
        "objects": objects if not failed else [],
        "import_export": ie.log_json()})
  except wzg_exceptions.Unauthorized:
    raise
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Import"))


def handle_file_download(id2):
  """  Download file  """
  try:
    export_to = request.args.get("export_to")
    ie = import_export.get(id2)
    return export_file(export_to, ie.title, ie.content.encode("utf-8"))
  except (wzg_exceptions.Forbidden,
          wzg_exceptions.NotFound,
          wzg_exceptions.Unauthorized):
    raise
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Download"))


def handle_export_put(**kwargs):
  """Handle export put"""
  command = kwargs.get("command2")
  ie_id = kwargs.get("id2")
  if not ie_id or not command or command != "stop":
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Export"))
  return handle_export_stop(**kwargs)


def handle_export_get(**kwargs):
  """Handle export get"""
  return handle_get(kwargs.get("id2"), kwargs.get("command2"), "Export")


def handle_export_post(**kwargs):
  """Handle export post"""
  check_import_export_headers()
  request_json = request.json
  objects = request_json.get("objects")
  exportable_objects = request_json.get("exportable_objects", [])
  current_time = request.json.get("current_time")
  user = login.get_current_user()
  if user.system_wide_role == 'No Access':
    raise wzg_exceptions.Forbidden()
  if not objects or not current_time:
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Export"))
  try:
    filename = import_helper.get_export_filename(objects,
                                                 current_time,
                                                 exportable_objects)
    ie = import_export.create_import_export_entry(
        job_type="Export",
        status="In Progress",
        title=filename,
        start_at=datetime.utcnow(),
        results={'errors': [], 'warnings': []}
    )
    run_background_export(ie.id, objects, exportable_objects)
    return make_import_export_response(ie.log_json())
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Export"))


def run_background_export(ie_job_id, objects, exportable_objects):
  """Run export job in background task."""
  background_task.create_task(
      name="export",
      url=flask.url_for(run_export.__name__),
      parameters={
          "ie_id": ie_job_id,
          "objects": objects,
          "exportable_objects": exportable_objects,
          "parent": {
              "type": "ImportExport",
              "id": ie_job_id,
          }
      },
      queue="ggrcImport",
      queued_callback=run_export,
      operation_type=all_models.ImportExport.EXPORT_JOB_TYPE.lower(),
  )
  db.session.commit()


def handle_delete(**kwargs):
  """ Delete import_export entry """
  check_import_export_headers()
  try:
    ie = import_export.get(kwargs["id2"])
    db.session.delete(ie)
    db.session.commit()
    return make_import_export_response("OK")
  except (wzg_exceptions.Forbidden, wzg_exceptions.NotFound):
    raise
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Import/Export"))


def handle_import_stop(**kwargs):
  """Handle import stop"""
  try:
    ie_job = import_export.get(kwargs["id2"])
    if ie_job.status in ("Analysis", "In Progress", "Blocked"):
      ie_job.status = "Stopped"
      ie_job.end_at = datetime.utcnow()
      # Stop tasks only on non local instance
      if getattr(settings, "APPENGINE_INSTANCE", "local") != "local":
        stop_ie_bg_tasks(ie_job)
      db.session.commit()
      expire_ie_cache(ie_job)
      return make_import_export_response(ie_job.log_json())
    if ie_job.status == "Stopped":
      raise models_exceptions.ImportStoppedException()
    if ie_job.status == "Finished":
      raise models_exceptions.ImportFinishedException()
  except wzg_exceptions.Forbidden:
    raise
  except models_exceptions.ImportStoppedException:
    raise wzg_exceptions.BadRequest(app_errors.IMPORT_STOPPED_WARNING)
  except models_exceptions.ImportFinishedException:
    raise wzg_exceptions.BadRequest(app_errors.IMPORT_FINISHED_WARNING)
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Import"))
  # Need to implement a better solution in order to identify specific
  # errors like here
  raise wzg_exceptions.BadRequest(app_errors.WRONG_STATUS)


def handle_export_stop(**kwargs):
  """Handle export stop"""
  try:
    ie_job = import_export.get(kwargs["id2"])
    if ie_job.status == "In Progress":
      ie_job.status = "Stopped"
      # Stop tasks only on non local instance
      if getattr(settings, "APPENGINE_INSTANCE", "local") != "local":
        stop_ie_bg_tasks(ie_job)
      db.session.commit()
      expire_ie_cache(ie_job)
      return make_import_export_response(ie_job.log_json())
    if ie_job.status == "Stopped":
      raise models_exceptions.ExportStoppedException()
    if ie_job.status == "Finished":
      raise models_exceptions.ExportFinishedException()
  except wzg_exceptions.Forbidden:
    raise
  except models_exceptions.ExportStoppedException:
    raise wzg_exceptions.BadRequest(app_errors.EXPORT_STOPPED_WARNING)
  except models_exceptions.ExportFinishedException:
    raise wzg_exceptions.BadRequest(app_errors.EXPORT_FINISHED_WARNING)
  except Exception as e:
    logger.exception(e.message)
    raise wzg_exceptions.BadRequest(
        app_errors.INCORRECT_REQUEST_DATA.format(job_type="Export"))
  raise wzg_exceptions.BadRequest(app_errors.WRONG_STATUS)


def expire_ie_cache(ie_job):
  """Expire export status cache to force DB request."""
  cache_manager = cache_utils.get_cache_manager()
  cache_key = cache_utils.get_ie_cache_key(ie_job)
  cache_manager.cache_object.memcache_client.delete(cache_key)


def get_ie_bg_tasks(ie_job):
  """Get BackgroundTasks related to ImportExport job."""
  return all_models.BackgroundTask.query.join(
      all_models.BackgroundOperation
  ).filter(
      all_models.BackgroundOperation.object_type == ie_job.type,
      all_models.BackgroundOperation.object_id == ie_job.id,
  )


def stop_ie_bg_tasks(ie_job):
  """Stop background tasks related to ImportExport job."""
  bg_tasks = get_ie_bg_tasks(ie_job)
  for task in bg_tasks:
    try:
      task_queue.stop_bg_task(task.name, "ggrcImport")
    except errors.HttpError as err:
      if err.resp.status == 404:
        logger.warning(
            "Task '%s' wasn't found in queue. It will be stopped.",
            task.name
        )
      else:
        raise err
    task.status = all_models.BackgroundTask.STOPPED_STATUS
