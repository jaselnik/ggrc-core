# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""Tests for task group task specific export."""

from collections import defaultdict

from ddt import data, ddt, unpack

from integration.ggrc_workflows.models import factories
from integration.ggrc.models import factories as ggrc_factories
from integration.ggrc import TestCase

from ggrc.models import all_models


@ddt
class TestExportTasks(TestCase):
  """Test imports for basic workflow objects."""

  model = all_models.CycleTaskGroupObjectTask

  def setUp(self):
    super(TestExportTasks, self).setUp()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  @staticmethod
  def generate_tasks_for_cycle(task_count):
    """generate number of task groups and task for current task group"""
    results = []
    with ggrc_factories.single_commit():
      for idx in range(task_count):
        person = ggrc_factories.PersonFactory(
            name="user for group {}".format(idx)
        )
        task = factories.CycleTaskGroupObjectTaskFactory()
        for role_name in ("Task Assignees", "Task Secondary Assignees"):
          task.add_person_with_role_name(person, role_name)
        results.append(task.id)
    return results

  @data(0, 1, 2)
  def test_filter_by_task_title(self, task_count):
    """Test filter tasks by title"""
    generated = self.generate_tasks_for_cycle(task_count)
    self.assertEqual(bool(task_count), bool(generated))
    for task_id in generated:
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      self.assert_slugs("task title", task.title, [task.slug])

  @data(0, 1, 2)
  def test_filter_by_task_due_date(self, task_count):
    """Test filter by task due date"""
    due_date_dict = defaultdict(set)
    generated = self.generate_tasks_for_cycle(task_count)
    self.assertEqual(bool(task_count), bool(generated))
    for task_id in generated:
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      due_date_dict[str(task.end_date)].add(task.slug)

    for due_date, slugs in due_date_dict.iteritems():
      self.assert_slugs("task due date", due_date, list(slugs))

  @data(0, 1, 2,)
  def test_filter_by_task_assignee(self, task_count):
    """Test filter task by assignee name or email"""
    generated = self.generate_tasks_for_cycle(task_count)
    self.assertEqual(bool(task_count), bool(generated))
    for task_id in generated:
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      role = all_models.AccessControlRole.query.filter(
          all_models.AccessControlRole.name == "Task Assignees",
          all_models.AccessControlRole.object_type == task.type,
      ).one()
      assignees = [person for person, acl in task.access_control_list
                   if acl.ac_role_id == role.id]
      self.assertEqual(1, len(assignees))
      self.assert_slugs("task assignees", assignees[0].email, [task.slug])
      self.assert_slugs("task assignees", assignees[0].name, [task.slug])

  @data(0, 1, 2,)
  def test_filter_by_task_secondary_assignee(self, task_count):  # noqa pylint: disable=invalid-name
    """Test filter task by secondary assignee name or email"""
    generated = self.generate_tasks_for_cycle(task_count)
    self.assertEqual(bool(task_count), bool(generated))
    for task_id in generated:
      task = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == task_id
      ).one()
      role = all_models.AccessControlRole.query.filter(
          all_models.AccessControlRole.name == "Task Secondary Assignees",
          all_models.AccessControlRole.object_type == task.type,
      ).one()
      s_assignees = [person for person, acl in task.access_control_list
                     if acl.ac_role_id == role.id]
      self.assertEqual(1, len(s_assignees))
      self.assert_slugs("task secondary assignees",
                        s_assignees[0].email, [task.slug])
      self.assert_slugs("task secondary assignees",
                        s_assignees[0].name, [task.slug])

  def test_filter_by_task_comment(self):
    """Test filter by comments"""
    task_id = self.generate_tasks_for_cycle(4)[0]
    comment_text = "123"
    task = all_models.CycleTaskGroupObjectTask.query.get(task_id)
    with ggrc_factories.single_commit():
      comment = ggrc_factories.CommentFactory(description=comment_text)
      ggrc_factories.RelationshipFactory(source=task, destination=comment)
    self.assert_slugs("comment", comment_text, [task.slug])

  @data(
      ("status", ["Task State", "task state", "status"]),
      (
          "end_date",
          ["Task Due Date", "task due date", "end_date"]
      ),
      (
          "start_date",
          ["Task Start Date", "task start date", "start_date"],
      ),
  )
  @unpack
  def test_filter_by_aliases(self, field, aliases):
    """Test filter by alias"""
    expected_results = defaultdict(list)
    tasks = all_models.CycleTaskGroupObjectTask.query.filter(
        all_models.CycleTaskGroupObjectTask.id.in_(
            self.generate_tasks_for_cycle(4)
        )
    ).all()
    for task in tasks:
      expected_results[str(getattr(task, field))].append(task.slug)
    for value, slugs in expected_results.iteritems():
      for alias in aliases:
        self.assert_slugs(alias, value, slugs)

  @data(
      (
          "updated_at",
          [
              "task Last Updated Date",
              "task last updated date",
              "updated_at"
          ],
      ),
      (
          "created_at",
          [
              "task Created Date",
              "task created Date",
              "created_at"
          ],
      ),
  )
  @unpack
  def test_filter_by_datetime_aliases(self, field, aliases):
    """Test filter by datetime field and it's aliases"""
    expected_results = defaultdict(list)
    tasks = all_models.CycleTaskGroupObjectTask.query.filter(
        all_models.CycleTaskGroupObjectTask.id.in_(
            self.generate_tasks_for_cycle(4)
        )
    ).all()
    for task in tasks:
      for value in self.generate_date_strings(getattr(task, field)):
        expected_results[value].append(task.slug)
    for value, slugs in expected_results.iteritems():
      for alias in aliases:
        self.assert_slugs(alias, value, slugs)
