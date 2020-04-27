# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""" This module is used for import and export of data with csv files """

from ggrc.extensions import get_extension_modules
from ggrc.models import all_models


def get_jobs_to_register(name):
  """Get cron job handlers defined in `converters` package.

  Get cron job handlers defined in `converters` package as `name`.

  Args:
    name (str): A name of job handlers to get.

  Returns:
    A list containing job handlers of provided name.
  """
  from ggrc.converters import cron_jobs
  return getattr(cron_jobs, name, [])


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
    "assessment template": all_models.AssessmentTemplate,
    "assessment": all_models.Assessment,
    "assessment_template": all_models.AssessmentTemplate,
    "audit": all_models.Audit,
    "control assessment": all_models.Assessment,
    "issue": all_models.Issue,
    "person": all_models.Person,
    "program": all_models.Program,
    "regulation": all_models.Regulation,
    "standard": all_models.Standard,
}

GGRC_EXPORTABLE = {
    "contract": all_models.Contract,
    "objective": all_models.Objective,
    "threat": all_models.Threat,
    "policy": all_models.Policy,
    "requirement": all_models.Requirement,
    "snapshot": all_models.Snapshot,
    "control": all_models.Control,
    "risk": all_models.Risk,
    "access group": all_models.AccessGroup,
    "access_group": all_models.AccessGroup,
    "accessgroup": all_models.AccessGroup,
    "account balance": all_models.AccountBalance,
    "account_balance": all_models.AccountBalance,
    "accountbalance": all_models.AccountBalance,
    "data asset": all_models.DataAsset,
    "data_asset": all_models.DataAsset,
    "dataasset": all_models.DataAsset,
    "facility": all_models.Facility,
    "keyreport": all_models.KeyReport,
    "key_report": all_models.KeyReport,
    "key report": all_models.KeyReport,
    "market": all_models.Market,
    "metric": all_models.Metric,
    "org group": all_models.OrgGroup,
    "org_group": all_models.OrgGroup,
    "orggroup": all_models.OrgGroup,
    "process": all_models.Process,
    "product group": all_models.ProductGroup,
    "product": all_models.Product,
    "product_group": all_models.ProductGroup,
    "productgroup": all_models.ProductGroup,
    "project": all_models.Project,
    "system": all_models.System,
    "technology environment": all_models.TechnologyEnvironment,
    "technology_environment": all_models.TechnologyEnvironment,
    "technologyenvironment": all_models.TechnologyEnvironment,
    "vendor": all_models.Vendor,
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
