# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for overridden __table_args__."""

import unittest

from ggrc.models.all_models import all_models
from ggrc.models.mixins.base import Identifiable


class TestTableArgs(unittest.TestCase):

  DP_MODELS = {
      "Namespaces",
      "Attributes",
      "AttributeDefinitions",
      "AttributeTypes",
      "ObjectTypes",
      "AttributeTemplates",
      "ObjectTemplates",
      "ExternalMapping",
  }
  DP_MODELS.update({
      "Regulation",
      "Standard",
  })

  def test_extra_args_included(self):
    """Table args for all models should contain extra args.

    This can be violated if you inherit Identifiable but then also define
    constraints via __table_args__ instead of _extra_table_args.
    """
    for model in all_models:
      if model.__name__ in self.DP_MODELS:
        # Data platform models do not follow normal ggrc model conventions.
        continue

      self.assertTrue(issubclass(model, Identifiable))

      extras = getattr(model, "_extra_table_args", None)
      if not extras:
        continue
      if callable(extras):
        extras = extras(model)

      # Doing only constraint name checking because equality doen't work here
      extra_names = {e.name for e in extras}
      args_names = {a.name for a in model.__table_args__}
      self.assertTrue(
          extra_names.issubset(args_names),
          "_extra_table_args for {} are not present in __table_args__"
          .format(model.__name__)
      )
