# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for workflow object exports."""

from freezegun import freeze_time
import ddt
from flask.json import dumps
from ggrc_workflows.models import TaskGroupTask, Workflow
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc_workflows.generator import WorkflowsGenerator
from integration.ggrc_workflows.models import factories as wf_factories


@ddt.ddt
class TestExportEmptyTemplate(TestCase):

  """Test empty export for all workflow object types."""

  def setUp(self):
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_single_object_export(self):
    """Test empty exports for workflow only."""
    data = {
        "export_to": "csv",
        "objects": [{"object_name": "Workflow", "fields": "all"}]
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Title*", response.data)

  def test_unit_tip(self):
    """Test Workflow's Unit column has hint correctly"""
    data = {
        "export_to": "csv",
        "objects": [{"object_name": "Workflow", "fields": "all"}]
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Allowed values are:\n{}".format(
        "\n".join(Workflow.VALID_UNITS)), response.data)

  def test_multiple_objects(self):
    """Test empty exports for all workflow object in one query."""
    data = [
        {"object_name": "Workflow", "fields": "all"},
        {"object_name": "TaskGroup", "fields": "all"},
        {"object_name": "TaskGroupTask", "fields": "all"},
        {"object_name": "Cycle", "fields": "all"},
        {"object_name": "CycleTaskGroup", "fields": "all"},
        {"object_name": "CycleTaskGroupObjectTask", "fields": "all"},
    ]
    request_body = {
        "export_to": "csv",
        "objects": data
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(request_body), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Workflow,", response.data)
    self.assertIn("Task Group,", response.data)
    self.assertIn("Task,", response.data)
    self.assertIn("Cycle,", response.data)
    self.assertIn("Cycle Task Group,", response.data)
    self.assertIn("Cycle Task,", response.data)

  def test_tips_tg_task(self):
    """Test if TaskGroupTask date attributes has hints correctly."""
    data = {
        "export_to": "csv",
        "objects": [{"object_name": "TaskGroupTask", "fields": "all"}]
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(2, response.data.count(
        "{}\nOnly working days are accepted".format(TaskGroupTask.DATE_HINT)))


class TestExportMultipleObjects(TestCase):

  """Test export of multiple objects."""

  def setUp(self):
    self.clear_data()
    self.client.get("/login")
    self.wf_generator = WorkflowsGenerator()

  def test_workflow_task_group_mapping(self):  # pylint: disable=invalid-name
    """Test workflow and task group mappings."""
    with freeze_time("2017-03-07"):
      workflow = wf_factories.WorkflowFactory()
      workflow_slug = workflow.slug
      task_group1 = wf_factories.TaskGroupFactory(workflow=workflow)
      task_group1_slug = task_group1.slug

      task_group2 = wf_factories.TaskGroupFactory(workflow=workflow)
      task_group2_slug = task_group2.slug

    data = [
        {
            "object_name": "Workflow",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "TaskGroup",
                    "slugs": [task_group1_slug],
                },
            },
            "fields": "all",
        }, {
            "object_name": "TaskGroup",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "__previous__",
                    "ids": [0],
                },
            },
            "fields": "all",
        },
    ]
    response = self.export_csv(data)
    self.assert200(response)
    response_data = response.data

    self.assertEqual(3, response_data.count(workflow_slug))
    self.assertIn(task_group1_slug, response_data)
    self.assertIn(task_group2_slug, response_data)

  def test_tg_task(self):
    """Test task group task mappings."""
    with freeze_time("2017-03-07"):
      workflow = wf_factories.WorkflowFactory()
      task_group1 = wf_factories.TaskGroupFactory(workflow=workflow)
      task_group1_slug = task_group1.slug
      task_group_task1 = wf_factories.TaskGroupTaskFactory(
          task_group=task_group1)
      task_group_task1_slug = task_group_task1.slug

      task_group_task2 = wf_factories.TaskGroupTaskFactory(
          task_group=task_group1)
      task_group_task2_slug = task_group_task2.slug

    data = [
        {
            "object_name": "TaskGroupTask",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "TaskGroup",
                    "slugs": [task_group1_slug],
                },
            },
            "fields": "all",
        }, {
            "object_name": "TaskGroup",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "__previous__",
                    "ids": ["0"],
                },
            },
            "fields": "all",
        },
    ]
    response = self.export_csv(data)
    self.assert200(response)
    response_data = response.data
    self.assertEqual(3, response_data.count(task_group1_slug))
    self.assertIn(task_group_task1_slug, response_data)
    self.assertIn(task_group_task2_slug, response_data)

  def test_workflow_cycle_mapping(self):
    """Test workflow and cycle mappings."""
    with freeze_time("2017-03-07"):
      workflow = wf_factories.WorkflowFactory()
      workflow_slug = workflow.slug
      task_group = wf_factories.TaskGroupFactory(workflow=workflow)
      wf_factories.TaskGroupTaskFactory(task_group=task_group)

      wf_factories.TaskGroupTaskFactory(task_group=task_group)

      self.wf_generator.generate_cycle(workflow)
      self.wf_generator.activate_workflow(workflow)

    def block(obj, obj_id):
      return {
          "object_name": obj,
          "filters": {
              "expression": {
                  "op": {"name": "relevant"},
                  "object_name": "__previous__",
                  "ids": [obj_id],
              },
          },
          "fields": "all",
      }

    data = [
        {
            "object_name": "Cycle",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "Workflow",
                    "slugs": [workflow_slug],
                },
            },
            "fields": "all",
        },
        block("Workflow", "0"),
        block("CycleTaskGroup", "0"),
        block("Cycle", "2"),
        block("CycleTaskGroupObjectTask", "2"),
        block("CycleTaskGroup", "4"),
    ]

    response = self.export_csv(data)
    self.assert200(response)
    response_data = response.data

    self.assertEqual(3, response_data.count(workflow_slug))
    self.assertEqual(4, response_data.count("CYCLEGROUP-"))
    self.assertEqual(6, response_data.count("CYCLE-"))
    self.assertEqual(2, response_data.count("CYCLETASK-"))

  def test_cycle_task_objects(self):
    """Test cycle task and various objects."""
    with freeze_time("2017-03-07"):
      workflow = wf_factories.WorkflowFactory()
      task_group = wf_factories.TaskGroupFactory(workflow=workflow)
      wf_factories.TaskGroupTaskFactory(task_group=task_group)

      wf_factories.TaskGroupTaskFactory(task_group=task_group)

      issue = factories.IssueFactory()
      issue_slug = issue.slug
      factories.RelationshipFactory(source=task_group, destination=issue)

      self.wf_generator.generate_cycle(workflow)
      self.wf_generator.activate_workflow(workflow)

    data = [
        {
            "object_name": "CycleTaskGroupObjectTask",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "Issue",
                    "slugs": [issue_slug],
                },
            },
            "fields": "all",
        }, {
            "object_name": "Issue",
            "filters": {
                "expression": {
                    "op": {"name": "relevant"},
                    "object_name": "__previous__",
                    "ids": ["0"],
                },
            },
            "fields": ["slug", "title"],
        },
    ]
    response = self.export_csv(data)
    self.assert200(response)
    response_data = response.data

    self.assertEqual(2, response_data.count("CYCLETASK-"))
    self.assertEqual(3, response_data.count(issue_slug))

  def test_wf_indirect_relevant_filters(self):  # pylint: disable=invalid-name
    """Test related filter for indirect relationships on wf objects."""
    with freeze_time("2017-03-07"):
      workflow = wf_factories.WorkflowFactory(title="workflow-1")
      task_group1 = wf_factories.TaskGroupFactory(workflow=workflow)
      wf_factories.TaskGroupTaskFactory(task_group=task_group1)

      wf_factories.TaskGroupTaskFactory(task_group=task_group1)

      task_group2 = wf_factories.TaskGroupFactory(workflow=workflow)
      wf_factories.TaskGroupTaskFactory(task_group=task_group2)

      issue = factories.IssueFactory()
      issue_slug = issue.slug
      factories.RelationshipFactory(source=task_group1, destination=issue)

      self.wf_generator.generate_cycle(workflow)
      self.wf_generator.activate_workflow(workflow)

    def block(obj):
      return {
          "object_name": obj,
          "fields": ["slug"],
          "filters": {
              "expression": {
                  "object_name": "Issue",
                  "op": {"name": "relevant"},
                  "slugs": [issue_slug],
              },
          },
      }

    data = [
        block("Workflow"),
        block("Cycle"),
        block("CycleTaskGroup"),
        block("CycleTaskGroupObjectTask"),
    ]
    response = self.export_csv(data)
    self.assert200(response)
    response_data = response.data

    wf1 = Workflow.query.filter_by(title="workflow-1").first()
    cycle = wf1.cycles[0]
    cycle_tasks = []
    for cycle_task in cycle.cycle_task_group_object_tasks:
      for related_object in cycle_task.related_objects():
        if related_object.slug == issue_slug:
          cycle_tasks.append(cycle_task)
          break

    cycle_task_groups = list({cycle_task.cycle_task_group
                              for cycle_task in cycle_tasks})

    self.assertEqual(1, response_data.count("WORKFLOW-"))

    self.assertRegexpMatches(response_data, ",{}[,\r\n]".format(wf1.slug))

    self.assertEqual(1, response_data.count("CYCLE-"))
    self.assertRegexpMatches(response_data, ",{}[,\r\n]".format(cycle.slug))

    self.assertEqual(1, response_data.count("CYCLEGROUP-"))
    self.assertEqual(1, len(cycle_task_groups))
    self.assertRegexpMatches(response_data, ",{}[,\r\n]".format(
        cycle_task_groups[0].slug))

    self.assertEqual(2, response_data.count("CYCLETASK-"))
    self.assertEqual(2, len(cycle_tasks))
    for cycle_task in cycle_tasks:
      self.assertRegexpMatches(response_data, ",{}[,\r\n]".format(
          cycle_task.slug))

    destinations = [
        ("Workflow", wf1.slug, 1),
        ("Cycle", cycle.slug, 1),
        ("CycleTaskGroupObjectTask", cycle_tasks[0].slug, 1),
        ("CycleTaskGroupObjectTask", cycle_tasks[1].slug, 1),
    ]
    for object_name, slug, count in destinations:
      data = [{
          "object_name": "Issue",
          "fields": ["slug"],
          "filters": {
              "expression": {
                  "object_name": object_name,
                  "op": {"name": "relevant"},
                  "slugs": [slug],
              },
          },
      }]
      response = self.export_csv(data)
      self.assert200(response)
      response_data = response.data
      self.assertEqual(count, response_data.count(",ISSUE-"),
                       "Count for " + object_name)
      self.assertIn("," + issue_slug, response_data)
