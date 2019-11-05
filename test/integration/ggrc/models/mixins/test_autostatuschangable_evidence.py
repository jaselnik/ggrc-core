# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for AutoStatusChangeable mixin related evidence"""
import collections

import ddt
import mock

from ggrc import models
from integration.ggrc.access_control import acl_helper
from integration.ggrc.models import factories
from integration.ggrc.models.mixins import test_autostatuschangable as asc


@ddt.ddt
class TestEvidences(asc.TestMixinAutoStatusChangeableBase):
  """Test case for AutoStatusChangeable evidences handlers"""
  # pylint: disable=invalid-name

  @ddt.data(
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.REWORK_NEEDED,
       models.Assessment.REWORK_NEEDED)
  )
  @ddt.unpack
  def test_evidence_added_status_check(self, kind,
                                       from_status, expected_status):
    """Move Assessment from '{1}' to '{2}' adding evidence of type {0}"""
    assessment = factories.AssessmentFactory(status=from_status)
    related_evidence = {
        'id': None,
        'type': 'Evidence',
        'kind': kind,
        'title': 'google.com',
        'link': 'google.com',
        'source_gdrive_id': 'some_id'
    }
    response = self.api.put(assessment, {
        'actions': {
            'add_related': [related_evidence]
        }
    })
    assessment = self.refresh_object(assessment)
    self.assert200(response, response.json)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.REWORK_NEEDED,
       models.Assessment.REWORK_NEEDED)
  )
  @ddt.unpack
  def test_evidence_remove_related(self, kind,
                                   from_status, expected_status):
    """Move Assessment from '{1}' to '{2}' remove evidence of type {0}"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      evidence = factories.EvidenceFactory(kind=kind,
                                           title='google.com',
                                           link='google.com',
                                           source_gdrive_id='some_id')
      factories.RelationshipFactory(destination=assessment, source=evidence)

    response = self.api.put(assessment, {
        'actions': {
            'remove_related': [{
                'id': evidence.id,
                'type': 'Evidence',
            }]
        }
    })
    assessment = self.refresh_object(assessment)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.REWORK_NEEDED,
       models.Assessment.REWORK_NEEDED)
  )
  @ddt.unpack
  def test_evidence_delete(self, kind, from_status,
                           expected_status):
    """Move Assessment from '{1}' to '{2}' delete evidence of type {0}"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      evidence = factories.EvidenceFactory(kind=kind,
                                           title='google.com',
                                           link='google.com',
                                           source_gdrive_id='some_id')
      factories.RelationshipFactory(destination=assessment, source=evidence)
    assessment_id = assessment.id
    response = self.api.delete(evidence)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.FINAL_STATE,
       models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.REWORK_NEEDED,
       models.Assessment.REWORK_NEEDED)
  )
  @ddt.unpack
  def test_evidence_update_status_check(self, kind, from_status,
                                        expected_status):
    """Move Assessment from '{1}' to '{2}' update evidence of type {0}"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      evidence = factories.EvidenceFactory(kind=kind,
                                           title='google.com',
                                           link='google.com',
                                           source_gdrive_id='some_id')
      factories.RelationshipFactory(destination=assessment, source=evidence)
    assessment_id = assessment.id
    response = self.api.modify_object(evidence, {
        'title': 'New evidence',
        'link': 'New evidence',
    })
    assessment = self.refresh_object(assessment, assessment_id)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('URL', models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      ('FILE', models.Assessment.FINAL_STATE, models.Assessment.FINAL_STATE),
  )
  @ddt.unpack
  def test_evidence_import_unmap(self, kind, from_status, expected_status):
    """Move Assessment from '{1}' to '{2}' if evidence unmapped in import."""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      evidence = factories.EvidenceFactory(
          kind=kind,
          title='google.com',
          link='google.com',
          source_gdrive_id='some_id'
      )
      factories.RelationshipFactory(destination=assessment, source=evidence)

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("Evidence URL", ""),
        ("Evidence File", ""),
    ]))
    self._check_csv_response(response, {})
    assessment = self.refresh_object(assessment)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      models.Assessment.DONE_STATE,
      models.Assessment.FINAL_STATE,
  )
  def test_put_empty_evidence_data(self, status):
    """Test put empty evidence data assessment status changed"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=status)
      assessment_id = assessment.id
      evidence = factories.EvidenceUrlFactory()
      factories.RelationshipFactory(destination=assessment,
                                    source=evidence)
    self.api.put(evidence, {})
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(assessment.status, models.Assessment.PROGRESS_STATE)

  @ddt.data(
      ("notes", models.Assessment.DONE_STATE),
      ("notes", models.Assessment.FINAL_STATE),
      ("description", models.Assessment.DONE_STATE),
      ("description", models.Assessment.FINAL_STATE),
  )
  @ddt.unpack
  def test_put_no_affect_evidence(self, attr_name, status):
    """Test assessment status not changed unimportant evidence attr changed"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=status)
      assessment_id = assessment.id
      evidence = factories.EvidenceUrlFactory()
      evidence_id = evidence.id
      factories.RelationshipFactory(destination=assessment,
                                    source=evidence)
    self.api.put(evidence, {attr_name: "test text"})
    assessment = self.refresh_object(assessment, assessment_id)
    evidence = self.refresh_object(evidence, evidence_id)
    self.assertEqual(assessment.status, status)
    self.assertEqual(getattr(evidence, attr_name), "test text")

  @ddt.data(
      models.Assessment.DONE_STATE,
      models.Assessment.FINAL_STATE,
  )
  def test_put_affected_evidence(self, status):
    """Test put affected of evidence data assessment status changed"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=status)
      assessment_id = assessment.id
      evidence = factories.EvidenceUrlFactory()
      factories.RelationshipFactory(destination=assessment,
                                    source=evidence)
      person_id = factories.PersonFactory().id
      role_id = models.AccessControlRole.query.filter(
          models.AccessControlRole.object_type == "Evidence",
          models.AccessControlRole.name == 'Admin',
      ).one().id
    self.api.put(
        evidence,
        {
            "access_control_list": [
                acl_helper.get_acl_json(role_id, person_id),
            ]
        }
    )
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(assessment.status, models.Assessment.PROGRESS_STATE)

  @ddt.data(
      models.Assessment.DONE_STATE,
      models.Assessment.FINAL_STATE,
  )
  def test_put_acl_evidence(self, status):
    """Test put acl of evidence data assessment status changed"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=status)
      assessment_id = assessment.id
      evidence = factories.EvidenceUrlFactory()
      factories.RelationshipFactory(destination=assessment,
                                    source=evidence)
      person = factories.PersonFactory()
      role = models.AccessControlRole.query.filter(
          models.AccessControlRole.object_type == "Evidence",
          models.AccessControlRole.name == 'Admin',
      ).one()
      assessment.add_person_with_role(person, role)
    self.api.put(evidence, {"access_control_list": []})
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(assessment.status, models.Assessment.PROGRESS_STATE)

  @ddt.data(
      ("notes", models.Assessment.DONE_STATE),
      ("notes", models.Assessment.FINAL_STATE),
      ("description", models.Assessment.DONE_STATE),
      ("description", models.Assessment.FINAL_STATE),
  )
  @ddt.unpack
  def test_put_all_affected_evidence(self, attr_name, status):
    """Test put all affected of evidence data assessment status changed"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=status)
      assessment_id = assessment.id
      evidence = factories.EvidenceUrlFactory()
      evidence_id = evidence.id
      factories.RelationshipFactory(destination=assessment,
                                    source=evidence)
      person_id = factories.PersonFactory().id
      role_id = models.AccessControlRole.query.filter(
          models.AccessControlRole.object_type == "Evidence",
          models.AccessControlRole.name == 'Admin',
      ).one().id
    self.api.put(
        evidence,
        {
            attr_name: "test text",
            "access_control_list": [
                acl_helper.get_acl_json(role_id, person_id),
            ]
        }
    )
    assessment = self.refresh_object(assessment, assessment_id)
    evidence = self.refresh_object(evidence, evidence_id)
    self.assertEqual(assessment.status, models.Assessment.PROGRESS_STATE)
    self.assertEqual(getattr(evidence, attr_name), "test text")

  def test_acl_not_implemented(self):
    """Test error due to tracking mocked evidence and asmt object"""
    from ggrc.utils.statusaffected import statusaffected

    evindece = mock.MagicMock()
    evindece.__class__.__name__ = "Evidence"
    affected_obj = mock.MagicMock()
    affected_obj.__class__.__name__ = "Assessment"

    with self.assertRaises(NotImplementedError) as exception:
      statusaffected.StatusAffectedChanges(
        evindece, affected_obj).was_affected()

      self.assertEqual(
          exception.exception.message,
          'Only Roleable instances can be tracked in a current tracker'
      )
