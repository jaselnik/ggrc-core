# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""""Test Import Automapping"""

import collections

import ddt
from ggrc import models
from integration.ggrc import TestCase
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


@ddt.ddt
class TestBasicCsvImport(TestCase):
  """"Test Import Automapping"""

  def setUp(self):
    super(TestBasicCsvImport, self).setUp()
    self.generator = ObjectGenerator()
    self.client.get("/login")

  @ddt.data("Policy", "Contract")
  def test_basic_automappings(self, object_name):
    """"Test Basic Automapping for {}"""

    with factories.single_commit():
      program = factories.ProgramFactory(title="program 1")
      program_manager = factories.PersonFactory()
      factories.AccessControlPersonFactory(ac_list=program.
                                           acr_name_acl_map["Program "
                                                            "Managers"],
                                           person=program_manager,)
      req_one = factories.RequirementFactory(title="section-1")

    self.import_data(collections.OrderedDict([
        ("object_type", object_name),
        ("Code*", ""),
        ("Title", object_name),
        ("Admin", "user@example.com"),
        ("map:program", program.slug),
        ("map:requirement", req_one.slug),
    ])
    )

    directive = models.get_model(object_name)
    directives = directive.query.filter_by(title=object_name).first()
    directives_slug = directives.slug

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": "program 1",
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    self.assertIn(req_one.slug, response.data)
    self.assertIn(directives_slug, response.data)
