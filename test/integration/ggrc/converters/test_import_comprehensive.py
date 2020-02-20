# -*- coding: utf-8 -*-

# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Comprehensive import tests.

These tests should eventually contain all good imports and imports with all
possible errors and warnings.
"""

from ggrc.gdrive import errors as gdrive_errors
from ggrc.models import exceptions
from integration.ggrc import TestCase


class TestComprehensiveSheets(TestCase):
  """Test class for import csv files."""

  def setUp(self):
    super(TestComprehensiveSheets, self).setUp()
    self.client.get("/login")

  def test_import_with_semicolon_delimiter(self):
    """Test import csv file with ";" delimiter."""
    # pylint: disable=invalid-name
    response = self.import_file(
        "object_with_semicolon_delimiter.csv",
        safe=False
    )
    expected_errors = {}
    self._check_csv_response(response, expected_errors)

  def test_import_with_nonstandard_delimiter(self):
    """Test import csv file with "$" delimiter, should raise an error."""
    # pylint: disable=invalid-name
    with self.assertRaises(exceptions.WrongDelimiterError) as ex:
      self.import_file(
          "object_with_dollar_delimiter.csv",
          safe=False
      )
    self.assertEqual(
        gdrive_errors.WRONG_DELIMITER_IN_CSV,
        ex.exception.message
    )

  def test_large_csv_import(self):
    """Test limitation for big imports"""
    filename = "large_csv_4000_assessments.csv"

    with self.assertRaises(exceptions.FileTooLargeExeption):
      self.import_file(filename, safe=False)

  def test_import_with_obscure_delimiter(self):
    """Test import csv file with multiple "Object type" text.

    Test for atypical situation when "Object type" is present in
    multiple locations in the csv file. It shouldn't affect finding
    the right delimiter and import of csv file.
    """
    # pylint: disable=invalid-name
    response = self.import_file(
        "object_with_obscure_delimiter.csv",
        safe=False
    )
    expected_errors = {}
    self._check_csv_response(response, expected_errors)
