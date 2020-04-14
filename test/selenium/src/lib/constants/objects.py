# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Constants and methods for work with objects."""
import itertools
import sys

import inflection


# objects
RELATIONSHIPS = "relationships"
PROGRAMS = "programs"
PROGRAM_PARENTS = "program_parents"
PROGRAM_CHILDS = "program_childs"
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
CHANGE_LOG_ITEMS = "change_log_items"

EDITABLE_GGRC_OBJS = (REGULATIONS, STANDARDS,)

# disabled
SCOPE_OBJECTS = (ACCESS_GROUPS, ACCOUNT_BALANCES, DATA_ASSETS, FACILITIES,
                 KEY_REPORTS, MARKETS, METRICS, ORG_GROUPS, PROCESSES,
                 PRODUCTS, PRODUCT_GROUPS, PROJECTS, SYSTEMS,
                 TECHNOLOGY_ENVIRONMENTS, VENDORS)

# disabled
STANDARDS_AND_REGULATIONS = (REGULATIONS, STANDARDS)

# disabled
DIRECTIVES = (CONTRACTS, POLICIES, REQUIREMENTS,)

# disabled
OBJECTIVES_AND_THREATS = (OBJECTIVES, THREATS)

# disabled
CONTROLS_AND_RISKS = (CONTROLS, RISKS)

ALL_DISABLED_OBJECTS = (
    CONTROLS_AND_RISKS + SCOPE_OBJECTS + DIRECTIVES + OBJECTIVES_AND_THREATS)

ALL_SNAPSHOTABLE_OBJS = EDITABLE_GGRC_OBJS + ALL_DISABLED_OBJECTS

EDITABLE_CA_OBJS = EDITABLE_GGRC_OBJS + (
    WORKFLOWS, PROGRAMS, AUDITS, ISSUES, ASSESSMENTS, PEOPLE)

OBJS_SUPPORTING_MANDATORY_CA = EDITABLE_GGRC_OBJS + (
    WORKFLOWS, PROGRAMS, AUDITS, ISSUES, PEOPLE)

ALL_CA_OBJS = EDITABLE_CA_OBJS + ALL_DISABLED_OBJECTS

EDITABLE_OBJS_W_CUSTOM_ROLES = EDITABLE_GGRC_OBJS + (
    ASSESSMENTS, DOCUMENTS, EVIDENCE, ISSUES, AUDITS, PROGRAMS)

ALL_OBJS_W_CUSTOM_ROLES = EDITABLE_OBJS_W_CUSTOM_ROLES + ALL_DISABLED_OBJECTS

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
    elif name == EVIDENCE:
      singular = EVIDENCE
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


def get_singular(plural, title=False, titleize=False):
  """Transform object name to singular and lower or title form.
 Example: product_groups -> product_group
 """
  _singular = _get_singular([plural])[0]
  _singular = (inflection.camelize(_singular.lower()) if title
               else _singular.lower())
  if titleize:
    _singular = inflection.titleize(_singular)
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


def get_normal_form(obj_name, title=True):
  """Replaces underscores with spaces.

  Transforms to title form if title is True.
  (product_groups -> Product Groups).
  """
  obj_name_wo_spaces = obj_name.replace("_", " ")
  return obj_name_wo_spaces.title() if title else obj_name_wo_spaces


ALL_PLURAL = [k for k in globals().keys() if
              not k.startswith("_") and "ALL" not in k and k.isupper()]

ALL_SINGULAR = _get_singular(ALL_PLURAL)

ALL_OBJS = [obj for obj in [getattr(sys.modules[__name__], _obj) for _obj in
            sys.modules[__name__].ALL_PLURAL] if isinstance(obj, str)]


def get_obj_type(obj_name):
  """Get object's type based on object's name."""
  return get_singular(obj_name, title=obj_name != CUSTOM_ATTRIBUTES)


SINGULAR_CONTROL_AND_RISK = [get_singular(x) for x in CONTROLS_AND_RISKS]

SINGULAR_SCOPE_OBJS_ITERATOR = itertools.cycle([get_singular(x)
                                                for x in SCOPE_OBJECTS])

SINGULAR_STANDARDS_AND_REGULATIONS_ITERATOR = itertools.cycle(
    [get_singular(x) for x in STANDARDS_AND_REGULATIONS])

ALL_SINGULAR_DISABLED_OBJS = [get_singular(x) for x in ALL_DISABLED_OBJECTS]
