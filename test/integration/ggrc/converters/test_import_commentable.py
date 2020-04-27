# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

# pylint: disable=maybe-no-member, invalid-name

"""Test import of commentable fields."""

import collections
import ddt

from ggrc.models import all_models
from integration.ggrc import TestCase


@ddt.ddt
class TestImportCommentable(TestCase):
  """Class with tests of importing fields of Commentable mixin."""

  @ddt.data(
      all_models.Regulation,
      all_models.Standard,
  )
  def test_model_import(self, model):
    """Test import commentable model {}."""
    recipients = model.VALID_RECIPIENTS
    model_name = model.__name__
    import_data = [
        ("object_type", model_name),
        ("Code", ""),
        ("Title", "{}-Title".format(model_name)),
        ("Admin", "user@example.com"),
        ("Recipients", ','.join(recipients)),
        ("Send by default", True),
    ]
    response = self.import_data(collections.OrderedDict(import_data))
    self._check_csv_response(response, {})
    obj = model.query.first()
    self.assertEqual(obj.send_by_default, True)
    self.assertEqual(sorted(obj.recipients.split(",")), sorted(recipients))

  def test_program_import(self):
    """Test import of program recipients."""
    recipients = all_models.Program.VALID_RECIPIENTS
    model_name = "Program"
    import_data = [
        ("object_type", model_name),
        ("Code", ""),
        ("Title", "{}-Title".format(model_name)),
        ("Program Managers", "user@example.com"),
        ("Recipients", ','.join(recipients)),
        ("Send by default", True),
    ]
    response = self.import_data(collections.OrderedDict(import_data))
    self._check_csv_response(response, {})
    obj = all_models.Program.query.first()
    self.assertEqual(obj.send_by_default, True)
    self.assertEqual(sorted(obj.recipients.split(",")), sorted(recipients))
