# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for /api/snapshot endpoints."""
import mock
import sqlalchemy as sa

from ggrc.models import all_models
from integration.ggrc import api_helper
from integration.ggrc import services
from integration.ggrc.models import factories


class TestSnapshotResourceDelete(services.TestCase):
  """Tests for special snapshots api endpoints."""

  def setUp(self):
    super(TestSnapshotResourceDelete, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  def _get_related_objects(self, snapshot_id):
    """Helper for retrieving snapshot related objects."""
    url = "/api/snapshots/{}/related_objects".format(snapshot_id)
    return self.client.get(url).json

  def check_no_relationship(self, snapshot_c_id):
    """Check that snapshot have no relationships"""
    rel = all_models.Relationship
    relationships = rel.query.filter(
        sa.or_(
            sa.and_(
                rel.destination_id == snapshot_c_id,
                rel.destination_type == all_models.Snapshot.__name__),
            sa.and_(
                rel.source_id == snapshot_c_id,
                rel.source_type == all_models.Snapshot.__name__)
        )).all()
    self.assertFalse(relationships)

  def test_snapshot_del_w_asmt(self):
    """Test validation of deletion of snapshot with mapped assessment, issue"""
    # pylint: disable=too-many-locals, too-many-statements
    # Prepare assessment with control and objective and raised issue
    rel = all_models.Relationship

    control = factories.ControlFactory()
    revision_c = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(all_models.Revision.id.desc()).first()
    with factories.single_commit():
      program = factories.ProgramFactory()
      audit = factories.AuditFactory(program=program)
      snapshot_c = factories.SnapshotFactory(
          parent=audit,
          child_id=control.id,
          child_type=control.__class__.__name__,
          revision_id=revision_c.id)
      snapshot_c_id = snapshot_c.id
      assessment = factories.AssessmentFactory(audit=audit)
      assessment_id = assessment.id
      issue = factories.IssueFactory()
      issue_id = issue.id
      factories.RelationshipFactory(source=program, destination=control)
      factories.RelationshipFactory(source=program, destination=audit)
      factories.RelationshipFactory(source=snapshot_c, destination=audit)
      factories.RelationshipFactory(source=assessment, destination=audit)
      factories.RelationshipFactory(source=snapshot_c, destination=assessment)
      factories.RelationshipFactory(source=issue, destination=audit)
      factories.RelationshipFactory(source=issue, destination=assessment)

    # Check related_objects endpoint
    related_objects = self._get_related_objects(snapshot_c_id)
    self.assertEqual(len(related_objects), 3)
    self.assertEqual(len(related_objects["Assessment"]), 1)
    self.assertEqual(len(related_objects["Audit"]), 1)
    self.assertEqual(len(related_objects["Issue"]), 1)

    # Check validation forbids deletion with linked asmts and issues
    resp = self.api.delete(all_models.Snapshot, snapshot_c_id)
    self.assertEqual(resp.status_code, 409)

    # Unmap assessment and issue from control snapshot
    issue = all_models.Issue.query.get(issue_id)
    assessment = all_models.Assessment.query.get(assessment_id)
    snapshot_c = all_models.Snapshot.query.get(snapshot_c_id)
    issue_snapshot = rel.find_related(issue, snapshot_c).id
    asmt_snapshot = rel.find_related(assessment, snapshot_c).id
    self.api.delete(rel, issue_snapshot)
    self.api.delete(rel, asmt_snapshot)

    # Check related_objects endpoint
    related_objects = self._get_related_objects(snapshot_c_id)
    self.assertEqual(len(related_objects), 1)
    self.assertEqual(len(related_objects["Audit"]), 1)

    # Check successful deletion of control snapshot
    resp = self.api.delete(all_models.Snapshot, snapshot_c_id)
    self.assertEqual(resp.status_code, 200)
    self.assertFalse(all_models.Snapshot.query.get(snapshot_c_id))

    # Check that snapshot unmapped from all objects successfully
    self.check_no_relationship(snapshot_c_id)

  def test_snapshot_del_w_snapshot(self):
    """Test validation of deletion of snapshot mapped to another snapshot"""
    # pylint: disable=too-many-locals, too-many-statements
    # Prepare assessment with control and objective and raised issue
    rel = all_models.Relationship

    control = factories.ControlFactory()
    control_id = control.id
    revision_c = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.__class__.__name__
    ).order_by(all_models.Revision.id.desc()).first()
    objective = factories.ObjectiveFactory()
    objective_id = objective.id
    revision_o = all_models.Revision.query.filter(
        all_models.Revision.resource_id == objective.id,
        all_models.Revision.resource_type == objective.__class__.__name__
    ).order_by(all_models.Revision.id.desc()).first()
    with factories.single_commit():
      program = factories.ProgramFactory()
      audit = factories.AuditFactory(program=program)
      snapshot_c = factories.SnapshotFactory(
          parent=audit,
          child_id=control.id,
          child_type=control.__class__.__name__,
          revision_id=revision_c.id)
      snapshot_o = factories.SnapshotFactory(
          parent=audit,
          child_id=objective.id,
          child_type=objective.__class__.__name__,
          revision_id=revision_o.id)
      snapshot_c_id = snapshot_c.id
      factories.RelationshipFactory(source=program, destination=control)
      factories.RelationshipFactory(source=program, destination=audit)
      with mock.patch('ggrc.models.relationship.is_external_app_user',
                      return_value=True):
        factories.RelationshipFactory(source=objective, destination=control)
        factories.RelationshipFactory(source=snapshot_o, destination=audit)
        factories.RelationshipFactory(source=snapshot_c,
                                      destination=snapshot_o)
      factories.RelationshipFactory(source=snapshot_c, destination=audit)

    # Check related_objects endpoint
    related_objects = self._get_related_objects(snapshot_c_id)
    self.assertEqual(len(related_objects), 2)
    self.assertEqual(len(related_objects["Audit"]), 1)
    self.assertEqual(len(related_objects["Snapshot"]), 1)

    # Check validation forbids deletion with linked Snapshot
    resp = self.api.delete(all_models.Snapshot, snapshot_c_id)
    self.assertEqual(resp.status_code, 409)

    # Unmap original control and objective
    control = all_models.Control.query.get(control_id)
    objective = all_models.Objective.query.get(objective_id)
    control_objective = rel.find_related(control, objective).id
    with self.api.as_external():
      resp = self.api.delete(rel, control_objective)
      self.assert200(resp, resp)

    # Check successful deletion of control snapshot
    resp = self.api.delete(all_models.Snapshot, snapshot_c_id)
    self.assertEqual(resp.status_code, 200)
    self.assertFalse(all_models.Snapshot.query.get(snapshot_c_id))

    # Check that snapshot unmapped from all objects successfully
    self.check_no_relationship(snapshot_c_id)
