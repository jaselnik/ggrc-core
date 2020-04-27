# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for basic Block Converter."""

from collections import defaultdict

import mock
from ddt import data, ddt

from ggrc import models
from ggrc.converters import base_block
from ggrc.utils import QueryCounter
from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt
class TestBaseBlock(TestCase):
  """Tests for BlockConverter."""
  # Protected access check is disable for testing private functions.
  # pylint: disable=protected-access

  QUERY_LIMIT = 4  # maximum number of queries allowed for building the cache

  @staticmethod
  def dd_to_dict(ddict):
    return {
        key: {
            type_: set(ids) for type_, ids in value.items()
        } for key, value in ddict.items()
    }

  @data(0, 1, 2, 4, 8)
  def test_create_mapping_cache(self, count):
    """Test creation of mapping cache for export."""

    with factories.single_commit():
      regulations = [factories.RegulationFactory() for _ in range(count)]
      requirements = [factories.RequirementFactory() for _ in range(count)]
      controls = [factories.ControlFactory() for _ in range(count)]

      expected_cache = defaultdict(lambda: defaultdict(list))
      for i in range(count):
        for j in range(i):
          with mock.patch('ggrc.models.relationship.is_external_app_user',
                          return_value=True):
            factories.RelationshipFactory(
                source=regulations[j] if i % 2 == 0 else requirements[i],
                destination=regulations[j] if i % 2 == 1 else requirements[i],
            )
            factories.RelationshipFactory(
                source=regulations[j] if i % 2 == 0 else controls[i],
                destination=regulations[j] if i % 2 == 1 else controls[i],
                is_external=True,
            )
          expected_cache[regulations[j].id]["Control"].append(
              controls[i].slug
          )
          expected_cache[regulations[j].id]["Requirement"].append(
              requirements[i].slug
          )

    block = base_block.ExportBlockConverter(
        mock.MagicMock(),
        object_class=models.Regulation,
        fields="all",
        object_ids=[r.id for r in regulations],
        class_name=models.Regulation.__name__,
    )

    with QueryCounter() as counter:
      cache = block._create_mapping_cache()
      self.assertEqual(
          self.dd_to_dict(cache),
          self.dd_to_dict(expected_cache),
      )
      self.assertLess(counter.get, self.QUERY_LIMIT)

  def test_get_identifier_mappings(self):
    """Test _get_identifier_mappings function."""
    count = 3

    with factories.single_commit():
      regulation = factories.RegulationFactory()
      requirements = [factories.RequirementFactory() for _ in range(count)]
      controls = [factories.ControlFactory() for _ in range(count)]
      expected_id_map = {
          "Requirement": {o.id: o.slug for o in requirements},
          "Control": {o.id: o.slug for o in controls},
      }

      relationships = []
      for i in range(count):
        with mock.patch('ggrc.models.relationship.is_external_app_user',
                        return_value=True):
          relationships.append(factories.RelationshipFactory(
              source=regulation if i % 2 == 0 else requirements[i],
              destination=regulation if i % 2 == 1 else requirements[i],
          ))
          relationships.append(factories.RelationshipFactory(
              source=regulation if i % 2 == 0 else controls[i],
              destination=regulation if i % 2 == 1 else controls[i],
              is_external=True,
          ))

    block = base_block.ExportBlockConverter(
        mock.MagicMock(),
        object_class=models.Regulation,
        fields="all",
        object_ids=[regulation.id],
        class_name=models.Regulation.__name__,
    )
    id_map = block._get_identifier_mappings(relationships)
    self.assertEqual(expected_id_map, id_map)
