# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests Workflow related API calls."""

import datetime
import unittest

import ddt
import freezegun

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.access_control import acl_helper
from integration.ggrc.models import factories
from integration.ggrc_workflows import generator as wf_generator
from integration.ggrc_workflows.models import factories as wf_factories


WF_ROLES = {
    role.name: role.id
    for role in all_models.AccessControlRole.eager_query().filter(
        all_models.AccessControlRole.object_type == "Workflow").all()
}


@ddt.ddt  # pylint: disable=too-many-public-methods
class TestWorkflowsApiPost(TestCase):
  """Test class for ggrc workflow api post action."""

  def setUp(self):
    super(TestWorkflowsApiPost, self).setUp()
    self.api = Api()
    self.generator = wf_generator.WorkflowsGenerator()
    self.wf_admin_id = all_models.Person.query.first().id
    with factories.single_commit():
      self.people_ids = [factories.PersonFactory().id for _ in xrange(6)]

  def tearDown(self):
    pass

  def _delete_and_check_related_acl(self, related_model, exp_acl_count,
                                    is_deleted):
    """Delete related model and check remaining ACL count.

    Args:
        related_model: related model class
        exp_acl_count: expected related ACL count after delete operation
        is_deleted: is related object already deleted
    """
    if is_deleted:
      related_count = related_model.query.count()
      self.assertEqual(related_count, 0)
    else:
      related = related_model.query.one()
      response = self.api.delete(related)
      self.assert200(response)

    related_acl_count = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type == related_model.__name__
    ).count()
    self.assertEqual(related_acl_count, 0)

    bg_task_count = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type == "BackgroundTask"
    ).count()

    all_acl_count = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type != 'PersonProfile').count()
    self.assertEqual(all_acl_count - bg_task_count, exp_acl_count)

  def test_acl_on_object_deletion(self):
    """Test related ACL records removed on related object delete"""
    self._create_propagation_acl_test_data()
    acl_count = all_models.AccessControlList.query.count()
    self.assertNotEqual(acl_count, 0)

    admin = all_models.Person.query.get(1)
    self.api.set_user(admin)

    related_models = (
        (all_models.TaskGroup, 16, False),
        (all_models.TaskGroupTask, 16, True),
        (all_models.Cycle, 2, False),
        (all_models.CycleTaskGroup, 2, True),
        (all_models.CycleTaskGroupObjectTask, 2, True),
    )
    for related_model, acl_count, is_deleted in related_models:
      self._delete_and_check_related_acl(related_model, acl_count, is_deleted)

  def test_acl_on_workflow_delete(self):
    """Test related ACL records removed on Workflow delete"""
    self._create_propagation_acl_test_data()
    acl_count = all_models.AccessControlList.query.count()
    self.assertNotEqual(acl_count, 0)

    admin = all_models.Person.query.get(1)
    self.api.set_user(admin)
    workflow = all_models.Workflow.query.one()
    response = self.api.delete(workflow)
    self.assert200(response)

    acl_count = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type != 'PersonProfile').count()
    bg_acl_count = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_type == "BackgroundTask"
    ).count()
    self.assertEqual(acl_count, bg_acl_count)

  def test_acl_for_new_related_object(self):
    """Test Workflow ACL propagation for new related objects."""
    data = self.get_workflow_dict()
    acl_map = {
        self.people_ids[0]: WF_ROLES['Admin'],
        self.people_ids[1]: WF_ROLES['Workflow Member'],
    }
    data["workflow"]["access_control_list"] = acl_helper.get_acl_list(acl_map)
    data["workflow"]["unit"] = "week"
    data["workflow"]["repeat_every"] = 1
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)

    data = self.get_task_group_dict(response.json["workflow"])
    data["task_group"]["contact"]["id"] = self.people_ids[2]
    data["task_group"]["contact"]["href"] = "/api/people/{}".format(
        self.people_ids[2])
    response = self.api.post(all_models.TaskGroup, data)
    self.assertEqual(response.status_code, 201)

    task_group = all_models.TaskGroup.eager_query().one()
    data = self.get_task_dict(task_group)
    data["task_group_task"]["start_date"] = "2018-01-04"
    data["task_group_task"]["end_date"] = "2018-01-05"
    response = self.api.post(all_models.TaskGroupTask, data)
    self.assertEqual(response.status_code, 201)

    workflow = all_models.Workflow.query.one()
    with freezegun.freeze_time("2018-01-05"):  # Generate 1 cycle
      self.generator.activate_workflow(workflow)

    cycle_task = all_models.CycleTaskGroupObjectTask.query.one()
    with factories.single_commit():
      comment = factories.CommentFactory()
      factories.RelationshipFactory(
          source=comment,
          destination=cycle_task
      )

    self._check_propagated_acl(2, has_comment=True)

  @ddt.data('Admin', 'Workflow Member')
  def test_tg_assignee(self, role_name):
    """Test TaskGroup assignee already has {0} role."""
    data = self.get_workflow_dict()
    init_acl = {
        self.people_ids[0]: WF_ROLES['Admin'],
        self.people_ids[1]: WF_ROLES[role_name],
    }
    data['workflow']['access_control_list'] = acl_helper.get_acl_list(init_acl)
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)

    data = self.get_task_group_dict(response.json["workflow"])
    data["task_group"]["contact"]["id"] = self.people_ids[1]
    data["task_group"]["contact"]["href"] = "/api/people/{}".format(
        self.people_ids[1])
    response = self.api.post(all_models.TaskGroup, data)
    self.assertEqual(response.status_code, 201)

    workflow = all_models.Workflow.query.one()
    task_group = all_models.TaskGroup.query.one()

    ac_people = all_models.AccessControlPerson.query.filter(
        all_models.AccessControlPerson.person_id == task_group.contact_id,
    ).all()
    self.assertEqual(len(ac_people), 2)

    actual = {
        (acp.ac_list.object_type, acp.ac_list.object_id)
        for acp in ac_people
    }
    self.assertIn((workflow.type, workflow.id), actual)
    self.assertNotIn((task_group.type, task_group.id), actual)

  def test_task_group_assignee_gets_workflow_member(self):  # noqa pylint: disable=invalid-name
    """Test TaskGroup assignee gets WorkflowMember role."""
    data = self.get_workflow_dict()
    init_acl = {
        self.people_ids[0]: WF_ROLES['Admin'],
        self.people_ids[1]: WF_ROLES['Workflow Member'],
    }
    data['workflow']['access_control_list'] = acl_helper.get_acl_list(init_acl)
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)

    data = self.get_task_group_dict(response.json["workflow"])
    data["task_group"]["contact"]["id"] = self.people_ids[2]
    data["task_group"]["contact"]["href"] = "/api/people/{}".format(
        self.people_ids[2])
    response = self.api.post(all_models.TaskGroup, data)
    self.assertEqual(response.status_code, 201)

    workflow = all_models.Workflow.query.one()

    wf_members = [
        acp.person.id
        for acp in
        workflow.acr_name_acl_map["Workflow Member"].access_control_people
    ]
    self.assertIn(self.people_ids[2], wf_members)

  def _create_propagation_acl_test_data(self):  # noqa pylint: disable=invalid-name
    """Create objects for Workflow ACL propagation test."""
    with freezegun.freeze_time("2017-08-9"):
      with factories.single_commit():
        workflow = wf_factories.WorkflowFactory(
            title='wf1',
            unit=all_models.Workflow.WEEK_UNIT,
            is_verification_needed=True,
            repeat_every=1)
        wf_factories.TaskGroupTaskFactory(
            title='tgt1',
            task_group=wf_factories.TaskGroupFactory(
                title='tg1',
                context=factories.ContextFactory(),
                workflow=workflow
            ),
            # One cycle should be created
            start_date=datetime.date(2017, 8, 3),
            end_date=datetime.date(2017, 8, 7)
        )
      self.generator.activate_workflow(workflow)
      workflow = all_models.Workflow.query.one()
      acl_map = {
          self.people_ids[0]: WF_ROLES['Admin'],
          self.people_ids[1]: WF_ROLES['Workflow Member'],
          self.people_ids[2]: WF_ROLES['Workflow Member'],
      }
      put_params = {'access_control_list': acl_helper.get_acl_list(acl_map)}
      response = self.api.put(workflow, put_params)
      self.assert200(response)

  def _check_propagated_acl(self, roles_count, has_comment=False):
    """ Check Workflow propagated ACL records.

    Args:
        roles_count: roles' count created in test
        has_comment: indicator that related objects contain comments
    """
    related_objects = [
        (all_models.TaskGroup.query.one().id, all_models.TaskGroup.__name__),
        (all_models.TaskGroupTask.query.one().id,
         all_models.TaskGroupTask.__name__),
        (all_models.Cycle.query.one().id, all_models.Cycle.__name__),
        (all_models.CycleTaskGroup.query.one().id,
         all_models.CycleTaskGroup.__name__),
        (all_models.CycleTaskGroupObjectTask.query.one().id,
         all_models.CycleTaskGroupObjectTask.__name__),
    ]
    if has_comment:
      related_objects.append(
          (all_models.Comment.query.one().id,
           all_models.Comment.__name__),
      )

    # *2 is for relationships
    related_count = roles_count * len(related_objects) * 2

    # additional acl count for Relationship and Comment propagation of
    # Task Assignees/Task Secondary Assignees access control roles
    if has_comment:
      related_count += roles_count * 2

    all_acls = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.parent_id_nn != 0
    ).count()
    self.assertEqual(
        all_acls,
        related_count
    )

  def test_assign_workflow_acl(self):
    """Test propagation Workflow ACL roles on Workflow's update ACL records."""
    self._create_propagation_acl_test_data()
    self._check_propagated_acl(2)

  def test_unassign_workflow_acl(self):
    """Test propagation Workflow ACL roles on person unassigned."""
    self._create_propagation_acl_test_data()
    with freezegun.freeze_time("2017-08-9"):
      workflow = all_models.Workflow.query.one()
      acl_map = {
          self.people_ids[0]: WF_ROLES['Admin'],
          self.people_ids[1]: WF_ROLES['Workflow Member'],
      }
      put_params = {'access_control_list': acl_helper.get_acl_list(acl_map)}
      response = self.api.put(workflow, put_params)
      self.assert200(response)

    self._check_propagated_acl(2)

  def test_post_workflow_with_acl(self):
    """Test PUT workflow with ACL."""
    data = self.get_workflow_dict()

    exp_res = {
        self.wf_admin_id: WF_ROLES['Admin'],
        self.people_ids[0]: WF_ROLES['Admin'],
        self.people_ids[1]: WF_ROLES['Workflow Member'],
        self.people_ids[2]: WF_ROLES['Workflow Member'],
        self.people_ids[3]: WF_ROLES['Workflow Member']
    }
    data['workflow']['access_control_list'] = acl_helper.get_acl_list(exp_res)
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)
    workflow = all_models.Workflow.eager_query().one()
    act_res = {person.id: acl.ac_role_id
               for person, acl in workflow.access_control_list}
    self.assertDictEqual(exp_res, act_res)

  def test_update_workflow_acl_people(self):
    """Test PUT workflow with updated ACL."""
    data = self.get_workflow_dict()
    init_map = {
        self.wf_admin_id: WF_ROLES['Admin'],
        self.people_ids[0]: WF_ROLES['Workflow Member'],
    }
    data['workflow']['access_control_list'] = acl_helper.get_acl_list(init_map)
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)
    exp_res = {
        self.people_ids[0]: WF_ROLES['Admin'],
        self.people_ids[1]: WF_ROLES['Admin'],
        self.people_ids[2]: WF_ROLES['Workflow Member'],
        self.people_ids[3]: WF_ROLES['Workflow Member'],
        self.people_ids[4]: WF_ROLES['Workflow Member']
    }
    workflow = all_models.Workflow.eager_query().one()
    put_params = {'access_control_list': acl_helper.get_acl_list(exp_res)}
    response = self.api.put(workflow, put_params)
    self.assert200(response)
    workflow = all_models.Workflow.eager_query().one()
    act_res = {person.id: acl.ac_role_id
               for person, acl in workflow.access_control_list}
    self.assertDictEqual(exp_res, act_res)

  def test_send_invalid_data(self):
    """Test send invalid data on Workflow post."""
    data = self.get_workflow_dict()
    del data["workflow"]["title"]
    response = self.api.post(all_models.Workflow, data)
    self.assert400(response)

  def test_create_one_time_workflows(self):
    """Test simple create one time Workflow over api."""
    data = self.get_workflow_dict()
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)

  def test_create_weekly_workflow(self):
    """Test create valid weekly wf"""
    data = self.get_workflow_dict()
    data["workflow"]["repeat_every"] = 7
    data["workflow"]["unit"] = "day"
    data["workflow"]["title"] = "Weekly"
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)

  def test_create_annually_workflow(self):
    """Test create valid annual wf"""
    data = self.get_workflow_dict()
    data["workflow"]["repeat_every"] = 12
    data["workflow"]["unit"] = "month"
    data["workflow"]["title"] = "Annually"
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 201)

  @ddt.data("wrong value", 0, -4)
  def test_create_wrong_repeat_every_workflow(self, value):  # noqa pylint: disable=invalid-name
    """Test case for invalid repeat_every value"""
    data = self.get_workflow_dict()
    data["workflow"]["repeat_every"] = value
    data["workflow"]["unit"] = "month"
    data["workflow"]["title"] = "Wrong wf"
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 400)

  def test_create_wrong_unit_workflow(self):
    """Test case for invalid unit value"""
    data = self.get_workflow_dict()
    data["workflow"]["repeat_every"] = 12
    data["workflow"]["unit"] = "wrong value"
    data["workflow"]["title"] = "Wrong wf"
    response = self.api.post(all_models.Workflow, data)
    self.assertEqual(response.status_code, 400)

  def test_create_task_group(self):
    """Test create task group over api."""
    wf_data = self.get_workflow_dict()
    wf_data["workflow"]["title"] = "Create_task_group"
    wf_response = self.api.post(all_models.Workflow, wf_data)

    data = self.get_task_group_dict(wf_response.json["workflow"])

    response = self.api.post(all_models.TaskGroup, data)
    self.assertEqual(response.status_code, 201)

  def test_incorrect_wf_id_on_tg_post(self):
    """Tests incorrect id in tg post payload.

    Tests that 400 is raised on tg post if id in
    payload has incorrect type."""
    wf_data = self.get_workflow_dict()
    wf_response = self.api.post(all_models.Workflow, wf_data)
    data = {
        "workflow": {
            "id": {
                "id": wf_response.json["workflow"]["id"]
            },
            "type": "Workflow"
        }
    }
    tg_response = self.api.post(all_models.TaskGroup, data)
    self.assertEqual(tg_response.status_code, 400)
    self.assertEqual(tg_response.json["message"],
                     ("Either type or id are specified "
                      "incorrectly in the request payload."))

  @staticmethod
  def get_workflow_dict():
    return {
        "workflow": {
            "custom_attribute_definitions": [],
            "custom_attributes": {},
            "title": "One_time",
            "description": "",
            "unit": None,
            "repeat_every": None,
            "notify_on_change": False,
            "task_group_title": "Task Group 1",
            "notify_custom_message": "",
            "is_verification_needed": True,
            "context": None,
        }
    }

  def get_task_group_dict(self, workflow):
    return {
        "task_group": {
            "custom_attribute_definitions": [],
            "custom_attributes": {},
            "_transient": {},
            "contact": {
                "id": self.wf_admin_id,
                "href": "/api/people/{}".format(self.wf_admin_id),
                "type": "Person"
            },
            "workflow": {
                "id": workflow["id"],
                "href": "/api/workflows/%d" % workflow["id"],
                "type": "Workflow"
            },
            "context": {
                "id": workflow["context"]["id"],
                "href": "/api/contexts/%d" % workflow["context"]["id"],
                "type": "Context"
            },
            "modal_title": "Create Task Group",
            "title": "Create_task_group",
            "description": "",
        }
    }

  def get_task_dict(self, task_group):
    return {
        "task_group_task": {
            "start_date": "2017-12-25",
            "end_date": "2017-12-31",
            "custom_attributes": {},
            "contact": {
                "id": self.wf_admin_id,
                "href": "/api/people/{}".format(self.wf_admin_id),
                "type": "Person"
            },
            "task_group": {
                "id": task_group.id,
                "href": "/api/task_groups/{}".format(task_group.id),
                "type": "TaskGroup"
            },
            "context": {
                "id": task_group.context_id,
                "href": "/api/contexts/{}".format(task_group.context_id),
                "type": "Context"
            },
            "title": "Create_task",
            "task_type": "text",
            "description": ""
        }
    }

  @ddt.data({},
            {"repeat_every": 5, "unit": "month"})
  def test_repeat_multiplier_field(self, data):
    """Check repeat_multiplier is set to 0 after wf creation."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(**data)
    workflow_id = workflow.id
    self.assertEqual(
        0, all_models.Workflow.query.get(workflow_id).repeat_multiplier)

  # TODO: Unskip in the patch 2
  @unittest.skip("Will be activated in patch 2")
  def test_change_to_one_time_wf(self):
    """Check repeat_every and unit can be set to Null only together."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(repeat_every=12,
                                              unit="day")
    resp = self.api.put(workflow, {"repeat_every": None,
                                   "unit": None})
    self.assert200(resp)

  @ddt.data({"repeat_every": 5},
            {"unit": "month"})
  def test_change_repeat_every(self, data):
    """Check repeat_every or unit can not be changed once set."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
    resp = self.api.put(workflow, data)
    self.assert400(resp)

  def test_not_change_to_one_time_wf(self):
    """Check repeat_every or unit can't be set to Null separately.
    This test will be useful in the 2nd patch, where we allow to change
    WF setup
    """
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(repeat_every=12,
                                              unit="day")
    resp = self.api.put(workflow, {"repeat_every": None})
    self.assert400(resp)
    resp = self.api.put(workflow, {"unit": None})
    self.assert400(resp)

  @ddt.data(True, False)
  def test_autogen_verification_flag(self, flag):
    """Check is_verification_needed flag for activate WF action."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(is_verification_needed=flag)
      group = wf_factories.TaskGroupFactory(workflow=workflow)
      wf_factories.TaskGroupTaskFactory(task_group=group)
    data = [{
        "cycle": {
            "autogenerate": True,
            "isOverdue": False,
            "title": factories.random_str(prefix='cycle - '),
            "workflow": {
                "id": workflow.id,
                "type": "Workflow",
            },
            "context": {
                "id": workflow.context_id,
                "type": "Context",
            },
        }
    }]
    resp = self.api.send_request(
        self.api.client.post,
        api_link="/api/cycles",
        data=data)
    cycle_id = resp.json[0][1]["cycle"]["id"]
    self.assertEqual(
        flag, all_models.Cycle.query.get(cycle_id).is_verification_needed)

  @ddt.data(True, False)
  def test_verification_flag_positive(self, flag):  # noqa pylint: disable=invalid-name
    """is_verification_needed flag is changeable for DRAFT workflow."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(is_verification_needed=flag)
    self.assertEqual(workflow.status, all_models.Workflow.DRAFT)
    workflow_id = workflow.id
    resp = self.api.put(workflow, {"is_verification_needed": not flag})
    self.assert200(resp)
    self.assertEqual(
        all_models.Workflow.query.get(workflow_id).is_verification_needed,
        not flag)

  @ddt.data(True, False)
  def test_verification_flag_negative(self, flag):
    """Test immutable verification flag on active workflows."""
    with freezegun.freeze_time("2017-08-10"):
      with factories.single_commit():
        workflow = wf_factories.WorkflowFactory(
            unit=all_models.Workflow.WEEK_UNIT,
            is_verification_needed=flag,
            repeat_every=1)
        wf_factories.TaskGroupTaskFactory(
            task_group=wf_factories.TaskGroupFactory(
                context=factories.ContextFactory(),
                workflow=workflow
            ),
            # Two cycles should be created
            start_date=datetime.date(2017, 8, 3),
            end_date=datetime.date(2017, 8, 7))
      workflow_id = workflow.id
      self.assertEqual(workflow.status, all_models.Workflow.DRAFT)
      self.generator.activate_workflow(workflow)
      workflow = all_models.Workflow.query.get(workflow_id)
      self.assertEqual(workflow.status, all_models.Workflow.ACTIVE)
      resp = self.api.put(workflow, {"is_verification_needed": not flag})
      self.assert400(resp)
      workflow = all_models.Workflow.query.get(workflow_id)
      self.assertEqual(workflow.is_verification_needed, flag)

      # End all current cycles
      for cycle in workflow.cycles:
        self.generator.modify_object(cycle, {'is_current': False})
      workflow = all_models.Workflow.query.filter(
          all_models.Workflow.id == workflow_id).first()
      self.assertEqual(workflow.status, all_models.Workflow.INACTIVE)
      resp = self.api.put(workflow, {"is_verification_needed": not flag})
      self.assert400(resp)
      workflow = all_models.Workflow.query.get(workflow_id)
      self.assertEqual(workflow.is_verification_needed, flag)

  @ddt.data(True, False)
  def test_not_change_vf_flag(self, flag):
    """Check is_verification_needed not change on update."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(is_verification_needed=flag)
    workflow_id = workflow.id
    resp = self.api.put(workflow, {"is_verification_needed": flag})
    self.assert200(resp)
    self.assertEqual(
        flag,
        all_models.Workflow.query.get(workflow_id).is_verification_needed)

  @ddt.data(True, False, None)
  def test_create_vf_flag(self, flag):
    """Check is_verification_needed flag setup on create."""
    data = self.get_workflow_dict()
    if flag is None:
      data['workflow'].pop('is_verification_needed', None)
    else:
      data['workflow']['is_verification_needed'] = flag
    resp = self.api.post(all_models.Workflow, data)
    self.assertEqual(201, resp.status_code)
    workflow_id = resp.json['workflow']['id']
    self.assertEqual(
        flag if flag is not None else False,
        all_models.Workflow.query.get(workflow_id).is_verification_needed)

  @ddt.data(
      ('Editor', 201, 1),
      ('Creator', 403, 0),
      ('Reader', 403, 0),
      ('Administrator', 201, 1),
  )
  @ddt.unpack
  def test_create_ctg_wf_member(self, member_role, response_code, exp_count):
    """Check creation cycle task group by workflow member"""
    member = self.create_user_with_role(member_role)
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
      workflow.add_person_with_role_name(member, 'Workflow Member')
      task_group = wf_factories.TaskGroupFactory(
          title='TestTG',
          context=factories.ContextFactory(),
          workflow=workflow
      )
      wf_factories.TaskGroupTaskFactory(
          title='TestTGT',
          task_group=task_group,
          start_date=datetime.date(2017, 8, 3),
          end_date=datetime.date(2017, 8, 7)
      )
      cycle = wf_factories.CycleFactory(workflow=workflow)
    self.generator.activate_workflow(workflow)
    self.api.set_user(member)

    response = self.api.post(all_models.CycleTaskGroup, {
        "cycle_task_group": {
            "cycle": {
                "id": cycle.id,
            },
            "contact": {
                "id": member.id,
            },
            "title": 'title1',
        },
    })

    self.assertEquals(response.status_code, response_code)
    count = len(all_models.CycleTaskGroup.query.all())
    self.assertEquals(count, exp_count)

  @ddt.data(
      'Creator',
      'Reader',
  )
  def test_create_cycle_task(self, member_role):
    """Check creation cycle task group by workflow member"""
    member = self.create_user_with_role(member_role)
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
      workflow.add_person_with_role_name(member, 'Workflow Member')
      cycle = wf_factories.CycleFactory(workflow=workflow)
      cycle_id = cycle.id
      ctg_id = wf_factories.CycleTaskGroupFactory(
          cycle=cycle,
          title='TestCTG',
      ).id
    self.generator.activate_workflow(workflow)
    self.api.set_user(member)

    response = self.api.post(all_models.CycleTaskGroupObjectTask, {
        "cycle_task_group_object_task": {
            "title": "New Cycle Task",
            "start_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "end_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "context": None,
            "task_type": "text",
            "cycle_task_group": {
                "id": ctg_id,
                "type": "Task Group",
            },
            "cycle": {
                "id": cycle_id,
                "type": "Cycle",
            },
        }
    })

    self.assert403(response)
    count = len(all_models.CycleTaskGroupObjectTask.query.all())
    self.assertEquals(count, 0)

  @ddt.data(
      'Reader',
      'Editor',
      'Administrator',
      'Creator',
  )
  def test_create_ctg_wf_admin(self, admin_role):
    """Check creation cycle task group by workflow admin"""
    admin = self.create_user_with_role(admin_role)
    exp_count = 1
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
      workflow.add_person_with_role_name(admin, 'Admin')
      task_group = wf_factories.TaskGroupFactory(
          title='TestTG',
          context=factories.ContextFactory(),
          workflow=workflow
      )
      wf_factories.TaskGroupTaskFactory(
          title='TestTGT',
          task_group=task_group,
          start_date=datetime.date(2017, 8, 3),
          end_date=datetime.date(2017, 8, 7)
      )
      cycle = wf_factories.CycleFactory(workflow=workflow)
    self.generator.activate_workflow(workflow)
    self.api.set_user(admin)

    response = self.api.post(all_models.CycleTaskGroup, {
        "cycle_task_group": {
            "cycle": {
                "id": cycle.id,
            },
            "contact": {
                "id": admin.id,
            },
            "title": 'title1',
        },
    })

    self.assert201(response)
    count = len(all_models.CycleTaskGroup.query.all())
    self.assertEquals(count, exp_count)

  def test_workflow_cloning(self):
    """Test cloning a workflow by users w/ and w/o read permissions

    This test checks that a user can create a workflow and after
    successfully clone it. But a cloning must be failed if some other user
    without a read permission try to do it.
    """
    user_role = "Creator"
    with factories.single_commit():
      person1 = self.create_user_with_role(user_role)
      person2 = self.create_user_with_role(user_role)
      workflow = wf_factories.WorkflowFactory()
      workflow.add_person_with_role_name(person1, 'Admin')

    person2_id = person2.id  # noqa #pylint: disable=unused-variable
    workflow_id = workflow.id
    self.generator.activate_workflow(workflow)

    data = [{
        "workflow": {
            "task_group_title": "Task Group 1",
            "is_verification_needed": False,
            "title": "test_title",
            "clone": workflow_id,
            "context": None,
            "clone_people": False,
            "clone_tasks": False,
            "clone_objects": True,
            "access_control_list": [],
        }
    }]

    # perform a request using a user w/ a read permission
    self.api.set_user(person1)
    response = self.api.post(all_models.Workflow, data)
    self.assert200(response)

    # perform a request using a user w/o a read permission
    self.api.set_user(person2)
    response = self.api.post(all_models.Workflow, data)
    self.assert403(response)

  @ddt.data(
      ('Editor', 200, 0),
      ('Creator', 403, 1),
      ('Reader', 403, 1),
      ('Administrator', 200, 0),
  )
  @ddt.unpack
  def test_delete_ctg_wf_member(self, member_role, response_code, exp_count):
    """Check deletion cycle task group by workflow member"""
    member = self.create_user_with_role(member_role)
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
      workflow.add_person_with_role_name(member, 'Workflow Member')
      task_group = wf_factories.TaskGroupFactory(
          title='TestTG',
          context=factories.ContextFactory(),
          workflow=workflow
      )
      wf_factories.TaskGroupTaskFactory(
          title='TestTGT',
          task_group=task_group,
          start_date=datetime.date(2017, 8, 3),
          end_date=datetime.date(2017, 8, 7)
      )
      cycle = wf_factories.CycleFactory(workflow=workflow)
      cycle_task_group = wf_factories.CycleTaskGroupFactory(
          cycle=cycle,
          title='Title1'
      )
    ctg = all_models.CycleTaskGroup.query.get(cycle_task_group.id)
    self.generator.activate_workflow(workflow)
    self.api.set_user(member)

    response = self.api.delete(ctg)

    self.assertEquals(response.status_code, response_code)
    count = len(all_models.CycleTaskGroup.query.all())
    self.assertEquals(count, exp_count)

  @ddt.data(
      'Reader',
      'Editor',
      'Administrator',
      'Creator',
  )
  def test_delete_ctg_wf_admin(self, admin_role):
    """Check deletion cycle task group by workflow member"""
    admin = self.create_user_with_role(admin_role)
    exp_count = 0
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
      workflow.add_person_with_role_name(admin, 'Admin')
      task_group = wf_factories.TaskGroupFactory(
          title='TestTG',
          context=factories.ContextFactory(),
          workflow=workflow
      )
      wf_factories.TaskGroupTaskFactory(
          title='TestTGT',
          task_group=task_group,
          start_date=datetime.date(2017, 8, 3),
          end_date=datetime.date(2017, 8, 7)
      )
      cycle = wf_factories.CycleFactory(workflow=workflow)
      cycle_task_group = wf_factories.CycleTaskGroupFactory(
          cycle=cycle,
          title='Title1'
      )
    ctg = all_models.CycleTaskGroup.query.get(cycle_task_group.id)
    self.generator.activate_workflow(workflow)
    self.api.set_user(admin)

    response = self.api.delete(ctg)

    self.assert200(response)
    count = len(all_models.CycleTaskGroup.query.all())
    self.assertEquals(count, exp_count)
