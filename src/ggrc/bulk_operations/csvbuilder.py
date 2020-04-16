# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>]

"""Building csv for bulk updates via import."""

import copy
import datetime

from ggrc import db
from ggrc import models


class AssessmentStub(object):
  """Class stores assessment attributes needed for builders"""
  # pylint: disable=too-few-public-methods
  def __init__(self):
    self.id = None
    self.files = []
    self.urls = []
    self.comments = []
    self.cavs = {}
    self.slug = u""
    self.needs_verification = False

  def __str__(self):
    return str({
        "id": self.id,
        "files": self.files,
        "urls": self.urls,
        "comments": self.comments,
        "cavs": self.cavs,
        "slug": self.slug,
        "verification": self.needs_verification,
    })


class AbstractCsvBuilder(object):
  """Abstract class to convert data to csv file"""
  # pylint: disable=too-few-public-methods
  def __init__(self, cav_data):
    """
      Args Example:
        cav_data:
          assessments_ids: [Number, ...]
          attributes: [{
            "attribute_value": String",
            "attribute_title": String,
            "attribute_type": "Dropdown",
            "extra": {"comment": String,
                      "urls": [String, ...],
                      "files": [{String: String}, ...]},
            "bulk_update": [{
                "assessment_id": asmt.id,
                "attribute_definition_id": None,
                "slug": asmt.slug,
            }],
          }, ...]
    """
    self.assessments = []
    self.assessment_ids = cav_data.get("assessments_ids", [])
    self.attr_data = cav_data.get("attributes", [])
    self._convert_data()

  def _convert_data(self):
    """Convert request data to appropriate format."""
    raise NotImplementedError


class VerifyCsvBuilder(AbstractCsvBuilder):
  """Handle data and build csv for assessments bulk verify."""
  def assessments_verify_to_csv(self):
    """Prepare csv to verify assessments in bulk via import"""

    verify_date = unicode(datetime.datetime.now().strftime("%m/%d/%Y"))

    assessments_list = []
    for assessment in self.assessments:
      assessments_list.append(
          [u"", assessment.slug, u"Completed", verify_date]
      )

    result_csv = []
    if assessments_list:
      result_csv.append([u"Object type"])
      result_csv.append([u"Assessment", u"Code", u"State", u"Verified Date"])
      result_csv.extend(assessments_list)

    return result_csv

  def _convert_data(self):
    """Collect if assessments have verification flow and slugs"""
    if not self.assessment_ids:
      return

    assessments = models.Assessment.query.filter(
        models.Assessment.id.in_(self.assessment_ids)
    ).all()

    for assessment in assessments:
      verifiers = assessment.get_person_ids_for_rolename("Verifiers")
      needs_verification = True if verifiers else False
      stub = AssessmentStub()
      stub.id = assessment.id
      stub.needs_verification = needs_verification
      stub.slug = assessment.slug
      self.assessments.append(stub)


class MatrixCsvBuilder(AbstractCsvBuilder):
  """Handle data and build csv for bulk assessment operations."""
  def __init__(self, *args, **kwargs):
    """
      Args:
        cav_data:
          assessments_ids: [Number, ...]
          assessments: [{
            "assessment": {
                "id": Number,
                "slug": String,
            },
            "values": [{
                "value": Any,
                "title": String,
                "type": String,
                "definition_id": Number,
                "id": Number,
                "extra": {
                    "comment": {"description": String, ...},
                    "urls": [String, ...],
                    "files": [{"source_gdrive_id": String}]
                },
            }]
        }]
    """
    self._people_cache = None
    self.cav_keys = None
    super(MatrixCsvBuilder, self).__init__(*args, **kwargs)

  def attributes_update_to_csv(self):
    """Prepare csv to update assessment's attributes in bulk via import

      Next attributes would be updated:
        - custom attributes values
        - attach evidence urls.
        - attach evidence files.
        - attach comments to LCA
    """
    prepared_csv = []
    self._build_assessment_block(prepared_csv)
    self._build_lca_block(prepared_csv)
    return prepared_csv

  def _convert_data(self):
    """Convert request data to appropriate format.

      expected output format:
        self.assessments:
            {"assessment_id (int)": assessment_stub,}
    """
    self._calculate_people_cache()
    self._collect_attributes()
    self._collect_required_data()

  def _calculate_people_cache(self):
    """Calculate people cache with their ids and emails values"""
    people_ids = []
    for asmt in self.attr_data:
      for cav in asmt["values"]:
        if cav["type"] == "Map:Person":
          people_ids.append(cav["value"])
    self._people_cache = dict(
        db.session.query(models.Person.id, models.Person.email).filter(
            models.Person.id.in_(people_ids)
        )
    )

  def _collect_attributes(self):
    """Collect attributes if any presented."""
    for asmt in self.attr_data:
      stub = AssessmentStub()
      stub.id = asmt["assessment"]["id"]
      stub.slug = asmt["assessment"]["slug"]
      for cav in asmt["values"]:
        cav_value = self._populate_value(
            cav["value"],
            cav["type"],
        )
        extra_data = cav["extra"] if cav["extra"] else {}
        cav_urls = extra_data.get("urls", [])
        cav_files = [file_data["source_gdrive_id"] for
                     file_data in extra_data.get("files", {})]
        cav_comment = extra_data.get("comment", {})

        stub.cavs[cav["title"]] = cav_value
        stub.urls.extend(cav_urls)
        stub.files.extend(cav_files)
        if cav_comment:
          comment = copy.copy(cav_comment)
          comment["cad_id"] = cav["id"]
          stub.comments.append(comment)
      self.assessments.append(stub)

  def _collect_required_data(self):
    """Collect all CAD titles, verification and slugs"""
    cav_keys_set = set()
    for assessment in self.assessments:
      cav_keys_set.update(assessment.cavs.keys())

    self.cav_keys = [unicode(cav_key) for cav_key in cav_keys_set]

  def _populate_value(self, raw_value, cav_type):
    """Populate values to be applicable for our import"""
    if cav_type == "Checkbox":
      return "yes" if raw_value == "1" else "no"
    if cav_type == "Map:Person":
      return self._people_cache.get(raw_value, "")
    return raw_value if raw_value else ""

  def _prepare_attributes_row(self, assessment):
    """Prepare row to update assessment attributes

      Header format: [Object type, Code, Evidence URL, Evidence File,
                      LCA titles]
      Prepares "Evidence URL", "Evidence File" rows and all LCA values.
    """
    urls_column = unicode("\n".join(assessment.urls))
    documents_column = unicode("\n".join(assessment.files))
    cav_columns = [unicode(assessment.cavs.get(key, ""))
                   for key in self.cav_keys]
    row = [u"", assessment.slug, urls_column, documents_column] + cav_columns
    return row

  def _build_assessment_block(self, result_csv):
    """Prepare block for assessment import to update CAVs and evidences"""

    attributes_rows = []
    for assessment in self.assessments:
      if assessment.cavs:
        attributes_rows.append(self._prepare_attributes_row(assessment))

    if attributes_rows:
      result_csv.append([u"Object type"])
      result_csv.append([u"Assessment", u"Code", u"Evidence URL",
                         u"Evidence File"] + self.cav_keys)
      result_csv.extend(attributes_rows)
      return

  def _build_lca_block(self, prepared_csv):
    """Prepare comments block to add comments to assessments linked to LCA"""
    if not any(assessment.comments for assessment in self.assessments):
      return
    prepared_csv.append([u"Object type"])
    prepared_csv.append([u"LCA Comment",
                         u"description",
                         u"custom_attribute_definition"])
    for assessment in self.assessments:
      for comment in assessment.comments:
        prepared_csv.append(
            [u"", unicode(comment["description"]), unicode(comment["cad_id"])]
        )
