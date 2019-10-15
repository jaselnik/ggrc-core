# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""" This module is used for import and export of data with csv files """

from ggrc.extensions import get_extension_modules
from ggrc.models import all_models


def get_shared_unique_rules():
  """ get rules for all cross checks betveen classes

  used for checking unique constraints on colums such as code and title
  """

  shared_tables = [
      (all_models.System, all_models.Process),
      (all_models.Policy, all_models.Regulation,
       all_models.Standard, all_models.Contract),
  ]
  rules = {}
  for tables in shared_tables:
    for table in tables:
      rules[table] = tables

  return rules


GGRC_IMPORTABLE = {
    "access group": all_models.AccessGroup,
    "access_group": all_models.AccessGroup,
    "accessgroup": all_models.AccessGroup,
    "account balance": all_models.AccountBalance,
    "account_balance": all_models.AccountBalance,
    "accountbalance": all_models.AccountBalance,
    "assessment template": all_models.AssessmentTemplate,
    "assessment": all_models.Assessment,
    "assessment_template": all_models.AssessmentTemplate,
    "audit": all_models.Audit,
    "contract": all_models.Contract,
    "control assessment": all_models.Assessment,
    "data asset": all_models.DataAsset,
    "data_asset": all_models.DataAsset,
    "dataasset": all_models.DataAsset,
    "facility": all_models.Facility,
    "issue": all_models.Issue,
    "keyreport": all_models.KeyReport,
    "key_report": all_models.KeyReport,
    "key report": all_models.KeyReport,
    "market": all_models.Market,
    "metric": all_models.Metric,
    "objective": all_models.Objective,
    "org group": all_models.OrgGroup,
    "org_group": all_models.OrgGroup,
    "orggroup": all_models.OrgGroup,
    "person": all_models.Person,
    "policy": all_models.Policy,
    "process": all_models.Process,
    "product group": all_models.ProductGroup,
    "product": all_models.Product,
    "product_group": all_models.ProductGroup,
    "productgroup": all_models.ProductGroup,
    "program": all_models.Program,
    "project": all_models.Project,
    "regulation": all_models.Regulation,
    "requirement": all_models.Requirement,
    "standard": all_models.Standard,
    "system": all_models.System,
    "technology environment": all_models.TechnologyEnvironment,
    "technology_environment": all_models.TechnologyEnvironment,
    "technologyenvironment": all_models.TechnologyEnvironment,
    "threat": all_models.Threat,
    "vendor": all_models.Vendor,
}

GGRC_EXPORTABLE = {
    "snapshot": all_models.Snapshot,
    "control": all_models.Control,
    "risk": all_models.Risk,
}

GGRC_IMPORTABLE_ONLY = {
    "lca comment": all_models.Comment,
}


def _get_types(attr):
  """Get contributed attribute types.

  Args:
    attr: String containing selected type. Either contributed_importables or
      contributed_exportables.
  """
  res = {}
  for extension_module in get_extension_modules():
    contributed = getattr(extension_module, attr, None)
    if callable(contributed):
      res.update(contributed())
    elif isinstance(contributed, dict):
      res.update(contributed)
  return res


def _get_importables_exportables():
  """ Get a dict of all objects can be importable and exportable """
  importable = GGRC_IMPORTABLE
  importable.update(_get_types("contributed_importables"))
  return importable


def get_importables():
  """ Get a dict of all importable objects from all modules """
  importable = GGRC_IMPORTABLE_ONLY
  importable.update(_get_importables_exportables())
  return importable


def get_importables_visible():
  """ Get a dict of visible importable objects from all modules """
  importable = _get_importables_exportables()
  return importable


def get_exportables():
  """ Get a dict of all exportable objects from all modules """
  exportable = GGRC_EXPORTABLE
  exportable.update(_get_importables_exportables())
  exportable.update(_get_types("contributed_exportables"))
  return exportable
