# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""Tests for Audit model."""
from ggrc import db
from ggrc.models import all_models
from ggrc.utils import errors
from integration.ggrc import generator
from integration.ggrc import TestCase, Api
from integration.ggrc.models import factories


class TestAudit(TestCase):
  """ Test Audit class. """
  # pylint: disable=invalid-name
  def setUp(self):
    super(TestAudit, self).setUp()
    self.api = Api()
    self.gen = generator.ObjectGenerator()

  def generate_control_mappings(self, control):
    """Map Control to several Assessments"""
    with factories.single_commit():
      person = factories.PersonFactory()
      asmnt_ids = []
      for _ in range(2):
        asmnt = factories.AssessmentFactory()
        asmnt_ids.append(asmnt.id)
        asmnt.add_person_with_role_name(person, "Creators")

    for asmnt_id in asmnt_ids:
      asmnt = all_models.Assessment.query.get(asmnt_id)
      self.gen.generate_relationship(source=asmnt, destination=control)

  def test_creation_mapped_control(self):
    """Check creation of new Audit if Program has Control with mapped roles"""
    control = factories.ControlFactory()
    # Map original of control to several assessments to get propagated roles
    self.generate_control_mappings(control)

    # Existing control should be updated to create new revision with ACL
    self.api.put(control, {"title": "Test Control"})

    program = factories.ProgramFactory()
    factories.RelationshipFactory(source=program, destination=control)
    response = self.api.post(all_models.Audit, [{
        "audit": {
            "title": "New Audit",
            "program": {"id": program.id},
            "status": "Planned",
            "context": None
        }
    }])
    self.assert200(response)

  def test_program_mapping(self):
    """Check creation of new Audit if Program has Control with mapped roles"""

    program = factories.ProgramFactory()
    self.api.post(all_models.Audit, [{
        "audit": {
            "title": "New Audit",
            "program": {"id": program.id, "type": program.type},
            "status": "Planned",
            "context": None
        }
    }])
    audit = all_models.Audit.query.first()
    program = all_models.Program.query.first()
    relationships = all_models.Relationship.find_related(audit, program)
    self.assertIsNotNone(audit)
    self.assertIsNotNone(program)
    self.assertIsNotNone(relationships)

  def test_control_mapping_missing_revision(self):
    """Test mapping control with missing revision to audit"""
    audit = factories.AuditFactory()
    control = factories.ControlFactory()
    all_models.Revision.query.filter_by(
        resource_id=control.id,
        resource_type=control.type
    ).delete()
    db.session.commit()
    response, _ = self.gen.generate_relationship(audit, control)
    self.assert500(response)
    self.assertEqual(response.json, errors.MISSING_REVISION)

  def test_delete_audit_asmnt_tmpl(self):
    """Check inability to delete audit in relation with assessment template."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment_template = factories.AssessmentTemplateFactory(audit=audit)
      factories.RelationshipFactory(
          source=audit,
          destination=assessment_template
      )
    response = self.api.delete(audit)
    self.assertStatus(response, 409)
    self.assertEqual(response.json["message"], errors.MAPPED_ASSESSMENT)

  def test_delete_audit_asmnt(self):
    """Check inability to delete audit in relation with assessment."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(
          source=audit,
          destination=assessment,
      )
    response = self.api.delete(audit)
    self.assertStatus(response, 409)
    self.assertEqual(response.json["message"], errors.MAPPED_ASSESSMENT)

  def test_delete_audit_proper(self):
    """Check delete audit with assessment template. Remove template first"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_id = audit.id
      assessment_template = factories.AssessmentTemplateFactory(audit=audit)
      assessment_template_id = assessment_template.id
      factories.RelationshipFactory(
          source=audit,
          destination=assessment_template
      )

    assessment_template = \
        all_models.AssessmentTemplate.query.get(assessment_template_id)
    response = self.api.delete(assessment_template)
    self.assert200(response)

    audit = all_models.Audit.query.get(audit_id)
    response = self.api.delete(audit)
    self.assert200(response)

  def test_new_audit_snapshots(self):
    """Test audit snapshot relationships on new audit creation."""

    program = factories.ProgramFactory()
    control = factories.ControlFactory()
    factories.RelationshipFactory(
        source=program,
        destination=control,
    )

    self.api.post(all_models.Audit, [{
        "audit": {
            "title": "New Audit",
            "program": {"id": program.id, "type": program.type},
            "status": "Planned",
            "context": None
        }
    }])
    audit = all_models.Audit.query.first()
    snapshot = all_models.Snapshot.query.first()
    relationships = all_models.Relationship.find_related(audit, snapshot)
    self.assertIsNotNone(audit)
    self.assertIsNotNone(snapshot)
    self.assertIsNotNone(relationships)

  def test_new_snapshot_mapping(self):
    """Test audit snapshot relationships on new snapshot creation."""

    audit = factories.AuditFactory()
    control = factories.ControlFactory()
    self.gen.generate_relationship(audit, control)

    audit = all_models.Audit.query.first()
    snapshot = all_models.Snapshot.query.first()
    relationships = all_models.Relationship.find_related(audit, snapshot)
    self.assertIsNotNone(audit)
    self.assertIsNotNone(snapshot)
    self.assertIsNotNone(relationships)

  def test_new_snapshots_on_update(self):
    """Test relationships for snapshots created by update audit scope."""
    audit = factories.AuditFactory()
    control = factories.ControlFactory()
    self.gen.generate_relationship(audit.program, control)

    self.api.put(audit, data={
        "snapshots": {"operation": "upsert"}
    })

    audit = all_models.Audit.query.first()
    snapshot = all_models.Snapshot.query.first()
    relationships = all_models.Relationship.find_related(audit, snapshot)
    self.assertIsNotNone(audit)
    self.assertIsNotNone(snapshot)
    self.assertIsNotNone(relationships)

  def test_slug_validation_create(self):
    """Test post slug with leading space"""
    with factories.single_commit():
      program = factories.ProgramFactory()
    audit_data = {
        "slug": " SLUG",
        "program": {"id": program.id},
    }
    response, audit = self.gen.generate_object(all_models.Audit, audit_data)
    self.assertEqual(response.status_code, 201)
    current_slug = audit.slug
    expected_slug = "SLUG"
    self.assertEqual(current_slug, expected_slug)

  def test_slug_no_update(self):
    """Test put slug has no effect since slug became
    not updatable API attribute"""
    with factories.single_commit():
      audit = factories.AuditFactory(slug="SLUG-01")

    response = self.api.put(audit, {"slug": "NEW SLUG"})
    self.assert200(response)
    audit = db.session.query(all_models.Audit).get(audit.id)
    current_slug = audit.slug
    expected_slug = "SLUG-01"
    self.assertEqual(current_slug, expected_slug)


class TestManualAudit(TestCase):
  """ Test Audit with manual snapshot mapping"""

  # pylint: disable=invalid-name
  def setUp(self):
    super(TestManualAudit, self).setUp()
    self.api = Api()
    self.gen = generator.ObjectGenerator()

  def assertSnapshotCount(self, count):
    """Assert snapshots count"""
    snapshot_count = all_models.Snapshot.query.count()
    self.assertEqual(snapshot_count, count)

  def count_related_objectives(self, snapshot_id):
    """Returns related objectives count for control snapshot"""
    query_data = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": {
                    "left": "child_type",
                    "op": {
                        "name": "="
                    },
                    "right": "Objective"
                },
                "op": {
                    "name": "AND"
                },
                "right": {
                    "object_name": "Snapshot",
                    "op": {
                        "name": "relevant"
                    },
                    "ids": [
                        str(snapshot_id)
                    ]
                }
            }
        },
        "fields": [
            "child_id",
            "child_type",
            "revision",
            "parent"
        ]
    }]
    response = self.api.send_request(
        self.api.client.post,
        data=query_data,
        api_link="/query"
    )
    self.assert200(response)
    return response.json[0]["Snapshot"]["count"]

  def test_audit_upsert(self):
    """Test upsert audit with manual mapping

    Audit with manual mapping should not add new snapshots
    after calling "Update objects to latest version"
    """
    with factories.single_commit():
      program = factories.ProgramFactory()
      control = factories.ControlFactory()
      factories.RelationshipFactory(source=program, destination=control)
    self.api.post(all_models.Audit, [{
        "audit": {
            "title": "New Audit",
            "program": {"id": program.id, "type": program.type},
            "status": "Planned",
            "context": None,
            "manual_snapshots": True,
        }
    }])
    self.assertSnapshotCount(0)

    audit = all_models.Audit.query.first()
    self.api.put(audit, data={"snapshots": {"operation": "upsert"}})
    self.assertSnapshotCount(0)

  def test_audit_manual_snapshots(self):
    """Test audit with manual snapshot mapping"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      control = factories.ControlFactory()
      control_id = control.id
      control2 = factories.ControlFactory()  # wouldn't be mapped to objective
      control2_id = control2.id
      factories.RelationshipFactory(source=program, destination=control)
      factories.RelationshipFactory(source=program, destination=control2)
      # factories.RelationshipFactory(source=program, destination=issue)
      # factories.RelationshipFactory(source=control, destination=issue)
    self.api.post(all_models.Audit, [{
        "audit": {
            "title": "New Audit",
            "program": {"id": program.id, "type": program.type},
            "status": "Planned",
            "context": None,
            "manual_snapshots": True,
        }
    }])
    self.assertSnapshotCount(0)

    audit = all_models.Audit.query.first()
    control = all_models.Control.query.get(control_id)
    control2 = all_models.Control.query.get(control2_id)
    # issue = all_models.Issue.query.first()

    self.gen.generate_relationship(audit, control)
    control_snapshot_id = all_models.Snapshot.query.filter_by(
        child_id=control_id, child_type="Control").first().id
    self.assertEqual(self.count_related_objectives(control_snapshot_id), 0)

    # self.gen.generate_relationship(audit, issue)
    # self.assertEqual(self.count_related_objectives(control_snapshot_id), 1)

    self.gen.generate_relationship(audit, control2)
    control2_snapshot_id = all_models.Snapshot.query.filter_by(
        child_id=control2_id, child_type="Control").first().id
    self.assertEqual(self.count_related_objectives(control2_snapshot_id), 0)

    self.assertSnapshotCount(2)
