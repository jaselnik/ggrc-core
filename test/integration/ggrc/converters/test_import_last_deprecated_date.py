# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Last Deprecated Date logic with imports."""

import collections
import datetime
import itertools

import ddt

from ggrc import models
from ggrc.converters import errors

from freezegun import freeze_time

from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
class TestImportLastDeprecatedDate(TestCase):
  """Test Last Deprecated Date logic with imports."""

  def setUp(self):
    """Set up for Last Deprecated Date import test cases."""
    super(TestImportLastDeprecatedDate, self).setUp()
    self.client.get("/login")
    self.warning_non_importable = {
        "row_warnings": {
            errors.EXPORT_ONLY_WARNING.format(
                line=3, column_name="Last Deprecated Date",
            ),
        },
    }

  def test_import_last_deprecated_date(self):  # pylint: disable=invalid-name
    """Last Deprecated Date on Audit should be not importable."""
    with freeze_time("2017-01-25"):
      audit = factories.AuditFactory(status="Deprecated")

    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Audit"),
        ("code", audit.slug),
        ("Last Deprecated Date", "02/25/2017"),
    ]))
    self._check_csv_response(resp, {
        "Audit": self.warning_non_importable,
    })

    updated_audit = models.audit.Audit.query.get(audit.id)
    self.assertEqual(updated_audit.last_deprecated_date,
                     datetime.date(2017, 1, 25))

  def test_import_deprecated_status(self):
    """Test import Deprecated Audit sets Last Deprecated Date to now."""
    audit = factories.AuditFactory()

    with freeze_time("2017-01-25"):
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Audit"),
          ("code", audit.slug),
          ("State", "Deprecated"),
      ]))
      self._check_csv_response(resp, {})

    updated_audit = models.audit.Audit.query.get(audit.id)
    self.assertEqual(updated_audit.last_deprecated_date,
                     datetime.date(2017, 1, 25))

  def test_import_deprecated_status_again(self):  # noqa pylint: disable=invalid-name
    """Last Deprecated Date on Audit isn't changed when status not changed."""
    with freeze_time("2017-01-25"):
      audit = factories.AuditFactory(status="Deprecated")

    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Audit"),
        ("code", audit.slug),
        ("State", "Deprecated"),
    ]))
    self._check_csv_response(resp, {})

    updated_audit = models.audit.Audit.query.get(audit.id)
    self.assertEqual(updated_audit.last_deprecated_date,
                     datetime.date(2017, 1, 25))

  def test_import_deprecated_date_with_state(self):  # noqa pylint: disable=invalid-name
    """Last Deprecated Date on Audit is set to now, not what user imports."""
    with freeze_time("2017-01-25"):
      audit = factories.AuditFactory()

    with freeze_time("2017-01-27"):
      resp = self.import_data(collections.OrderedDict([
          ("object_type", "Audit"),
          ("code", audit.slug),
          ("State", "Deprecated"),
          ("Last Deprecated Date", "02/25/2017"),
      ]))
      self._check_csv_response(resp, {
          "Audit": self.warning_non_importable,
      })

    updated_audit = models.audit.Audit.query.get(audit.id)
    self.assertEqual(updated_audit.last_deprecated_date,
                     datetime.date(2017, 1, 27))

  @ddt.data(*itertools.product(
      ["Audit"],
      [(True, True), (False, True), (True, False), (False, False)],
  ))
  @ddt.unpack
  def test_import_deprecated_date_warnings(self, model_name,
                                           (empty_object, empty_import)):
    """Check warnings on imported Last Deprecated Date for {}

    In this test covered next scenarios:
    1) object has empty last_deprecated_date field, user imports empty
       field - no warnings
    2) object has non-empty last_deprecated_date field, user imports empty
       field - no warnings
    3) object has empty last_deprecated_date field, user imports non-empty
       field - warning
    4) object has non-empty last_deprecated_date field, user imports non-empty
       field - warning
    """
    if empty_object:
      obj = factories.get_model_factory(model_name)()
    else:
      obj = factories.get_model_factory(model_name)(status="Deprecated")
    if empty_import:
      resp = self.import_data(collections.OrderedDict([
          ("object_type", model_name),
          ("code", obj.slug),
          ("Last Deprecated Date", ""),
      ]))
    else:
      resp = self.import_data(collections.OrderedDict([
          ("object_type", model_name),
          ("code", obj.slug),
          ("Last Deprecated Date", "02/25/2017"),
      ]))

    expected_errors = {
        model_name: self.warning_non_importable,
    }

    if empty_import:
      self._check_csv_response(resp, {})
    else:
      self._check_csv_response(resp, expected_errors)

  @ddt.data(*itertools.product(
      ["Audit"],
      ["01/25/2017", "2017-01-25"],
  ))
  @ddt.unpack
  def test_import_same_deprecated_date(self, model_name, formatted_date):
    """Check case of import the same last_deprecated_date field in {0}.

    If user imports the {0} with the same last_deprecated_date field -
    imported without warnings.
    """
    with freeze_time("2017-01-25"):
      obj = factories.get_model_factory(model_name)(title="test",
                                                    status="Deprecated")

    resp = self.import_data(collections.OrderedDict([
        ("object_type", model_name),
        ("code", obj.slug),
        ("title", "New title"),
        ("Last Deprecated Date", formatted_date),
    ]))

    self._check_csv_response(resp, {})

  def test_import_invalid_date(self):
    """Invalid date in Last Deprecated Date is ignored in Audit import."""
    with freeze_time("2017-01-25"):
      audit = factories.AuditFactory(title="test", status="Deprecated")

    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Audit"),
        ("code", audit.slug),
        ("title", "New title"),
        ("Last Deprecated Date", "0125/2017"),
    ]))

    expected_errors = {
        "Audit": self.warning_non_importable,
    }
    self._check_csv_response(resp, expected_errors)
