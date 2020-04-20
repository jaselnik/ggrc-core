# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for making sure eager queries are working on all mixins."""

import ddt

from ggrc.utils import QueryCounter

from integration.ggrc import TestCase
from integration.ggrc.models import factories as ggrc_factories
from integration.ggrc_workflows.models import factories as wf_factories
from integration.ggrc.query_helper import WithQueryApi
from integration.ggrc import api_helper


@ddt.ddt
class TestAllModels(WithQueryApi, TestCase):
  """Test basic model structure for all models"""

  def setUp(self):
    super(TestAllModels, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  QUERY_API_LIMIT = {
      'Assessment': 14,
      'AssessmentTemplate': 8,
      'AccessGroup': 16,
      'AccountBalance': 12,
      'Audit': 12,
      'Comment': 6,
      'Contract': 13,
      'Control': 14,
      'Cycle': 7,
      'CycleTaskGroup': 8,
      'CycleTaskGroupObjectTask': 14,
      'Document': 7,
      'Issue': 14,
      'KeyReport': 12,
      'Market': 12,
      'Objective': 13,
      'OrgGroup': 12,
      'Person': 10,
      'Policy': 13,
      'Process': 12,
      'System': 12,
      'Program': 16,
      'Regulation': 13,
      'TaskGroup': 8,
      'TaskGroupTask': 7,
      'Workflow': 12,
      'TechnologyEnvironment': 7,
      'Product': 12,
      'Metric': 12,
      'ProductGroup': 12,
  }

  MODEL_FACTORIES = [
      ggrc_factories.AccountBalanceFactory,
      ggrc_factories.AuditFactory,
      ggrc_factories.AssessmentFactory,
      ggrc_factories.AssessmentTemplateFactory,
      ggrc_factories.CommentFactory,
      ggrc_factories.ContractFactory,
      ggrc_factories.ControlFactory,
      ggrc_factories.IssueFactory,
      ggrc_factories.KeyReportFactory,
      ggrc_factories.MarketFactory,
      ggrc_factories.ObjectiveFactory,
      ggrc_factories.OrgGroupFactory,
      ggrc_factories.PersonFactory,
      ggrc_factories.PolicyFactory,
      ggrc_factories.ProcessFactory,
      ggrc_factories.SystemFactory,
      ggrc_factories.ProgramFactory,
      ggrc_factories.RegulationFactory,
      ggrc_factories.DocumentFactory,
      ggrc_factories.MetricFactory,
      ggrc_factories.ProductFactory,
      ggrc_factories.ProductGroupFactory,
      wf_factories.CycleFactory,
      wf_factories.CycleTaskGroupFactory,
      wf_factories.CycleTaskGroupObjectTaskFactory,
      wf_factories.TaskGroupFactory,
      wf_factories.TaskGroupTaskFactory,
      wf_factories.WorkflowFactory,
  ]

  LOWER_BOUND_COUNT = 10

  UPPER_BOUND_COUNT = 20

  QUERY_API_TEST_CASES = [(f, count) for f in MODEL_FACTORIES
                          for count in (LOWER_BOUND_COUNT,
                                        UPPER_BOUND_COUNT)]

  @ddt.data(*QUERY_API_TEST_CASES)
  @ddt.unpack
  def test_index_on_commit(self, factory, obj_count):
    """Test count number of queries on eager query procedure."""

    model = factory._meta.model  # pylint: disable=protected-access
    with ggrc_factories.single_commit():
      # pylint: disable=expression-not-assigned
      {factory() for _ in range(obj_count)}
    with QueryCounter() as counter:
      self._post([{
          "object_name": model.__name__,
          "filters": {"expression": {}},
          "limit": [0, obj_count],
          "order_by": [{"name": "updated_at", "desc": True}]
      }])
      self.assertEqual(
          counter.get,
          self.QUERY_API_LIMIT[model.__name__],
          "Eager query of {model} has unexpected number of queries: "
          "actual={counted}, expected={expected} for query "
          "{obj_count} instances".format(
              model=model,
              expected=self.QUERY_API_LIMIT[model.__name__],
              counted=counter.get,
              obj_count=obj_count,
          )
      )

  def test_soring_objects(self):
    """Test sorting in pagination module"""
    with ggrc_factories.single_commit():
      audit = ggrc_factories.AuditFactory()
      for _ in xrange(10):
        ggrc_factories.AssessmentFactory(audit=audit)
    response = self._post([{
        "object_name": "Assessment",
        "filters": {"expression": {}},
        "limit": [0, 10],
        "order_by": [{"name": "created_at", "desc": True}]
    }])
    values = response.json[0]["Assessment"]["values"]
    for index in xrange(0, len(values) - 1):
      self.assertGreaterEqual(values[index]["created_at"],
                              values[index + 1]["created_at"])
      # sorted by id if equal created_at values
      if values[index]["created_at"] == values[index + 1]["created_at"]:
        self.assertGreater(values[index]["id"],
                           values[index + 1]["id"])
