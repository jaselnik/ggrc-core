# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Add test about folder in api."""

import ddt

from ggrc import db
from ggrc.models import all_models
from ggrc.models.mixins.synchronizable import Synchronizable
from integration.ggrc import TestCase, Api
from integration.ggrc.models import factories
from integration.external_app import external_api_helper

CAD = factories.CustomAttributeDefinitionFactory
CAV = factories.CustomAttributeValueFactory


@ddt.ddt
class TestFolderField(TestCase):
  """Test class about all folder field activities."""

  FOLDERABLE_FACTORIES = [
      factories.AccessGroupFactory,
      factories.AccountBalanceFactory,
      factories.ContractFactory,
      factories.ControlFactory,
      factories.DataAssetFactory,
      factories.DirectiveFactory,
      factories.FacilityFactory,
      factories.IssueFactory,
      factories.KeyReportFactory,
      factories.MarketFactory,
      factories.MetricFactory,
      factories.ObjectiveFactory,
      factories.OrgGroupFactory,
      factories.PolicyFactory,
      factories.ProcessFactory,
      factories.ProductFactory,
      factories.ProductGroupFactory,
      factories.ProgramFactory,
      factories.ProjectFactory,
      factories.RegulationFactory,
      factories.RequirementFactory,
      factories.RiskFactory,
      factories.StandardFactory,
      factories.SystemFactory,
      factories.TechnologyEnvironmentFactory,
      factories.ThreatFactory,
      factories.VendorFactory,
  ]

  def setUp(self):
    super(TestFolderField, self).setUp()
    self.api = Api()
    self.api.login_as_normal()
    self.ext_api = external_api_helper.ExternalApiClient()

  NOT_PUTABLE_FACTORIES = NOT_POSTABLE_FACTORIES = [
      factories.DirectiveFactory,
  ]

  @ddt.data(*FOLDERABLE_FACTORIES)
  def test_create_object(self, factory):
    """Test create folder field for {0._meta.model.__name__}."""
    test_folder_name = "tmp_folder_create_name"
    self.assertEqual(
        test_folder_name,
        factory(folder=test_folder_name).folder
    )

  @ddt.data(*FOLDERABLE_FACTORIES)
  def test_get_object(self, factory):
    """Test get folder field for {0._meta.model.__name__}."""
    test_folder_name = "tmp_folder_get_name"
    obj = factory(folder=test_folder_name)
    data = self.api.get(obj, obj.id).json
    self.assertEqual(
        test_folder_name,
        data[obj._inflector.table_singular.lower()]["folder"]
    )

  @ddt.data(*FOLDERABLE_FACTORIES)
  def test_put_object(self, factory):
    """Test folder field can't be updated
    with put for {0._meta.model.__name__}."""
    test_folder_name = "tmp_folder_put_name"
    obj = factory(folder=test_folder_name)
    update_test_folder_name = "upd_tmp_folder_put_name"
    obj_id = obj.id
    if factory in self.NOT_PUTABLE_FACTORIES:
      with self.assertRaises(NotImplementedError):
        self.api.put(obj, {"folder": update_test_folder_name})
    else:
      if isinstance(obj, Synchronizable):
        # Currently external user can't modify folder field
        # because of WithProtectedAttributes mixin
        return

      self.api.put(obj, {"folder": update_test_folder_name})
      self.assertEqual(
          test_folder_name,
          obj.__class__.query.get(obj_id).folder
      )

  @ddt.data(*FOLDERABLE_FACTORIES)
  def test_post_object(self, factory):
    """Test post folder field for {0._meta.model.__name__}."""
    test_folder_name = "tmp_folder_put_name"
    obj = factory(folder=test_folder_name)
    obj_id = obj.id
    key = obj._inflector.table_singular.lower()
    post_data = self.api.get(obj, obj.id).json
    model = obj.__class__
    db.session.delete(obj)
    db.session.commit()
    del post_data[key]["id"]
    if factory in self.NOT_POSTABLE_FACTORIES:
      with self.assertRaises(NotImplementedError):
        self.api.post(model, post_data)
    else:
      if isinstance(obj, Synchronizable):
        self.api.login_as_external()
      if model in (all_models.Regulation, all_models.Standard):
        post_data[key]["id"] = obj_id + 1
      resp = self.api.post(model, post_data)
      new_obj_id = resp.json[key]["id"]
      self.assertNotEqual(obj_id, new_obj_id)
      self.assertEqual(
          test_folder_name,
          model.query.get(new_obj_id).folder
      )
