# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

# pylint: disable=maybe-no-member, invalid-name, too-many-lines

"""Test request import and updates."""

import unittest
import datetime
import collections

import ddt
import freezegun

from mock import mock

from ggrc import db
from ggrc import utils
from ggrc.models import all_models
from ggrc.access_control.role import get_custom_roles_for
from ggrc.converters import errors

from integration.ggrc import generator
from integration.ggrc import TestCase
from integration.ggrc.models import factories


# pylint: disable=too-many-public-methods
@ddt.ddt
class TestAssessmentImport(TestCase):
  """Basic Assessment import tests with.

  This test suite should test new Assessment imports, exports, and updates.
  The main focus of these tests is checking error messages for invalid state
  transitions.
  """

  def setUp(self):
    """Set up for Assessment test cases."""
    super(TestAssessmentImport, self).setUp()
    self.client.get("/login")

  def test_import_assessments_with_templates(self):
    """Test importing of assessments with templates."""

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment_template = factories.AssessmentTemplateFactory(audit=audit)
      assessment_template_slug = assessment_template.slug
      factories.CustomAttributeDefinitionFactory(
          title='test_attr1',
          definition_type='assessment_template',
          definition_id=assessment_template.id,
      )
      factories.CustomAttributeDefinitionFactory(
          title='test_attr2',
          attribute_type="Date",
          definition_type='assessment_template',
          definition_id=assessment_template.id,
      )

    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Template", assessment_template_slug),
        ("Audit", audit.slug),
        ("Assignees", "user@example.com"),
        ("Creators", "user@example.com"),
        ("Title", "Assessment 1"),
        ("test_attr1", "abc"),
        ("test_attr2", "7/15/2015"),
    ]))

    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.title == "Assessment 1").first()

    values = set(v.attribute_value for v in assessment.custom_attribute_values)
    self.assertIn("abc", values)
    self.assertIn("2015-07-15", values)

  def test_import_assessment_with_evidence_file(self):
    """Test import evidence file should add warning"""

    evidence_url = "test_gdrive_url"
    audit = factories.AuditFactory()
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Title*", "Assessment1"),
        ("Assignees", "user@example.com"),
        ("Creators", "user@example.com"),
        ("Evidence File", evidence_url),
    ]))

    evidences = all_models.Evidence.query.filter(
        all_models.Evidence.kind == all_models.Evidence.FILE).all()
    self.assertEquals(len(evidences), 0)
    expected_warning = (u"Line 3: 'Evidence File' can't be changed via "
                        u"import. Please go on Assessment page and make "
                        u"changes manually. The column will be skipped")
    expected_messages = {
        "Assessment": {
            "row_warnings": {expected_warning},
        }
    }
    self._check_csv_response(response, expected_messages)

  def test_import_assessment_with_evidence_file_existing(self):
    """If file already mapped to evidence not show warning to user"""
    evidence_url = "test_gdrive_url"

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory()
      assessment_slug = assessment.slug
      factories.RelationshipFactory(source=audit,
                                    destination=assessment)
      evidence = factories.EvidenceFileFactory(link=evidence_url)
      factories.RelationshipFactory(source=assessment,
                                    destination=evidence)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment_slug),
        ("Evidence File", evidence_url),
    ]))
    self.assertEquals([], response[0]['row_warnings'])

  def test_import_assessment_with_template(self):
    """If assessment exist and import with template and lca"""

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory()
      template = factories.AssessmentTemplateFactory()
      factories.RelationshipFactory(source=audit,
                                    destination=assessment)
      factories.CustomAttributeDefinitionFactory(
          title="Test LCA",
          definition_type="assessment",
          attribute_type="Text",
          definition_id=assessment.id
      )

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("Template", template.slug),
    ]))

    self.assertEquals([], response[0]["row_warnings"])
    self.assertEquals([], response[0]["row_errors"])

  def test_import_assessment_with_evidence_url_existing(self):
    """If url already mapped to assessment ignore it"""
    evidence_url = "test_gdrive_url"

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory()
      assessment_slug = assessment.slug
      factories.RelationshipFactory(source=audit,
                                    destination=assessment)
      evidence = factories.EvidenceUrlFactory(link=evidence_url)
      factories.RelationshipFactory(source=assessment,
                                    destination=evidence)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment_slug),
        ("Evidence Url", evidence_url),
    ]))

    evidences = all_models.Evidence.query.filter_by(link=evidence_url).all()
    self.assertEquals(1, len(evidences))
    self.assertEquals([], response[0]['row_warnings'])

  def test_import_assessment_with_evidence_file_multiple(self):
    """Show warning if at least one of Evidence Files not mapped"""
    evidence_url = "test_gdrive_url"

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory()
      assessment_slug = assessment.slug
      factories.RelationshipFactory(source=audit,
                                    destination=assessment)
      evidence1 = factories.EvidenceFileFactory(link=evidence_url)
      factories.RelationshipFactory(source=assessment,
                                    destination=evidence1)
      evidence2 = factories.EvidenceFileFactory(link="test_gdrive_url_2")
      factories.RelationshipFactory(source=assessment,
                                    destination=evidence2)

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment_slug),
        ("Evidence File", evidence_url + "\n another_gdrive_url"),
    ]))
    expected_warning = (u"Line 3: 'Evidence File' can't be changed via import."
                        u" Please go on Assessment page and make changes"
                        u" manually. The column will be skipped")
    self.assertEquals([expected_warning], response[0]['row_warnings'])

  def test_import_assessment_with_evidence_file_blank_multiple(self):
    """No warnings in Evidence Files"""
    evidence_file = "test_gdrive_url \n \n another_gdrive_url"

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory()
      assessment_slug = assessment.slug
      factories.RelationshipFactory(source=audit, destination=assessment)
      evidence1 = factories.EvidenceFileFactory(link="test_gdrive_url")
      factories.RelationshipFactory(source=assessment,
                                    destination=evidence1)
      evidence2 = factories.EvidenceFileFactory(link="another_gdrive_url")
      factories.RelationshipFactory(source=assessment,
                                    destination=evidence2)

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment_slug),
        ("Evidence File", evidence_file),
    ]))

    self.assertEquals([], response[0]['row_warnings'])

  @mock.patch('ggrc.gdrive.file_actions.process_gdrive_file')
  @mock.patch('ggrc.gdrive.file_actions.get_gdrive_file_link')
  def test_assessment_bulk_mode(self, get_gdrive_link, process_gdrive_mock):
    """Test import assessment evidence file in bulk_import mode"""

    evidence_file = "mock_id"
    process_gdrive_mock.return_value = {
        "id": "mock_id",
        "webViewLink": "mock_link",
        "name": "mock_name",
    }
    get_gdrive_link.return_value = "mock_id"

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory()
      assessment_slug = assessment.slug
      factories.RelationshipFactory(source=audit, destination=assessment)

    with mock.patch("ggrc.converters.base.ImportConverter.is_bulk_import",
                    return_value=True):
      response = self.import_data(collections.OrderedDict([
          ("object_type", "Assessment"),
          ("Code*", assessment_slug),
          ("Evidence File", evidence_file),
      ]))
    self.assertEqual(process_gdrive_mock.call_count, 1)
    self.assertEqual(get_gdrive_link.call_count, 1)
    self._check_csv_response(response, {})
    assessment = all_models.Assessment.query.filter_by(
        slug=assessment_slug
    ).first()
    self.assertEqual(len(assessment.evidences_file), 1)

  def _test_assessment_users(self, asmt, users):
    """ Test that all users have correct roles on specified Assessment"""
    verification_errors = ""
    ac_roles = {
        acr_name: acr_id
        for acr_id, acr_name in get_custom_roles_for(asmt.type).items()
    }
    for user_name, expected_types in users.items():
      for role in expected_types:
        try:
          user = all_models.Person.query.filter_by(name=user_name).first()
          acl_len = all_models.AccessControlPerson.query.join(
              all_models.AccessControlList
          ).filter(
              all_models.AccessControlList.ac_role_id == ac_roles[role],
              all_models.AccessControlPerson.person_id == user.id,
              all_models.AccessControlList.object_id == asmt.id,
              all_models.AccessControlList.object_type == asmt.type,
          ).count()
          self.assertEqual(
              acl_len, 1,
              "User {} is not mapped to {}".format(user.email, asmt.slug)
          )
        except AssertionError as error:
          verification_errors += "\n\nChecks for Users-Assessment mapping "\
              "failed for user '{}' with:\n{}".format(user_name, str(error))

    self.assertEqual(verification_errors, "", verification_errors)

  def _test_assigned_user(self, assessment, user_id, role):
    """Check if user has role on assessment"""
    acls = all_models.AccessControlPerson.query.join(
        all_models.AccessControlList
    ).filter(
        all_models.AccessControlPerson.person_id == user_id,
        all_models.AccessControlList.object_id == assessment.id,
        all_models.AccessControlList.object_type == assessment.type,
    )
    self.assertEqual(
        [user_id] if user_id else [],
        [i.person_id for i in acls if i.ac_list.ac_role.name == role]
    )

  def test_assessment_full_no_warnings(self):
    """ Test full assessment import with no warnings

    CSV sheet:
      https://docs.google.com/spreadsheets/d/1Jg8jum2eQfvR3kZNVYbVKizWIGZXvfqv3yQpo2rIiD8/edit#gid=704933240&vpid=A7
    """
    with factories.single_commit():
      for i in range(1, 4):
        factories.PersonFactory(
            name="user {}".format(i),
            email="user{}@example.com".format(i)
        )
      audit = factories.AuditFactory()

    assessment_data = [
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit.slug),
            ("Assignees*", "user1@example.com\nuser2@example.com"),
            ("Creators", "user2@example.com"),
            ("Title", "Assessment 1"),
            ("Evidence Url", "http://i.imgur.com/Lppr347.jpg")
        ]),
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit.slug),
            ("Assignees*", "user1@example.com\nuser3@example.com"),
            ("Creators", "user2@example.com\nuser3@example.com"),
            ("Title", "Assessment 2"),
            ("Status", "In Progress")
        ]),
    ]
    self.import_data(*assessment_data)
    # Test first Assessment
    asmt_1 = all_models.Assessment.query.filter_by(
        title="Assessment 1").first()
    users = {
        "user 1": {"Assignees"},
        "user 2": {"Assignees", "Creators"},
        "user 3": {}
    }
    self._test_assessment_users(asmt_1, users)
    self.assertEqual(asmt_1.status, all_models.Assessment.PROGRESS_STATE)

    # Test second Assessment
    asmt_2 = all_models.Assessment.query.filter_by(
        title="Assessment 2").first()
    users = {
        "user 1": {"Assignees"},
        "user 2": {"Creators"},
        "user 3": {"Assignees", "Creators"},
    }
    self._test_assessment_users(asmt_2, users)
    self.assertEqual(asmt_2.status, all_models.Assessment.PROGRESS_STATE)

    audit = [obj for obj in asmt_1.related_objects() if obj.type == "Audit"][0]
    self.assertEqual(audit.context, asmt_1.context)

    evidence = all_models.Evidence.query.filter_by(
        link="http://i.imgur.com/Lppr347.jpg").first()
    self.assertEqual(audit.context, evidence.context)

  @ddt.data(
      ("In PROGRESS",
       {
           "State": "Verified",
           "Verifiers": "user@example.com",
       },
       all_models.Assessment.PROGRESS_STATE
       ),
      ("not started",
       {
           "State": "In Review",
           "Verifiers": "user@example.com",
           "Title": "Modified Assessment",
           "Notes": "Edited Notes"
       },
       all_models.Assessment.PROGRESS_STATE
       )
  )
  @ddt.unpack
  def test_assessment_import_states(self, start_status,
                                    modified_data, expected_status):
    """ Test Assessment state imports

    These tests are an intermediate part for zucchini release and will be
    updated in the next release.

    CSV sheet:
      https://docs.google.com/spreadsheets/d/1Jg8jum2eQfvR3kZNVYbVKizWIGZXvfqv3yQpo2rIiD8/edit#gid=299569476
    """
    emails = ["user1@example.com", "user2@example.com"]
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_slug = audit.slug
      for email in emails:
        factories.PersonFactory(email=email)

    assessment_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Audit*", audit_slug),
        ("Assignees*", "user1@example.com"),
        ("Creators", "user2@example.com"),
        ("Title", "New Assessment"),
        ("State", start_status)
    ])
    self.import_data(assessment_data)

    assessment = all_models.Assessment.query.filter_by(
        title="New Assessment").first()
    assessment_slug = assessment.slug

    modified_asmt_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment_slug),
    ])
    modified_asmt_data.update(modified_data)
    response = self.import_data(modified_asmt_data)

    self._check_csv_response(response, {
        "Assessment": {
            "row_warnings": {
                errors.STATE_WILL_BE_IGNORED.format(line=3),
            }
        }
    })

    assessment = all_models.Assessment.query.first()
    self.assertEqual(assessment.status, expected_status)

  @unittest.skip("Test randomly fails because backend does not return errors")
  def test_error_ca_import_states(self):
    """Test changing state of Assessment with unfilled mandatory CA"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      factories.CustomAttributeDefinitionFactory(
          title="def1",
          definition_type="assessment",
          definition_id=asmnt.id,
          attribute_type="Text",
          mandatory=True,
      )
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmnt.slug),
        ("Audit", audit.slug),
        ("Assignees", "user@example.com"),
        ("Creators", "user@example.com"),
        ("Title", asmnt.title),
        ("State", "Completed"),
    ]))
    expected_errors = {
        "Assessment": {
            "row_errors": {
                errors.VALIDATION_ERROR.format(
                    line=3,
                    column_name="State",
                    message="CA-introduced completion preconditions are not "
                            "satisfied. Check preconditions_failed of items "
                            "of self.custom_attribute_values"
                )
            }
        }
    }
    self._check_csv_response(response, expected_errors)
    asmnt = all_models.Assessment.query.filter(
        all_models.Assessment.slug == asmnt.slug
    ).first()
    self.assertEqual(asmnt.status, "Not Started")

  @ddt.data(
      (
          [
              collections.OrderedDict([
                  ("object_type", "Assessment"),
                  ("Code*", ""),
                  ("Assignees", "user@example.com"),
                  ("Creators", "user@example.com"),
                  ("Title", "Some title"),
                  ("Unexpected Column", "Some value")
              ])
          ],
          {
              "Assessment": {
                  "block_warnings": {
                      errors.UNKNOWN_COLUMN.format(
                          line=2,
                          column_name="unexpected column"
                      )
                  }
              }
          }
      ),
      (
          [
              collections.OrderedDict([
                  ("object_type", "Assessment"),
                  ("Code*", ""),
                  ("Assignees", "user@example.com"),
                  ("Creators", "user@example.com"),
                  ("Title", "Some title"),
                  ("map:project", "")
              ])
          ],
          {
              "Assessment": {
                  "block_warnings": {
                      errors.UNSUPPORTED_MAPPING.format(
                          line=2,
                          obj_a="Assessment",
                          obj_b="Project",
                          column_name="map:project"
                      )
                  }
              }
          }
      ),
      (
          [
              collections.OrderedDict([
                  ("object_type", "Assessment"),
                  ("Code*", ""),
                  ("Audit*", "not existing"),
                  ("Assignees", "user@example.com"),
                  ("Creators", "user@example.com"),
                  ("Title", "Some title"),
              ])
          ],
          {
              "Assessment": {
                  "row_errors": {
                      errors.MISSING_VALUE_ERROR.format(
                          line=3,
                          column_name="Audit"
                      )
                  },
                  "row_warnings": {
                      errors.UNKNOWN_OBJECT.format(
                          line=3,
                          object_type="Audit",
                          slug="not existing"
                      )
                  }
              }
          }
      ),
      (
          [
              collections.OrderedDict([
                  ("object_type", "Assessment"),
                  ("Code*", ""),
                  ("Assignees", "user@example.com"),
                  ("Creators", "user@example.com"),
                  ("Title", "Some title"),
                  ("State", "Open")
              ])
          ],
          {
              "Assessment": {
                  "row_warnings": {
                      errors.WRONG_VALUE_DEFAULT.format(
                          line=3,
                          column_name="State",
                          value="open",
                      )
                  }
              }
          }
      ),
      (
          [
              collections.OrderedDict([
                  ("object_type", "Assessment"),
                  ("Code*", ""),
                  ("Title", "New Assessment"),
                  ("Creators", "user@example.com"),
                  ("Assignees", "user@example.com"),
                  ("Verifiers", "user@example.com"),
                  ("Finished Date", "7/3/2015"),
                  ("Verified Date", "5/14/2016"),
              ]),
              collections.OrderedDict([
                  ("object_type", "Assessment"),
                  ("Code*", ""),
                  ("Verified Date", "5/15/2016"),
              ])
          ],
          {
              "Assessment": {
                  "row_warnings": {
                      errors.UNMODIFIABLE_COLUMN.format(
                          line=3,
                          column_name="Verified Date"
                      )
                  }
              }
          }
      ),
  )
  @ddt.unpack
  def test_assessment_warnings_errors(self, assessment_data, expected_errors):
    """ Test full assessment import with warnings and errors

    CSV sheet:
      https://docs.google.com/spreadsheets/d/1Jg8jum2eQfvR3kZNVYbVKizWIGZXvfqv3yQpo2rIiD8/edit#gid=889865936
    """
    if len(assessment_data) == 1:
      if "Audit*" not in assessment_data[0]:
        audit = factories.AuditFactory()
        assessment_data[0]["Audit*"] = audit.slug
      response = self.import_data(*assessment_data)
    else:
      audit = factories.AuditFactory()
      assessment_data[0]["Audit*"] = audit.slug
      self.import_data(assessment_data[0])
      assessment = all_models.Assessment.query.filter_by(
          title="New Assessment").first()
      assessment_data[1]["Code*"] = assessment.slug
      assessment_data[1]["Audit*"] = audit.slug

      response = self.import_data(assessment_data[1])

    self._check_csv_response(response, expected_errors)

  def test_blank_optional_field(self):
    """Test warnings while import assessment with blank IssueTracker fields"""
    audit = factories.AuditFactory()
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Title*", "ass1"),
        ("Creators*", "user@example.com"),
        ("Assignees*", "user@example.com"),
        ("Component ID", ""),
        ("Hotlist ID", ""),
        ("Priority", ""),
        ("Severity", ""),
        ("Issue Type", ""),
        ("Ticket Title", ""),
        ("Ticket Tracker Integration", ""),
    ]))
    self._check_csv_response(resp, {})

  def test_mapping_control_through_snapshot(self):
    "Test for add mapping control on assessment"
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(
        all_models.Revision.id.desc()
    ).first()
    factories.SnapshotFactory(
        parent=audit,
        child_id=control.id,
        child_type=control.__class__.__name__,
        revision_id=revision.id
    )
    db.session.commit()
    self.assertFalse(db.session.query(
        all_models.Relationship.get_related_query(
            assessment, all_models.Snapshot()
        ).exists()).first()[0])
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("map:Control versions", control.slug),
    ]))
    self.assertTrue(db.session.query(
        all_models.Relationship.get_related_query(
            assessment, all_models.Snapshot()
        ).exists()).first()[0])

  @ddt.data(
      ("yes", True),
      ("no", True),
      ("invalid_data", False),
  )
  @ddt.unpack
  def test_import_view_only_field(self, value, is_valid):
    "Test import view only fields"
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("archived", value),
    ]))
    row_warnings = []
    if not is_valid:
      row_warnings.append(u"Line 3: Field 'Archived' contains invalid data. "
                          u"The value will be ignored.")
    self.assertEqual(
        [{
            u'ignored': 0,
            u'updated': 1,
            u'block_errors': [],
            u'name': u'Assessment',
            u'created': 0,
            u'deleted': 0,
            u'deprecated': 0,
            u'row_warnings': row_warnings,
            u'rows': 1,
            u'block_warnings': [],
            u'row_errors': [],
        }],
        resp)

  @ddt.data((False, "no", 0, 1, []),
            (True, "yes", 1, 0, [u'Line 3: Importing archived instance is '
                                 u'prohibited. The line will be ignored.']))
  @ddt.unpack
  # pylint: disable=too-many-arguments
  def test_import_archived_assessment(self, is_archived, value, ignored,
                                      updated, row_errors):
    """Test archived assessment import procedure"""
    with factories.single_commit():
      audit = factories.AuditFactory(archived=is_archived)
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("archived", value),
        ("description", "archived assessment description")
    ]))
    self.assertEqual([{
        u'ignored': ignored,
        u'updated': updated,
        u'block_errors': [],
        u'name': u'Assessment',
        u'created': 0,
        u'deleted': 0,
        u'deprecated': 0,
        u'row_warnings': [],
        u'rows': 1,
        u'block_warnings': [],
        u'row_errors': row_errors
    }], resp)

  def test_create_new_assessment_with_mapped_control(self):
    "Test for creation assessment with mapped controls"
    with factories.single_commit():
      audit = factories.AuditFactory()
      control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(
        all_models.Revision.id.desc()
    ).first()
    factories.SnapshotFactory(
        parent=audit,
        child_id=control.id,
        child_type=control.__class__.__name__,
        revision_id=revision.id
    )
    db.session.commit()
    self.assertFalse(db.session.query(
        all_models.Relationship.get_related_query(
            all_models.Assessment(), all_models.Snapshot()
        ).exists()).first()[0])

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Assignees*", all_models.Person.query.all()[0].email),
        ("Creators", all_models.Person.query.all()[0].email),
        ("Title", "Strange title"),
        ("map:Control versions", control.slug),
    ]))
    self._check_csv_response(response, {})
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.title == "Strange title"
    ).first()
    self.assertTrue(db.session.query(all_models.Relationship.get_related_query(
        assessment, all_models.Snapshot()).exists()).first()[0]
    )

  def test_create_import_assignee(self):
    "Test for creation assessment with mapped assignees"
    name = "test_name"
    email = "test@email.com"
    with factories.single_commit():
      audit = factories.AuditFactory()
      assignee_id = factories.PersonFactory(name=name, email=email).id
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Assignees*", email),
        ("Creators", all_models.Person.query.all()[0].email),
        ("Title", "Strange title"),
    ]))
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.title == "Strange title"
    ).first()
    self._test_assigned_user(assessment, assignee_id, "Assignees")

  def test_create_import_creators(self):
    "Test for creation assessment with mapped creator"
    name = "test_name"
    email = "test@email.com"
    with factories.single_commit():
      audit = factories.AuditFactory()
      creator_id = factories.PersonFactory(name=name, email=email).id
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Assignees*", all_models.Person.query.all()[0].email),
        ("Creators", email),
        ("Title", "Strange title"),
    ]))
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.title == "Strange title"
    ).first()
    self._test_assigned_user(assessment, creator_id, "Creators")

  def test_update_import_creators(self):
    "Test for creation assessment with mapped creator"
    slug = "TestAssessment"
    name = "test_name"
    email = "test@email.com"
    with factories.single_commit():
      assessment = factories.AssessmentFactory(slug=slug)
      creator_id = factories.PersonFactory(name=name, email=email).id
    self._test_assigned_user(assessment, None, "Creators")
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", slug),
        ("Creators", email),
    ]))
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.slug == slug
    ).first()
    self._test_assigned_user(assessment, creator_id, "Creators")

  def test_update_import_assignee(self):
    "Test for creation assessment with mapped creator"
    slug = "TestAssessment"
    name = "test_name"
    email = "test@email.com"
    with factories.single_commit():
      assessment = factories.AssessmentFactory(slug=slug)
      assignee_id = factories.PersonFactory(name=name, email=email).id
    self._test_assigned_user(assessment, None, "Assignees")
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", slug),
        ("Assignees", email),
    ]))
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.slug == slug
    ).first()
    self._test_assigned_user(assessment, assignee_id, "Assignees")

  def test_update_import_verifiers(self):
    """Test import does not delete verifiers if empty value imported"""
    slug = "TestAssessment"
    assessment = factories.AssessmentFactory(slug=slug)

    name = "test_name"
    email = "test@email.com"
    verifier = factories.PersonFactory(name=name, email=email)
    verifier_id = verifier.id

    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", slug),
        ("Verifiers", email),
    ]))
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.slug == slug
    ).first()
    self._test_assigned_user(assessment, verifier_id, "Verifiers")
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", slug),
        ("Verifiers", ""),
    ]))
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.slug == slug
    ).first()
    self._test_assigned_user(assessment, verifier_id, "Verifiers")

  @ddt.data(
      (
          "Created Date",
          lambda: datetime.date.today() - datetime.timedelta(7),
      ),
  )
  @ddt.unpack
  def test_update_non_changeable_field(self, field, value_creator):
    """Test importing Assessment's "Created Date" field"""
    slug = "TestAssessment"
    with factories.single_commit():
      value = value_creator()
      factories.AssessmentFactory(
          slug=slug,
          modified_by=factories.PersonFactory(email="modifier@email.com"),
      )
    data = [{
        "object_name": "Assessment",
        "fields": "all",
        "filters": {
            "expression": {
                "left": "code",
                "op": {"name": "="},
                "right": slug
            },
        }
    }]
    before_update = self.export_parsed_csv(data)["Assessment"][0][field]
    with freezegun.freeze_time("2017-9-10"):
      self.import_data(collections.OrderedDict([
          ("object_type", "Assessment"),
          ("Code*", slug),
          (field, value)
      ]))
    self.assertEqual(before_update,
                     self.export_parsed_csv(data)["Assessment"][0][field])

  @ddt.data(
      ("Last Updated By", "new_user@email.com"),
  )
  @ddt.unpack
  def test_exportable_only_updated_by(self, field, value):
    """Test exportable only "Last Updated By" field"""
    slug = "TestAssessment"
    with factories.single_commit():
      factories.AssessmentFactory(
          slug=slug,
          modified_by=factories.PersonFactory(email="modifier@email.com"),
      )
    data = [{
        "object_name": "Assessment",
        "fields": "all",
        "filters": {
            "expression": {
                "left": "code",
                "op": {"name": "="},
                "right": slug
            },
        }
    }]
    before_update = self.export_parsed_csv(data)["Assessment"][0][field]
    self.assertEqual(before_update, "modifier@email.com")
    self.import_data(collections.OrderedDict(
        [
            ("object_type", "Assessment"),
            ("Code*", slug),
            (field, value)
        ]
    ))
    after_update = self.export_parsed_csv(data)["Assessment"][0][field]
    self.assertEqual(after_update, "user@example.com")

  def test_import_last_deprecated_date(self):
    """Last Deprecated Date on assessment should be non editable."""
    with factories.single_commit():
      with freezegun.freeze_time("2017-01-01"):
        assessment = factories.AssessmentFactory(status="Deprecated")

    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("code", assessment.slug),
        ("Last Deprecated Date", "02/02/2017"),
    ]))

    result = all_models.Assessment.query.get(assessment.id)

    self.assertEqual(1, len(resp))
    self.assertEqual(1, resp[0]["updated"])
    self.assertEqual(result.end_date, datetime.date(2017, 1, 1))

  @ddt.data(*all_models.Assessment.VALID_STATES)
  def test_import_set_up_deprecated(self, start_state):
    """Update assessment from {0} to Deprecated."""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=start_state)
    resp = self.import_data(
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("code", assessment.slug),
            ("State", all_models.Assessment.DEPRECATED),
        ]))
    self.assertEqual(1, len(resp))

    self.assertEqual(1, resp[0]["updated"])
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).status,
        all_models.Assessment.DEPRECATED)

  def test_asmnt_cads_update_completed(self):
    """Test update of assessment without cads."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      factories.CustomAttributeDefinitionFactory(
          title="CAD",
          definition_type="assessment",
          definition_id=asmnt.id,
          attribute_type="Text",
          mandatory=True,
      )
    data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmnt.slug),
        ("Audit", audit.slug),
        ("Title", "Test title"),
        ("State", "Completed"),
        ("CAD", "Some value"),
    ])
    response = self.import_data(data)
    self._check_csv_response(response, {})

  def test_import_complete_missing_answers_warnings(self):
    """Test complete assessment with missing mandatory CAD comments."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      factories.CustomAttributeDefinitionFactory(
          title="CAD",
          definition_type="assessment",
          definition_id=asmnt.id,
          attribute_type="Dropdown",
          multi_choice_options="no,yes",
          multi_choice_mandatory="0,1"
      )
    data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmnt.slug),
        ("Audit", audit.slug),
        ("Title", "Test title"),
        ("State", "Completed"),
        ("CAD", "yes"),
    ])
    expected_response = {
        "Assessment": {
            "row_warnings": {
                errors.NO_REQUIRED_ANSWERS_WARNING.format(line=3),
            }
        }
    }
    response = self.import_data(data)
    self._check_csv_response(response, expected_response)

  def test_import_asmnt_rev_query_count(self):
    """Test only one revisions insert query should occur while importing."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      cad_names = ("CAD1", "CAD2", "CAD3")
      for name in cad_names:
        factories.CustomAttributeDefinitionFactory(
            title=name,
            definition_type="assessment",
            definition_id=asmnt.id,
            attribute_type="Text",
            mandatory=True,
        )
    data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmnt.slug),
        ("Audit", audit.slug),
        ("Title", "Test title"),
        ("State", "Completed"),
        ("CAD1", "Some value 1"),
        ("CAD2", "Some value 2"),
        ("CAD3", "Some value 3"),
    ])
    with utils.QueryCounter() as counter:
      response = self.import_data(data)
    self._check_csv_response(response, {})
    rev_insert_queries = [query for query in counter.queries
                          if 'INSERT INTO revisions' in query]
    self.assertEqual(len(rev_insert_queries), 1)

  def test_asmt_verified_date_update_from_none(self):
    """Test that we able to set Verified Date if it is empty"""
    audit = factories.AuditFactory()
    assessment = factories.AssessmentFactory(audit=audit)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", assessment.slug),
        ("Verifiers", "user@example.com"),
        ("Verified Date", "01/22/2019"),
    ]))
    self._check_csv_response(response, {})
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).verified_date,
        datetime.datetime(2019, 1, 22))

  def test_asmt_verified_date_readonly(self):
    """Test that Verified Date is readonly"""
    audit = factories.AuditFactory()
    date = datetime.datetime(2019, 05, 22)
    assessment = \
        factories.AssessmentFactory(audit=audit,
                                    verified_date=date)
    expected_warnings = {
        'Assessment': {
            'row_warnings': {
                errors.UNMODIFIABLE_COLUMN.format(
                    line=3,
                    column_name="Verified Date"
                )}}}
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", assessment.slug),
        ("Verifiers", "user@example.com"),
        ("Verified Date", "01/21/2019"),
    ]))
    self._check_csv_response(response, expected_warnings)
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).verified_date,
        date)

  @ddt.data("user@example.com", "--")
  def test_asmt_state_after_updating_verifiers(self, new_verifier):
    """Test that after updating Verifiers assessment became In Progress"""
    audit = factories.AuditFactory()
    assessment = \
        factories.AssessmentFactory(audit=audit,
                                    status=all_models.Assessment.DONE_STATE,
                                    )
    person = factories.PersonFactory(email="verifier@example.com")
    factories.AccessControlPersonFactory(
        ac_list=assessment.acr_name_acl_map["Verifiers"],
        person=person,
    )
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).status,
        all_models.Assessment.DONE_STATE)
    self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", assessment.slug),
        ("Verifiers", new_verifier),
    ]))
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).status,
        all_models.Assessment.PROGRESS_STATE)

  def test_assmt_with_multiselect_gca(self):
    """Import of assessment with multiselect CAD shouldn't add assmt.CAV"""
    assess_slug = "TestAssessment"
    with factories.single_commit():
      # create 2 GCA's
      cad_text = factories.CustomAttributeDefinitionFactory(
          title="text_GCA",
          definition_type="assessment",
          attribute_type="Text",
      )
      factories.CustomAttributeDefinitionFactory(
          title="multiselect_GCA",
          definition_type="assessment",
          attribute_type="Multiselect",
          multi_choice_options="1,2,3"
      )

      # create assessment with 1 CAV
      assessment = factories.AssessmentFactory(
          slug=assess_slug,
      )
      factories.CustomAttributeValueFactory(
          custom_attribute=cad_text,
          attributable=assessment,
          attribute_value="text",
      )
      assessment_id = assessment.id
    # update given assessment with empty GCA multiselect type
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", assess_slug),
        ("multiselect_GCA", ""),
    ]))
    self._check_csv_response(response, {})
    assessment = all_models.Assessment.query.get(assessment_id)
    self.assertEquals(1, len(assessment.custom_attribute_values))
    self.assertEquals(
        "text", assessment.custom_attribute_values[0].attribute_value
    )

  def test_asmt_missing_mandatory_gca(self):
    """"Import asmt with mandatory empty multiselect CAD"""
    asmt_slug = "TestAssessment"
    with factories.single_commit():
      factories.CustomAttributeDefinitionFactory(
          title="multiselect_GCA",
          definition_type="assessment",
          attribute_type="Multiselect",
          multi_choice_options="1,2,3",
          mandatory=True,
      )
      factories.AssessmentFactory(slug=asmt_slug)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", asmt_slug),
        ("multiselect_GCA", ""),
    ]))
    expected_response = {
        "Assessment": {
            "row_errors": {
                errors.MISSING_VALUE_ERROR.format(
                    column_name="multiselect_GCA",
                    line=3
                ),
            },
        },
    }
    self._check_csv_response(response, expected_response)

  def test_asmt_with_multiselect_gca_diff_text(self):
    """"Import asmt with mandatory diff case text multiselect CAD"""
    asmt_slug = "TestAssessment"
    with factories.single_commit():
      factories.CustomAttributeDefinitionFactory(
          title="multiselect_GCA",
          definition_type="assessment",
          attribute_type="Multiselect",
          multi_choice_options="Option 1,Option 2,Option 3",
      )

      # create assessment with 1 CAV
      asmt = factories.AssessmentFactory(slug=asmt_slug)
      asmt_id = asmt.id
    # update given assessment with empty GCA multiselect type
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", asmt_slug),
        ("multiselect_GCA", "option 1"),
    ]))
    self._check_csv_response(response, {})
    asmt = all_models.Assessment.query.get(asmt_id)
    self.assertEquals(1, len(asmt.custom_attribute_values))
    self.assertEquals(
        "Option 1", asmt.custom_attribute_values[0].attribute_value
    )

  @ddt.data(
      (
          factories.IssueFactory,
          "map:issue",
          "user@example.com",
      ),
      (
          factories.ObjectiveFactory,
          "map:objective versions",
          "user@example.com",
      ),
  )
  @ddt.unpack
  def test_asmt_state_updating_verifiers_with_map_fields(
      self, map_factory, map_column_name, new_verifier
  ):
    """Test assessment In Progress after updating Verifiers and map fields"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      map_object = map_factory()
      spanpshot = factories.SnapshotFactory(
          parent=audit,
          child_id=map_object.id,
          child_type=map_object.__class__.__name__,
          revision=factories.RevisionFactory()
      )
      assessment = factories.AssessmentFactory(
          audit=audit,
          status=all_models.Assessment.DONE_STATE,
      )
      person = factories.PersonFactory(email="verifier@example.com")
      factories.RelationshipFactory(source=assessment, destination=spanpshot)
      factories.AccessControlPersonFactory(
          ac_list=assessment.acr_name_acl_map["Verifiers"],
          person=person,
      )
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).status,
        all_models.Assessment.DONE_STATE)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", assessment.slug),
        ("Verifiers", new_verifier),
        (map_column_name, map_object.slug),
    ]))
    expected_response = {
        "Assessment": {
            "row_warnings": {
                errors.STATE_WILL_BE_IGNORED.format(line=3),
            }
        }
    }
    self._check_csv_response(response, expected_response)
    assessment = all_models.Assessment.query.get(assessment.id)
    verifiers = [v.email for v in assessment.verifiers]
    self.assertEqual(assessment.status, all_models.Assessment.PROGRESS_STATE)
    self.assertEqual(verifiers or [""], [new_verifier])

  @ddt.data(
      (
          factories.IssueFactory,
          "map:issue",
      ),
      (
          factories.ObjectiveFactory,
          "map:objective versions",
      ),
  )
  @ddt.unpack
  def test_asmt_state_updating_empty_verifiers_with_map_fields(
      self, map_factory, map_column_name
  ):
    """Test assessment In Progress after updating empty Verifiers,map fields"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      map_object = map_factory()
      spanpshot = factories.SnapshotFactory(
          parent=audit,
          child_id=map_object.id,
          child_type=map_object.__class__.__name__,
          revision=factories.RevisionFactory()
      )
      assessment = factories.AssessmentFactory(
          audit=audit,
          status=all_models.Assessment.DONE_STATE,
      )
      person = factories.PersonFactory(email="verifier@example.com")
      factories.RelationshipFactory(source=assessment, destination=spanpshot)
      factories.AccessControlPersonFactory(
          ac_list=assessment.acr_name_acl_map["Verifiers"],
          person=person,
      )
    self.assertEqual(
        all_models.Assessment.query.get(assessment.id).status,
        all_models.Assessment.DONE_STATE)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code", assessment.slug),
        ("Verifiers", "--"),
        (map_column_name, map_object.slug),
    ]))
    expected_response = {
        "Assessment": {
            "row_warnings": {
                errors.STATE_WILL_BE_IGNORED.format(line=3),
            }
        }
    }
    self._check_csv_response(response, expected_response)
    assessment = all_models.Assessment.query.get(assessment.id)
    verifiers = [v.email for v in assessment.verifiers]
    self.assertEqual(assessment.status, all_models.Assessment.PROGRESS_STATE)
    self.assertEqual(verifiers or [""], [""])


@ddt.ddt
class TestAssessmentExport(TestCase):
  """Test Assessment object export."""

  def setUp(self):
    """ Set up for Assessment test cases """
    super(TestAssessmentExport, self).setUp()
    self.client.get("/login")
    self.headers = generator.ObjectGenerator.get_header()

  def test_simple_export(self):
    """ Test full assessment export with no warnings"""
    assessment = factories.AssessmentFactory(title="Assessment 1")
    assessment_slug = assessment.slug

    data = [{
        "object_name": "Assessment",
        "filters": {
            "expression": {}
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    self.assertIn(',{},'.format(assessment_slug), response.data)

  # pylint: disable=invalid-name
  def assertColumnExportedValue(self, value, instance, column):
    """ Assertion checks is value equal to exported instance column value."""
    data = [{
        "object_name": instance.__class__.__name__,
        "fields": "all",
        "filters": {
            "expression": {
                "text": str(instance.id),
                "op": {
                    "name": "text_search",
                }
            },
        },
    }]
    instance_dict = self.export_parsed_csv(data)[instance.type][0]
    self.assertEqual(value, instance_dict[column])

  # pylint: disable=invalid-name
  def test_export_assessments_without_map_control(self):
    """Test export assessment without related control instance"""
    audit = factories.AuditFactory()
    assessment = factories.AssessmentFactory(audit=audit)
    factories.RelationshipFactory(source=audit, destination=assessment)
    control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(
        all_models.Revision.id.desc()
    ).first()
    factories.SnapshotFactory(
        parent=audit,
        child_id=control.id,
        child_type=control.__class__.__name__,
        revision_id=revision.id
    )
    db.session.commit()
    self.assertColumnExportedValue("", assessment,
                                   "map:control versions")

  @ddt.data(True, False)
  def test_export_map_control(self, with_map):
    """Test export assessment with and without related control instance"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(
        all_models.Revision.id.desc()
    ).first()
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          parent=audit,
          child_id=control.id,
          child_type=control.__class__.__name__,
          revision_id=revision.id
      )
      if with_map:
        factories.RelationshipFactory(source=snapshot, destination=assessment)
    if with_map:
      val = control.slug
    else:
      val = ""
    self.assertColumnExportedValue(val, assessment, "map:control versions")

  # pylint: disable=invalid-name
  def test_export_with_map_control_mirror_relation(self):
    """Test export assessment with related control instance

    relation assessment -> snapshot
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(
        all_models.Revision.id.desc()
    ).first()
    snapshot = factories.SnapshotFactory(
        parent=audit,
        child_id=control.id,
        child_type=control.__class__.__name__,
        revision_id=revision.id
    )
    db.session.commit()
    factories.RelationshipFactory(destination=snapshot, source=assessment)
    self.assertColumnExportedValue(control.slug, assessment,
                                   "map:control versions")

  # pylint: disable=invalid-name
  def test_export_assessments_with_filters_and_conflicting_ca_names(self):
    """Test exporting assessments with conflicting custom attribute names."""

    # also create an object level custom attribute with a name that clashes
    # with a name of a "regular" attribute
    assessment = factories.AssessmentFactory(title="No template Assessment 1")
    assessment_slug = assessment.slug
    assessment = all_models.Assessment.query.filter(
        all_models.Assessment.slug == assessment_slug).first()
    cad = all_models.CustomAttributeDefinition(
        attribute_type=u"Text",
        title=u"ca title",
        definition_type=u"assessment",
        definition_id=assessment.id
    )
    db.session.add(cad)
    db.session.commit()

    data = [{
        "object_name": "Assessment",
        "fields": ["slug", "title", "description", "status"],
        "filters": {
            "expression": {
                "left": {
                    "left": "code",
                    "op": {"name": "~"},
                    "right": "ASSESSMENT"
                },
                "op": {"name": "AND"},
                "right": {
                    "left": "title",
                    "op": {"name": "~"},
                    "right": "no template Assessment"
                }
            },
            "keys": ["code", "title", "status"],
            "order_by": {
                "keys": [],
                "order": "",
                "compare": None
            }
        }
    }]

    response = self.export_csv(data)
    self.assertIn(u"No template Assessment 1", response.data)

  @ddt.data(
      ("Last Updated By", "new_user@email.com"),
      ("modified_by", "new_user1@email.com"),
  )
  @ddt.unpack
  def test_export_by_modified_by(self, field, email):
    """Test for creation assessment with mapped creator"""
    slug = "TestAssessment"
    with factories.single_commit():
      factories.AssessmentFactory(
          slug=slug,
          modified_by=factories.PersonFactory(email=email),
      )
    data = [{
        "object_name": "Assessment",
        "fields": "all",
        "filters": {
            "expression": {
                "left": field,
                "op": {"name": "="},
                "right": email
            },
        }
    }]

    resp = self.export_parsed_csv(data)["Assessment"]
    self.assertEqual(1, len(resp))
    self.assertEqual(slug, resp[0]["Code*"])

  @ddt.data(
      ("", "In Review", "", True),
      ("", "In Review", "user@example.com", False),
      ("", "Rework Needed", "", True),
      ("12/27/2018", "Completed", "", True),
      ("", "Completed", "", False),
      ("12/27/2018", "Completed", "user@example.com", False),
      ("", "In Progress", "", False),
  )
  @ddt.unpack
  def test_asmt_status_and_verifier(self, date, status, verifiers, warning):
    """Test assessment status validation requiring verifier"""
    audit = factories.AuditFactory()
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Title", "Test title"),
        ("Audit", audit.slug),
        ("Creators", "user@example.com"),
        ("Assignees", "user@example.com"),
        ("Verifiers", verifiers),
        ("Verified Date", date),
        ("State", status),
    ]))

    expected_warnings = {
        'Assessment': {
            'row_warnings': {
                errors.NO_VERIFIER_WARNING.format(
                    line=3,
                    status=status
                )}}}
    if warning:
      self._check_csv_response(response, expected_warnings)
    else:
      self._check_csv_response(response, {})

  def test_import_assessment_without_verifiers(self):
    """Test import with change status and remove verifiers"""
    asmt = factories.AssessmentFactory()
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("State", "In Review"),
        ("Verifiers", "--")
    ]))

    expected_errors = {
        "Assessment": {
            "row_warnings": {
                errors.NO_VERIFIER_WARNING.format(line=3, status='In Review'),
            }
        }
    }
    self._check_csv_response(response, expected_errors)

  @ddt.data(1, 2)
  def test_import_assessment_with_verifiers(self, verifiers_num):
    """Test import with change status and remove verifiers"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(status="In Review")
      for _ in range(verifiers_num):
        user = factories.PersonFactory()
        asmt.add_person_with_role_name(user, "Verifiers")
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("State", "In Review"),
        ("Verifiers", "--")
    ]))

    expected_errors = {
        "Assessment": {
            "row_warnings": {
                errors.STATE_WILL_BE_IGNORED.format(line=3),
            }
        }
    }
    self._check_csv_response(response, expected_errors)

  def test_import_assessment_with_deleted_template(self):
    """Test import with deleted template from exported assessment"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment_template = factories.AssessmentTemplateFactory(audit=audit)
      assessment = factories.AssessmentFactory(audit=audit)
      factories.CustomAttributeDefinitionFactory(
          title='test_attr',
          definition_type='assessment_template',
          definition_id=assessment_template.id,
      )
      factories.CustomAttributeDefinitionFactory(
          title='test_attr',
          definition_type='assessment',
          definition_id=assessment.id,
      )
      db.session.delete(assessment_template)

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Template", ""),
        ("Audit", audit.slug),
        ("Assignees", "user@example.com"),
        ("Creators", "user@example.com"),
        ("Title", "test-{id}Title".format(id=assessment.id)),
        ("test_attr", "asdfafs"),
    ]), dry_run=True)

    self._check_csv_response(response, {})
