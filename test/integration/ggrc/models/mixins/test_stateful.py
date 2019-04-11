# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for Stateful mixin."""

import ddt

from integration.ggrc import api_helper
from integration.ggrc.query_helper import WithQueryApi
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from ggrc.models import get_model
from ggrc.models.mixins import synchronizable


@ddt.ddt
class TestStatefulMixin(WithQueryApi, TestCase):
  """Test cases for Stateful mixin."""

  def setUp(self):
    super(TestStatefulMixin, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  @ddt.data(
      "AccessGroup",
      "Audit",
      "Control",
      "DataAsset",
      "Requirement",
      "Facility",
      "Issue",
      "Market",
      "Objective",
      "OrgGroup",
      "Product",
      "Program",
      "Project",
      "Risk",
      "RiskAssessment",
      "Requirement",
      "Threat",
      "Vendor",
      "ProductGroup",
      "TechnologyEnvironment",
  )
  def test_update_status(self, model_name):
    """Test status updating."""
    factory = factories.get_model_factory(model_name)

    # pylint: disable=protected-access
    if issubclass(factory._meta.model, synchronizable.Synchronizable):
      self.api.login_as_external()

    obj = factory()
    object_name = obj._inflector.table_singular
    for status in obj.VALID_STATES:
      # Try to update status.
      response = self.api.put(obj, {u"status": status})
      self.assert200(response)

      # Check that status has been updated.
      response = self.api.get(get_model(model_name), obj.id)
      self.assert200(response)
      new_status = response.json.get(object_name, {}).get("status")
      self.assertEqual(new_status, status)

  @ddt.data(
      "AccessGroup",
      "Audit",
      "Control",
      "DataAsset",
      "Requirement",
      "Facility",
      "Issue",
      "Market",
      "Objective",
      "OrgGroup",
      "Product",
      "Program",
      "Project",
      "Risk",
      "RiskAssessment",
      "Requirement",
      "Threat",
      "Vendor",
      "ProductGroup",
      "TechnologyEnvironment",
  )
  def test_set_invalid_status(self, model_name):
    """Test returning 400 code for setting invalid status."""
    factory = factories.get_model_factory(model_name)

    # pylint: disable=protected-access
    if issubclass(factory._meta.model, synchronizable.Synchronizable):
      self.api.login_as_external()

    obj = factory()
    invalid_status = u"Invalid status."
    response = self.api.put(obj, {u"status": invalid_status})
    self.assert400(response)
