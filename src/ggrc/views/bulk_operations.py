# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides endpoints to calc cavs in bulk"""

import json

import flask
from werkzeug import exceptions
from ggrc.models import all_models

from ggrc import login
from ggrc.app import app

CAD = all_models.CustomAttributeDefinition


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
  if not data or not data[0].get("ids"):
    return exceptions.BadRequest()
  all_cads = CAD.query.filter(
      CAD.definition_type == 'assessment',
      CAD.definition_id.in_(data[0]["ids"])
  ).all()
  response = []
  for cad in all_cads:
    item_response = {
        "attribute": {
            "attribute_type": cad.attribute_type,
            "title": cad.title,
            "default_value": cad.default_value,
            "multi_choice_options": cad.multi_choice_options,
            "multi_choice_mandatory": cad.multi_choice_mandatory,
            "mandatory": cad.mandatory,
        },
        "related_assessments": [],
        "assessments_with_values": []
    }
    if cad.attribute_values and cad.attribute_values[-1].attribute_value:
      item_response["assessments_with_values"].append({
          "id": cad.definition.id,
          "title": cad.definition.title,
          "attribute_value": cad.attribute_values[-1].attribute_value,
      })
    else:
      item_response["related_assessments"].append({
          "assessments_type": cad.definition.assessment_type,
          "assessments": [{
              "id": cad.definition.id,
              "attribute_definition_id": cad.id,
          }]
      })
    response.append(item_response)
  return flask.Response(json.dumps(response), mimetype='application/json')
