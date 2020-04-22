# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Workflow Admin propagation"""

import ddt

from ggrc.models import all_models
from integration.ggrc.access_control import rbac_factories
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.utils import helpers


@ddt.ddt
class TestWfAdminPropagation(base.TestACLPropagation):
  """Test Workflow Admin role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "Workflow": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "clone": True,
          },
          "TaskGroup": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map_control": False,
              "map_created_control": True,
              "read_mapped_control": False,
              "upmap_control": False,
              "clone": True,
          },
          "TaskGroupTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
          },
          "Cycle": {
              "activate": True,
              "create": True,
              "read": True,
              "update": False,
              "delete": (False, "unimplemented"),
              "end": (False, "unimplemented"),
          },
          "CycleTaskGroup": {
              "read": True,
              "update": False,
              "delete": True,
          },
          "CycleTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": (False, "unimplemented"),
              "add_comment": True,
              "read_comment": True,
              "map_control": False,
              "map_created_control": True,
              "read_mapped_control": False,
              "upmap_control": False,
              "start": True,
              "end": True,
              "verify": True,
              "decline": True,
              "restore": True,
          },
      },
      "Reader": {
          "Workflow": {
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "clone": True,
          },
          "TaskGroup": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map_control": False,
              "map_created_control": True,
              "read_mapped_control": True,
              "upmap_control": False,
              "clone": True,
          },
          "TaskGroupTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
          },
          "Cycle": {
              "activate": True,
              "create": True,
              "read": True,
              "update": False,
              "delete": (False, "unimplemented"),
              "end": (False, "unimplemented"),
          },
          "CycleTaskGroup": {
              "read": True,
              "update": False,
              "delete": True,
          },
          "CycleTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": (False, "unimplemented"),
              "add_comment": True,
              "read_comment": True,
              "map_control": False,
              "map_created_control": True,
              "read_mapped_control": True,
              "upmap_control": (True, "unimplemented"),
              "start": True,
              "end": True,
              "verify": True,
              "decline": True,
              "restore": True,
          },
      },
      "Editor": {
          "Workflow": {
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "clone": True,
          },
          "TaskGroup": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map_control": True,
              "map_created_control": True,
              "read_mapped_control": True,
              "upmap_control": True,
              "clone": True,
          },
          "TaskGroupTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
          },
          "Cycle": {
              "activate": True,
              "create": True,
              "read": True,
              "update": False,
              "delete": (False, "unimplemented"),
              "end": (False, "unimplemented"),
          },
          "CycleTaskGroup": {
              "read": True,
              "update": False,
              "delete": True,
          },
          "CycleTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": (False, "unimplemented"),
              "add_comment": True,
              "read_comment": True,
              "map_control": True,
              "map_created_control": True,
              "read_mapped_control": True,
              "upmap_control": True,
              "start": True,
              "end": True,
              "verify": True,
              "decline": True,
              "restore": True,
          },
      },
  }

  def init_factory(self, role, model, parent):
    """Initialize RBAC factory with propagated Workflow Admin role.

    Args:
        role: Global Custom role that user have (Creator/Reader/Editor).
        model: Model name for which factory should be got.
        parent: Model name in scope of which objects should be installed.

    Returns:
        Initialized RBACFactory object.
    """
    self.setup_people()
    wf_admin_acr = all_models.AccessControlRole.query.filter_by(
        name="Admin",
        object_type="Workflow",
    ).first()

    rbac_factory = rbac_factories.TEST_FACTORIES_MAPPING[model]
    return rbac_factory(self.people[role].id, wf_admin_acr, parent)

  @helpers.unwrap(PERMISSIONS)
  def test_access(self, role, model, action_name, expected_result):
    """Workflow Admin {0:<7}: On {1:<20} test {2:<20} - Expected {3:<2} """
    self.runtest(role, model, action_name, expected_result)
