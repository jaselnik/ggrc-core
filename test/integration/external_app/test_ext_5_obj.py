# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for external Contract, Objective, Policy, Requirement and
Threat models"""

from collections import OrderedDict

import ddt

from ggrc.converters import errors
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc import api_helper


class TestBaseExternal5Objects(TestCase):
  """Base class for testing externalization for Objects"""

  OBJECT_MODELS = (all_models.Contract,
                   all_models.Objective,
                   all_models.Policy,
                   all_models.Requirement,
                   all_models.Threat)


@ddt.ddt
class TestInternalApp5Objects(TestBaseExternal5Objects):
  """Class for tests Objects with internal client"""

  def setUp(self):
    super(TestInternalApp5Objects, self).setUp()
    self.api = api_helper.Api()

  @ddt.data(*TestBaseExternal5Objects.OBJECT_MODELS)
  def test_import_deprecated(self, model):
    """
        Test that import of'{0.__name__}' model is deprecated
    """
    excepted_resp = {
        model._inflector.title_singular: {
            "row_errors": {
                errors.EXTERNAL_MODEL_IMPORT_RESTRICTION.format(
                    line=3,
                    external_model_name=model.__name__),
            },
        },
    }
    response = self.import_data(OrderedDict([
        ("object_type", model.__name__),
        ("Code*", ""),
        ("Title", "Test title")
    ]))
    self._check_csv_response(response, excepted_resp)
