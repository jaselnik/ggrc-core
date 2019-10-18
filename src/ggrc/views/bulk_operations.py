# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides endpoints to calc cavs in bulk"""

import json

from collections import OrderedDict
import flask
from werkzeug import exceptions

from ggrc.views import converters
from ggrc.bulk_operations import csvbuilder
from ggrc.login import login_required
from ggrc.models import all_models, background_task

from ggrc import db
from ggrc import login
from ggrc import gdrive
from ggrc import utils
from ggrc.app import app

CAD = all_models.CustomAttributeDefinition
CAV = all_models.CustomAttributeValue


def _get_bulk_cad_assessment_data(data):
  """Returns CADs and joined assessment data

  :param data:
    {
      "ids": list of int assessments ids
    }
  :return:
    [{
      "attribute": {
          "attribute_type": str,
          "title": str,
          "default_value": any,
          "multi_choice_options": str,
          "multi_choice_mandatory":  str,
          "mandatory": bool,
      },
      "related_assessments": {
          "count": int,
          "values": [{
              "assessments_type": str,
              "assessments": [{
                  "id": int,
                  "attribute_definition_id": int,
                  "slug": str,
          }]
      },
      "assessments_with_values": [{
          "id": int,
          "title": str,
          "attribute_value": any,
          "attribute_person_id": str,
      }]
    }]
  """
  # pylint: disable=too-many-locals
  all_cads = db.session.query(
      CAD,
      all_models.Assessment.id,
      all_models.Assessment.title,
      all_models.Assessment.assessment_type,
      all_models.Assessment.slug,
      CAV.attribute_value,
      CAV.attribute_object_id,
  ).join(
      all_models.Assessment, CAD.definition_id == all_models.Assessment.id
  ).outerjoin(
      CAV, CAD.id == CAV.custom_attribute_id,
  ).filter(
      all_models.Assessment.id.in_(data["ids"]),
      CAD.definition_type == 'assessment',
  )
  response_dict = OrderedDict()
  for (cad, asmt_id, asmt_title, asmt_type, asmt_slug,
       cav_value, cav_person_id) in all_cads:
    multi_choice_options = ",".join(
        sorted(cad.multi_choice_options.split(','))
    ).lower() if cad.multi_choice_options else cad.multi_choice_options
    item_key = (cad.title, cad.attribute_type, cad.mandatory,
                multi_choice_options, cad.multi_choice_mandatory)
    item_response = response_dict.get(
        item_key,
        {
            "attribute": {
                "attribute_type": cad.attribute_type,
                "title": cad.title,
                "default_value": cad.default_value,
                "multi_choice_options": cad.multi_choice_options,
                "multi_choice_mandatory": cad.multi_choice_mandatory,
                "mandatory": cad.mandatory,
                "placeholder": None,
            },
            "related_assessments": {},
            "assessments_with_values": [],
        }
    )
    if cav_value:
      item_response["assessments_with_values"].append({
          "id": asmt_id,
          "title": asmt_title,
          "attribute_value": cav_value,
          "attribute_person_id": cav_person_id,
      })
    if not item_response["related_assessments"].get(asmt_type):
      item_response["related_assessments"][asmt_type] = []
    item_response["related_assessments"][asmt_type].append({
        "id": asmt_id,
        "attribute_definition_id": cad.id,
        "slug": asmt_slug,
    })
    response_dict[item_key] = item_response
  response = []

  for _, cad_item in response_dict.items():
    related_assessments = cad_item["related_assessments"]
    cad_item["related_assessments"] = {"values": []}
    asmt_count = 0
    for asmt_type, assessments in related_assessments.items():
      cad_item["related_assessments"]["values"].append({
          "assessments_type": asmt_type,
          "assessments": assessments
      })
      asmt_count += len(assessments)
    cad_item["related_assessments"]["count"] = asmt_count
    response.append(cad_item)
  return response


@app.route("/api/bulk_operations/cavs/search", methods=["POST"])
@login.login_required
def bulk_cavs_search():
  """Calculate all LCA for the assessment

  Endpoint returns a dict for LCA with assessment definition type for
  the received POST data assessment ids list.
  Response contains all the CADs in the attribute dict,
  related_assessments for all the assessment with CAD which has no value,
  assessments_with_values for all the assessment with CAD which has value,
  """

  data = flask.request.json
  if not data or not data.get("ids"):
    return exceptions.BadRequest()
  response = _get_bulk_cad_assessment_data(data)
  return flask.Response(json.dumps(response), mimetype='application/json')


def _detect_files(data):
  """Checks if we need to attach files"""
  return any(attr["extra"].get("files")
             for attr in data.get("attributes") if attr["extra"])


def _send_notification(update_errors, complete_errors):
  """Send bulk complete job finished."""
  del update_errors
  del complete_errors


@app.route("/bulk_operations/_complete", methods=["POST"])
@background_task.queued_task
def bulk_complete(task):
  """Process bulk complete"""
  flask.session['credentials'] = task.parameters.get("credentials")

  builder = csvbuilder.CsvBuilder(task.parameters.get("data", {}))
  update_data = builder.attributes_update_to_csv()
  update_attrs = converters.make_import(csv_data=update_data,
                                        dry_run=False,
                                        bulk_import=True)
  upd_errors = set(update_attrs["failed_slugs"])
  complete_data = builder.assessments_complete_to_csv(upd_errors)
  if complete_data:
    complete_assmts = converters.make_import(csv_data=complete_data,
                                             dry_run=False,
                                             bulk_import=True)
  complete_errors = set(complete_assmts["failed_slugs"])
  _send_notification(upd_errors, complete_errors)


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
    parameters["credentials"] = flask.session['credentials']

  bg_task = background_task.create_task(
      name="bulk_complete",
      url=flask.url_for(bulk_complete.__name__),
      queued_callback=lambda _: None,
      parameters=parameters
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response((utils.as_json(bg_task), 200,
                         [('Content-Type', "text/json")]))
  )
