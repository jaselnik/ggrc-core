# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for Program."""

import datetime
import ddt

from ggrc.models import all_models
from ggrc.utils import errors

from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc import TestCase
from integration.ggrc import review


class TestProgram(TestCase):
  """Program test cases."""

  def setUp(self):
    self.api = api_helper.Api()

    with factories.single_commit():
      self.program = factories.ProgramFactory()
      self.audit_id = factories.AuditFactory(program=self.program).id

  def test_put_empty_audits(self):
    """Audit doesn't get deleted when empty audits field is put."""
    response = self.api.put(self.program, data={"audits": []})

    self.assert200(response)
    audit = self.refresh_object(all_models.Audit, id_=self.audit_id)
    self.assertIsNotNone(audit)

  def test_delete_with_audits(self):
    """Test deletion of a program with a mapped audit"""

    response = self.api.delete(self.program)
    self.assertEqual(response.status_code, 409)
    self.assertEqual(
        response.json,
        {
            "message": errors.MAPPED_AUDITS,
            "code": 409,
        }
    )

  def test_delete_without_audits(self):
    """Test deletion of a program with a mapped audit"""
    response = self.api.delete(self.program.audits[0])
    self.assert200(response)
    response = self.api.delete(self.program)
    self.assert200(response)

  def test_create_wrong_recipients(self):
    """Test creation of a program with a wrong recipients"""
    data = [{
        'program': {
            'status': 'Draft',
            'kind': 'Directive',
            'send_by_default': True,
            'managers': ['user@example.com'],
            'recipients': 'Admin,Primary Contacts,Secondary Contacts',
            'title': 'Program_Test',
            'review': {
                'status': 'Unreviewed',
            },
            'access_control_list': [],
            'slug': 'program_test'
        }
    }]
    response = self.api.post(all_models.Program, data=data)
    self.assert400(response)
    self.assertIn(
        u"Value should be either empty or comma separated list of",
        response.json[0][1]
    )


@ddt.ddt
class TestProgramVersionHistory(TestCase):
  """Test Version History for Program"""

  def setUp(self):
    super(TestProgramVersionHistory, self).setUp()
    self.api = api_helper.Api()

    with factories.single_commit():
      self.program = factories.ProgramFactory(
          title="Test Program",
          description="Program Description",
          slug="PROGRAM-2346",
          start_date=datetime.date(2019, 6, 1),
          end_date=datetime.date(2019, 6, 2),
          updated_at=datetime.date(2019, 6, 2),
          folder="Program Folder",
          notes="Program Notes",
          status="Draft",
      )
      self.cad = factories.CustomAttributeDefinitionFactory(
          title="test cad",
          definition_type="program",
          definition_id=self.program.id,
          attribute_type="Text",
          mandatory=True,
      )
      self.cav = factories.CustomAttributeValueFactory(
          custom_attribute=self.cad,
          attributable=self.program,
          attribute_value="Text",
      )

  @ddt.data(
      ("title", "Prev Program Title", True),
      ("description", "Prev Program Decription", True),
      ("slug", "PREV-PROGRAM-SLUG", False),
      ("folder", "Prev Program Folder", False),
      ("status", "Active", True),
      ("notes", "Prev Program Notes", True),
      ("start_date", datetime.date(2019, 5, 1), True),
      ("end_date", datetime.date(2019, 5, 2), False),
      ("updated_at", datetime.date(2019, 5, 2), False),
  )
  @ddt.unpack
  def test_restore_attr_from_history(self, attr_name,
                                     attr_value, restored):
    """Test only allowed fields can be restored from Version History"""

    response = self.api.put(self.program, data={attr_name: attr_value})
    self.assert200(response)

    self.program = self.refresh_object(
        all_models.Program,
        id_=self.program.id,
    )
    self.assertEqual(
        getattr(self.program, attr_name, None) == attr_value,
        restored,
    )

  def test_restore_cav_from_history(self):
    """Test CAV can be restored from Version History"""

    prev_cav_value = "Prev Text"
    prev_cav = self.cav.log_json()
    prev_cav.update({"attribute_value": prev_cav_value})

    response = self.api.put(
        self.program,
        data={
            "custom_attribute_definitions": [self.cad.log_json()],
            "custom_attribute_values": [prev_cav]
        },
    )
    self.assert200(response)

    self.program = self.refresh_object(
        all_models.Program,
        id_=self.program.id,
    )
    self.assertEqual(
        self.program.custom_attribute_values[0].attribute_value,
        prev_cav_value
    )

  def test_review_not_changed(self):
    """Test review status and recipients not changed after restore obj"""
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
    instance = self.refresh_object(all_models.Program, instance.id)
    initial_recipients = instance.recipients
    initial_review_state = instance.review.status
    response = self.api.put(
        instance,
        self.api.get(all_models.Program, instance.id).json
    )
    self.assert200(response)
    instance = self.refresh_object(all_models.Program, instance.id)
    self.assertEqual(initial_recipients, instance.recipients)
    self.assertEqual(initial_review_state, instance.review.status)


class TestMegaProgram(TestCase):
  """Mega Program test cases"""

  def setUp(self):
    """Setup tests"""
    self.api = api_helper.Api()

  def test_is_mega_attr(self):
    """Test is_mega attribute of program"""
    with factories.single_commit():
      program_child = factories.ProgramFactory()
      program_parent = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_parent,
                                    destination=program_child)
    program_child_id = program_child.id
    program_parent_id = program_parent.id
    response = self.api.get(all_models.Program, program_child_id)
    self.assertEqual(response.json["program"]["is_mega"], False)
    response = self.api.get(all_models.Program, program_parent_id)
    self.assertEqual(response.json["program"]["is_mega"], True)

  def test_program_relatives(self):
    """Test program children and parents
               +--C<--+
               |      |
               v      |
        A<-----B<-----E<----F
                      |
                      |
               D<-----+
    """

    with factories.single_commit():
      program_a = factories.ProgramFactory()
      program_b = factories.ProgramFactory()
      program_c = factories.ProgramFactory()
      program_d = factories.ProgramFactory()
      program_e = factories.ProgramFactory()
      program_f = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_b,
                                    destination=program_a)
      factories.RelationshipFactory(source=program_c,
                                    destination=program_b)
      factories.RelationshipFactory(source=program_e,
                                    destination=program_d)
      factories.RelationshipFactory(source=program_e,
                                    destination=program_b)
      factories.RelationshipFactory(source=program_e,
                                    destination=program_c)
      factories.RelationshipFactory(source=program_f,
                                    destination=program_e)
    parents_b = all_models.Program.get_all_relatives_ids(program_b.id,
                                                         "parents")
    children_b = all_models.Program.get_all_relatives_ids(program_b.id,
                                                          "children")
    parents_e = all_models.Program.get_all_relatives_ids(program_e.id,
                                                         "parents")
    children_e = all_models.Program.get_all_relatives_ids(program_e.id,
                                                          "children")
    self.assertEqual(parents_b, {program_c.id, program_e.id, program_f.id})
    self.assertEqual(children_b, {program_a.id, })
    self.assertEqual(parents_e, {program_f.id, })
    self.assertEqual(children_e, {program_c.id, program_b.id,
                                  program_d.id, program_a.id})

  def test_program_cycle_relatives(self):
    """Test programs cycle children and parents
        +-->C--+
        |      |
        |      v
        A<-----B
    """

    with factories.single_commit():
      program_a = factories.ProgramFactory()
      program_b = factories.ProgramFactory()
      program_c = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_b,
                                    destination=program_a)
      factories.RelationshipFactory(source=program_c,
                                    destination=program_b)
      factories.RelationshipFactory(source=program_a,
                                    destination=program_c)
    parents_b = all_models.Program.get_all_relatives_ids(program_b.id,
                                                         "parents")
    children_b = all_models.Program.get_all_relatives_ids(program_b.id,
                                                          "children")
    self.assertEqual(parents_b, {program_a.id, program_c.id})
    self.assertEqual(children_b, {program_a.id, program_c.id})
