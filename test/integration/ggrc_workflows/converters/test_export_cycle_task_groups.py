# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""Tests for task group task specific export."""

from collections import defaultdict

import ddt

from ggrc.models import all_models
from integration import ggrc
from integration.ggrc.models import factories as ggrc_factories
from integration.ggrc_workflows.models import factories


@ddt.ddt
class TestExportTasks(ggrc.TestCase):
  """Test imports for basic workflow objects."""

  CYCLES_TASKS_COUNT = (
      # (Cycle count, tasks in cycle)
      (0, 0),
      (1, 2),
      (2, 1),
  )

  model = all_models.CycleTaskGroup

  def setUp(self):
    super(TestExportTasks, self).setUp()
    self.client.get("/login")
    self.headers = {
        "X-Requested-By": "GGRC",
        'Content-Type': 'application/json',
        "X-export-view": "blocks",
    }

  @staticmethod
  def generate_tasks_for_cycle(group_count, task_count):
    """generate number of task groups and task for current task group"""
    role_names = ("Task Assignees", "Task Secondary Assignees")
    results = {}
    with ggrc_factories.single_commit():
      workflow = factories.WorkflowFactory()
      cycle = factories.CycleFactory(workflow=workflow)
      task_group = factories.TaskGroupFactory(workflow=workflow)
      for idx in range(group_count):
        person = ggrc_factories.PersonFactory(
            name="user for group {}".format(idx)
        )
        cycle_task_group = factories.CycleTaskGroupFactory(cycle=cycle,
                                                           contact=person)
        for _ in range(task_count):
          task_group_task = factories.TaskGroupTaskFactory(
              task_group=task_group)
          for r_name in role_names:
            ggrc_factories.AccessControlPersonFactory(
                ac_list=task_group_task.acr_name_acl_map[r_name],
                person=person,
            )
          task = factories.CycleTaskGroupObjectTaskFactory(
              cycle=cycle,
              cycle_task_group=cycle_task_group,
              task_group_task=task_group_task
          )
          for r_name in role_names:
            ggrc_factories.AccessControlPersonFactory(
                person=person,
                ac_list=task.acr_name_acl_map[r_name],
            )
          results[task.id] = cycle_task_group.slug
    return results

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_task_title(self, group_count, task_count):
    """Test filter groups by task title"""
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      self.assert_slugs("task title", task.title, [slug])

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_group_title(self, group_count, task_count):
    """Test filter groups by title"""
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.get(task_id)
      self.assert_slugs("group title", task.cycle_task_group.title, [slug])

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_task_due_date(self, group_count, task_count):
    """Test filter by task due date"""
    due_date_dict = defaultdict(set)
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      due_date_dict[str(task.end_date)].add(slug)

    for due_date, slugs in due_date_dict.iteritems():
      self.assert_slugs("task due date", due_date, list(slugs))

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_group_due_date(self, group_count, task_count):
    """Test filter by group due date"""
    due_date_dict = defaultdict(set)
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      due_date_dict[str(task.cycle_task_group.next_due_date)].add(slug)

    for due_date, slugs in due_date_dict.iteritems():
      self.assert_slugs("group due date", due_date, list(slugs))

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_group_assignee(self, group_count, task_count):
    """Test filter by group assignee name or email"""
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      self.assert_slugs(
          "group assignee", task.cycle_task_group.contact.email, [slug])
      self.assert_slugs(
          "group assignee", task.cycle_task_group.contact.name, [slug])

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_task_assignee(self, group_count, task_count):
    """Test filter cycles by task assignee name or email"""
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      assignees = list(self.get_persons_for_role_name(task, "Task Assignees"))
      self.assertEqual(1, len(assignees))
      self.assert_slugs("task assignees", assignees[0].email, [slug])
      self.assert_slugs("task assignees", assignees[0].name, [slug])

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_task_secondary_assignee(self, group_count, task_count):
    """Test filter cycles by task secondary assignee name or email"""
    generated = self.generate_tasks_for_cycle(group_count, task_count)
    self.assertEqual(bool(group_count), bool(generated))
    for task_id, slug in generated.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      s_assignees = list(
          self.get_persons_for_role_name(task, "Task Secondary Assignees"))
      self.assertEqual(1, len(s_assignees))
      self.assert_slugs("task secondary assignees",
                        s_assignees[0].email, [slug])
      self.assert_slugs("task secondary assignees",
                        s_assignees[0].name, [slug])

  @ddt.data(*CYCLES_TASKS_COUNT)
  @ddt.unpack
  def test_filter_by_task_comment(self, cycle_count, task_count):
    """Test filter groups by task comments."""
    filter_params = {}
    task_cycle_filter = self.generate_tasks_for_cycle(cycle_count, task_count)
    for task_id, slug in task_cycle_filter.iteritems():
      task = all_models.CycleTaskGroupObjectTask.query.get(task_id)
      comment_text = "comment for task # {}".format(task_id)
      with ggrc_factories.single_commit():
        comment = ggrc_factories.CommentFactory(description=comment_text)
        ggrc_factories.RelationshipFactory(source=task, destination=comment)
      filter_params[comment_text] = slug

    for comment_text, slug in filter_params.iteritems():
      self.assert_slugs("task comment", comment_text, [slug])
