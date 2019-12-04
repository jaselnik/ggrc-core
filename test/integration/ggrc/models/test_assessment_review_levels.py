# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=missing-docstring, invalid-name

import json

import ddt

from ggrc.models import all_models, review_level
from ggrc.models.assessment_template import VerificationWorkflow

from integration import ggrc
from integration.ggrc.models import factories


def generate_mlv_assessment(
    test_case,
    workflow,
    levels_count,
    with_verifiers=False,
):
  with factories.single_commit():
    audit = factories.AuditFactory()
    control = factories.ControlFactory()

    # pylint: disable=protected-access
    snapshot = test_case._create_snapshots(audit, [control])[0]

    template = factories.AssessmentTemplateFactory(
        verification_workflow=workflow,
        review_levels_count=levels_count,
    )

    review_levels = []

    if with_verifiers:
      for i in range(levels_count):
        person0 = factories.PersonFactory(
            email="reviewer_{}_0@example.com".format(i),
        )
        person1 = factories.PersonFactory(
            email="reviewer_{}_1@example.com".format(i),
        )

        review_level_dict = {
            "users": [{
                "id": person0.id,
            }, {
                "id": person1.id,
            }]
        }

        review_levels.append(review_level_dict)

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
          "review_levels": review_levels,
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

  def test_successful_creation_default(self):
    """
      Test that assessment template is properly created even though
      neither review_levels_count nor verification_workflow are
      provided in POST data.
    """

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
            },
        },
    )

    self.assert201(response)

    created_template_dict = json.loads(response.data)["assessment_template"]

    self.assertEqual(
        created_template_dict["review_levels_count"],
        None,
    )

    self.assertEqual(
        created_template_dict["verification_workflow"],
        VerificationWorkflow.STANDARD,
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
        "Number of review levels should be in range [2, 10] if multiple"
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


@ddt.ddt
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

  @ddt.data(
      review_level.ReviewLevel.Status.IN_REVIEW,
      review_level.ReviewLevel.Status.REVIEWED,
  )
  def test_review_level_bad_status(self, status):
    """
      Test that setting status of assessment review level
      to 'In Review' fails due to missing verifiers.
    """
    assessment = generate_mlv_assessment(self, VerificationWorkflow.MLV, 1)

    review_level_id = assessment.review_levels[0].id

    response = self.api.put(assessment, {
        "review_levels": [{
            "id": review_level_id,
            "status": status,
        }],
    })

    self.assert400(response)
    self.assertEqual(
        json.loads(response.data)["message"],
        "Can't change review_level with id = {} from '{}' "
        "due to missing verifiers.".format(
            review_level_id,
            review_level.ReviewLevel.Status.NOT_STARTED,
        )
    )

    _review_level = review_level.ReviewLevel.query.get(review_level_id)

    self.assertEqual(
        _review_level.status,
        review_level.ReviewLevel.Status.NOT_STARTED,
    )

    self.assertIsNone(
        _review_level.verified_by,
    )

  @ddt.data(
      review_level.ReviewLevel.Status.IN_REVIEW,
      review_level.ReviewLevel.Status.REVIEWED,
  )
  def test_review_level_status_properly_set(self, status):
    """
      It should be allowed to change status for review
      level if it's the only one and verifiers are
      present.
    """

    assessment = generate_mlv_assessment(
        self,
        VerificationWorkflow.MLV,
        1,
        with_verifiers=True,
    )

    review_level_id = assessment.review_levels[0].id

    response = self.api.put(assessment, {
        "review_levels": [{
            "id": review_level_id,
            "status": status,
        }],
    })

    self.assert200(response)

    _review_level = review_level.ReviewLevel.query.get(review_level_id)

    self.assertEqual(
        _review_level.status,
        status,
    )

    self.assertEqual(
        _review_level.level_number,
        1,
    )

    self.assertIsNone(
        _review_level.verified_by,
    )

  @ddt.data(0, 1)
  def test_adding_people_to_existing_review_levels(self, review_level_idx):
    assessment = generate_mlv_assessment(
        self,
        VerificationWorkflow.MLV,
        2,
    )

    review_level_id = assessment.review_levels[review_level_idx].id

    person0 = factories.PersonFactory(
        email="reviewer0@example.com",
    )
    person1 = factories.PersonFactory(
        email="reviewer1@example.com",
    )

    self.api.put(assessment, {
        "review_levels": [{
            "id": review_level_id,
            "users": [{
                "id": person0.id,
            }, {
                "id": person1.id,
            }]
        }],
    })

    _review_level = review_level.ReviewLevel.query.get(review_level_id)

    self.assertEqual(len(_review_level.verifiers), 2)

    self.assertEqual(
        _review_level.verifiers[0].email,
        "reviewer0@example.com",
    )

    self.assertEqual(
        _review_level.verifiers[1].email,
        "reviewer1@example.com",
    )

  @ddt.data(0, 1)
  def test_removing_people_from_review_levels(self, review_level_idx):
    assessment = generate_mlv_assessment(
        self,
        VerificationWorkflow.MLV,
        2,
        with_verifiers=True,
    )

    review_level_id = assessment.review_levels[review_level_idx].id

    self.api.put(assessment, {
        "review_levels": [{
            "id": review_level_id,
            "users": [],
        }],
    })

    _review_level = review_level.ReviewLevel.query.get(review_level_id)

    self.assertEqual(len(_review_level.verifiers), 0)
