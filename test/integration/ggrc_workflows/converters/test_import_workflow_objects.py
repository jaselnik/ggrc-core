# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for workflow specific imports."""

from datetime import date
import collections

import ddt
import freezegun

from integration.ggrc import TestCase
from integration.ggrc_workflows import generator as wf_generator
from integration.ggrc_workflows.models import factories as wf_factories
from integration.ggrc.models import factories
from integration.ggrc.converters import constants

from ggrc import db
from ggrc.converters import errors
from ggrc_workflows.models.task_group_task import TaskGroupTask
from ggrc_workflows.models.workflow import Workflow


@ddt.ddt
class TestWorkflowObjectsImport(TestCase):
  """Test imports for basic workflow objects."""

  def setUp(self):
    super(TestWorkflowObjectsImport, self).setUp()
    self.generator = wf_generator.WorkflowsGenerator()

  def test_invalid_import(self):
    """Test import of a workflow with missing data"""
    bad_workflow = [
        collections.OrderedDict([
            ("object_type", "Workflow"),
            ("code", ""),
            ("title", "bad_workflow-1"),
            ("admin", ""),
            ("Need Verification", 'True'),
        ]),
    ]

    response = self.import_data(*bad_workflow)

    expected_errors = {
        "Workflow": {
            "row_warnings": {
                errors.OWNER_MISSING.format(line=3, column_name="Admin")
            },
        }
    }
    self._check_csv_response(response, expected_errors)

  @ddt.data(
      ("Rich Text", "Rich text example", {}),
      ("Checkboxes", "ch1, ch2, some checkbox 3", {}),
      ("aaaa", "Wrong task type", {
          "Task Group Task": {
              "row_warnings": {
                  errors.WRONG_REQUIRED_VALUE.format(
                      line=3, value="aaaa", column_name="Task Type"
                  ),
              }
          }
      }),
      ("", "Empty task type", {
          "Task Group Task": {
              "row_warnings": {
                  errors.MISSING_VALUE_WARNING.format(
                      line=3, default_value="Rich Text",
                      column_name="Task Type"),
              }
          }
      })
  )
  @ddt.unpack
  def test_import_task_types(self, task_type, task_description,
                             expected_errors):
    """Test task import with warnings

    Check that the warnings for bad task type field work and that the task type
    gets set to default when an invalid values is found in the csv.

    Raises:
      AssertionError: When file import does not return correct errors for the
        example csv, or if any of the tasks does not have the expected task
        type.

    """
    task_group = wf_factories.TaskGroupFactory(title="tg-1")
    tgt_data_block = [
        collections.OrderedDict([
            ("object_type", "Task Group Task"),
            ("code", ""),
            ("task title", "task-1"),
            ("task type", task_type),
            ("task description", task_description),
            ("task group code", task_group.slug),
            ("task start date", date(2015, 7, 1)),
            ("task due date", date(2015, 7, 15)),
            ("task assignees", "user@example.com"),
        ]),
    ]

    response = self.import_data(*tgt_data_block)

    self._check_csv_response(response, expected_errors)

    task_type_aliases = {
        "Rich Text": "text",
        "Checkboxes": "checkbox"
    }

    if task_type not in task_type_aliases:
      task_type = "Rich Text"

    task_slug = db.session.query(TaskGroupTask.slug).filter(
        TaskGroupTask.task_type == task_type_aliases[task_type]).one()
    self.assert_task_types(task_type_aliases[task_type], task_slug)

  @ddt.data(
      (date(2099, 7, 1), date(2015, 7, 15), {
          "Task Group Task": {
              "row_errors": {
                  errors.INVALID_START_END_DATES.format(
                      line=3, start_date="Task Start Date",
                      end_date="Task Due Date"),
              }
          }
      }),
      (date(2016, 12, 25), date(2017, 1, 12), {
          "Task Group Task": {
              "row_errors": {
                  errors.START_DATE_ON_WEEKEND_ERROR.format(line=3),
              }
          }
      }),
      (date(2015, 7, 1), date(2016, 12, 25), {
          "Task Group Task": {
              "row_errors": {
                  errors.END_DATE_ON_WEEKEND_ERROR.format(line=3),
              }
          }
      }),
  )
  @ddt.unpack
  def test_bad_task_dates(self, start_date, end_date, expected_errors):
    """Test import updates with invalid task dates.

    This import checks if it's possible to update task dates
      1. with start date being bigger than the end date.
      2. Start date being a weekend
      3. Due date being a weekend
    """
    task_group = wf_factories.TaskGroupFactory(title="tg-1")

    tgt_data_block = [
        collections.OrderedDict([
            ("object_type", "Task Group Task"),
            ("code", ""),
            ("task title", "task-1"),
            ("task type", "Rich Text"),
            ("task group code", task_group.slug),
            ("task start date", date(2015, 7, 1)),
            ("task due date", date(2015, 7, 15)),
            ("task assignees", "user@example.com"),
        ]),
    ]

    self.import_data(*tgt_data_block)

    task1 = TaskGroupTask.query.filter_by(title="task-1").first()

    bad_tgt_data_block = [
        collections.OrderedDict([
            ("object_type", "Task Group Task"),
            ("code", task1.slug),
            ("task start date", start_date),
            ("task due date", end_date),
        ]),
    ]

    response = self.import_data(*bad_tgt_data_block)

    self._check_csv_response(response, expected_errors)

  def assert_task_types(self, expected_type, task_slugs):
    """Test that all listed tasks have expected text type.

    This is a part of the test_import_task_date_format

    Args:
      expected_type: Expected task type for all tasks specified by task_slugs.
      task_slugs: list of slugs for the tasks that will be tested.

    Raises:
      AssertionError: if any of the tasks does not exists or if their type is
        not text.
    """
    tasks = db.session.query(TaskGroupTask).filter(
        TaskGroupTask.slug.in_(task_slugs)).all()

    for task in tasks:
      self.assertEqual(
          task.task_type,
          expected_type,
          "task '{}' has type '{}', expected '{}'".format(
              task.slug,
              task.task_type,
              expected_type,
          )
      )
    self.assertEqual(len(tasks), len(task_slugs))

  @ddt.data(
      (True, 'True'),
      (True, 'true'),
      (True, 'TRUE'),
      (False, 'False'),
      (False, 'false'),
      (False, 'FALSE'),
      (True, 'yes'),
      (True, 'YES'),
      (True, 'Yes '),
      (True, 'yEs'),
      (False, ' no '),
      (False, 'No '),
      (False, 'nO'),
      (False, 'NO'),
  )
  @ddt.unpack
  def test_import_verification_flag(self, flag, import_value):
    """Create wf with need verification flag."""
    title = "SomeTitle"
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Workflow"),
        ("code", ""),
        ("title", title),
        ("Need Verification", import_value),
        ("force real-time email updates", "no"),
        ("Admin", "user@example.com"),
    ]))
    self.assertEqual(1, resp[0]['created'])
    workflow = Workflow.query.filter(Workflow.title == title).first()
    self.assertEqual(flag, workflow.is_verification_needed)

  @ddt.data(*constants.FLAG_VALIDATORS)
  @ddt.unpack
  # pylint: disable=invalid-name
  def test_update_verification_true_flag_positive(self, import_value,
                                                  expected_value):
    """Test update of verification flag before activation
       when is_verification_needed is TRUE
    """
    slug = 'SomeCode'
    with freezegun.freeze_time("2017-08-10"):
      with factories.single_commit():
        workflow = wf_factories.WorkflowFactory(
            slug=slug, is_verification_needed=True)
        wf_factories.TaskGroupTaskFactory(
            task_group=wf_factories.TaskGroupFactory(
                workflow=workflow,
                context=factories.ContextFactory()
            ),
            start_date=date(2017, 8, 3),
            end_date=date(2017, 8, 7))
      wf_id = workflow.id
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Workflow"),
          ("code", slug),
          ("title", "SomeTitle"),
          ("Need Verification", import_value),
          ("force real-time email updates", "no"),
          ("Admin", "user@example.com"),
      ]))
      self.assertEqual(1, resp[0]['updated'])
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.is_verification_needed, expected_value)

  @ddt.data(*constants.FLAG_VALIDATORS)
  @ddt.unpack
  # pylint: disable=invalid-name
  def test_update_verification_false_flag_positive(self, import_value,
                                                   expected_value):
    """Test update of verification flag before activation
       when is_verification_needed is FALSE
    """
    slug = 'SomeCode'
    with freezegun.freeze_time("2017-08-10"):
      with factories.single_commit():
        workflow = wf_factories.WorkflowFactory(
            slug=slug, is_verification_needed=False)
        wf_factories.TaskGroupTaskFactory(
            task_group=wf_factories.TaskGroupFactory(
                workflow=workflow,
                context=factories.ContextFactory()
            ),
            start_date=date(2017, 8, 3),
            end_date=date(2017, 8, 7))
      wf_id = workflow.id
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Workflow"),
          ("code", slug),
          ("title", "SomeTitle"),
          ("Need Verification", import_value),
          ("force real-time email updates", "no"),
          ("Admin", "user@example.com"),
      ]))
      self.assertEqual(1, resp[0]['updated'])
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.is_verification_needed, expected_value)

  @ddt.data(
      (True, 'FALSE'),
      (True, 'False'),
      (True, 'false'),
      (False, 'TRUE'),
      (False, 'True'),
      (False, 'true'),
      (False, 'yes'),
      (False, 'YES'),
      (False, 'Yes '),
      (False, 'yEs'),
      (True, ' no '),
      (True, 'No '),
      (True, 'nO'),
      (True, 'NO'),
  )
  @ddt.unpack  # pylint: disable=invalid-name
  def test_update_verification_flag_negative(self, db_value, import_value):
    """Test update of verification flag after activation"""
    slug = 'SomeCode'
    with freezegun.freeze_time("2017-08-10"):
      with factories.single_commit():
        workflow = wf_factories.WorkflowFactory(
            slug=slug,
            is_verification_needed=db_value,
            repeat_every=1,
            unit=Workflow.WEEK_UNIT)
        wf_factories.TaskGroupTaskFactory(
            task_group=wf_factories.TaskGroupFactory(
                workflow=workflow,
                context=factories.ContextFactory()
            ),
            # Two cycles should be created
            start_date=date(2017, 8, 3),
            end_date=date(2017, 8, 7))

      wf_id = workflow.id
      self.generator.activate_workflow(workflow)
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.status, workflow.ACTIVE)
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Workflow"),
          ("code", slug),
          ("title", "SomeTitle"),
          ("Need Verification", import_value),
          ("force real-time email updates", "no"),
          ("Admin", "user@example.com"),
      ]))
      self.assertEqual(1, resp[0]['ignored'])
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.is_verification_needed, db_value)

      # End all current cycles
      for cycle in workflow.cycles:
        self.generator.modify_object(cycle, {'is_current': False})
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.status, workflow.INACTIVE)
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Workflow"),
          ("code", slug),
          ("title", "SomeTitle"),
          ("Need Verification", import_value),
          ("force real-time email updates", "no"),
          ("Admin", "user@example.com"),
      ]))
      self.assertEqual(1, resp[0]['ignored'])
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.is_verification_needed, db_value)

  def test_error_verification_flag(self):
    """Test create wf without Needed Verification flag"""
    title = "SomeTitle"
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Workflow"),
        ("code", ""),
        ("title", title),
        ("force real-time email updates", "no"),
        ("Admin", "user@example.com"),
    ]))
    self.assertEqual(1, resp[0]['ignored'])
    self.assertIsNone(Workflow.query.filter(Workflow.title == title).first())

  @ddt.data(("", errors.MISSING_VALUE_ERROR), ("--", errors.WRONG_VALUE_ERROR))
  @ddt.unpack
  def test_create_required_flag_error(self, data, msg):
    """Test create wf with empty or invalid Needed Verification flag"""
    title = "SomeTitle"
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Workflow"),
        ("code", ""),
        ("title", title),
        ("force real-time email updates", "no"),
        ("Admin", "user@example.com"),
        ("Need Verification", data),
    ]))
    data = {
        "Workflow": {
            "row_errors": {
                msg.format(line=3, column_name="Need Verification")
            }
        }
    }
    self.assertEqual(1, resp[0]['ignored'])
    self._check_csv_response(resp, data)
    self.assertIsNone(Workflow.query.filter(Workflow.title == title).first())
