# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test default slug prefix values."""

import unittest

import ddt

from ggrc.models import all_models
from ggrc.models import exceptions
from ggrc.models.mixins import Slugged


@ddt.ddt
class TestSlugPrefix(unittest.TestCase):
  """Test default slug prefix values."""

  EXPECTED_PREFIXES = {
      'AccessGroup': 'ACCESSGROUP',
      'AccountBalance': 'ACCOUNTBALANCE',
      'Assessment': 'ASSESSMENT',
      'AssessmentTemplate': 'TEMPLATE',
      'Audit': 'AUDIT',
      'Contract': 'CONTRACT',
      'Control': 'CONTROL',
      'Cycle': 'CYCLE',
      'CycleTaskGroup': 'CYCLEGROUP',
      'CycleTaskGroupObjectTask': 'CYCLETASK',
      'DataAsset': 'DATAASSET',
      'Directive': 'DIRECTIVE',  # unused but has slug prefix
      'Evidence': 'EVIDENCE',
      'Document': 'DOCUMENT',
      'Facility': 'FACILITY',
      'Issue': 'ISSUE',
      'Market': 'MARKET',
      'Objective': 'OBJECTIVE',
      'OrgGroup': 'ORGGROUP',
      'Policy': 'POLICY',
      'Process': 'PROCESS',
      'Product': 'PRODUCT',
      'Program': 'PROGRAM',
      'Project': 'PROJECT',
      'Regulation': 'REGULATION',
      'Risk': 'RISK',
      'Requirement': 'REQUIREMENT',
      'Standard': 'STANDARD',
      'System': 'SYSTEM',
      'TaskGroup': 'TASKGROUP',
      'TaskGroupTask': 'TASK',
      'Threat': 'THREAT',
      'Vendor': 'VENDOR',
      'Workflow': 'WORKFLOW',
      'Metric': 'METRIC',
      'ProductGroup': 'PRODUCTGROUP',
      'TechnologyEnvironment': 'TECHNOLOGYENVIRONMENT',
      'KeyReport': 'KEYREPORT',
  }

  @ddt.data(*all_models.all_models)
  def test_slug_prefix(self, model):
    """Test slug prefix for model {}."""
    if model.__name__ not in self.EXPECTED_PREFIXES:
      # No slug prefix defined at all
      self.assertIsNone(getattr(model, "generate_slug_prefix", None))
    else:
      self.assertEqual(model.generate_slug_prefix(),
                       self.EXPECTED_PREFIXES[model.__name__])

  def test_prefix_uniqueness(self):
    """Test slug prefix uniqueness for all models."""
    all_prefixes = [
        model.generate_slug_prefix()
        for model in all_models.all_models
        if hasattr(model, "generate_slug_prefix")
    ]

    self.assertEqual(
        sorted(all_prefixes),
        sorted(set(all_prefixes))
    )

  @ddt.data("*BAD-SLUG", "BAD**SLUG", "BAD-SLUG*")
  def test_bad_slug_validation(self, bad_slug):
    """Test slug validation with bad value"""
    self.assertRaises(
        exceptions.ValidationError,
        Slugged().validate_slug, "slug", bad_slug
    )

  @ddt.data("GOOD-SLUG", None)
  def test_good_slug_validation(self, good_slug):
    """Test slug validation with good value"""
    self.assertEqual(
        Slugged().validate_slug("slug", good_slug),
        good_slug
    )
