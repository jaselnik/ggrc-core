# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides endpoints to calc cavs in bulk"""

import json

import flask
from werkzeug import exceptions
from ggrc.models import all_models

from ggrc import db
from ggrc import login
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
                  "attribute_definition_id": int
          }]
      },
      "assessments_with_values": [{
          "id": int,
          "title": str,
          "attribute_value": any,
      }]
    }]
  """
  # pylint: disable=too-many-locals
  all_cads = db.session.query(
      CAD,
      all_models.Assessment.id,
      all_models.Assessment.title,
      all_models.Assessment.assessment_type,
      CAV.attribute_value,
  ).join(
      all_models.Assessment, CAD.definition_id == all_models.Assessment.id
  ).outerjoin(
      CAV, CAD.id == CAV.custom_attribute_id,
  ).filter(
      all_models.Assessment.id.in_(data["ids"]),
      CAD.definition_type == 'assessment',
  )
  response_dict = {}
  for cad, asmt_id, asmt_title, asmt_type, cav_value in all_cads:
    item_key = (cad.title, cad.attribute_type, cad.mandatory,
                cad.multi_choice_options, cad.multi_choice_mandatory)
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
      })
    else:
      if not item_response["related_assessments"].get(asmt_type):
        item_response["related_assessments"][asmt_type] = []
      item_response["related_assessments"][asmt_type].append({
          "id": asmt_id,
          "attribute_definition_id": cad.id,
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
