# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=missing-docstring, invalid-name

import json
from datetime import datetime

import ddt

from ggrc import login
from ggrc.models import all_models, review_level
from ggrc.models.assessment_template import VerificationWorkflow

from integration import ggrc
from integration.ggrc.models import factories


# pylint: disable=protected-access
def generate_mlv_assessment(test_case, workflow, levels_count):
  with factories.single_commit():
    audit = factories.AuditFactory()
    control = factories.ControlFactory()
    snapshot = test_case._create_snapshots(audit, [control])[0]
    template = factories.AssessmentTemplateFactory(
        verification_workflow=workflow,
        review_levels_count=levels_count,
    )

  response = test_case.api.post(all_models.Assessment, {
      "assessment": {
          "_generated": True,
          "audit": {
              "id": audit.id,
              "type": "Audit"
          },
          "object": {
              "id": snapshot.id,
              "type": "Snapshot"
          },
          "context": {
              "id": audit.context.id,
              "type": "Context"
          },
          "title": "Temp title",
          "template": {
              "id": template.id,
              "type": "AssessmentTemplate",
          },
          "review_levels": [],
      }
  })

  assessment_id = json.loads(response.data)["assessment"]["id"]

  return all_models.Assessment.query.get(assessment_id)


@ddt.ddt
class TestAssessmentTemplateCreation(ggrc.TestCase):

  def setUp(self):
    super(TestAssessmentTemplateCreation, self).setUp()

    self.api = ggrc.api_helper.Api()

  @ddt.data(
      {
          "workflow": VerificationWorkflow.SOX302,
          "review_levels_count": 100,
      },
      {
          "workflow": VerificationWorkflow.STANDARD,
          "review_levels_count": 100,
      },
      {
          "workflow": VerificationWorkflow.MLV,
          "review_levels_count": 10,
      },
      {
          "workflow": VerificationWorkflow.MLV,
          "review_levels_count": 3,
      },
  )
  @ddt.unpack
  def test_successful_creation(self, workflow, review_levels_count):
    audit = ggrc.models.factories.AuditFactory()

    response = self.api.post(
        all_models.AssessmentTemplate,
        {
            "assessment_template": {
                "audit": {"id": audit.id},
                "context": {"id": audit.context.id},
                "default_people": {
                    "assignees": "Admin",
                    "verifiers": "Admin",
                },
                "title": "AssessmentTemplate Title",
                "verification_workflow": workflow,
                "review_levels_count": review_levels_count,
            },
        },
    )

    self.assert201(response)

    created_template_dict = json.loads(response.data)["assessment_template"]

    self.assertEqual(
        created_template_dict["review_levels_count"],
        review_levels_count,
    )

    self.assertEqual(
        created_template_dict["verification_workflow"],
        workflow,
    )

  @ddt.data(
      {
          "workflow": VerificationWorkflow.MLV,
          "review_levels_count": 0,
      },
      {
          "workflow": VerificationWorkflow.MLV,
          "review_levels_count": 11,
      },
  )
  @ddt.unpack
  def test_failed_creation_bad_review_levels_count(
      self,
      workflow,
      review_levels_count
  ):
    audit = ggrc.models.factories.AuditFactory()

    response = self.api.post(
        all_models.AssessmentTemplate,
        {
            "assessment_template": {
                "audit": {"id": audit.id},
                "context": {"id": audit.context.id},
                "default_people": {
                    "assignees": "Admin",
                    "verifiers": "Admin",
                },
                "title": "AssessmentTemplate Title",
                "verification_workflow": workflow,
                "review_levels_count": review_levels_count,
            },
        },
    )

    self.assert400(response)
    self.assertEqual(
        json.loads(response.data),
        "Number of review levels should be in range [1, 11] if multiple"
        " review levels are enabled.",
    )

  def test_failed_creation_bad_workflow(self):
    audit = ggrc.models.factories.AuditFactory()

    response = self.api.post(
        all_models.AssessmentTemplate,
        {
            "assessment_template": {
                "audit": {"id": audit.id},
                "context": {"id": audit.context.id},
                "default_people": {
                    "assignees": "Admin",
                    "verifiers": "Admin",
                },
                "title": "AssessmentTemplate Title",
                "verification_workflow": "INCORRECT WORKFLOW",
                "review_levels_count": 42,
            },
        },
    )

    self.assert400(response)
    self.assertEqual(
        json.loads(response.data),
        "Verification workflow should be one of STANDARD, SOX302, MLV."
    )


@ddt.ddt
class TestAssessmentGeneration(ggrc.TestCase):
  def setUp(self):
    super(TestAssessmentGeneration, self).setUp()

    self.api = ggrc.api_helper.Api()

  @ddt.data(
      {
          "workflow": VerificationWorkflow.MLV,
          "review_levels_count": 10,
      },
      {
          "workflow": VerificationWorkflow.MLV,
          "review_levels_count": 3,
      },
  )
  @ddt.unpack
  def test_successful_generation(self, workflow, review_levels_count):
    assessment = generate_mlv_assessment(self, workflow, review_levels_count)

    self.assertEqual(
        assessment.verification_workflow,
        workflow,
    )

    self.assertEqual(
        assessment.review_levels_count,
        review_levels_count,
    )

    self.assertEqual(
        len(assessment.review_levels),
        review_levels_count,
    )

    for i in range(review_levels_count):
      self.assertEqual(
          assessment.review_levels[i].status,
          "Not Started",
      )

      self.assertEqual(
          assessment.review_levels[i].level_number,
          i + 1,
      )


class TestAssessmentUpdate(ggrc.TestCase):

  def setUp(self):
    super(TestAssessmentUpdate, self).setUp()

    self.api = ggrc.api_helper.Api()

  def test_mlv_fields_are_immutable(self):
    """
      Test that verification_workflow and review_levels_count fields
      can't be modified via API PUT requests.
    """

    assessment = generate_mlv_assessment(self, VerificationWorkflow.MLV, 4)

    response = self.api.put(assessment, {
        "verification_workflow": VerificationWorkflow.STANDARD,
        "review_levels_count": 5,
    })

    assessment_dict = json.loads(response.data)["assessment"]

    self.assertEqual(
        assessment_dict["verification_workflow"],
        VerificationWorkflow.MLV,
    )

    self.assertEqual(
        assessment_dict["review_levels_count"],
        4,
    )

  def test_review_level_fields_update(self):
    assessment = generate_mlv_assessment(self, VerificationWorkflow.MLV, 1)

    review_level_id = assessment.review_levels[0].id
    current_user_id = login.get_current_user_id()
    completed_at = datetime.now()

    self.api.put(assessment, {
        "review_levels": [{
            "id": review_level_id,
            "status": "In Review",
            "person_id": current_user_id,
            "completed_at": completed_at,
        }],
    })

    _review_level = review_level.ReviewLevel.query.get(review_level_id)

    self.assertEqual(
        _review_level.status,
        "In Review",
    )

    self.assertEqual(
        _review_level.verified_by,
        current_user_id,
    )
