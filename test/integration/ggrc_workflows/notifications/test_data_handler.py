# coding: utf-8
# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=no-self-use

"""Tests wf data_handler module."""
import ddt
import mock
from ggrc import db
from ggrc import login
from ggrc.models.revision import Revision
from ggrc_workflows.notification.data_handler import get_cycle_task_dict
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


@ddt.ddt
class TestDataHandler(TestCase):

  """ This class test basic functions in the data_handler module """
  def setUp(self):
    super(TestDataHandler, self).setUp()
    from ggrc.login import noop
    noop.login()

  def test_get_cycle_task_dict(self):
    """Tests get_cycle_task_dict functionality."""
    contract = factories.ContractFactory(title=u"Contract1")
    cycle_task = wf_factories.CycleTaskGroupObjectTaskFactory(title=u"task1")
    relationship = factories.RelationshipFactory(
        source=contract,
        destination=cycle_task
    )
    db.session.delete(relationship)
    db.session.commit()

    relationship_revision = Revision(obj=relationship,
                                     modified_by_id=None,
                                     action="deleted",
                                     content="{}")
    contract_revision = Revision(obj=contract,
                                 modified_by_id=None,
                                 action="deleted",
                                 content='{"display_name": "Contract1"}')
    revisions = [relationship_revision, contract_revision]
    factories.EventFactory(
        modified_by_id=login.get_current_user_id(),
        action="DELETE",
        resource_id=relationship.id,
        resource_type=relationship.type,
        revisions=revisions
    )
    task_dict = get_cycle_task_dict(cycle_task)
    self.assertEqual(task_dict["related_objects"][0],
                     u"Contract1 [removed from task]")

  @ddt.data(True, False)
  def test_related_object_name(self, with_related):
    """Test checks related object name"""
    issue_name = "Test issue name"
    issue = factories.IssueFactory(title=issue_name)
    cycle_task = wf_factories.CycleTaskGroupObjectTaskFactory(title=u"task1")
    factories.RelationshipFactory(
        source=issue,
        destination=cycle_task
    )
    task_dict = get_cycle_task_dict(cycle_task, with_related=with_related)
    if with_related:
      self.assertEqual(task_dict["related_objects"][0], (issue_name, ))
    else:
      self.assertEqual(task_dict["related_objects"], [])

  @mock.patch("ggrc_workflows.notification.data_handler.logger")
  def test_ct_without_revisions_error(self, logger):
    """Tests that notifications for CycleTask
    without revisions are handled properly."""
    contract = factories.ContractFactory(title=u"Test Contract")
    cycle_task = wf_factories.CycleTaskGroupObjectTaskFactory(title=u"task1")
    relationship = factories.RelationshipFactory(
        source=contract,
        destination=cycle_task
    )
    db.session.delete(relationship)
    db.session.commit()

    relationship_revision = Revision(obj=relationship,
                                     modified_by_id=None,
                                     action="deleted",
                                     content="{}")
    revisions = [relationship_revision]
    factories.EventFactory(
        modified_by_id=login.get_current_user_id(),
        action="DELETE",
        resource_id=relationship.id,
        resource_type=relationship.type,
        revisions=revisions
    )
    contract_revision = db.session.query(Revision).filter(
        Revision.resource_type == "Contract",
        Revision.action == "created",
        Revision.resource_id == contract.id
    ).one()
    db.session.delete(contract_revision)
    db.session.commit()
    get_cycle_task_dict(cycle_task)
    logger.warning.assert_called_once_with(
        "Unmapped %s id %s from CycleTask id %s has no revisions logged. ",
        "Contract", contract.id, cycle_task.id
    )
