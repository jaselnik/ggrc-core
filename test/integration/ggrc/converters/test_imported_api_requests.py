# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Check number of db queries per API request.

This is in converters because it depends on import to provide data
"""

import collections

import ddt

from ggrc.models import all_models
from ggrc.utils import QueryCounter
from ggrc.views import all_object_views
from integration.ggrc_workflows.generator import WorkflowsGenerator

from integration.ggrc import TestCase
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories
from appengine import base


@ddt.ddt
@base.with_memcache
class TestComprehensiveSheets(TestCase):

  """
  test sheet from:
    https://docs.google.com/spreadsheets/d/1Jg8jum2eQfvR3kZNVYbVKizWIGZXvfqv3yQpo2rIiD8/edit#gid=0

  """

  # skip abstract models since they are not really first class
  WHITELIST = {"Directive"}
  MODELS = [getattr(all_models, model_name)
            for model_name in all_models.__all__
            if model_name not in WHITELIST]

  def setUp(self):
    super(TestComprehensiveSheets, self).setUp()
    self.client.get("/login")
    self.generator = ObjectGenerator()

    self.create_custom_attributes()
    # TODO: use here such a CSV that doesn't have errors or warnings
    self.import_file("comprehensive_sheet1.csv", safe=False)

    gen = WorkflowsGenerator()
    wfs = all_models.Workflow.eager_query().filter_by(status='Draft').all()
    for workflow in wfs:
      _, cycle = gen.generate_cycle(workflow)
      self.assertIsNotNone(cycle)

  # limit found by trial and error, may need tweaking if models change

  LIMIT_DICT = {
      "LIST": {
          all_models.Revision: 86,
          all_models.Event: 291,
      },
      "SINGLE": {}
  }
  DEFAULT_LIMIT = 39

  def test_queries_per_api_call(self):
    """Import comprehensive_sheet1 and count db requests per model.

    collection get
    Query count should be <LIMIT for all model types.
    """
    for model in self.MODELS:
      limit = self.LIMIT_DICT["LIST"].get(model, self.DEFAULT_LIMIT)
      with QueryCounter() as counter:
        counter.queries = []
        self.generator.api.get_query(model, "")
        if counter.get > limit:
          print collections.Counter(counter.queries).most_common(1)
        self.assertLessEqual(
            counter.get,
            limit,
            "Query count for object {} exceeded: {}/{}".format(
                model.__name__, counter.get, limit)
        )

  def test_queries_per_object_page(self):
    """Import comprehensive_sheet1 and count db requests per collection get.

    Query count should be <LIMIT for all model types.
    """
    for view in all_object_views():
      with QueryCounter() as counter:
        model = view.model_class
        if model not in self.MODELS:
          return
        instance = model.query.first()
        if instance is None or getattr(instance, "id", None) is None:
          return
        limit = self.LIMIT_DICT["SINGLE"].get(model, self.DEFAULT_LIMIT)
        counter.queries = []
        res = self.client.get("/{}/{}".format(view.url, instance.id))
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(
            counter.get, limit,
            "Query count for object {} exceeded: {}/{}".format(
                model.__name__, counter.get, limit)
        )

  def test_queries_for_dashboard(self):
    """Test query count for dashboard page."""
    with QueryCounter() as counter:
      res = self.client.get("/dashboard")
      self.assertEqual(res.status_code, 200)
      self.assertLess(counter.get,
                      self.DEFAULT_LIMIT,
                      "Query count for dashboard")

  def test_queries_for_permissions(self):
    """Test query count for permissions loading."""
    with QueryCounter() as counter:
      res = self.client.get("/permissions")
      self.assertEqual(res.status_code, 200)
      self.assertLess(counter.get,
                      self.DEFAULT_LIMIT,
                      "Query count for permissions")

  @staticmethod
  def create_custom_attributes():
    """Generate custom attributes needed by comprehensive_sheet1.csv."""
    cad = factories.CustomAttributeDefinitionFactory

    with factories.single_commit():
      cad(definition_type="objective", title="my custom text", mandatory=True)
      cad(definition_type="program", title="my_text", mandatory=True)
      cad(definition_type="program", title="my_date", attribute_type="Date")
      cad(definition_type="program", title="my_checkbox",
          attribute_type="Checkbox")
      cad(definition_type="program", title="my_dropdown",
          attribute_type="Dropdown",
          multi_choice_options="a,b,c,d")
      cad(definition_type="program", title="my_multiselect",
          attribute_type="Multiselect")
