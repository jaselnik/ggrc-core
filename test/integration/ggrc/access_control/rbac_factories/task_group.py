# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Task Group RBAC Factory."""
from ggrc import access_control
from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


class TaskGroupRBACFactory(base.BaseRBACFactory):
  """Task Group RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Task Group permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=unused-argument
    self.setup_workflow_scope(user_id, acr)

    self.admin_control_id = {
        name: id_ for id_, name
        in access_control.role.get_custom_roles_for("Control").items()
    }["Admin"]
    self.api = Api()

    if user_id:
      self.user_id = user_id
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Task Group object."""
    person = factories.PersonFactory()
    return self.api.post(all_models.TaskGroup, {
        "task_group": {
            "contact": {
                "id": person.id,
                "type": "Person",
            },
            "title": "New Task Group",
            "context": None,
            "workflow": {
                "id": self.workflow_id,
                "type": "Workflow",
            },
        }
    })

  def read(self):
    """Read existing Task Group object."""
    return self.api.get(all_models.TaskGroup, self.task_group_id)

  def update(self):
    """Update title of existing Task Group object."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    return self.api.put(task_group, {"title": factories.random_str()})

  def delete(self):
    """Delete Task Group object."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    return self.api.delete(task_group)

  def read_revisions(self):
    """Read revisions for Task Group object."""
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              all_models.TaskGroup,
              query.format("task_group", self.task_group_id)
          )
      )
    return responses

  def map_control(self):
    """Map Control on which user don't have any rights to Cycle Task."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    control = factories.ControlFactory()
    return self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": task_group.id, "type": task_group.type},
            "destination": {"id": control.id, "type": control.type},
            "context": None
        }
    })

  def map_created_control(self):
    """Map Control that was created by user to Cycle Task."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    with factories.single_commit():
      control = factories.ControlFactory()
      for acl in control._access_control_list:
        if acl.ac_role_id == self.admin_control_id:
          factories.AccessControlPersonFactory(
              person_id=self.user_id,
              ac_list=acl,
          )
    return self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": task_group.id, "type": task_group.type},
            "destination": {"id": control.id, "type": control.type},
            "context": None
        }
    })

  def read_mapped_control(self):
    """Read Control object mapped to Task Group."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    with factories.single_commit():
      control = factories.ControlFactory()
      factories.RelationshipFactory(
          source=task_group, destination=control
      )
    return self.api.get(control, control.id)

  def upmap_control(self):
    """Unmap Control from Task Group."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    with factories.single_commit():
      control = factories.ControlFactory()
      tg_obj = factories.RelationshipFactory(
          source=task_group, destination=control
      )
    return self.api.delete(tg_obj)

  def clone(self):
    """Clone existing Task Group object."""
    task_group = all_models.TaskGroup.query.get(self.task_group_id)
    wf_factories.TaskGroupTaskFactory(task_group=task_group)

    return self.api.post(all_models.TaskGroup, {
        "task_group": {
            # workaround - title is required for validation
            "title": "test title",
            "clone": self.task_group_id,
            "clone_objects": True,
            "clone_people": True,
            "clone_tasks": True,
            "context": None,
        }
    })
