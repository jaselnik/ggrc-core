# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test automappings"""

import itertools
from collections import OrderedDict
from contextlib import contextmanager

import ddt

import ggrc
from ggrc import automapper
from ggrc import models
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc import generator
from integration.ggrc.models import factories
from integration.ggrc.models.factories import random_str


def make_name(msg):
  """Make name helper function"""
  return random_str(prefix=msg)


@contextmanager
def automapping_count_limit(new_limit):
  """Automapping count limit"""
  original_limit = ggrc.automapper.AutomapperGenerator.COUNT_LIMIT
  ggrc.automapper.AutomapperGenerator.COUNT_LIMIT = new_limit
  yield
  ggrc.automapper.AutomapperGenerator.COUNT_LIMIT = original_limit


class TestAutomappings(TestCase):
  """Test automappings"""

  @classmethod
  def setUpClass(cls):
    cls.gen = generator.ObjectGenerator()

  def setUp(self):
    super(TestAutomappings, self).setUp()
    self.api = self.gen.api
    self.api.login_as_normal()

  @classmethod
  def create_ac_roles(cls, obj, person_id, role_name="Admin"):
    """Create access control roles"""
    factories.AccessControlPersonFactory(
        ac_list=obj.acr_name_acl_map[role_name],
        person_id=person_id,
    )

  def create_object(self, cls, data):
    """Helper function for creating an object"""
    name = cls._inflector.table_singular
    data['context'] = None
    res, obj = self.gen.generate_object(cls, data={name: data})
    self.assertIsNotNone(obj, '%s, %s: %s' % (name, str(data), str(res)))
    return obj

  def create_mapping(self, src, dst):
    """Helper function for creating mappings"""
    return self.gen.generate_relationship(src, dst)[1]

  def assert_mapping(self, obj1, obj2, missing=False):
    """Helper function for asserting mappings"""
    ggrc.db.session.flush()
    rel = models.Relationship.find_related(obj1, obj2)
    if not missing:
      self.assertIsNotNone(rel,
                           msg='%s not mapped to %s' % (obj1.type, obj2.type))
      revisions = models.Revision.query.filter_by(
          resource_type='Relationship',
          resource_id=rel.id,
      ).count()
      self.assertEqual(revisions, 1)
    else:
      self.assertIsNone(rel,
                        msg='%s mapped to %s' % (obj1.type, obj2.type))

  def assert_mapping_implication(self, to_create, implied, relevant=None):
    """Helper function for asserting mapping implication"""
    if relevant is None:
      relevant = set()
    objects = set()
    for obj in relevant:
      objects.add(obj)
    mappings = set()
    if not isinstance(to_create, list):
      to_create = [to_create]
    for src, dst in to_create:
      objects.add(src)
      objects.add(dst)
      self.create_mapping(src, dst)
      mappings.add(automapper.AutomapperGenerator.order(src, dst))
    if not isinstance(implied, list):
      implied = [implied]
    for src, dst in implied:
      objects.add(src)
      objects.add(dst)
      self.assert_mapping(src, dst)
      mappings.add(automapper.AutomapperGenerator.order(src, dst))
    possible = set()
    for src, dst in itertools.product(objects, objects):
      possible.add(automapper.AutomapperGenerator.order(src, dst))
    for src, dst in possible - mappings:
      self.assert_mapping(src, dst, missing=True)

  def with_permutations(self, mk1, mk2, mk3):
    """Helper function for creating permutations"""
    obj1, obj2, obj3 = mk1(), mk2(), mk3()
    self.assert_mapping_implication(
        to_create=[(obj1, obj2), (obj2, obj3)],
        implied=(obj1, obj3),
    )
    obj1, obj2, obj3 = mk1(), mk2(), mk3()
    self.assert_mapping_implication(
        to_create=[(obj2, obj3), (obj1, obj2)],
        implied=(obj1, obj3),
    )

  def test_automapping_limit(self):
    """Test mapping limit"""
    with automapping_count_limit(-1):
      regulation = self.create_object(models.Regulation, {
          'title': make_name('Test Regulation')
      })
      with self.api.as_external():
        requirement = self.create_object(models.Requirement, {
            'title': make_name('Test requirement'),
        })
        objective = self.create_object(models.Objective, {
            'title': make_name('Objective')
        })
      self.assert_mapping_implication(
          to_create=[(regulation, requirement), (objective, requirement)],
          implied=[],
      )

  def test_mapping_between_objectives(self):
    """Test mapping between objectives"""
    regulation = self.create_object(models.Regulation, {
        'title': make_name('Test PD Regulation')
    })
    with self.api.as_external():
      requirement = self.create_object(models.Requirement, {
          'title': make_name('Test requirement'),
          'directive': {'id': regulation.id},
      })
      objective1 = self.create_object(models.Objective, {
          'title': make_name('Test Objective')
      })
      objective2 = self.create_object(models.Objective, {
          'title': make_name('Test Objective')
      })
    self.assert_mapping_implication(
        to_create=[(regulation, requirement),
                   (requirement, objective1),
                   (objective1, objective2)],
        implied=[]
    )

  def test_mapping_nested_controls(self):
    """Test mapping of nested controls"""
    with self.api.as_external():
      objective = self.create_object(models.Objective, data={
          'title': make_name('Test Objective')
      })
      control_p = self.create_object(models.Control, {
          'title': make_name('Test control')
      })
      control1 = self.create_object(models.Control, {
          'title': make_name('Test control')
      })
      control2 = self.create_object(models.Control, {
          'title': make_name('Test control')
      })
    self.assert_mapping_implication(
        to_create=[(objective, control_p),
                   (control_p, control1),
                   (control_p, control2)],
        implied=[]
    )


class TestIssueAutomappings(TestCase):
  """Test suite for Issue-related automappings."""
  # pylint: disable=invalid-name

  def setUp(self):
    super(TestIssueAutomappings, self).setUp()

    # TODO: replace this hack with a special test util
    from ggrc.login import noop
    noop.login()  # this is needed to pass the permission checks in automapper

    snapshottable = factories.ObjectiveFactory()
    with factories.single_commit():
      self.audit, self.asmt, self.snapshot = self._make_audit_asmt_snapshot(
          snapshottable,
      )

      self.issue = factories.IssueFactory()
      self.issue_audit = factories.IssueFactory()
      self.issue_snapshot = factories.IssueFactory()

      factories.RelationshipFactory(source=self.issue_audit,
                                    destination=self.audit)

      # to map an Issue to a Snapshot, you first should map it to Audit
      factories.RelationshipFactory(source=self.issue_snapshot,
                                    destination=self.audit)
      factories.RelationshipFactory(source=self.issue_snapshot,
                                    destination=self.snapshot)

  @staticmethod
  def _make_audit_asmt_snapshot(snapshottable):
    """Make Audit, Assessment, Snapshot and map them correctly."""
    audit = factories.AuditFactory()
    assessment = factories.AssessmentFactory(audit=audit)

    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == snapshottable.id,
        all_models.Revision.resource_type == snapshottable.type,
    ).first()
    snapshot = factories.SnapshotFactory(
        parent=audit,
        revision_id=revision.id,
        child_type=snapshottable.type,
        child_id=snapshottable.id,
    )

    # Audit-Assessment Relationship is created only on Assessment POST
    factories.RelationshipFactory(source=audit, destination=assessment)
    factories.RelationshipFactory(source=assessment, destination=snapshot)

    return audit, assessment, snapshot

  @staticmethod
  def _ordered_pairs_from_relationships(relationships):
    """Make list of ordered src, dst from a list of Relationship objects."""
    def order(src, dst):
      return ((src, dst) if (src.type, src.id) < (dst.type, dst.id) else
              (dst, src))

    return [order(r.source, r.destination) for r in relationships]

  @classmethod
  def _get_automapped_relationships(cls):
    """Get list of ordered src, dst mapped by the only automapping."""
    automapping = all_models.Automapping.query.one()
    automapped = all_models.Relationship.query.filter(
        all_models.Relationship.automapping_id == automapping.id,
    ).all()
    return cls._ordered_pairs_from_relationships(automapped)

  def test_issue_assessment_automapping(self):
    """Issue is automapped to Audit and Snapshot."""
    factories.RelationshipFactory(source=self.issue,
                                  destination=self.asmt)

    automapped = self._get_automapped_relationships()

    self.assertItemsEqual(automapped,
                          [(self.audit, self.issue),
                           (self.issue, self.snapshot)])

  def test_issue_assessment_automapping_no_audit(self):
    """Issue is automapped to Snapshot if Audit already mapped."""
    factories.RelationshipFactory(source=self.issue_audit,
                                  destination=self.asmt)

    automapped = self._get_automapped_relationships()

    self.assertItemsEqual(automapped,
                          [(self.issue_audit, self.snapshot)])

  def test_issue_assessment_automapping_all_mapped(self):
    """Issue is not automapped to Snapshot and Audit if already mapped."""
    factories.RelationshipFactory(source=self.issue_snapshot,
                                  destination=self.asmt)

    self.assertEqual(all_models.Automapping.query.count(), 0)


@ddt.ddt
class TestMegaProgramAutomappings(TestCase):
  """Test Mega Program automappings"""

  @classmethod
  def setUpClass(cls):
    cls.gen = generator.ObjectGenerator()

  def setUp(self):
    super(TestMegaProgramAutomappings, self).setUp()

    # TODO: replace this hack with a special test util
    from ggrc.login import noop
    noop.login()  # this is needed to pass the permission checks in automapper

  @ddt.data(
      "Regulation", "Objective", "Control", "Contract",
      "Policy", "Risk", "Standard", "Threat", "Requirement",
      "System", "Product", "Process", "Market", "DataAsset",
      "Facility", "OrgGroup", "Metric", "TechnologyEnvironment",
      "ProductGroup", "Project", "Vendor", "AccessGroup",
      "KeyReport", "AccountBalance",
  )
  def test_megaprogram_automapping(self, model_name):
    """Test automapping of {0} to parent programs"""
    with factories.single_commit():
      program_a = factories.ProgramFactory()
      program_c = factories.ProgramFactory()
      program_b = factories.ProgramFactory()
      program_d = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_b,
                                    destination=program_a)
      factories.RelationshipFactory(source=program_c,
                                    destination=program_b)
      factories.RelationshipFactory(source=program_d,
                                    destination=program_c)
      _model = factories.get_model_factory(model_name)()
      factories.RelationshipFactory(source=_model,
                                    destination=program_b)

    program_a_related = program_a.related_objects()
    program_c_related = program_c.related_objects()
    program_d_related = program_d.related_objects()
    self.assertTrue(_model not in program_a_related)
    self.assertTrue(_model in program_c_related)
    self.assertTrue(_model in program_d_related)

  def test_cyclic_automapping(self):
    """Test mapping object to program in cycle program-to-program mapping"""
    with factories.single_commit():
      program_b = factories.ProgramFactory()
      program_a = factories.ProgramFactory()
      program_c = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_b,
                                    destination=program_a)
      factories.RelationshipFactory(source=program_a,
                                    destination=program_c)
      factories.RelationshipFactory(source=program_c,
                                    destination=program_b)
      standard = factories.StandardFactory()
      factories.RelationshipFactory(source=standard,
                                    destination=program_c)

    program_a_related = program_a.related_objects()
    program_b_related = program_b.related_objects()
    program_c_related = program_c.related_objects()
    self.assertTrue(standard in program_a_related)
    self.assertTrue(standard in program_b_related)
    self.assertTrue(standard in program_c_related)

  def test_automapping_during_import(self):
    """Test automapping of Standart to parent Program during import"""
    with factories.single_commit():
      program_a = factories.ProgramFactory()
      program_b = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_b,
                                    destination=program_a)
    program_b_id = program_b.id
    response = self.import_data(OrderedDict([
        ("object_type", "Standard"),
        ("Code*", ""),
        ("Title*", "Test standard"),
        ("Admin*", "user@example.com"),
        ("map:Program", program_a.slug),
    ]))
    self._check_csv_response(response, {})
    program_b = all_models.Program.query.get(program_b_id)
    program_b_related = program_b.related_objects()
    self.assertIn("Standard", {obj.type for obj in program_b_related})

  def test_snapshot_automapping(self):
    """Test automapping after Snapshot to Audit mapping"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      program_id = program.id
      parent_program = factories.ProgramFactory()
      parent_program_id = parent_program.id
      factories.RelationshipFactory(source=parent_program, destination=program)
      audit = factories.AuditFactory(program=program)
      standard = factories.StandardFactory()
      requirement = factories.RequirementFactory()
      factories.RelationshipFactory(source=standard, destination=requirement,
                                    is_external=True)
    self.gen.generate_relationship(audit, standard)
    program = all_models.Program.query.get(program_id)
    program_related = program.related_objects()
    parent_program = all_models.Program.query.get(parent_program_id)
    parent_program_related = parent_program.related_objects()
    self.assertEqual(len(program_related), 3)
    self.assertEqual(len(parent_program_related), 3)
    self.assertEqual({o.type for o in parent_program_related},
                     {"Program", "Standard", "Requirement"})
