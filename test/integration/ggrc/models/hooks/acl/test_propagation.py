# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control Propagation for Audit Roles like
   Auditor & Audit Captains"""

# pylint: disable=protected-access
# Disable protected access since this test suite tests internal function for
# ACL propagation.

import itertools
from collections import defaultdict
from collections import OrderedDict
import mock

import ddt
import flask
import sqlalchemy as sa
from sqlalchemy.orm.session import Session

from ggrc import app
from ggrc import db
from ggrc.models import all_models
from ggrc.models.hooks import acl
from ggrc.models.hooks.acl import propagation
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


class BaseTestPropagation(TestCase):
  """Base test case for all propagation scenarios."""

  def setUp(self):
    super(BaseTestPropagation, self).setUp()
    self.roles = defaultdict(dict)
    for role in all_models.AccessControlRole.query:
      self.roles[role.object_type][role.name] = role


@ddt.ddt
class TestPropagation(BaseTestPropagation):
  """TestAuditRoleProgation"""

  def setUp(self):
    super(TestPropagation, self).setUp()
    sa.event.remove(Session, "after_flush", acl.after_flush)
    self.user_id = factories.PersonFactory().id

  def tearDown(self):
    sa.event.listen(Session, "after_flush", acl.after_flush)

  @ddt.data(
      ("source", "destination"),
      ("destination", "source"),
  )
  def test_single_acl(self, rel_order):
    """Test propagation for a single relationship with {}.

    Test propagation of program role to audit through a relationship with both
    options for source and destination.
    """
    with factories.single_commit():
      person = factories.PersonFactory()
      audit = factories.AuditFactory()
      rel_data = {
          rel_order[0]: audit,
          rel_order[1]: audit.program,
      }
      factories.RelationshipFactory(**rel_data)
      audit.program.add_person_with_role(
          person,
          self.roles["Program"]["Program Editors"],
      )

    acl_entries = [acl.id for acl in audit.program._access_control_list]

    self.assertEqual(all_models.AccessControlList.query.count(), 9)
    propagation._handle_acl_step(acl_entries, self.user_id)
    db.session.commit()
    self.assertEqual(all_models.AccessControlList.query.count(), 15)

  @ddt.data(0, 2, 3)
  def test_single_acl_to_multiple(self, count):
    """Test propagation of single ACL entry to multiple children."""
    with factories.single_commit():
      program = factories.ProgramFactory()
      for i in range(count):
        audit = factories.AuditFactory(program=program)
        factories.RelationshipFactory(
            source=program if i % 2 == 0 else audit,
            destination=program if i % 2 == 1 else audit,
        )

    acl_id = program.acr_name_acl_map["Program Editors"].id

    child_ids = propagation._handle_acl_step([acl_id], self.user_id)

    self.assertEqual(
        all_models.AccessControlList.query.filter(
            all_models.AccessControlList.parent_id.isnot(None)
        ).count(),
        count * 2
    )
    self.assertEqual(
        db.session.execute(child_ids.alias("counts").count()).scalar(),
        count,
    )

  def test_multi_acl_to_multiple(self):
    """Test multiple ACL propagation to multiple children."""
    audit_count = 3
    with factories.single_commit():
      program = factories.ProgramFactory()
      for i in range(audit_count):
        audit = factories.AuditFactory(program=program)
        factories.RelationshipFactory(
            source=program if i % 2 == 0 else audit,
            destination=program if i % 2 == 1 else audit,
        )
    acl_ids = [acl.id for acl in program._access_control_list]

    self.assertEqual(
        all_models.AccessControlList.query.count(),
        12  # 5 program roles, 6 audit roles 1 person_profile role
    )
    propagation._handle_acl_step(acl_ids, self.user_id)

    self.assertEqual(
        all_models.AccessControlList.query.count(),
        11 + 1 + 3 * 3 * 2
        # 11 previous roles
        # 1 person_profile role
        # 3 audits
        # 3 program propagated roles
        # 2 propagations per audit (audit + relationship)
    )

  @ddt.data(1, 2, 3)
  def test_partial_acl_to_multiple(self, partial_count):
    audit_count = 3
    with factories.single_commit():
      program = factories.ProgramFactory()
      for i in range(audit_count):
        audit = factories.AuditFactory(program=program)
        factories.RelationshipFactory(
            source=program if i % 2 == 0 else audit,
            destination=program if i % 2 == 1 else audit,
        )

    propagated_roles = {
        "Program Managers",
        "Program Readers",
        "Program Editors"
    }

    acl_ids = [acl.id for acl in program._access_control_list
               if acl.ac_role.name in propagated_roles]

    propagate_acl_ids = acl_ids[:partial_count]
    propagation._handle_acl_step(propagate_acl_ids, self.user_id)

    self.assertEqual(
        all_models.AccessControlList.query.filter(
            all_models.AccessControlList.parent_id.isnot(None)
        ).count(),
        partial_count * 3 * 2
    )

  def test_deep_propagation(self):
    """Test nested propagation from programs to assessments.

    Test 3 people with 2 roles on programs to propagate to assessments
    """
    audit_count = 3
    with factories.single_commit():
      for i in range(audit_count):
        audit = factories.AuditFactory()
        assessment = factories.AssessmentFactory(audit=audit)
        factories.RelationshipFactory(
            source=audit.program if i % 2 == 0 else audit,
            destination=audit.program if i % 2 == 1 else audit,
        )
        factories.RelationshipFactory(
            source=assessment if i % 2 == 0 else audit,
            destination=assessment if i % 2 == 1 else audit,
        )

    acl_ids = [acl.id for acl in audit.program._access_control_list]

    propagation._propagate(acl_ids, self.user_id)

    assessment_acls = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type ==
        all_models.Assessment.__name__,
        all_models.AccessControlList.parent_id.isnot(None),
    ).all()

    # one for PR, PE, PM
    self.assertEqual(len(assessment_acls), 3)

  def test_relationship_single_layer(self):
    """Test single layer propagation through relationships.

    Test propagation of a new relationship between audit and assessment. Here
    we check that propagation happens both ways on the relationship creation.
    """

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment1 = factories.AssessmentFactory(audit=audit)
      assessment2 = factories.AssessmentFactory(audit=audit)

      # This is excluded from propagation to test for proper filtering
      assessment3 = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=assessment3, destination=audit)

      relationship_ids = [
          factories.RelationshipFactory(
              source=assessment1,
              destination=audit,
          ).id,
          factories.RelationshipFactory(
              source=audit,
              destination=assessment2,
          ).id,
      ]

    with app.app.app_context():
      flask.g.user_ids = set()
      child_ids = propagation._handle_relationship_step(
          relationship_ids,
          [],
          self.user_id,
      )

    self.assertEqual(
        all_models.AccessControlList.query.filter(
            all_models.AccessControlList.parent_id.isnot(None)
        ).count(),
        20
    )
    self.assertEqual(
        db.session.execute(child_ids.alias("counts").count()).scalar(),
        10,
    )

  def test_propagation_conflict(self):
    """Test propagation conflicts

    When we create a new acl entry and a new relationship in the same commit
    some roles would be propagated twice and would cause unique constraint
    errors. This test checks for the most basic such scenario.
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      relationship = factories.RelationshipFactory(
          source=audit,
          destination=audit.program,
      )

    acl_ids = set()
    user_ids = set()
    for _acl in audit.program._access_control_list:
      acl_ids.add(_acl.id)
      for acp in _acl.access_control_people:
        user_ids.append(acp.id)

    with app.app.app_context():
      flask.g.new_acl_ids = acl_ids
      flask.g.new_relationship_ids = {relationship.id}
      flask.g.user_ids = user_ids
      flask.g.deleted_objects = set()

      propagation.propagate()

      db.session.commit()

      self.assertEqual(all_models.AccessControlList.query.count(), 14)

  def test_propagate_all(self):
    """Test clean propagation of all ACL entries."""
    with factories.single_commit():
      wf_factories.TaskGroupTaskFactory()
      audit = factories.AuditFactory()
      factories.RelationshipFactory(
          source=audit,
          destination=audit.program,
      )

    acl_ids = [acl.id for acl in audit.program._access_control_list]

    propagation._propagate(acl_ids, self.user_id)
    self.assertEqual(all_models.AccessControlList.query.count(), 18)
    propagation.propagate_all()
    self.assertEqual(all_models.AccessControlList.query.count(), 27)

  def test_creating_missing_acl_entries(self):
    """Test clean propagation of all ACL entries."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      wf_factories.TaskGroupTaskFactory()
      factories.RelationshipFactory(source=audit, destination=audit.program)

    propagation.propagate_all()
    self.assertEqual(all_models.AccessControlList.query.count(), 27)
    all_models.AccessControlPerson.query.delete()
    all_models.AccessControlList.query.delete()
    db.session.commit()
    self.assertEqual(all_models.AccessControlList.query.count(), 0)
    propagation.propagate_all()
    self.assertEqual(all_models.AccessControlList.query.count(), 27)

  def test_complex_propagation_count(self):
    """Test multiple object ACL propagation.

    This test is meant to catch invalid ACL entries for propagation that can
    not happen.
    Example for this is propagation control -> relationships -> document. In
    that propagation rule we should only propagate control acl entries to
    relationships to documents. But what can happen is; when a control has
    multiple relationships, some to objects and only one to document, all of
    those relationships would get an ACL entry even though in some cases that
    is a propagation dead end.

    Setup for this test is:

    Objects:
      control
      regulation
      objective
      program
      audit
      assessment, assessment_2

    Relationships:
      control - regulation
      control - objective
      objective - regulations
      program - control, regulation, objective, audit
      audit - assessment, assessment_2,
      audit - control-snapshot, regulation-snapshot, objective-snapshot
      control_snapshot - regulation_snapshot
      control_snapshot - objective_snapshot
      objective_snapshot - regulations_snapshot
      document - regulation, objective, control
      evidence - assessment
    """
    # pylint: disable=too-many-locals
    with factories.single_commit():
      control = factories.ControlFactory()
      regulation = factories.RegulationFactory()
      issue = factories.IssueFactory()
      normal_objects = [control, regulation, issue]

      for obj1, obj2 in itertools.combinations(normal_objects, 2):
        if control in (obj1, obj2):
          with mock.patch('ggrc.models.relationship.is_external_app_user',
                          return_value=True):
            factories.RelationshipFactory(source=obj1, destination=obj2,
                                          is_external=True)
        else:
          factories.RelationshipFactory(source=obj1, destination=obj2)

      assessment = factories.AssessmentFactory()
      assessment_2 = factories.AssessmentFactory(audit=assessment.audit)
      factories.RelationshipFactory(
          source=assessment,
          destination=assessment.audit,
      )
      factories.RelationshipFactory(
          source=assessment_2,
          destination=assessment.audit,
      )
      factories.RelationshipFactory(
          source=assessment.audit,
          destination=assessment.audit.program,
      )
      for obj in normal_objects:
        factories.RelationshipFactory(
            source=assessment.audit.program,
            destination=obj,
        )

      snapshots = self._create_snapshots(assessment.audit, normal_objects)
      for snapshot in snapshots:
        factories.RelationshipFactory(
            source=assessment.audit,
            destination=snapshot,
        )

      for obj1, obj2 in itertools.combinations(snapshots, 2):
        factories.RelationshipFactory(source=obj1, destination=obj2)

      for obj in normal_objects:
        document = factories.DocumentFactory()
        factories.RelationshipFactory(source=obj, destination=document)

      evidence = factories.EvidenceUrlFactory()
      factories.RelationshipFactory(source=evidence, destination=assessment)

    acl_entry = control._access_control_list[0]

    propagation._propagate([acl_entry.id], self.user_id)

    self.assertEqual(
        all_models.AccessControlList.query.filter(
            all_models.AccessControlList.parent_id.isnot(None)
        ).count(),
        2,  # 1 for relationship to document and 1 for document.
    )

    acl_entry = next(
        acl for acl in assessment.audit.program._access_control_list
        if acl.ac_role.name == "Program Editors"
    )
    propagation._propagate([acl_entry.id], self.user_id)

    self.assertEqual(
        all_models.AccessControlList.query.filter(
            all_models.AccessControlList.parent_id.isnot(None)
        ).count(),
        2 + 2 + 4 + 6 + 2 + 6 + 6
        # 2 previous entries for control
        # 2 for audit (relationship + audit propagation)
        # 4 for assessments (2 assessments and 2 relationships for them)
        # 6 for snapshots (3 snapshots with relationships)
        # 2 assessment document with relationships
        # 6 for normal objects
        # 6 for normal object documents
    )


class TestPropagationViaImport(BaseTestPropagation):
  """Test case for import propagation scenarios."""

  def test_import_propagation(self):
    """Test propagation program roles via import"""
    # pylint: disable=too-many-locals
    with factories.single_commit():
      program = factories.ProgramFactory()
      control = factories.ControlFactory()
      control_1 = factories.ControlFactory()
      factories.RelationshipFactory(destination=program, source=control)
      factories.RelationshipFactory(destination=program, source=control_1)

    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.type,
    ).first()
    with factories.single_commit():
      audit = factories.AuditFactory(program=program)
      rel = factories.RelationshipFactory(destination=audit.program,
                                          source=audit)
      snapshot = factories.SnapshotFactory(parent=audit,
                                           revision_id=revision.id,
                                           child_type=control.type,
                                           child_id=control.id)
      factories.RelationshipFactory(destination=audit, source=snapshot)

    acl_ids = set()
    user_ids = set()
    for _acl in program._access_control_list:
      acl_ids.add(_acl.id)
      for acp in _acl.access_control_people:
        user_ids.append(acp.id)

    flask.g.new_relationship_ids = [rel.id]
    flask.g.new_acl_ids = acl_ids
    flask.g.user_ids = user_ids
    flask.g.deleted_objects = []

    propagation.propagate()
    acl_q = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type == "Assessment",
    )
    self.assertEqual(acl_q.count(), 0)
    response = self.import_data(
        OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit.slug),
            ("title", "Assessment title 1"),
            ("Creators", "user@example.com"),
            ("Assignees", "user@example.com"),
            ("map:Control versions", control.slug),
        ]),
        OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit.slug),
            ("title", "Assessment title 2"),
            ("Creators", "user@example.com"),
            ("Assignees", "user@example.com"),
            ("map:Control versions", control.slug),
        ]),
    )
    self.check_import_errors(response)
    self.assertEqual(acl_q.count(), 20)
