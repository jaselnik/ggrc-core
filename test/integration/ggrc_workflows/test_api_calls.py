# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for api calls on ggrc_workflows module."""

import datetime
import collections
import string
from mock import MagicMock, patch

import ddt

from ggrc import db
from ggrc.models import all_models
from ggrc.fulltext import mysql
from ggrc.notifications.common import generate_cycle_tasks_notifs

from integration.ggrc import TestCase

from integration.ggrc.api_helper import Api
from integration.ggrc import generator
from integration.ggrc.models import factories
from integration.ggrc_workflows import WorkflowTestCase
from integration.ggrc_workflows.helpers import workflow_api
from integration.ggrc_workflows.models import factories as wf_factories


class TestTaskGroupTaskApiPost(WorkflowTestCase):
  """
  Tesk TestTaskGroupTask basic api actions
  """
  def test_create_tgt_correct_dates(self):
    """Test case for correct tgt start_ end_ dates"""
    response, _ = self.generator.generate_task_group_task(
        data={"start_date": datetime.date.today(),
              "end_date": datetime.date.today() + datetime.timedelta(days=4)}
    )
    self.assertEqual(response.status_code, 201)

  def test_create_tgt_wrong_dates(self):
    """Test case for tgt wrong start_ end_ dates"""
    response, _ = self.generator.generate_task_group_task(
        data={
            "start_date": datetime.date.today(),
            "end_date": datetime.date.today() - datetime.timedelta(days=4)
        }
    )
    self.assertEqual(response.status_code, 400)

  def test_tgt_has_view_dates(self):
    """Test get view only fields for TGT."""
    workflow = wf_factories.WorkflowFactory()
    task_group = wf_factories.TaskGroupFactory(workflow=workflow)
    tgt = wf_factories.TaskGroupTaskFactory(task_group=task_group)
    resp = self.api.get(tgt, tgt.id)
    self.assertIn("task_group_task", resp.json)
    self.assertIn("view_start_date", resp.json["task_group_task"])
    self.assertIn("view_end_date", resp.json["task_group_task"])


@ddt.ddt
class TestStatusApiPost(TestCase):
  """Test for api calls changes states of Cycle, Tasks and Groups."""

  def setUp(self):
    super(TestStatusApiPost, self).setUp()
    self.api = Api()
    with factories.single_commit():
      self.workflow = wf_factories.WorkflowFactory()
      self.cycle = wf_factories.CycleFactory(workflow=self.workflow)
      self.group = wf_factories.CycleTaskGroupFactory(
          cycle=self.cycle,
          context=self.cycle.workflow.context
      )
      self.task = wf_factories.CycleTaskGroupObjectTaskFactory(
          cycle=self.cycle,
          cycle_task_group=self.group,
          context=self.cycle.workflow.context
      )

  def setup_cycle_state(self, is_verification_needed):
    """Setup cycle is_verification_needed state."""
    self.cycle.is_verification_needed = is_verification_needed
    db.session.add(self.cycle)
    db.session.commit()

  @ddt.data(u"Assigned",
            u"In Progress",
            u"Finished",
            u"Verified",
            u"Declined")
  def test_set_state_verified_task(self, state):
    """Check state for verification required task."""
    self.setup_cycle_state(True)
    resp = self.api.put(self.task, data={"status": state})
    task = all_models.CycleTaskGroupObjectTask.query.get(
        resp.json["cycle_task_group_object_task"]["id"]
    )
    self.assertEqual(state, task.status)

  @ddt.data((u"Assigned", True),
            (u"In Progress", True),
            (u"Finished", True),
            (u"Verified", False),
            (u"Declined", False))
  @ddt.unpack
  def test_state_non_verified_task(self, state, is_valid):
    """Check state for verification non required task."""
    self.setup_cycle_state(False)
    resp = self.api.put(self.task, data={"status": state})
    if is_valid:
      task = all_models.CycleTaskGroupObjectTask.query.get(
          resp.json["cycle_task_group_object_task"]["id"]
      )
      self.assertEqual(state, task.status)
    else:
      self.assert400(resp)

  @ddt.data(u"Assigned",
            u"In Progress",
            u"Finished",
            u"Verified")
  def test_state_verified_group(self, state):
    """Check state for verification required group.
    API PUT is restricted for all users 403"""
    self.setup_cycle_state(True)
    resp = self.api.put(self.group, data={"status": state})
    self.assert403(resp)

  def test_update_title_of_cycle_task_group(self):
    # pylint: disable=invalid-name
    """Check title updating of Cycle Task Group """
    resp = self.api.put(self.group, data={"title": "Updated title"})
    self.assert403(resp)

  @ddt.data(u"Assigned",
            u"In Progress",
            u"Finished",
            u"Verified")
  def test_state_verified_cycle(self, state):
    """Check state for verification required cycle."""
    self.setup_cycle_state(True)
    resp = self.api.put(self.cycle, data={"status": state})
    cycle = all_models.Cycle.query.get(resp.json["cycle"]["id"])
    self.assertEqual(state, cycle.status)

  def test_update_title_of_cycle(self):
    """Check title updating of Cycle"""
    resp = self.api.put(self.cycle, data={"title": "Updated title"})
    self.assert403(resp)

  @ddt.data((u"Assigned", True),
            (u"In Progress", True),
            (u"Finished", True),
            (u"Verified", False))
  @ddt.unpack
  def test_state_non_verified_cycle(self, state, is_valid):
    """Check state for verification non required cycle."""
    self.setup_cycle_state(False)
    resp = self.api.put(self.cycle, data={"status": state})
    if is_valid:
      cycle = all_models.Cycle.query.get(resp.json["cycle"]["id"])
      self.assertEqual(state, cycle.status)
    else:
      self.assert400(resp)

  @ddt.data(True, False)
  def test_change_is_verification(self, flag):
    """Try to change cycle is_verification_needed."""
    self.setup_cycle_state(flag)
    resp = self.api.put(self.cycle, data={"is_verification_needed": flag})
    self.assert200(resp)
    cycle = all_models.Cycle.query.get(resp.json["cycle"]["id"])
    self.assertEqual(flag, cycle.is_verification_needed)

  @ddt.data(True, False)
  def test_change_is_vf_wrong(self, flag):
    """Try to change cycle is_verification_needed not changed."""
    self.setup_cycle_state(flag)
    resp = self.api.put(self.cycle, data={"is_verification_needed": not flag})
    self.assert200(resp)
    cycle = all_models.Cycle.query.get(resp.json["cycle"]["id"])
    self.assertEqual(flag, cycle.is_verification_needed)

  @ddt.data(True, False)
  def test_change_cycle_none_flag(self, flag):
    """Try to change cycle is_verification_needed not changed
    by not sending is_verification_flag."""
    self.setup_cycle_state(flag)
    resp = self.api.put(self.cycle, not_send_fields=["is_verification_needed"])
    self.assert200(resp)
    cycle = all_models.Cycle.query.get(resp.json["cycle"]["id"])
    self.assertEqual(flag, cycle.is_verification_needed)

  @ddt.data(True, False)
  def test_change_wf_none_flag(self, flag):
    """Try to change workflow is_verification_needed not changed by
    not sending is_verification_flag."""
    db.engine.execute(
        "update workflows set is_verification_needed={} where id={}".format(
            flag, self.workflow.id
        )
    )
    resp = self.api.put(self.workflow,
                        not_send_fields=["is_verification_needed"])
    self.assert200(resp)
    workflow = all_models.Workflow.query.get(resp.json["workflow"]["id"])
    self.assertEqual(flag, workflow.is_verification_needed)

  @ddt.data((u"In Progress", True, True),
            (u"In Progress", False, True),
            (u"Declined", True, True),
            (u"Verified", True, False),
            (u"Finished", True, True),
            (u"Finished", False, False))
  @ddt.unpack
  def test_move_to_history(self, state, is_vf_needed, is_current):
    """Moved to history if state changed."""
    self.setup_cycle_state(is_vf_needed)
    resp = self.api.put(self.task, data={"status": state})
    task = all_models.CycleTaskGroupObjectTask.query.get(
        resp.json["cycle_task_group_object_task"]["id"]
    )
    self.assertEqual(is_current, task.cycle.is_current)


@ddt.ddt
class TestCloneWorkflow(TestCase):
  """Test clone Workflow operation."""

  def setUp(self):
    super(TestCloneWorkflow, self).setUp()
    self.object_generator = generator.ObjectGenerator()

  @ddt.data(
      (None, None),
      (all_models.Workflow.DAY_UNIT, 10),
      (all_models.Workflow.MONTH_UNIT, 10),
      (all_models.Workflow.WEEK_UNIT, 10),
  )
  @ddt.unpack
  def test_workflow_copy(self, unit, repeat_every):
    """Check clone wf with unit and repeat."""
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(unit=unit,
                                              repeat_every=repeat_every)
    _, clone_wf = self.object_generator.generate_object(
        all_models.Workflow, {"title": "WF - copy 1", "clone": workflow.id})
    self.assertEqual(unit, clone_wf.unit)
    self.assertEqual(repeat_every, clone_wf.repeat_every)

  @patch("ggrc_workflows.get_copy_title")
  def test_workflow_copy_title(self, get_copy_title_patch):
    """Check if get_copy_title is called with proper arguments."""
    expected_title = 'Copy Title'
    get_copy_title_patch.return_value = expected_title

    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory()
      cloned_workflow = wf_factories.WorkflowFactory(parent_id=workflow.id)
      cloned_title = cloned_workflow.title

    _, clone_wf = self.object_generator.generate_object(
        all_models.Workflow, {"title": "WF - copy 1", "clone": workflow.id})
    get_copy_title_patch.assert_called_once_with(
        workflow.title, [cloned_title])
    self.assertEqual(clone_wf.title, expected_title)
    self.assertEqual(clone_wf.parent_id, workflow.id)


@ddt.ddt
class TestStatusApiPatch(TestCase):
  """Test CycleTask's statuses change via PATCH operation."""
  ASSIGNED = all_models.CycleTaskGroupObjectTask.ASSIGNED
  IN_PROGRESS = all_models.CycleTaskGroupObjectTask.IN_PROGRESS
  FINISHED = all_models.CycleTaskGroupObjectTask.FINISHED
  DEPRECATED = all_models.CycleTaskGroupObjectTask.DEPRECATED
  VERIFIED = all_models.CycleTaskGroupObjectTask.VERIFIED
  DECLINED = all_models.CycleTaskGroupObjectTask.DECLINED

  def _create_cycle_structure(self):
    """Create cycle structure.

    It will create workflow, cycle, group and 3 tasks in that group.

    Retruns tuple:
        workflow, cycle, group and list of tasks.
    """
    wf_slug = "WF-SLUG-{}".format(factories.random_str(
        length=6, chars=string.ascii_letters))
    with factories.single_commit():
      workflow = wf_factories.WorkflowFactory(slug=wf_slug,
                                              is_verification_needed=True)
      task_group = wf_factories.TaskGroupFactory(workflow=workflow)
      for ind in xrange(3):
        wf_factories.TaskGroupTaskFactory(
            task_group=task_group,
            title='task{}'.format(ind),
            start_date=datetime.datetime.now(),
            end_date=datetime.datetime.now() + datetime.timedelta(7)
        )
    data = workflow_api.get_cycle_post_dict(workflow)
    self.api.post(all_models.Cycle, data)
    workflow = all_models.Workflow.query.filter_by(slug=wf_slug).one()
    cycle = all_models.Cycle.query.filter_by(workflow_id=workflow.id).one()
    group = all_models.CycleTaskGroup.query.filter_by(cycle_id=cycle.id).one()
    tasks = all_models.CycleTaskGroupObjectTask.query.filter_by(
        cycle_id=cycle.id).all()
    return workflow, cycle, group, tasks

  def setUp(self):
    super(TestStatusApiPatch, self).setUp()
    self.api = Api()

    with factories.single_commit():
      self.assignee = factories.PersonFactory(email="assignee@example.com")
      (
          self.workflow,
          self.cycle,
          self.group,
          self.tasks,
      ) = self._create_cycle_structure()
    self.group_id = self.group.id
    # Emulate that current user is assignee for all test CycleTasks.
    all_models.CycleTaskGroupObjectTask.current_user_wfa_or_assignee = (
        MagicMock(return_value=True))

  def _update_ct_via_patch(self, new_states):
    """Update CycleTasks' state via PATCH.

    Args:
        new_states: List of states to which CTs should be moved via PATCH.

    Returns:
        JSON response which was returned by back-end.
    """
    data = [{"state": state, "id": self.tasks[ind].id}
            for ind, state in enumerate(new_states)]
    resp = self.api.patch(all_models.CycleTaskGroupObjectTask, data)
    return resp.json

  def _get_exp_response(self, exp_res):
    """Format expected response from CycleTasks' test data indexes.

    Args:
        exp_res: Expected results dict: {test_ctask_index: response_status}

    Returns:
        [{'id': updated_task_id, 'status': 'success|skipped|error'}, ...]
    """
    return [{'id': self.tasks[ind].id, 'status': status}
            for ind, status in exp_res.iteritems()]

  @ddt.data(
      (
          # New statuses which we try to set during the test
          [IN_PROGRESS, IN_PROGRESS, IN_PROGRESS],
          # Expected results: {test_ctask_index: response_status}
          {0: 'updated', 1: 'updated', 2: 'updated'},
          # Expected states after update
          [IN_PROGRESS, IN_PROGRESS, IN_PROGRESS]
      ),
      (
          [DEPRECATED, DEPRECATED, DEPRECATED],
          {0: 'updated', 1: 'updated', 2: 'updated'},
          [DEPRECATED, DEPRECATED, DEPRECATED]
      ),
      (
          [FINISHED, FINISHED, FINISHED],
          {0: 'not allowed status', 1: 'not allowed status',
           2: 'not allowed status'},
          [ASSIGNED, ASSIGNED, ASSIGNED]
      )
  )
  @ddt.unpack
  def test_ct_status_bulk_update_ok(self, new_states, exp_res, exp_states):
    """Check CycleTasks' state update with valid data via PATCH."""
    self.assertItemsEqual(self._get_exp_response(exp_res),
                          self._update_ct_via_patch(new_states))
    self.assertItemsEqual(
        exp_states,
        [obj.status for obj in all_models.CycleTaskGroupObjectTask.query])

  def test_ct_status_bulk_update_json_error(self):  # noqa pylint: disable=invalid-name
    """Check CycleTasks' state update with invalid data via PATCH."""
    exp_resp = {
        "message": "Request's JSON contains multiple statuses for CycleTasks",
        "code": 400
    }
    self.assertEqual(exp_resp, self._update_ct_via_patch([self.IN_PROGRESS,
                                                          self.FINISHED,
                                                          self.IN_PROGRESS]))
    self.assertItemsEqual(
        [self.ASSIGNED, self.ASSIGNED, self.ASSIGNED],
        [obj.status for obj in all_models.CycleTaskGroupObjectTask.query])

  def test_ct_status_bulk_update_without_permissions(self):  # noqa pylint: disable=invalid-name
    """Check CycleTasks' state update without permissions via PATCH."""
    # Emulate that current user is not assignee for all test CycleTasks.
    all_models.CycleTaskGroupObjectTask.current_user_wfa_or_assignee = (
        MagicMock(return_value=False))
    self.assertItemsEqual(
        self._get_exp_response({0: 'forbidden',
                                1: 'forbidden',
                                2: 'forbidden'}),
        self._update_ct_via_patch([self.IN_PROGRESS,
                                   self.IN_PROGRESS,
                                   self.IN_PROGRESS]))
    self.assertItemsEqual(
        [self.ASSIGNED, self.ASSIGNED, self.ASSIGNED],
        [obj.status for obj in all_models.CycleTaskGroupObjectTask.query])

  def test_ct_status_bulk_update_invalid_state(self):  # noqa pylint: disable=invalid-name
    """Check CycleTasks' state update with invalid statuses via PATCH."""
    exp_resp = {
        "message": "Request's JSON contains invalid statuses for CycleTasks",
        "code": 400
    }
    self.assertItemsEqual(exp_resp,
                          self._update_ct_via_patch(['InVaLiD', 'InVaLiD']))
    self.assertItemsEqual(
        [self.ASSIGNED, self.ASSIGNED, self.ASSIGNED],
        [obj.status for obj in all_models.CycleTaskGroupObjectTask.query])

  def refresh_set_up_instances(self):
    """Update set up instances after request operation."""
    self.tasks = all_models.CycleTaskGroupObjectTask.query.order_by(
        all_models.CycleTaskGroupObjectTask.id
    ).all()
    self.group = all_models.CycleTaskGroup.query.get(self.group_id)
    self.cycle = self.group.cycle
    self.workflow = self.group.cycle.workflow

  def assert_latest_revision_status(self, *obj_status_chain):
    """Assert last status for object and status chain."""
    objs_status_dict = {(o.type, o.id): s for o, s in obj_status_chain}
    revisions = []
    for o_type, o_id in objs_status_dict:
      revisions.append(all_models.Revision.query.filter(
          all_models.Revision.resource_id == o_id,
          all_models.Revision.resource_type == o_type
      ))
    revisions_query = revisions[0].union(
        *revisions[1:]
    ).order_by(
        all_models.Revision.id
    )
    revisions_dict = collections.defaultdict(list)
    for revision in revisions_query:
      key = (revision.resource_type, revision.resource_id)
      revisions_dict[key].append(revision.content)
    for key, status in objs_status_dict.iteritems():
      self.assertIn(key, revisions_dict)
      content = revisions_dict[key][-1]
      self.assertIn("status", content)
      self.assertEqual(status, content["status"])

  def assert_searchable_by_status(self, *obj_status_chain):
    """Assert expected status in full text search."""
    objs_status_dict = {(o.type, o.id): s for o, s in obj_status_chain}
    full_text_properties = []
    for o_type, o_id in objs_status_dict:
      full_text_properties.append(
          mysql.MysqlRecordProperty.query.filter(
              mysql.MysqlRecordProperty.key == o_id,
              mysql.MysqlRecordProperty.type == o_type,
              mysql.MysqlRecordProperty.property == "status",
          )
      )
    query = full_text_properties[0].union(*full_text_properties[1:])
    full_text_dict = {(f.type, f.key): f.content for f in query}
    for key, status in objs_status_dict.iteritems():
      self.assertIn(key, full_text_dict)
      self.assertEqual(status, full_text_dict[key])

  def assert_status_over_bulk_update(self, statuses, assert_statuses):
    """Assertion cycle_task statuses over bulk update."""
    self._update_ct_via_patch(statuses)
    self.refresh_set_up_instances()
    self.assertItemsEqual(assert_statuses, [obj.status for obj in self.tasks])
    obj_status_chain = [
        (t, assert_statuses[idx]) for idx, t in enumerate(self.tasks)
    ]
    self.assert_latest_revision_status(*obj_status_chain)
    self.assert_searchable_by_status(*obj_status_chain)

  def test_propagation_status_full(self):
    """Task status propagation for required verification workflow."""
    # all tasks in assigned state
    self.assertEqual([self.ASSIGNED] * 3, [t.status for t in self.tasks])
    # all tasks in progress state
    self.assert_status_over_bulk_update([self.IN_PROGRESS] * 3,
                                        [self.IN_PROGRESS] * 3)
    self.assertEqual(self.IN_PROGRESS, self.group.status)
    self.assertEqual(self.IN_PROGRESS, self.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    # update 1 task to finished
    self.assert_status_over_bulk_update(
        [self.FINISHED],
        [self.FINISHED, self.IN_PROGRESS, self.IN_PROGRESS])
    self.assertEqual(self.IN_PROGRESS, self.group.status)
    self.assertEqual(self.IN_PROGRESS, self.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    # all tasks moved to finished
    self.assert_status_over_bulk_update([self.FINISHED] * 3,
                                        [self.FINISHED] * 3)
    self.assertEqual(self.FINISHED, self.group.status)
    self.assertEqual(self.FINISHED, self.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    for task in self.tasks:
      self.assert_notifications_for_object(task,
                                           u'cycle_task_due_in',
                                           u'cycle_task_due_today',
                                           u'cycle_task_overdue',
                                           u'manual_cycle_created')
    self.cycle = self.tasks[0].cycle
    self.assert_notifications_for_object(self.cycle, u'manual_cycle_created')
    # all tasks moved to verified
    self.assert_status_over_bulk_update([self.VERIFIED] * 3,
                                        [self.VERIFIED] * 3)
    self.assertEqual(self.VERIFIED, self.group.status)
    self.assertEqual(self.VERIFIED, self.cycle.status)
    self.assertEqual(all_models.Workflow.INACTIVE, self.workflow.status)
    generate_cycle_tasks_notifs()
    for task in self.tasks:
      self.assert_notifications_for_object(task)
    self.cycle = self.tasks[0].cycle
    self.assert_notifications_for_object(self.cycle,
                                         u"all_cycle_tasks_completed",
                                         u'manual_cycle_created')

  def test_propagation_status_short(self):
    """Task status propagation for not required verification workflow."""
    all_models.Cycle.query.filter(
        all_models.Cycle.id == self.cycle.id
    ).update({
        all_models.Cycle.is_verification_needed: False
    })
    db.session.commit()
    self.tasks = all_models.CycleTaskGroupObjectTask.query.order_by(
        all_models.CycleTaskGroupObjectTask.id
    ).all()
    # all tasks in assigned state
    self.assertEqual([self.ASSIGNED] * 3, [t.status for t in self.tasks])
    # all tasks in progress state
    self.assert_status_over_bulk_update([self.IN_PROGRESS] * 3,
                                        [self.IN_PROGRESS] * 3)
    self.assertEqual(self.IN_PROGRESS, self.group.status)
    self.assertEqual(self.IN_PROGRESS, self.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    # update 1 task to finished
    self.assert_status_over_bulk_update(
        [self.FINISHED],
        [self.FINISHED, self.IN_PROGRESS, self.IN_PROGRESS])
    self.assertEqual(self.IN_PROGRESS, self.group.status)
    self.assertEqual(self.IN_PROGRESS, self.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    generate_cycle_tasks_notifs()
    self.assert_notifications_for_object(self.tasks[0])
    for task in self.tasks[1:]:
      self.assert_notifications_for_object(task,
                                           u'cycle_task_due_in',
                                           u'cycle_task_due_today',
                                           u'cycle_task_overdue',
                                           u'manual_cycle_created')
    self.cycle = self.tasks[0].cycle
    self.assert_notifications_for_object(self.cycle, u'manual_cycle_created')
    # all tasks moved to finished
    self.assert_status_over_bulk_update([self.FINISHED] * 3,
                                        [self.FINISHED] * 3)
    self.assertEqual(self.FINISHED, self.group.status)
    self.assertEqual(self.FINISHED, self.cycle.status)
    self.assertEqual(all_models.Workflow.INACTIVE, self.workflow.status)
    generate_cycle_tasks_notifs()
    for task in self.tasks:
      self.assert_notifications_for_object(task)
    self.cycle = self.tasks[0].cycle
    self.assert_notifications_for_object(self.cycle,
                                         u"all_cycle_tasks_completed",
                                         u'manual_cycle_created')

  def test_deprecated_final(self):
    """Test task status propagation for deprecated workflow."""
    self.assertEqual([self.ASSIGNED] * 3, [t.status for t in self.tasks])
    # all tasks in progress state
    self.assert_status_over_bulk_update([self.DEPRECATED] * 3,
                                        [self.DEPRECATED] * 3)
    self.assertEqual(self.DEPRECATED, self.group.status)
    self.assertEqual(self.DEPRECATED, self.cycle.status)
    self.assertEqual(all_models.Workflow.INACTIVE, self.workflow.status)
    self.assert_status_over_bulk_update(
        [self.ASSIGNED, self.VERIFIED, self.FINISHED],
        [self.DEPRECATED] * 3)
    self.assertEqual(self.DEPRECATED, self.group.status)
    self.assertEqual(self.DEPRECATED, self.cycle.status)
    self.assertEqual(all_models.Workflow.INACTIVE, self.workflow.status)

  @ddt.data({"to_state": FINISHED, "success": True},
            {"to_state": IN_PROGRESS, "success": False},
            {"to_state": ASSIGNED, "success": False},
            {"to_state": VERIFIED, "success": False})
  @ddt.unpack
  def test_move_from_declined(self, to_state, success):
    """Test status propagation over update declined tasks to {to_state}."""
    self.assertEqual([self.ASSIGNED] * len(self.tasks),
                     [t.status for t in self.tasks])
    start_state = self.DECLINED
    start_statuses = [start_state] * len(self.tasks)
    with factories.single_commit():
      for idx, status in enumerate(start_statuses):
        self.tasks[idx].status = status
      self.group.status = self.IN_PROGRESS
      self.cycle.status = self.IN_PROGRESS
      self.workflow.status = all_models.Workflow.ACTIVE
    self.assertEqual(start_statuses, [t.status for t in self.tasks])
    # all tasks in progress state
    to_states = [to_state] * len(self.tasks)
    self._update_ct_via_patch(to_states)
    self.refresh_set_up_instances()
    if success:
      task_state = group_state = cycle_state = to_state
    else:
      task_state = start_state
      group_state = cycle_state = self.IN_PROGRESS
    self.assertEqual([task_state] * len(self.tasks),
                     [t.status for t in self.tasks])
    self.assertEqual(group_state, self.group.status)
    self.assertEqual(cycle_state, self.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)

  def test_update_tasks_from_2_cycles(self):
    """Test bulk update few cycles at the same time."""
    with factories.single_commit():
      _, _, group, _ = self._create_cycle_structure()
    group_id = group.id
    all_models.Cycle.query.update({
        all_models.Cycle.is_verification_needed: False
    })
    db.session.commit()
    self.tasks = all_models.CycleTaskGroupObjectTask.query.order_by(
        all_models.CycleTaskGroupObjectTask.id
    ).all()
    # all tasks in assigned state
    self.assertEqual([self.ASSIGNED] * 6, [t.status for t in self.tasks])
    # all tasks in progress state
    self.assert_status_over_bulk_update([self.IN_PROGRESS] * 6,
                                        [self.IN_PROGRESS] * 6)
    group = all_models.CycleTaskGroup.query.get(group_id)
    self.assertEqual(self.IN_PROGRESS, self.group.status)
    self.assertEqual(self.IN_PROGRESS, group.status)
    self.assertEqual(self.IN_PROGRESS, self.cycle.status)
    self.assertEqual(self.IN_PROGRESS, group.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    self.assertEqual(all_models.Workflow.ACTIVE, group.cycle.workflow.status)
    # update 1 task to finished
    self.assert_status_over_bulk_update(
        [self.FINISHED],
        [self.FINISHED] + [self.IN_PROGRESS] * 5)
    group = all_models.CycleTaskGroup.query.get(group_id)
    self.assertEqual(self.IN_PROGRESS, self.group.status)
    self.assertEqual(self.IN_PROGRESS, group.status)
    self.assertEqual(self.IN_PROGRESS, self.cycle.status)
    self.assertEqual(self.IN_PROGRESS, group.cycle.status)
    self.assertEqual(all_models.Workflow.ACTIVE, self.workflow.status)
    self.assertEqual(all_models.Workflow.ACTIVE, group.cycle.workflow.status)
    generate_cycle_tasks_notifs()
    self.assert_notifications_for_object(self.tasks[0])
    for task in self.tasks[1:]:
      self.assert_notifications_for_object(task,
                                           u'cycle_task_due_in',
                                           u'cycle_task_due_today',
                                           u'cycle_task_overdue',
                                           u'manual_cycle_created')
    self.assert_notifications_for_object(self.group.cycle,
                                         u'manual_cycle_created')
    self.assert_notifications_for_object(group.cycle,
                                         u'manual_cycle_created')
    # all tasks moved to finished
    self.assert_status_over_bulk_update([self.FINISHED] * 6,
                                        [self.FINISHED] * 6)
    group = all_models.CycleTaskGroup.query.get(group_id)
    self.assertEqual(self.FINISHED, self.group.status)
    self.assertEqual(self.FINISHED, group.status)
    self.assertEqual(self.FINISHED, self.cycle.status)
    self.assertEqual(self.FINISHED, group.cycle.status)
    self.assertEqual(all_models.Workflow.INACTIVE, self.workflow.status)
    self.assertEqual(all_models.Workflow.INACTIVE, group.cycle.workflow.status)
    generate_cycle_tasks_notifs()
    for task in self.tasks:
      self.assert_notifications_for_object(task)
    self.assert_notifications_for_object(self.cycle,
                                         u"all_cycle_tasks_completed",
                                         u'manual_cycle_created')
    self.assert_notifications_for_object(group.cycle,
                                         u"all_cycle_tasks_completed",
                                         u'manual_cycle_created')
