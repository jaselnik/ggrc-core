# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Reviewer propagation"""

import ddt

from ggrc.models import all_models
from integration.ggrc.access_control import rbac_factories
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.utils import helpers


@ddt.ddt
class TestReviewersPropagation(base.TestACLPropagation):
  """Test Reviewer role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "MappedReview Program": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Regulation": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Objective": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Contract": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Policy": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Standard": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Threat": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
          "MappedReview Requirement": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
      },
      "Reader": {
          "MappedReview Contract": {
              "read_parent": True,
              "read_document": True,
              "update_document": False,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": False,
              "read_document_comment": True,
              "create_and_map_document_comment": False,
          },
      },
      "Editor": {
          "MappedReview Requirement": {
              "read_parent": True,
              "read_document": True,
              "update_document": True,
              "delete_document": False,
              "read_comment": True,
              "create_and_map_comment": True,
              "read_document_comment": True,
              "create_and_map_document_comment": True,
          },
      },
  }

  def init_factory(self, role, model, parent):
    """Initialize RBAC factory with propagated Secondary Contacts role.

    Args:
        role: Global Custom role that user have (Creator/Reader/Editor).
        model: Model name for which factory should be got.
        parent: Model name in scope of which objects should be installed.

    Returns:
        Initialized RBACFactory object.
    """
    self.setup_people()
    reviewer_acr = all_models.AccessControlRole.query.filter_by(
        name="Reviewers",
        object_type="Review",
    ).one()

    rbac_factory = rbac_factories.TEST_FACTORIES_MAPPING[model]
    return rbac_factory(
        self.people[role].id, reviewer_acr, parent, role_at_review=True
    )

  @helpers.unwrap(PERMISSIONS)
  def test_access(self, role, model, action_name, expected_result):
    """Reviewer {0:<7}: On {1:<20} test {2:<20} - Expected {3:<2} """
    self.runtest(role, model, action_name, expected_result)
