# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests import of multiple objects"""
# pylint: disable=invalid-name

import collections

import sqlalchemy as sa

from ggrc.converters import errors
from ggrc.models import all_models
from integration import ggrc as integration_ggrc
from integration.ggrc import factories


class TestCsvImport(integration_ggrc.TestCase):
  """Tests for import of multiple objects."""

  def setUp(self):  # pulint: disable=missing-docstring
    super(TestCsvImport, self).setUp()
    self.client.get("/login")

    self.test_data = [
        collections.OrderedDict([
            ("object_type", "Program"),
            ("Code*", ""),
            ("Title*", "Program-1"),
            ("Program managers", "user@example.com"),
        ]),
        collections.OrderedDict([
            ("object_type", "Program"),
            ("Code*", ""),
            ("Title*", "Program-2"),
            ("Program managers", "user@example.com"),
        ]),
    ]

  def test_multi_basic_program(self):
    """Tests for import of multiple programs, defined correctly."""
    expected_object_counts = {
        "Program": (2, 0, 0),
    }

    response = self.import_data(*self.test_data)

    for block in response:
      created, updated, ignored = expected_object_counts[block["name"]]
      self.assertEqual(created, block["created"])
      self.assertEqual(updated, block["updated"])
      self.assertEqual(ignored, block["ignored"])
      self.assertEqual(set(), set(block["row_warnings"]))

    self.assertEqual(all_models.Program.query.count(), 2)

  def test_multi_basic_program_with_warnings(self):
    """Test for import of multiple programs with warnings."""
    test_data = (
        self.test_data +
        [
            collections.OrderedDict([
                ("object_type", "Program"),
                ("Code*", ""),
                ("Title*", "Program-1"),
                ("Program managers", "user@example.com"),
            ])
        ]
    )

    expected_object_counts = {
        "Program": (2, 0, 1),
    }

    response = self.import_data(*test_data)

    row_messages = []
    for block in response:
      created, updated, ignored = expected_object_counts[block["name"]]
      self.assertEqual(created, block["created"])
      self.assertEqual(updated, block["updated"])
      self.assertEqual(ignored, block["ignored"])
      row_messages.extend(block["row_warnings"])
      row_messages.extend(block["row_errors"])

    expected_warnings = {
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="5", processed_line="3",
            column_name="Title", value="Program-1",
        ),
    }

    self.assertEqual(expected_warnings, set(row_messages))
    self.assertEqual(2, all_models.Program.query.count())

  @staticmethod
  def get_relationships_for(obj):
    """Return Relationships for given `obj`."""
    return all_models.Relationship.query.filter(
        sa.or_(
            sa.and_(
                all_models.Relationship.destination_type == obj.type,
                all_models.Relationship.destination_id == obj.id,
            ),
            sa.and_(
                all_models.Relationship.source_type == obj.type,
                all_models.Relationship.source_id == obj.id,
            ),
        ),
    )

  def test_multi_basic_program_with_mappings(self):
    """Tests mapping of multiple objects"""
    with factories.single_commit():
      issue = factories.IssueFactory()
    for data in self.test_data:
      data["map:issue"] = issue.slug

    expected_object_counts = {
        "Program": (2, 0, 0),
    }

    response = self.import_data(*self.test_data)

    for block in response:
      created, updated, ignored = expected_object_counts[block["name"]]
      self.assertEqual(created, block["created"])
      self.assertEqual(updated, block["updated"])
      self.assertEqual(ignored, block["ignored"])
      self.assertEqual(set(), set(block["row_warnings"]))

    self.assertEqual(2, all_models.Program.query.count())

    program_1 = all_models.Program.query.filter_by(title="Program-1").one()
    program_2 = all_models.Program.query.filter_by(title="Program-2").one()

    self.assertEqual(2, self.get_relationships_for(issue).count())
    self.assertEqual(1, self.get_relationships_for(program_1).count())
    self.assertEqual(1, self.get_relationships_for(program_2).count())
