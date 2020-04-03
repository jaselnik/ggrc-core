# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>]

"""Building csv for bulk updates via import."""

import collections
import copy
import datetime

from ggrc import models


class AssessmentStub(object):
  """Class stores assessment attributes needed for builders"""
  # pylint: disable=too-few-public-methods
  def __init__(self):
    self.files = []
    self.urls = []
    self.comments = []
    self.cavs = {}
    self.slug = u""
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


class AbstractCsvBuilder(object):
  """Abstract class to convert data to csv file"""
  # pylint: disable=too-few-public-methods
  def __init__(self, cav_data):
    """
      Args:
        cav_data:
          assessments_ids: [Number, ...]
          attributes: [Any, ...]
    """
    self.assessments = collections.defaultdict(AssessmentStub)
    self.assessment_ids = cav_data.get("assessments_ids", [])
    self.attr_data = cav_data.get("attributes", [])
    self.convert_data()

  def convert_data(self):
    """Convert request data to appropriate format.

      expected output format:
        self.assessments:
            {"assessment_id (int)": assessment_stub,}
    """
    self._collect_data_from_db()

  def _collect_data_from_db(self):
    """Collect if assessments have verification flow and slugs"""
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


class VerifyCsvBuilder(AbstractCsvBuilder):
  """Handle data and build csv for assessments bulk verify."""

  @staticmethod
  def _prepare_assmt_verify_row(assessment, verify_date):
    """Prepare csv to verify assessments in bulk via import"""
    row = [u"", assessment.slug, u"Completed", verify_date]
    return row

  def assessments_verify_to_csv(self):
    """Prepare csv to verify assessments in bulk via import"""

    verify_date = unicode(datetime.datetime.now().strftime("%m/%d/%Y"))

    assessments_list = []
    for assessment in self.assessments.values():
      assessments_list.append(self._prepare_assmt_verify_row(assessment,
                                                             verify_date))

    result_csv = []
    if assessments_list:
      result_csv.append([u"Object type"])
      result_csv.append([u"Assessment", u"Code", u"State", u"Verified Date"])
      result_csv.extend(assessments_list)

    return result_csv


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
    self.populate_fields = {
        "Checkbox": self._populate_checkbox,
        "Map:Person": self._populate_people,
    }
    self.cav_keys = []
    super(MatrixCsvBuilder, self).__init__(*args, **kwargs)

  @staticmethod
  def _populate_checkbox(raw_value):
    """Populate checkbox value. We receive "0"/"1" from FE"""
    return "yes" if raw_value == "1" else "no"

  @staticmethod
  def _populate_people(raw_value):
    """Take person email. We receive person id instead of email from FE"""
    person = models.Person.query.filter_by(id=raw_value).first()
    return person.email if person else ""

  def convert_data(self):
    """Convert request data to appropriate format.

      expected output format:
        self.assessments:
            {"assessment_id (int)": assessment_stub,}
    """
    self._collect_attributes()

    self._collect_required_data()
    super(MatrixCsvBuilder, self).convert_data()

  def _collect_required_data(self):
    """Collect all CAD titles, verification and slugs"""
    cav_keys_set = set()
    for assessment in self.assessments.values():
      cav_keys_set.update(assessment.cavs.keys())

    cav_keys_set = [unicode(cav_key) for cav_key in cav_keys_set]
    self.cav_keys.extend(cav_keys_set)

  @staticmethod
  def _populate_raw(raw_value):
    """Populate raw attributes values w/o special logic"""
    return raw_value if raw_value else ""

  def _populate_value(self, raw_value, cav_type):
    """Populate values to be applicable for our import"""
    value = self.populate_fields.get(cav_type, self._populate_raw)(raw_value)
    return value

  def _collect_attributes(self):
    """Collect attributes if any presented."""
    for asmt in self.attr_data:
      assessment_id = asmt["assessment"]["id"]
      self.assessments[assessment_id].slug = asmt["assessment"]["slug"]
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

        self.assessments[assessment_id].cavs[cav["title"]] = cav_value
        self.assessments[assessment_id].urls.extend(cav_urls)
        self.assessments[assessment_id].files.extend(cav_files)
        if cav_comment:
          comment = copy.copy(cav_comment)
          comment["cad_id"] = cav["id"]
          self.assessments[assessment_id].comments.append(comment)

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

  @staticmethod
  def _prepare_assmt_complete_row(assessment):
    """Prepare row for assessment complete via import"""
    status = u"In Review" if assessment.needs_verification else u"Completed"
    row = [u"", assessment.slug, status]
    return row

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
