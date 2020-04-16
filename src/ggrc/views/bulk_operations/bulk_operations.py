# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides endpoints to calc cavs in bulk"""

import json
import logging

import flask

from ggrc import db
from ggrc import gdrive
from ggrc import login
from ggrc import utils
from ggrc.app import app
from ggrc.bulk_operations import csvbuilder
from ggrc.login import login_required
from ggrc.models import background_task
from ggrc.notifications import bulk_notifications
from ggrc.utils import benchmark
from ggrc.views import converters
from ggrc.views.bulk_operations import utils as bulk_utils
from ggrc.query import default_handler


logger = logging.getLogger(__name__)

_BULK_VERIFY_MESSAGES = {
    "success": {
        "title": "Ticket(s) update for your Bulk update action was "
                 "completed.",
        "body": "The assessments from the Bulk update action that required "
                "ticket(s) updates have been successfully updated.",
    },
    "failure": {
        "title": "There were some errors in updating ticket(s) for your "
                 "Bulk update action.",
        "body": "There were errors that prevented updates of some ticket(s) "
                "after the Bulk update action. The error may be due to your "
                "lack to sufficient access to generate/update the ticket(s)."
                " Here is the list of assessment(s) that was not updated.",
    },
}


@app.route("/api/bulk_operations/cavs/search", methods=["POST"])
@login.login_required
def bulk_cavs_search():
  """Calculate all LCA for the assessment

  Endpoint returns a dict for LCA with assessment definition type for
  the received POST data assessment ids list.
  Response contains all the CADs in the dict form.
  """

  data = flask.request.json
  response = bulk_utils.get_data(
      default_handler.DefaultHandler(data).get_results()[0]["ids"]
  )
  return flask.Response(json.dumps(response), mimetype='application/json')


def _detect_files(data):
  """Checks if we need to attach files"""
  return any(attr["extra"].get("files")
             for attr in data["attributes"] if attr["extra"])


def _log_import(data):
  """Log messages that happened during imports"""
  warning_messages = ("block_warnings", "row_warnings")
  error_messages = ("block_errors", "row_errors")
  for block in data:
    for message in warning_messages:
      if block[message]:
        logger.warning("Warnings during bulk operations: %s", block[message])

    for message in error_messages:
      if block[message]:
        logger.error("Errors during bulk operations %s", block[message])


@app.route("/_background_tasks/bulk_complete", methods=["POST"])
@background_task.queued_task
def bulk_complete(task):
  """Process bulk complete"""
  flask.session['credentials'] = task.parameters.get("credentials")

  with benchmark("Create CsvBuilder"):
    builder = csvbuilder.MatrixCsvBuilder(task.parameters.get("data", {}))

  with benchmark("Prepare import data for attributes update"):
    update_data = builder.attributes_update_to_csv()

  with benchmark("Update assessments attributes"):
    update_attrs = converters.make_import(csv_data=update_data,
                                          dry_run=False,
                                          bulk_import=True)
    _log_import(update_attrs["data"])

  upd_errors = set(update_attrs["failed_slugs"])

  with benchmark("Prepare import data for attributes update"):
    complete_data = builder.assessments_complete_to_csv(upd_errors)

  complete_errors = []
  if complete_data:
    with benchmark("Update assessments attributes"):
      complete_assmts = converters.make_import(csv_data=complete_data,
                                               dry_run=False,
                                               bulk_import=True)
    complete_errors = set(complete_assmts["failed_slugs"])

  bulk_notifications.send_notification(update_errors=upd_errors,
                                       partial_errors=complete_errors,
                                       asmnt_ids=builder.assessment_ids)

  return app.make_response(('success', 200, [("Content-Type", "text/json")]))


@app.route("/_background_tasks/bulk_verify", methods=["POST"])
@background_task.queued_task
def bulk_verify(task):
  """Process bulk verify"""

  with benchmark("Create CsvBuilder"):
    builder = csvbuilder.VerifyCsvBuilder(task.parameters.get("data", {}))

  with benchmark("Prepare import data for verification"):
    update_data = builder.assessments_verify_to_csv()

  with benchmark("Verify assessments"):
    import_arguments = {
        "csv_data": update_data,
        "dry_run": False,
        "bulk_import": True,
    }

    if "bulk_verify" in task.name:
      # task name will look like
      # u'be5d6e58-b8ae-4210-9ceb-30ac66020711_bulk_verify'
      # when it gets here

      import_arguments["custom_messages"] = _BULK_VERIFY_MESSAGES

    verify_assmts = converters.make_import(**import_arguments)

    _log_import(verify_assmts["data"])

  verify_errors = set(verify_assmts["failed_slugs"])

  bulk_notifications.send_notification(update_errors=verify_errors,
                                       partial_errors={},
                                       asmnt_ids=builder.assessment_ids)

  return app.make_response(('success', 200, [("Content-Type", "text/json")]))


@app.route("/_background_tasks/cavs/save", methods=["POST"])
@background_task.queued_task
def bulk_cavs_save(task):
  """Process bulk cavs save"""
  with benchmark("Create CsvBuilder"):
    builder = csvbuilder.MatrixCsvBuilder(task.parameters.get("data", {}))

  with benchmark("Prepare import data for attributes update"):
    update_data = builder.attributes_update_to_csv()

  with benchmark("Update assessments attributes"):
    import_arguments = {
        "csv_data": update_data,
        "dry_run": False,
        "bulk_import": True,
    }

    update_attrs = converters.make_import(**import_arguments)

  _log_import(update_attrs["data"])

  upd_errors = set(update_attrs["failed_slugs"])
  bulk_notifications.send_notification(
      update_errors=upd_errors,
      partial_errors={},
      asmnt_ids=[asmt.id for asmt in builder.assessments],
  )

  return app.make_response(('success', 200, [("Content-Type", "text/json")]))


@app.route('/api/bulk_operations/complete', methods=['POST'])
@login_required
def run_bulk_complete():
  """Call bulk complete job"""
  data = flask.request.json
  parameters = {"data": data}

  if _detect_files(data):
    try:
      gdrive.get_http_auth()
    except gdrive.GdriveUnauthorized:
      response = app.make_response(("auth", 401,
                                    [("Content-Type", "text/html")]))
      return response
    parameters["credentials"] = flask.session.get('credentials')

  bg_task = background_task.create_task(
      name="bulk_complete",
      url=flask.url_for(bulk_complete.__name__),
      queued_callback=bulk_complete,
      parameters=parameters
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response((utils.as_json(bg_task), 200,
                         [('Content-Type', "text/json")]))
  )


@app.route('/api/bulk_operations/verify', methods=['POST'])
@login_required
def run_bulk_verify():
  """Call bulk verify job"""
  data = flask.request.json
  parameters = {"data": data}

  bg_task = background_task.create_task(
      name="bulk_verify",
      url=flask.url_for(bulk_verify.__name__),
      queued_callback=bulk_verify,
      parameters=parameters
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response((utils.as_json(bg_task), 200,
                         [('Content-Type', "text/json")]))
  )


@app.route("/api/bulk_operations/cavs/save", methods=["POST"])
@login.login_required
def run_bulk_cavs_save():
  """Call bulk cavs save"""
  data = flask.request.json
  parameters = {"data": data}

  bg_task = background_task.create_task(
      name="bulk_cavs_save",
      url=flask.url_for(bulk_cavs_save.__name__),
      queued_callback=bulk_cavs_save,
      parameters=parameters
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(
          (utils.as_json(bg_task), 200, [('Content-Type', "text/json")])
      )
  )
