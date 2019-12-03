# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Workflow RBAC Factory."""
from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


class WorkflowRBACFactory(base.BaseRBACFactory):
  """Workflow RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Workflow permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=unused-argument
    self.setup_workflow_scope(user_id, acr)
    self.api = Api()

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Workflow object."""
    return self.api.post(all_models.Workflow, {
        "workflow": {
            "title": "New workflow",
            "context": None,
        }
    })

  def read(self):
    """Read existing Workflow object."""
    return self.api.get(all_models.Workflow, self.workflow_id)

  def update(self):
    """Update title of existing Workflow object."""
    workflow = all_models.Workflow.query.get(self.workflow_id)
    return self.api.put(workflow, {"title": factories.random_str()})

  def delete(self):
    """Delete Workflow object."""
    workflow = all_models.Workflow.query.get(self.workflow_id)
    return self.api.delete(workflow)

  def read_revisions(self):
    """Read revisions for Workflow object."""
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              all_models.Workflow, query.format("workflow", self.workflow_id)
          )
      )
    return responses

  def clone(self):
    """Clone existing Workflow object."""
    with factories.single_commit():
      task_group = wf_factories.TaskGroupFactory(workflow_id=self.workflow_id)
      wf_factories.TaskGroupTaskFactory(task_group=task_group)

    return self.api.post(all_models.Workflow, {
        "workflow": {
            # workaround - title is required for validation
            "title": "test title",
            "clone": self.workflow_id,
            "clone_objects": True,
            "clone_people": True,
            "clone_tasks": True,
            "context": None,
        }
    })
