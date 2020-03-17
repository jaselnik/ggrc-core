# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides functions to calculate data `/cavs/search` data"""

import collections

from ggrc import db
from ggrc.models import all_models


CAD = all_models.CustomAttributeDefinition
CAV = all_models.CustomAttributeValue


def _query_all_cads_asmt_matches(asmt_ids):
  """
  Query all assessments joined with their LCA
  and filtered by `asmt_ids` param.

  Args:
    asmt_ids: list of assessments ids which should be used in filter
  Returns:
    sqlalchemy.Query response with LCA joined with assessments or
    empty list if asmt_ids is empty.
  """
  if not asmt_ids:
    return []
  all_cads = db.session.query(
      CAD,
      all_models.Assessment.id,
      all_models.Assessment.title,
      all_models.Assessment.assessment_type,
      all_models.Assessment.status,
      CAV.attribute_value,
      CAV.attribute_object_id,
  ).join(
      all_models.Assessment, CAD.definition_id == all_models.Assessment.id
  ).outerjoin(
      CAV, CAD.id == CAV.custom_attribute_id,
  ).filter(
      all_models.Assessment.id.in_(asmt_ids),
      CAD.definition_type == 'assessment',
  )
  return all_cads


def _generate_unique_cad_key(cad):
  """
  Generate unique CAD key by `title`, `attribute_type` and `mandatory` fields.

  Args:
    cad: specific custom attribute
  Returns:
    unique key represented as a tuple
  """
  return (
      cad.title,
      cad.attribute_type,
      cad.mandatory,
      cad.default_value,
  )


# pylint: disable=too-many-arguments
def _get_or_generate_cad_stub(
    cad,
    cav_value,
    cav_person_id,
    assessment_id,
    attributes,
    unique_key,
):
  """
  Prepare attribute stub.
  If value already prepared then just update "values" dict
  with new assessment data.

  Args:
    cad: specific custom attribute on which stub will be prepared
    cav_value: custom attribute value
    cav_person_id: person_id which is not null for Map:Person type cavs
    assessment_id: Custom attribute definition_id
    attributes: dict with the all the new attribute stubs
    unique_key: unique custom attribute key on which value will be saved
  Returns:
    newly created/updated custom attribute stub
  """
  stub = attributes.get(
      unique_key,
      {
          "title": cad.title,
          "mandatory": cad.mandatory,
          "attribute_type": cad.attribute_type,
          "default_value": cad.default_value,
          "values": {}
      },
  )
  stub["values"][assessment_id] = {
      "value": cav_value,
      "attribute_person_id": cav_person_id,
      "definition_id": assessment_id,
      "attribute_definition_id": cad.id,
      "multi_choice_options": cad.multi_choice_options,
      "multi_choice_mandatory": cad.multi_choice_mandatory,
  }
  return stub


def _prepare_attributes_and_assessments(all_cads):
  # pylint: disable=invalid-name
  """
  Prepare attributes and assessments stubs data.

  Args:
    all_cads: iterated objects of cads joined with assessments
  Returns:
    response of attributes in OrderedDict form and list of assessments stubs
  """
  attributes = collections.OrderedDict()
  assessments = []
  for (cad, asmt_id, asmt_title, asmt_type,
       asmt_status, cav_value, cav_person_id) in all_cads:
    unique_key = _generate_unique_cad_key(cad)
    attributes[unique_key] = _get_or_generate_cad_stub(
        cad,
        cav_value,
        cav_person_id,
        asmt_id,
        attributes,
        unique_key,
    )

    assessments.append({
        "assessment_type": asmt_type,
        "id": asmt_id,
        "title": asmt_title,
        "status": asmt_status,
    })
  return attributes.values(), assessments


def get_data(asmt_ids):
  """Get response of calculated assessment joined with attributes

  Args:
    asmt_ids:
      {
        "ids": list of int assessments ids
      }
  Returns:
    {
      /* Contains the list of the grouped LCAs (needed to render columns) */
      "attributes": [{
        "title": 'Some title', /* String */
        "mandatory": False, /* Bool */
        "attribute_type": 'Some type', /* String */
        "default_value": None, /* Any */
        "values": {
          [assessment_id] : { /* Number */
            "attribute_definition_id": 123, /* Number / custom attribute id */
            "value": null, /* Any */
            "attribute_person_id": None, /* Number / non nullable
                                          for Person type */
            "definition_id": 12345, /* Number assessment id*/
            "multi_choice_options": None, /* String */
            "multi_choice_mandatory": None, /* String */
          }
        }
      },
     /* Contains the list of assessments */
     "assessments": [{
        "assessment_type": 'Type', /* String */
        "id": 12345, /* Number */
        "title": 'Some title', /* String */
        "status": 'Some status', /* String */
     }],
    }

  """
  all_cads = _query_all_cads_asmt_matches(asmt_ids)
  attributes, assessments = _prepare_attributes_and_assessments(all_cads)
  response = {
      "attributes": attributes,
      "assessments": assessments,
  }
  return response
