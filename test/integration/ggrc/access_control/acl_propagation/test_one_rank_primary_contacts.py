# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Primary Contacts propagation"""

import ddt

from ggrc.models import all_models
from integration.ggrc.access_control import rbac_factories
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.utils import helpers


@ddt.ddt
class TestPrimaryContactsPropagation(base.TestACLPropagation):
  """Test Primary Contacts role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "MappedReview Program": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Regulation": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Objective": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Contract": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Policy": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Standard": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Threat": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
          "MappedReview Requirement": {
              "create_review": True,
              "read_review": True,
              "update_review": True,
              "delete_review": False,
          },
      },
  }

  def init_factory(self, role, model, parent):
    """Initialize RBAC factory with propagated Primary Contacts role.

    Args:
        role: Global Custom role that user have (Creator/Reader/Editor).
        model: Model name for which factory should be got.
        parent: Model name in scope of which objects should be installed.

    Returns:
        Initialized RBACFactory object.
    """
    self.setup_people()
    primary_contacts = all_models.AccessControlRole.query.filter_by(
        name="Primary Contacts",
        object_type=parent,
    ).first()
    rbac_factory = rbac_factories.TEST_FACTORIES_MAPPING[model]
    return rbac_factory(self.people[role].id, primary_contacts, parent)

  @helpers.unwrap(PERMISSIONS)
  def test_access(self, role, model, action_name, expected_result):
    """Primary Contacts {0:<7}: On {1:<20} test {2:<20} - Expected {3:<2} """
    self.runtest(role, model, action_name, expected_result)
