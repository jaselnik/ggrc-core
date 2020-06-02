# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides functions to calculate data `/cavs/search` data"""

import collections

import sqlalchemy as sa

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
  all_cads = db.session.query(all_models.Assessment, CAD, CAV).outerjoin(
      CAD, CAD.definition_id == all_models.Assessment.id
  ).outerjoin(
      CAV, CAD.id == CAV.custom_attribute_id,
  ).filter(
      all_models.Assessment.id.in_(asmt_ids),
      sa.or_(
          CAD.definition_type == 'assessment',
          CAD.id.is_(None)
      )
  )
  return all_cads


def _generate_unique_cad_key(cad):
  """
  Generate unique CAD key by `title`, `attribute_type`, `mandatory`,
   `default_value`, `multi_choice_options` and `multi_choice_mandatory` fields.

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
      cad.multi_choice_options,
      cad.multi_choice_mandatory,
  )


# pylint: disable=too-many-arguments
def _get_or_generate_cad_stub(
    cad,
    cav,
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
    cav: specific custom attribute value instance for the related cad
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
          "values": {},
      },
  )
  cav_value = None
  cav_attribute_object_id = None
  cav_preconditions_failed = None
  if cav:
    cav_value = cav.attribute_value
    cav_attribute_object_id = cav.attribute_object_id
    cav_preconditions_failed = cav.preconditions_failed
  stub["values"][assessment_id] = {
      "value": cav_value,
      "attribute_person_id": cav_attribute_object_id,
      "preconditions_failed": cav_preconditions_failed,
      "definition_id": assessment_id,
      "attribute_definition_id": cad.id,
      "multi_choice_options": cad.multi_choice_options,
      "multi_choice_mandatory": cad.multi_choice_mandatory,
  }
  return stub


def _prepare_attributes_and_assessments(all_cads, asmts_ids):
  # pylint: disable=invalid-name
  """
  Prepare attributes and assessments stubs data.

  Args:
    all_cads: iterated objects of cads joined with assessments
    asmts_ids: list of ordered and filtered int asssessments ids
  Returns:
    response of attributes in OrderedDict form and list of assessments stubs
  """
  attributes = collections.OrderedDict()
  assessments = collections.OrderedDict()

  # We should preset all asmt ids to the ordereddict to save ordering
  for asmt_id in asmts_ids:
    assessments[asmt_id] = None

  for (asmt, cad, cav) in all_cads:
    if cad:
      unique_key = _generate_unique_cad_key(cad)
      attributes[unique_key] = _get_or_generate_cad_stub(
          cad,
          cav,
          asmt.id,
          attributes,
          unique_key,
      )
    if not assessments.get(asmt.id):
      assessments[asmt.id] = {
          "assessment_type": asmt.assessment_type,
          "id": asmt.id,
          "slug": asmt.slug,
          "title": asmt.title,
          "status": asmt.status,
          "urls_count": len(asmt.evidences_url),
          "files_count": len(asmt.evidences_file),
      }
  return attributes.values(), assessments.values()


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
        "slug": 'Some slug', /* String */
        "title": 'Some title', /* String */
        "status": 'Some status', /* String */
     }],
    }

  """
  all_cads = _query_all_cads_asmt_matches(asmt_ids)
  attributes, assessments = _prepare_attributes_and_assessments(
      all_cads,
      asmt_ids,
  )
  response = {
      "attributes": attributes,
      "assessments": assessments,
  }
  return response
