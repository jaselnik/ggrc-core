# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Constants and methods for work with objects."""

import sys

import inflection


# objects
RELATIONSHIPS = "relationships"
PROGRAMS = "programs"
WORKFLOWS = "workflows"
AUDITS = "audits"
ASSESSMENTS = "assessments"
ASSESSMENT_TEMPLATES = "assessment_templates"
ISSUES = "issues"
REGULATIONS = "regulations"
POLICIES = "policies"
STANDARDS = "standards"
CONTRACTS = "contracts"
REQUIREMENTS = "requirements"
CONTROLS = "controls"
OBJECTIVES = "objectives"
PEOPLE = "people"
GLOBAL_ROLES = "roles"
USER_ROLES = "user_roles"
ACL_ROLES = "access_control_roles"
ORG_GROUPS = "org_groups"
VENDORS = "vendors"
ACCESS_GROUPS = "access_groups"
ACCOUNT_BALANCES = "account_balances"
SYSTEMS = "systems"
PROCESSES = "processes"
DATA_ASSETS = "data_assets"
PRODUCTS = "products"
PROJECTS = "projects"
FACILITIES = "facilities"
KEY_REPORTS = "key_reports"
MARKETS = "markets"
RISKS = "risks"
THREATS = "threats"
CUSTOM_ATTRIBUTES = "custom_attribute_definitions"
EXTERNAL_CUSTOM_ATTRIBUTES = "external_" + CUSTOM_ATTRIBUTES
COMMENTS = "comments"
SNAPSHOTS = "snapshots"
TASK_GROUPS = "task_groups"
TASK_GROUP_TASKS = "task_group_tasks"
CYCLE_TASK_GROUP_OBJECT_TASKS = "cycle_task_group_object_tasks"
CYCLES = "cycles"
DOCUMENTS = "documents"
METRICS = "metrics"
TECHNOLOGY_ENVIRONMENTS = "technology_environments"
PRODUCT_GROUPS = "product_groups"
PROPOSALS = "proposals"
EVIDENCE = 'evidence'
REVIEWS = "reviews"

EDITABLE_GGRC_OBJ = (
    ACCESS_GROUPS, CONTRACTS, DATA_ASSETS, FACILITIES,
    METRICS, MARKETS, OBJECTIVES, ORG_GROUPS, POLICIES, PROCESSES, PRODUCTS,
    PROJECTS, REGULATIONS, REQUIREMENTS, STANDARDS, SYSTEMS, VENDORS, THREATS,
    TECHNOLOGY_ENVIRONMENTS, PRODUCT_GROUPS, KEY_REPORTS, ACCOUNT_BALANCES,
)

EXTERNAL_OBJECTS = (CONTROLS, RISKS)

ALL_SNAPSHOTABLE_OBJS = EDITABLE_GGRC_OBJ + EXTERNAL_OBJECTS

EDITABLE_CA_OBJS = EDITABLE_GGRC_OBJ + (
    WORKFLOWS, PROGRAMS, AUDITS, ISSUES, ASSESSMENTS, PEOPLE)

OBJS_SUPPORTING_MANDATORY_CA = EDITABLE_GGRC_OBJ + (
    WORKFLOWS, PROGRAMS, AUDITS, ISSUES, PEOPLE)

ALL_CA_OBJS = EDITABLE_CA_OBJS + EXTERNAL_OBJECTS

ALL_OBJS_WO_STATE_FILTERING = (
    PEOPLE, WORKFLOWS, TASK_GROUPS, CYCLES, CYCLE_TASK_GROUP_OBJECT_TASKS)

EDITABLE_OBJS_W_CUSTOM_ROLES = EDITABLE_GGRC_OBJ + (
    PROJECTS, ASSESSMENTS, DOCUMENTS, EVIDENCE, ISSUES, AUDITS, PROGRAMS)

ALL_OBJS_W_CUSTOM_ROLES = EDITABLE_OBJS_W_CUSTOM_ROLES + EXTERNAL_OBJECTS

IMPORTABLE_OBJECTS = EDITABLE_CA_OBJS + (
    ASSESSMENT_TEMPLATES, TASK_GROUPS, TASK_GROUP_TASKS)


def _get_singular(plurals):
  """
 Return: list of basestring: Capitalized object names in singular form
 """
  singulars = []
  for name in plurals:
    name = inflection.underscore(name)
    if name == PEOPLE:
      singular = "person"
    elif name == POLICIES:
      singular = "policy"
    elif name == PROCESSES:
      singular = "process"
    elif name == FACILITIES:
      singular = "facility"
    else:
      singular = name[:-1]
    singulars.append(singular.upper())
  return singulars


def _get_plural(singulars):
  """
  Return: list of basestring: Capitalized object names in plural form
  """
  plurals = []
  for name in singulars:
    name = inflection.underscore(name)
    if name == "person":
      plural = PEOPLE
    elif name == "policy":
      plural = POLICIES
    elif name == "process":
      plural = PROCESSES
    elif name == "facility":
      plural = FACILITIES
    else:
      plural = name + "s"
    plurals.append(plural.upper())
  return plurals


def get_singular(plural, title=False):
  """Transform object name to singular and lower or title form.
 Example: product_groups -> product_group
 """
  _singular = _get_singular([plural])[0]
  if title:
    _singular = inflection.camelize(_singular.lower())
  else:
    _singular = _singular.lower()
  return _singular


def get_plural(singular, title=False):
  """Transform object name to plural and lower form or title form.
  Example: product_group -> product_groups
  """
  _plural = _get_plural([singular])[0]
  if title:
    _plural = _plural.title()
  else:
    _plural = _plural.lower()
  return _plural


def get_normal_form(obj_name):
  """Transforms object name to title form
  (product_groups -> Product Groups).
  """
  return obj_name.replace("_", " ").title()


ALL_PLURAL = [k for k in globals().keys() if
              not k.startswith("_") and "ALL" not in k and k.isupper()]

ALL_SINGULAR = _get_singular(ALL_PLURAL)

ALL_OBJS = [obj for obj in [getattr(sys.modules[__name__], _obj) for _obj in
            sys.modules[__name__].ALL_PLURAL] if isinstance(obj, str)]


def get_obj_type(obj_name):
  """Get object's type based on object's name."""
  return get_singular(obj_name, title=obj_name != CUSTOM_ATTRIBUTES)


EXTERNAL_END_POINTS = [get_singular(x) for x
                       in EXTERNAL_OBJECTS + (EXTERNAL_CUSTOM_ATTRIBUTES,)]

SINGULAR_TITLE_EXTERNAL_OBJS = [
    get_singular(x, title=True) for x in EXTERNAL_OBJECTS]
