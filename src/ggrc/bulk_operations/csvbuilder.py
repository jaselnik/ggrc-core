# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>]

"""Building csv for bulk updates via import."""

import collections
import copy

from ggrc import models


class AssessmentStub(object):
  """Class stores assessment attributes needed for builders"""
  # pylint: disable=too-few-public-methods
  def __init__(self):
    self.files = []
    self.urls = []
    self.comments = []
    self.cavs = {}
    self.slug = ""
    self.needs_verification = False

  def __str__(self):
    return str({
        "files": self.files,
        "urls": self.urls,
        "comments": self.comments,
        "cavs": self.cavs,
        "slug": self.slug,
        "verification": self.needs_verification,
    })


class CsvBuilder(object):
  """Handle data and build csv for bulk assessment complete."""
  def __init__(self, cav_data):
    """
      Args:
        cav_data:
          assessments_ids: [Number, ...]
          attributes:
            [{"attribute_value": str,
              "attribute_title": str,
              "attribute_type": str,
              "extra":
                "comment": {"description": str
                            "modified_by": {"type": "Person",
                                            "id": int}
                            },
                "urls": [url,],
                "files": [{source_gdrive_id: str,
                          title: str}, ]},
              "bulk_update": [{"assessment_id": int,
                               "attribute_definition_id": int,
                               "slug": str},]},]
    """
    self.populate_fields = {
        "Checkbox": self._populate_checkbox,
        "Map:Person": self._populate_people,
    }
    self.assessments = collections.defaultdict(AssessmentStub)
    self.cav_keys = []
    self.assessment_ids = []
    self.attr_data = cav_data.get("attributes", [])
    self.assmt_ids = cav_data.get("assessments_ids", [])
    self.convert_data()

  @staticmethod
  def _populate_checkbox(raw_value):
    """Populate checkbox value. We receive 0/1 from FE"""
    if raw_value:
      return "yes"
    return "no"

  @staticmethod
  def _populate_people(raw_value):
    """Take person email. We receive person id instead of email from FE"""
    person = models.Person.query.filter_by(id=raw_value).first()
    return person.email if person else ""

  def _collect_keys(self):
    """Collect all CAD titles and assessment ids to create import file"""
    cav_keys_set = set()
    for assessment in self.assessments.values():
      cav_keys_set.update(assessment.cavs.keys())

    cav_keys_set = [unicode(cav_key) for cav_key in cav_keys_set]
    self.cav_keys.extend(cav_keys_set)
    self.assessment_ids = self.assessments.keys()
    self._collect_verification()

  def _collect_verification(self):
    """Collect if assessments have verification flow"""
    if not self.assessment_ids:
      return

    assessments = models.Assessment.query.filter(
        models.Assessment.id.in_(self.assessment_ids)
    ).all()

    for assessment in assessments:
      verifiers = assessment.get_person_ids_for_rolename("Verifiers")
      needs_verification = True if verifiers else False
      self.assessments[assessment.id].needs_verification = needs_verification
      self.assessments[assessment.id].slug = assessment.slug

  def _collect_assmts(self):
    """Collect data for assessments that would be updated."""
    for assessment_id in self.assmt_ids:
      self.assessments[assessment_id] = AssessmentStub()

  @staticmethod
  def _populate_raw(raw_value):
    """Populate raw attributes values w/o special logic"""
    return raw_value if raw_value else ""

  def _populate_value(self, raw_value, cav_type):
    """Populate values to be applicable for our import"""
    value = self.populate_fields.get(cav_type, self._populate_raw)(raw_value)
    return value

  def convert_data(self):
    """Convert request data to appropriate format.

      expected output format:
        self.assessments:
            {"assessment_id (int)": assessment_stub,}
    """
    self._collect_assmts()

    for cav in self.attr_data:
      cav_title = cav["attribute_title"]
      cav_type = cav["attribute_type"]
      cav_value = self._populate_value(cav["attribute_value"], cav_type)

      extra_data = cav["extra"] if cav["extra"] else {}

      cav_urls = extra_data.get("urls", [])
      cav_files = [file_data["source_gdrive_id"] for
                   file_data in extra_data.get("files", {})]
      cav_comment = extra_data.get("comment", {})

      for assessment in cav["bulk_update"]:
        assessment_id = assessment["assessment_id"]

        self.assessments[assessment_id].urls.extend(cav_urls)
        self.assessments[assessment_id].files.extend(cav_files)

        self.assessments[assessment_id].cavs[cav_title] = cav_value

        if cav_comment.get("description"):
          comment = copy.copy(cav_comment)
          comment["cad_id"] = assessment["attribute_definition_id"]
          self.assessments[assessment_id].comments.append(comment)

    self._collect_keys()

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

  @staticmethod
  def _prepare_comment_row(comment):
    """Prepare row to add comment to LCA"""
    row = [u"", unicode(comment["description"]), unicode(comment["cad_id"])]
    return row

  @staticmethod
  def _prepare_assmt_complete_row(assessment):
    """Prepare row for assessment complete via import"""
    status = u"In Review" if assessment.needs_verification else u"Completed"
    row = [u"", assessment.slug, status]
    return row

  def _build_assessment_block(self, result_csv):
    """Prepare block for assessment import to update CAVs and evidences"""

    attributes_rows = []
    for assessment in self.assessments.values():
      if assessment.cavs:
        attributes_rows.append(self._prepare_attributes_row(assessment))

    if attributes_rows:
      result_csv.append([u"Object type"])
      result_csv.append([u"Assessment", u"Code", u"Evidence URL",
                         u"Evidence File"] + self.cav_keys)
      result_csv.extend(attributes_rows)
      return

  def _need_lca_update(self):
    """Check if we need LCA Comment import section in import data"""
    return any(assessment.comments for assessment in self.assessments.values())

  def _build_lca_block(self, prepared_csv):
    """Prepare comments block to add comments to assessments linked to LCA"""
    if not self._need_lca_update():
      return
    prepared_csv.append([u"Object type"])
    prepared_csv.append([u"LCA Comment",
                         u"description",
                         u"custom_attribute_definition"])
    for assessment in self.assessments.values():
      for comment in assessment.comments:
        prepared_csv.append(self._prepare_comment_row(comment))

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

  def assessments_complete_to_csv(self, errors):
    """Prepare csv to complete assessments in bulk via import"""

    assessments_list = []
    for assessment in self.assessments.values():
      if assessment.slug not in errors:
        assessments_list.append(self._prepare_assmt_complete_row(assessment))

    result_csv = []
    if assessments_list:
      result_csv.append([u"Object type"])
      result_csv.append([u"Assessment", u"Code", u"State"])
      result_csv.extend(assessments_list)

    return result_csv
