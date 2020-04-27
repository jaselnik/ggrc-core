# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""Tests for task group task specific export."""

# pylint: disable=too-many-public-methods

import datetime
import ddt
import mock

from ggrc import db
from ggrc.models import all_models
from integration.ggrc.models import factories
from integration.ggrc import TestCase
from integration.ggrc import query_helper

COPIED_TITLE = 'test_name'
COPIED_LINK = 'http://mega.doc'


# pylint: disable=unused-argument
def dummy_gdrive_response(*args, **kwargs):
  return {'webViewLink': COPIED_LINK,
          'name': COPIED_TITLE,
          'id': '12345'}


@ddt.ddt
class TestExport(query_helper.WithQueryApi, TestCase):
  """Test imports for assessment objects."""

  model = all_models.Assessment

  def setUp(self):
    super(TestExport, self).setUp()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }
    with factories.single_commit():
      extr_comment = factories.CommentFactory(description="bad_desc")
      extr_assessment = factories.AssessmentFactory(title="bad_assmnt")
      factories.RelationshipFactory(source=extr_assessment,
                                    destination=extr_comment)

      self.comment = factories.CommentFactory(description="123")
      self.assessment = factories.AssessmentFactory(
          verified_date=datetime.datetime.now(),
          finished_date=datetime.datetime.now(),
      )

      self.rel = factories.RelationshipFactory(source=self.comment,
                                               destination=self.assessment)

  def _change_date_fields(self):
    assmnt = all_models.Assessment.query.filter(
        all_models.Assessment.title == "bad_assmnt"
    ).one()
    assmnt.created_at = "2010-10-10"
    assmnt.updated_at = "2010-10-10"
    db.session.add(assmnt)
    db.session.commit()

  # pylint: disable=too-many-arguments
  def assert_filter_by_datetime(self, alias, datetime_value, slugs,
                                formats=None, operator=None):
    """Assert slugs for each date format ent datetime"""
    for date_string in self.generate_date_strings(datetime_value, formats):
      self.assert_slugs(alias, date_string, slugs, operator)

  def test_export_with_missing_lca(self):
    """Check export works if assessment lacks some exported LCAs.

    When exporting objects, user can specify list of attributes (local or
    global) that should be present in exported CSV. Export should work even
    if exported assessment lacks some of specified attributes.
    """
    with factories.single_commit():
      assessment1 = factories.AssessmentFactory()
      assessment1_slug = assessment1.slug
      factories.CustomAttributeDefinitionFactory(
          title="Test LCAD1",
          definition_type="assessment",
          definition_id=assessment1.id,
          attribute_type="Text",
      )
      factories.CustomAttributeDefinitionFactory(
          title="Test GCA",
          definition_type="assessment",
          attribute_type="Text",
      )
      assessment2 = factories.AssessmentFactory()
      factories.CustomAttributeDefinitionFactory(
          title="Test LCAD2",
          definition_type="assessment",
          definition_id=assessment2.id,
          attribute_type="Text",
      )

    export_query = self._make_query_dict(
        "Assessment",
        expression=[
            "code",
            "=",
            assessment1_slug,
        ],
        fields=[
            'slug',
            '__object_custom__:test lcad1',
            '__object_custom__:test lcad2',
            '__custom__:test gca',
        ]
    )

    response = self.export_parsed_csv([export_query])

    assessment1_data = response["Assessment"][0]
    self.assertEqual(assessment1_data["Code*"], assessment1_slug)
    self.assertNotIn("Test LCAD2", assessment1_data)
    self.assertEqual(assessment1_data["Test LCAD1"], "")
    self.assertEqual(assessment1_data["Test GCA"], "")

  def test_export_with_missing_lca_correct_values(self):  # noqa pylint: disable=invalid-name
    """Check correct values in export if assessment lacks some exported LCAs.

    When exporting objects, user can specify list of attributes (local or
    global) that should be present in exported CSV. Export result should have
    CSV columns filled with appropriate values even if exported assessment
    lacks some of specified attributes.
    """
    with factories.single_commit():
      assessment1 = factories.AssessmentFactory()
      factories.CustomAttributeDefinitionFactory(
          title="Test LCAD1",
          definition_type="assessment",
          definition_id=assessment1.id,
          attribute_type="Text",
      )

      assessment2 = factories.AssessmentFactory()
      assessment2_slug = assessment2.slug
      assesmsent2_lca = factories.CustomAttributeDefinitionFactory(
          title="Test LCAD2",
          definition_type="assessment",
          definition_id=assessment2.id,
          attribute_type="Text",
      )
      factories.CustomAttributeValueFactory(
          custom_attribute=assesmsent2_lca,
          attributable=assessment2,
          attribute_value="Test LCAD2 value",
      )
      factories.CustomAttributeDefinitionFactory(
          title="Test GCA",
          definition_type="assessment",
          attribute_type="Text",
      )

    export_query = self._make_query_dict(
        "Assessment",
        expression=[
            "code",
            "=",
            assessment2_slug,
        ],
        fields=[
            'slug',
            '__object_custom__:test lcad1',
            '__object_custom__:test lcad2',
            '__custom__:test gca',
        ]
    )

    response = self.export_parsed_csv([export_query])

    assessment2_data = response["Assessment"][0]
    self.assertEqual(assessment2_data["Code*"], assessment2_slug)
    self.assertNotIn("Test LCAD1", assessment2_data)
    self.assertEqual(assessment2_data["Test LCAD2"], "Test LCAD2 value")
    self.assertEqual(assessment2_data["Test GCA"], "")

  def test_search_by_comment(self):
    self.assert_slugs("comment",
                      self.comment.description,
                      [self.assessment.slug])

  def test_search_by_new_comment(self):
    """Filter by added new comment and old comment exists"""
    slugs = [self.assessment.slug]
    desc = "321"
    with factories.single_commit():
      new_comment = factories.CommentFactory(description=desc)
      factories.RelationshipFactory(source=self.assessment,
                                    destination=new_comment)
    self.assert_slugs("comment", self.comment.description, slugs)
    self.assert_slugs("comment", desc, slugs)

  def test_search_by_deleted_relation(self):
    """Filter by deleted relation to comment"""
    db.session.delete(self.rel)
    db.session.commit()
    self.assert_slugs("comment", self.comment.description, [])

  def test_search_by_deleted_comment(self):
    """Filter by deleted comment"""
    db.session.delete(self.comment)
    db.session.commit()
    self.assert_slugs("comment", self.comment.description, [])

  @ddt.data("created_at", "Created Date", "created Date")
  def test_filter_by_created_at(self, alias):
    """Test filter by created at"""
    self._change_date_fields()
    self.assert_filter_by_datetime(alias,
                                   self.assessment.created_at,
                                   [self.assessment.slug])

  @ddt.data("updated_at", "Last Updated Date", "Last Updated Date")
  def test_filter_by_updated_at(self, alias):
    """Test filter by updated at"""
    self._change_date_fields()
    self.assert_filter_by_datetime(alias,
                                   self.assessment.updated_at,
                                   [self.assessment.slug])

  @ddt.data("finished_date", "Finished Date", "finished date")
  def test_filter_by_finished_date(self, alias):
    """Test filter by finished date"""
    self.assert_filter_by_datetime(alias,
                                   self.assessment.finished_date,
                                   [self.assessment.slug])

  @ddt.data("verified_date", "Verified Date", "verified date")
  def test_filter_by_verified_date(self, alias):
    """Test filter by verified date"""
    self.assert_filter_by_datetime(alias,
                                   self.assessment.verified_date,
                                   [self.assessment.slug])

  def assert_only_date_for(self, alias, operator, date, slugs):
    self.assert_filter_by_datetime(
        alias,
        date,
        slugs,
        formats=["{year}-{month}-{day}"],
        operator=operator
    )

  def test_filter_not_equal_operators(self):
    """Test filter by != operator."""
    self.assert_only_date_for(
        "verified_date",
        "!=",
        self.assessment.verified_date + datetime.timedelta(1),
        [self.assessment.slug],
    )
    self.assert_only_date_for(
        "verified_date",
        "!=",
        self.assessment.verified_date,
        [],
    )

  def test_filter_not_like_operators(self):
    """Test filter by !~ operator."""
    self.assert_only_date_for(
        "verified_date",
        "!~",
        self.assessment.verified_date + datetime.timedelta(1),
        [self.assessment.slug],
    )
    self.assert_only_date_for(
        "verified_date", "!~", self.assessment.verified_date, [],
    )

  def test_filter_like_operators(self):
    """Test filter by ~ operator."""
    self.assert_only_date_for(
        "verified_date",
        "~",
        self.assessment.verified_date,
        [self.assessment.slug],
    )
    self.assert_only_date_for(
        "verified_date",
        "~",
        self.assessment.verified_date + datetime.timedelta(1),
        [],
    )

  def test_filter_gte_operators(self):
    """Test filter by >= operator."""
    self.assert_only_date_for(
        "verified_date",
        ">=",
        self.assessment.verified_date,
        [self.assessment.slug],
    )
    self.assert_only_date_for(
        "verified_date",
        ">=",
        self.assessment.verified_date + datetime.timedelta(1),
        [],
    )

  def test_filter_gt_operators(self):
    """Test filter by > operator."""
    self.assert_only_date_for(
        "verified_date",
        ">",
        self.assessment.verified_date,
        [],
    )
    self.assert_only_date_for(
        "verified_date",
        ">",
        self.assessment.verified_date - datetime.timedelta(1),
        [self.assessment.slug],
    )

  def test_filter_lte_operators(self):
    """Test filter by <= operator."""
    self.assert_only_date_for(
        "verified_date",
        "<=",
        self.assessment.verified_date,
        [self.assessment.slug],
    )
    self.assert_only_date_for(
        "verified_date",
        "<=",
        self.assessment.verified_date - datetime.timedelta(1),
        [],
    )

  def test_filter_lt_operators(self):
    """Test filter by < operator."""
    self.assert_only_date_for(
        "verified_date",
        "<",
        self.assessment.verified_date,
        [],
    )
    self.assert_only_date_for(
        "verified_date",
        "<",
        self.assessment.verified_date + datetime.timedelta(1),
        [self.assessment.slug],
    )

  @ddt.data(
      # (offset, verified_date, filter_date)
      (180, datetime.datetime(2017, 1, 1, 22, 30), "2017-01-02"),
      (-180, datetime.datetime(2017, 1, 2, 1, 30), "2017-01-01"),
      (0, datetime.datetime(2017, 1, 1, 1, 30), "2017-01-01"),
      (None, datetime.datetime(2017, 1, 1, 1, 30), "2017-01-01"),
  )
  @ddt.unpack
  def test_filter_by_tz_depend(self, offset, verified_date, filter_value):
    """Test filter by verified date with timezone info"""
    user_headers = {}
    if offset is not None:
      user_headers["X-UserTimezoneOffset"] = str(offset)
    self.assessment.verified_date = verified_date
    db.session.add(self.assessment)
    db.session.commit()
    with self.custom_headers(user_headers):
      self.assert_slugs("verified_date", filter_value, [self.assessment.slug])

  @mock.patch('ggrc.gdrive.file_actions.process_gdrive_file',
              dummy_gdrive_response)
  def test_evidence_export(self):
    """Test evidence fields of the assessments"""
    with factories.single_commit():
      evid_file = factories.EvidenceFactory(
          title="Simple title",
          kind=all_models.Evidence.FILE,
          link="https://d.go.com/d/18YJavJlv8YvIoCy/edit",
          description="mega description"
      )
      factories.RelationshipFactory(source=self.assessment,
                                    destination=evid_file)
      evid_file_link = evid_file.link
      evid_file_title = evid_file.title

      evid_url = factories.EvidenceFactory(
          title="Simple title",
          kind=all_models.Evidence.URL,
          link="google.com",
          description="mega description"
      )
      factories.RelationshipFactory(source=self.assessment,
                                    destination=evid_url)
      evid_url_link = evid_url.link

    search_request = [{
        "object_name": "Assessment",
        "fields": "all",
        "filters": {
            "expression": {
                "left": "id",
                "op": {"name": "="},
                "right": self.assessment.id
            }
        }
    }]

    resp = self.export_parsed_csv(search_request)["Assessment"][0]
    expected_evid_file_string = evid_file_link + " " + evid_file_title

    self.assertEquals(expected_evid_file_string, resp["Evidence File"])
    self.assertEquals(evid_url_link, resp["Evidence URL"])

  def test_exported_columns_order(self):
    """Test GCA and LCA columns order in exported file"""

    with factories.single_commit():
      assessment1 = factories.AssessmentFactory(
          title="test assessment",
      )
      factories.CustomAttributeDefinitionFactory(
          title="Test LCA",
          definition_type="assessment",
          definition_id=assessment1.id,
          attribute_type="Text",
      )
      factories.CustomAttributeDefinitionFactory(
          title="Test GCA",
          definition_type="assessment",
          attribute_type="Text",
      )

    search_request = [{
        "object_name": "Assessment",
        "filters": {
            "expression": {}
        },
        "fields": "all"
    }]

    response = self.export_csv(search_request)
    # Here expected string contains the part of sorted headers sequence
    # Normal Attributes, GCA, LCA and Ticket Tracker
    expected_order = 'Last Comment,Test GCA,Test LCA,Ticket Tracker'
    header_line = response.data.split("\r\n")[1]
    self.assertIn(expected_order, header_line)
