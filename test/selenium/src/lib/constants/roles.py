# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Constants for roles."""
# pylint: disable=too-many-public-methods
from lib import url
from lib.constants import objects
from lib.decorator import lazy_property, memoize
from lib.service.rest import client


# global roles
NO_ROLE = "No Role"
NO_ROLE_UI = "(Inactive user)"
ADMIN = "Admin"
CREATOR = "Creator"
READER = "Reader"
EDITOR = "Editor"
ADMINISTRATOR = "Administrator"
GLOBAL_ROLES = (CREATOR, EDITOR, ADMINISTRATOR)
# assessment roles
ASSIGNEES = "Assignees"
VERIFIERS = "Verifiers"
# program roles
PROGRAM_EDITOR = "Program Editor"
PROGRAM_EDITORS = PROGRAM_EDITOR + "s"
PROGRAM_MANAGER = "Program Manager"
PROGRAM_MANAGERS = PROGRAM_MANAGER + "s"
PROGRAM_READER = "Program Reader"
# workflow roles
WORKFLOW_MEMBER = "Workflow Member"
WORKFLOW_MANAGER = "Workflow Manager"
# other roles
OTHER = "other"
CREATORS = CREATOR + "s"
AUDIT_LEAD = "Audit Lead"
AUDITORS = "Auditors"
AUDIT_CAPTAINS = "Audit Captains"
PRINCIPAL_ASSIGNEES = "Principal " + ASSIGNEES
SECONDARY_ASSIGNEES = "Secondary " + ASSIGNEES
COMPLIANCE_CONTACT = "Compliance Contacts"
PRIMARY_CONTACTS = "Primary Contacts"
SECONDARY_CONTACTS = "Secondary Contacts"
CONTROL_OPERATORS = "Control Operators"
CONTROL_OWNERS = "Control Owners"
PRODUCT_MANAGERS = "Product Managers"
TECHNICAL_LEADS = "Technical Leads"
TECHNICAL_PMS = "Technical / Program Managers"
LEGAL_COUNSELS = "Legal Counsels"
SYSTEM_OWNERS = "System Owners"
REVIEWERS = "Reviewers"
RISK_OWNERS = "Risk Owners"

# Some Smoke ACL tests check functionality under this set of roles
IMPORTANT_ASMT_ROLES = [
    ("audit", "auditors"),
    ("assessment", "assignees"),
    ("assessment", "verifiers")
]

# role scopes
SYSTEM = "System"
PRIVATE_PROGRAM = "Private Program"
WORKFLOW = "Workflow"
SUPERUSER = "Superuser"
NO_ACCESS = "No Access"


@memoize
def global_roles():
  """Get global roles as array of dicts"""
  global_roles_url = "/".join([url.API, url.GLOBAL_ROLES])
  return client.RestClient().send_get(global_roles_url)[
      "{}_collection".format(url.GLOBAL_ROLES)][url.GLOBAL_ROLES]


class ACLRolesIDsMetaClass(type):
  """A class to set ACL role ids"""
  # pylint: disable=invalid-name
  # pylint: disable=no-self-use
  # pylint: disable=not-an-iterable
  # pylint: disable=no-value-for-parameter
  # pylint: disable=too-many-public-methods

  def roles(cls):
    """Return ACL roles."""
    acr_url = "/".join([url.API, url.ACCESS_CONTROL_ROLES])
    return client.RestClient("").get_object(acr_url).json()[
        "{}_collection".format(url.ACCESS_CONTROL_ROLES)][
        url.ACCESS_CONTROL_ROLES]

  @lazy_property
  def standard_roles(cls):
    """Return standard ACL roles."""
    return cls.roles()

  def _role_id_from_list(cls, roles, object_type, name):
    """Get id of the role by `object_type` and `name` from roles."""
    role_id = None
    for role in roles:
      if role["object_type"] == object_type and role["name"] == name:
        role_id = role["id"]
        break
    return role_id

  def object_roles(cls, object_type):
    """Get role ids by `object_type`."""
    roles = []
    for role in cls.roles():
      if role["object_type"] == object_type:
        roles.append(role)
    return roles

  def id_of_role(cls, object_type, name):
    """Get id of the role by `object_type` and `name`."""
    role_id = cls._role_id_from_list(cls.standard_roles, object_type, name)
    if not role_id:
      role_id = cls._role_id_from_list(cls.roles(), object_type, name)
    if not role_id:
      raise ValueError("Invalid role. name {0}, object_type {1}".format(
          name, object_type))
    return role_id

  @property
  def CONTROL_ADMINS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.CONTROLS),
                          name=ADMIN)

  @property
  def ISSUE_ADMINS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.ISSUES),
                          name=ADMIN)

  @property
  def OBJECTIVE_ADMINS(cls):
    return cls.id_of_role(objects.get_obj_type(objects.OBJECTIVES), name=ADMIN)

  @property
  def THREAT_ADMINS(cls):
    return cls.id_of_role(objects.get_obj_type(objects.THREATS), name=ADMIN)

  @property
  def RISK_ADMINS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.RISKS),
                          name=ADMIN)

  @property
  def ORG_GROUPS_ADMINS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.ORG_GROUPS),
                          name=ADMIN)

  @property
  def ASSESSMENT_CREATORS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.ASSESSMENTS),
        name=CREATORS)

  @property
  def ASSESSMENT_ASSIGNEES(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.ASSESSMENTS),
        name=ASSIGNEES)

  @property
  def ASSESSMENT_VERIFIERS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.ASSESSMENTS),
        name=VERIFIERS)

  @property
  def AUDIT_CAPTAINS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.AUDITS),
                          name=AUDIT_CAPTAINS)

  @property
  def AUDITORS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.AUDITS),
                          name=AUDITORS)

  @property
  def PROGRAM_MANAGERS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.PROGRAMS),
                          name=PROGRAM_MANAGERS)

  @property
  def PROGRAM_EDITORS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.PROGRAMS),
                          name=PROGRAM_EDITORS)

  @property
  def PROGRAM_PRIMARY_CONTACTS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.PROGRAMS),
                          name=PRIMARY_CONTACTS)

  @property
  def PRODUCT_MANAGERS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.PRODUCTS),
                          name=PRODUCT_MANAGERS)

  @property
  def TECHNOLOGY_ENVIRONMENT_ADMINS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(
                          objects.TECHNOLOGY_ENVIRONMENTS),
                          name=ADMIN)

  @property
  def REVIEWERS(cls):
    return cls.id_of_role(object_type=objects.get_obj_type(objects.REVIEWS),
                          name=REVIEWERS)

  @property
  def STANDARD_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.STANDARDS), name=ADMIN)

  @property
  def REGULATION_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.REGULATIONS), name=ADMIN)

  @property
  def REQUIREMENT_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.REQUIREMENTS), name=ADMIN)

  @property
  def POLICY_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.POLICIES), name=ADMIN)

  @property
  def CONTRACT_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.CONTRACTS), name=ADMIN)

  @property
  def EVIDENCE_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.EVIDENCE), name=ADMIN)

  @property
  def PROJECT_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.PROJECTS), name=ADMIN)

  @property
  def PROJECT_ASSIGNEES(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.PROJECTS),
        name=objects.get_singular(ASSIGNEES, title=True))

  @property
  def PROJECT_VERIFIERS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.PROJECTS),
        name=objects.get_singular(VERIFIERS, title=True))

  @property
  def KEY_REPORT_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.KEY_REPORTS), name=ADMIN)

  @property
  def ACCOUNT_BALANCE_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.ACCOUNT_BALANCES), name=ADMIN)

  @property
  def ACCESS_GROUP_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.ACCESS_GROUPS), name=ADMIN)

  @property
  def DATA_ASSET_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.DATA_ASSETS), name=ADMIN)

  @property
  def FACILITY_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.FACILITIES), name=ADMIN)

  @property
  def MARKET_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.MARKETS), name=ADMIN)

  @property
  def METRIC_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.METRICS), name=ADMIN)

  @property
  def PROCESS_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.PROCESSES), name=ADMIN)

  @property
  def PRODUCT_GROUP_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.PRODUCT_GROUPS), name=ADMIN)

  @property
  def SYSTEM_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.SYSTEMS), name=ADMIN)

  @property
  def VENDOR_ADMINS(cls):
    return cls.id_of_role(
        object_type=objects.get_obj_type(objects.VENDORS), name=ADMIN)


class ACLRolesIDs(object):
  """Access Control List Roles IDs."""
  # pylint: disable=too-few-public-methods

  __metaclass__ = ACLRolesIDsMetaClass
