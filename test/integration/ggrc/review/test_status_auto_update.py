# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base TestCase for automatic review status update."""

import ddt

from ggrc.models import all_models
from ggrc.snapshotter import rules

from integration.ggrc import TestCase, generator
from integration.ggrc.models import factories

from integration.ggrc.api_helper import Api
from integration.ggrc.review import generate_review_object


@ddt.ddt
class TestReviewStatusUpdate(TestCase):
  """Base TestCase class automatic review status update."""

  def setUp(self):
    super(TestReviewStatusUpdate, self).setUp()
    self.api = Api()

    self.generator = generator.ObjectGenerator()

  def test_gca(self):
    """if GCA of reviewable is changed review -> unreviewed"""
    with factories.single_commit():
      ca_factory = factories.CustomAttributeDefinitionFactory
      gca = ca_factory(
          definition_type="program",
          title="rich_test_gca",
          attribute_type="Rich Text"
      )
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
    review_id = review.id
    reviewable = review.reviewable

    review = all_models.Review.query.get(review_id)

    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

    self.api.modify_object(
        reviewable, {
            "custom_attribute_values":
            [{
                "custom_attribute_id": gca.id,
                "attribute_value": "new_value",
            }],
        }
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

  def test_update_gca(self):
    """if existing GCA value changed review -> unreviewed"""
    with factories.single_commit():
      ca_factory = factories.CustomAttributeDefinitionFactory
      gca = ca_factory(
          definition_type="program",
          title="rich_test_gca",
          attribute_type="Rich Text"
      )
      program = factories.ProgramFactory()

      program.custom_attribute_values = [{
          "attribute_value": "starting_value",
          "custom_attribute_id": gca.id
      }]
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
    review_id = review.id
    reviewable = review.reviewable

    review = all_models.Review.query.get(review_id)

    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

    self.api.modify_object(
        reviewable, {
            "custom_attribute_values":
            [{
                "custom_attribute_id": gca.id,
                "attribute_value": "new_value",
            }],
        }
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

  @ddt.data("custom attr", "slug", "self")
  def test_gca_with_varying_titles(self, title):
    """if GCA with any title is changed review -> unreviewed"""
    with factories.single_commit():
      ca_factory = factories.CustomAttributeDefinitionFactory
      gca = ca_factory(
          definition_type="program",
          title=title,
          attribute_type="Rich Text"
      )
      program = factories.ProgramFactory()

      program.custom_attribute_values = [{
          "attribute_value": "starting_value",
          "custom_attribute_id": gca.id
      }]
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
    review_id = review.id
    reviewable = review.reviewable

    review = all_models.Review.query.get(review_id)

    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

    self.api.modify_object(
        reviewable, {
            "custom_attribute_values":
            [{
                "custom_attribute_id": gca.id,
                "attribute_value": "new_value",
            }],
        }
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

  def test_reference_url(self):
    """If reference url is updated state should not updated"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      doc = factories.DocumentReferenceUrlFactory(
          title="Simple title",
          link="some_url.com",
          description="mega description",
          parent_obj={
              "id": program.id,
              "type": "Program"
          }
      )
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
    review_id = review.id

    self.api.modify_object(doc, {"link": "new_link.com"})
    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

  def test_acl_roles(self):
    """Update of reviewable ACL shouldn't change review status"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
    review_id = review.id

    ac_role_id = all_models.AccessControlRole.query.filter_by(
        name="Primary Contacts", object_type="Program"
    ).one().id

    user_id = all_models.Person.query.filter_by(
        email="user@example.com"
    ).one().id

    self.api.modify_object(
        program, {
            "access_control_list":
            [{
                "ac_role_id": ac_role_id,
                "person": {
                    "id": user_id
                },
            }],
        }
    )
    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

  def test_comments(self):
    """Add comment to reviewable shouldn't update review state"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
    review_id = review.id

    self.generator.generate_comment(
        program, "Verifiers", "some comment", send_notification="false"
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

  def test_mapping_non_snapshotable(self):
    """Map non-snapshotable shouldn't change review status"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
      review_id = review.id

    factories.RelationshipFactory(
        source=program, destination=factories.IssueFactory()
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

  @ddt.data(*rules.Types.all)
  def test_map_snapshotable(self, snapshotable):
    """Map '{}' should change review status"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED, reviewable=program
      )
      review_id = review.id

    self.generator.generate_relationship(
        source=program,
        destination=factories.get_model_factory(snapshotable)(),
        context=None,
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

  def test_unmap_snapshotable(self):
    """Unmap snapshotable should change review status"""
    program = factories.ProgramFactory()
    resp, review = generate_review_object(program)
    review_id = review.id

    _, rel = self.generator.generate_relationship(
        source=program,
        destination=factories.ProductFactory(),
        context=None,
    )

    review = all_models.Review.query.get(review_id)
    resp = self.api.modify_object(
        review, {"status": all_models.Review.STATES.REVIEWED}
    )
    self.assert200(resp)

    resp = self.api.delete(rel)
    self.assert200(resp)
    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

  @ddt.data(*rules.Types.ignore)
  def test_map_nonsnapshotable(self, nonsnapshotable):
    """Map '{}' shouldn't change review status"""
    program = factories.ProgramFactory()
    _, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    review_id = review.id

    review = all_models.Review.query.get(review_id)

    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

    self.generator.generate_relationship(
        source=program,
        destination=factories.get_model_factory(nonsnapshotable)(),
        context=None,
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

  def test_unmap_nonsnapshotable(self):
    """Unmap nonsnapshotable shouldn't change review status"""
    program = factories.ProgramFactory()
    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    review_id = review.id
    _, rel = self.generator.generate_relationship(
        source=program,
        destination=factories.ProgramFactory(),
        context=None,
    )

    review = all_models.Review.query.get(review_id)
    resp = self.api.modify_object(
        review, {"status": all_models.Review.STATES.REVIEWED}
    )
    self.assert200(resp)
    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

    resp = self.api.delete(rel)
    self.assert200(resp)
    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.REVIEWED)

  def test_proposal_apply(self):
    """Reviewable object changed via proposal -> review.state-> UNREVIEWED"""
    program = factories.ProgramFactory()
    _, review = generate_review_object(program)

    review_id = review.id

    proposal_content = {
        "fields": {
            "title": "new title"
        },
    }
    proposal = factories.ProposalFactory(
        instance=program, content=proposal_content, agenda="agenda content"
    )
    self.api.modify_object(proposal, {"status": proposal.STATES.APPLIED})

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

  def test_review_status_update(self):
    """Test updating folder preserves review status"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      factories.ReviewFactory(
          reviewable=program,
          status=all_models.Review.STATES.REVIEWED,
      )
    self.api.put(program, {"folder": factories.random_str()})
    program = all_models.Program.query.get(program.id)
    self.assertEqual(program.review.status, all_models.Review.STATES.REVIEWED)
