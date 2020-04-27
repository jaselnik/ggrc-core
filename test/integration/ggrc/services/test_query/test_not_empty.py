# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for not_empty operator."""

import ddt
import mock

from ggrc.models import all_models

from integration import ggrc as test_ggrc
from integration.ggrc import factories
from integration.ggrc import api_helper
from integration.ggrc import query_helper
from integration.ggrc import review


@ddt.ddt
class TestNotEmptyRevisions(test_ggrc.TestCase, query_helper.WithQueryApi):
  """Test for correctness of `not_empty_revisions` operator."""

  def setUp(self):  # pylint: disable=missing-docstring
    super(TestNotEmptyRevisions, self).setUp()
    self.api = api_helper.Api()
    self.client.get("/login")

  def _turn_on_bg_indexing(self):
    """Helper method to turn on bg indexing."""
    from ggrc.fulltext import listeners
    from ggrc.models import background_task

    listeners.reindex_on_commit = background_task.reindex_on_commit
    self.init_taskqueue()

  def _turn_off_bg_indexing(self):
    """Helper method to turn off bg indexing."""
    from ggrc.fulltext import listeners

    listeners.reindex_on_commit = lambda: True
    self.del_taskueue()

  def _query_not_empty_revisions(self, instance, ignore_relationships=False):
    """Helper function to qeury not empty revisions with query API."""
    return self._get_first_result_set(
        {
            "object_name": "Revision",
            "type": "ids",
            "filters": {
                "expression": {
                    "op": {"name": "not_empty_revisions"},
                    "resource_type": instance.type,
                    "resource_id": instance.id,
                    "ignore_relationships": ignore_relationships,
                },
            },
        },
        "Revision",
        "ids",
    )

  @staticmethod
  def _count_revisions(instance):
    """Helper function to count instance revisions."""
    return all_models.Revision.query.filter(
        all_models.Revision.resource_type == instance.type,
        all_models.Revision.resource_id == instance.id,
    ).count()

  @staticmethod
  def _refresh_instance(instance_type, instance_id):
    """Helper function to refresh instance from db."""
    instance_cls = getattr(all_models, instance_type, None)
    if instance_cls is None:
      raise ValueError("'{}' is not a valid instance type"
                       .format(instance_type))
    return instance_cls.query.get(instance_id)

  def test_not_empty_revisions(self):
    """Test `not_empty_revisions` returns revisions with changes."""
    self._turn_on_bg_indexing()
    instance = factories.ProgramFactory()

    def edit_without_changes(instance):
      """Helper function to perform instance edit without actual changes."""
      response = self.api.put(instance, {})
      self.assert200(response)

    edit_without_changes(instance)
    instance = self._refresh_instance(instance.type, instance.id)
    revisions_count = self._count_revisions(instance)
    not_empty_revisions = self._query_not_empty_revisions(instance)

    self.assertEqual(revisions_count, 2)
    self.assertEqual(len(not_empty_revisions), 1)
    self._turn_off_bg_indexing()

  def test_review_status(self):
    """Test not_empty_revisions works correcly with review status change."""
    instance = factories.ProgramFactory()

    def mark_as_reviewed(instance):
      """Helper function to mark `instance` as reviewed."""
      response = self.api.post(
          all_models.Review,
          {
              "review": {
                  "reviewable": {
                      "type": instance.type,
                      "id": instance.id,
                  },
                  "context": None,
                  "notification_type": "email",
                  "status": all_models.Review.STATES.REVIEWED,
                  "access_control_list": review.build_reviewer_acl(),
              },
          },
      )
      self.assertStatus(response, 201)

    mark_as_reviewed(instance)
    instance = self._refresh_instance(instance.type, instance.id)
    revisions_count = self._count_revisions(instance)
    not_empty_revisions = self._query_not_empty_revisions(instance)

    self.assertEqual(revisions_count, 2)
    self.assertEqual(len(not_empty_revisions), 3)

  @ddt.data(
      {"ignore_relationships": True, "exp_revs_count": 1},
      {"ignore_relationships": False, "exp_revs_count": 3},
  )
  @ddt.unpack
  def test_ignore_relationships(self, ignore_relationships, exp_revs_count):
    """Test `ignore_relationships` flag works as expected.

    If `ignore_relationships` is passed with `True` value, the query API
    operator should return only Revisions of the resource.
    If `ignore_relationships` is passed with `False` value, the query API
    operator should return Revisions of the resource as well as of it's
    Relationships.
    """
    with factories.single_commit():
      objective = factories.ObjectiveFactory()
      data_asset = factories.DataAssetFactory()
      metric = factories.MetricFactory()
      with mock.patch('ggrc.models.relationship.is_external_app_user',
                      return_value=True):
        factories.RelationshipFactory(source=objective, destination=data_asset)
        factories.RelationshipFactory(source=metric, destination=objective)

    not_empty_revisions = self._query_not_empty_revisions(
        objective, ignore_relationships
    )

    self.assertEqual(len(not_empty_revisions), exp_revs_count)

  def test_ignore_modified_relationship_revs(self):  # noqa pylint: disable=invalid-name
    """Test `not_empty_revisions` ignores modified relationship's revisions."""
    with factories.single_commit():
      program = factories.ProgramFactory()
      comment = factories.CommentFactory()
      progam_comment_rel = factories.RelationshipFactory(
          source=program,
          destination=comment,
      )
      factories.RevisionFactory(
          obj=progam_comment_rel,
          action="modified",
      )

    program_id = program.id
    progam_comment_rel_id = progam_comment_rel.id

    not_empty_program_revisions = self._query_not_empty_revisions(
        instance=program, ignore_relationships=False)

    program = self._refresh_instance(program.type, program_id)
    progam_comment_rel = self._refresh_instance(
        progam_comment_rel.type, progam_comment_rel_id)
    self.assertEqual(
        len(not_empty_program_revisions),
        (
            self._count_revisions(program) +
            self._count_revisions(progam_comment_rel) -
            1  # "modified" Revisions of the Relationship
        )
    )
