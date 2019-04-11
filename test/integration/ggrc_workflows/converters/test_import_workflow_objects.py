# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for workflow specific imports."""

from datetime import date
from os.path import abspath
from os.path import dirname
from os.path import join
import collections

import ddt
import freezegun

from integration.ggrc import TestCase
from integration.ggrc_workflows import generator as wf_generator
from integration.ggrc_workflows.models import factories as wf_factories
from integration.ggrc.models import factories

from ggrc import db
from ggrc.converters import errors
from ggrc_workflows.models.task_group import TaskGroup
from ggrc_workflows.models.task_group_task import TaskGroupTask
from ggrc_workflows.models.workflow import Workflow

THIS_ABS_PATH = abspath(dirname(__file__))


@ddt.ddt
class TestWorkflowObjectsImport(TestCase):
  """Test imports for basic workflow objects."""

  CSV_DIR = join(THIS_ABS_PATH, "test_csvs/")

  def setUp(self):
    super(TestWorkflowObjectsImport, self).setUp()
    self.client.get("/login")
    self.generator = wf_generator.WorkflowsGenerator()

  def test_full_good_import(self):
    """Test full good import without any warnings."""
    self.import_file("workflow_small_sheet.csv")

    self.assertEqual(1, Workflow.query.count())
    self.assertEqual(1, TaskGroup.query.count())
    self.assertEqual(4, TaskGroupTask.query.count())
    task_group = TaskGroup.query.first()
    mapped_objs = filter(
        lambda rel: rel.destination_type != 'TaskGroupTask',
        task_group.related_destinations
    )
    self.assertEqual(2, len(mapped_objs))

    task2 = TaskGroupTask.query.filter_by(slug="t-2").first()
    task3 = TaskGroupTask.query.filter_by(slug="t-3").first()
    task4 = TaskGroupTask.query.filter_by(slug="t-4").first()
    self.assertEqual(task2.start_date, date(2015, 7, 10))
    self.assertEqual(task2.end_date, date(2016, 12, 30))
    self.assertIn("ch2", task3.response_options)
    self.assertIn("option 1", task4.response_options)

  def test_bad_imports(self):
    """Test workflow import with errors and warnings"""
    response = self.import_file("workflow_with_warnings_and_errors.csv",
                                safe=False)

    expected_errors = {
        "Workflow": {
            "row_warnings": {
                errors.OWNER_MISSING.format(line=14, column_name="Admin")
            },
        }
    }
    self._check_csv_response(response, expected_errors)

  def test_import_task_types(self):
    """Test task import with warnings

    Check that the warnings for bay task type field work and that the task type
    gets set to default when an invalid values is found in the csv.

    Raises:
      AssertionError: When file import does not return correct errors for the
        example csv, or if any of the tasks does not have the expected task
        type.

    """
    response = self.import_file("workflow_big_sheet.csv", safe=False)
    expected_errors = {
        "Task Group Task": {
            "row_warnings": {
                errors.WRONG_REQUIRED_VALUE.format(
                    line=73, value="aaaa", column_name="Task Type"
                ),
                errors.MISSING_VALUE_WARNING.format(
                    line=74, default_value="Rich Text", column_name="Task Type"
                ),
                errors.MISSING_VALUE_WARNING.format(
                    line=75, default_value="Rich Text", column_name="Task Type"
                ),
            }
        },
    }
    self._check_csv_response(response, expected_errors)

    task_types = {
        "text": [
            "task-1",
            "task-2",
            "task-4",
            "task-7",
            "task-9",
            "task-10",
            "task-11",
        ],
        "menu": [
            "task-5",
            "task-8",
        ],
        "checkbox": [
            "task-3",
            "task-6",
        ],
    }

    for task_type, slugs in task_types.items():
      self._test_task_types(task_type, slugs)

  def test_bad_task_dates(self):
    """Test import updates with invalid task dates.

    This import checks if it's possible to update task dates with start date
    being bigger than the end date.
    """
    self.import_file("workflow_small_sheet.csv")
    response = self.import_file("workflow_bad_task_dates.csv", safe=False)

    expected_errors = {
        "Task Group Task": {
            "row_errors": {
                errors.INVALID_START_END_DATES.format(
                    line=4, start_date="Start date", end_date="End date"),
                errors.INVALID_START_END_DATES.format(
                    line=5, start_date="Start date", end_date="End date"),
                errors.INVALID_START_END_DATES.format(
                    line=6, start_date="Start date", end_date="End date"),
                errors.INVALID_START_END_DATES.format(
                    line=7, start_date="Start date", end_date="End date"),
            }
        },
    }
    self._check_csv_response(response, expected_errors)

  def _test_task_types(self, expected_type, task_slugs):
    """Test that all listed tasks have rich text type.

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
  )
  @ddt.unpack
  def test_import_verification_flag(self, flag, import_value):
    """Create wf with need verification flag."""
    person = factories.PersonFactory(email="test@email.py")
    slug = "SomeCode"
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Workflow"),
        ("code", slug),
        ("title", "SomeTitle"),
        ("Need Verification", import_value),
        ("force real-time email updates", "no"),
        ("Admin", person.email),
    ]))
    self.assertEqual(1, resp[0]['created'])
    workflow = Workflow.query.filter(Workflow.slug == slug).first()
    self.assertEqual(flag, workflow.is_verification_needed)

  @ddt.data(
      ('FALSE', False),
      ('False', False),
      ('false', False),
      ('TRUE', True),
      ('True', True),
      ('true', True),
  )
  @ddt.unpack  # pylint: disable=invalid-name
  def test_update_verification_flag_positive(self, import_value,
                                             expected_value):
    workflow_test_data = {
        'WORKFLOW_VERIF': True,
        'WORKFLOW_NO_VERIF': False
    }
    with freezegun.freeze_time("2017-08-10"):
      for slug, db_value in workflow_test_data.iteritems():
        with factories.single_commit():
          workflow = wf_factories.WorkflowFactory(
              slug=slug, is_verification_needed=db_value)
          wf_factories.TaskGroupTaskFactory(
              task_group=wf_factories.TaskGroupFactory(
                  workflow=workflow,
                  context=factories.ContextFactory()
              ),
              start_date=date(2017, 8, 3),
              end_date=date(2017, 8, 7))
          person = factories.PersonFactory(email="{}@email.py".format(slug))
        wf_id = workflow.id
        self.assertEqual(workflow.status, workflow.DRAFT)
        resp = self.import_data(collections.OrderedDict([
            ("object_type", "Workflow"),
            ("code", slug),
            ("title", "SomeTitle"),
            ("Need Verification", import_value),
            ("force real-time email updates", "no"),
            ("Admin", person.email),
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
  )
  @ddt.unpack  # pylint: disable=invalid-name
  def test_update_verification_flag_negative(self, db_value, import_value):
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
        person = factories.PersonFactory(email="{}@email.py".format(slug))
      wf_id = workflow.id
      person_email = person.email

      self.generator.activate_workflow(workflow)
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.status, workflow.ACTIVE)
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Workflow"),
          ("code", slug),
          ("title", "SomeTitle"),
          ("Need Verification", import_value),
          ("force real-time email updates", "no"),
          ("Admin", person_email),
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
          ("Admin", person_email),
      ]))
      self.assertEqual(1, resp[0]['ignored'])
      workflow = Workflow.query.filter(Workflow.id == wf_id).first()
      self.assertEqual(workflow.is_verification_needed, db_value)

  def test_error_verification_flag(self):
    """Test create wf without Needed Verification flag"""
    slug = "SomeCode"
    with factories.single_commit():
      person = factories.PersonFactory(email="test@email.py")
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Workflow"),
        ("code", slug),
        ("title", "SomeTitle"),
        ("force real-time email updates", "no"),
        ("Admin", person.email),
    ]))
    self.assertEqual(1, resp[0]['ignored'])
    self.assertIsNone(Workflow.query.filter(Workflow.slug == slug).first())

  @ddt.data(("", errors.MISSING_VALUE_ERROR), ("--", errors.WRONG_VALUE_ERROR))
  @ddt.unpack
  def test_create_required_flag_error(self, data, msg):
    """Test create wf with empty or invalid Needed Verification flag"""
    slug = "SomeCode"
    with factories.single_commit():
      person = factories.PersonFactory(email="test@email.py")
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Workflow"),
        ("code", slug),
        ("title", "SomeTitle"),
        ("force real-time email updates", "no"),
        ("Admin", person.email),
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
    self.assertIsNone(Workflow.query.filter(Workflow.slug == slug).first())
