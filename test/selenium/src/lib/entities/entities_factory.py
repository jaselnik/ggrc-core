# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Factories that create entities."""
# pylint: disable=too-many-lines
# pylint: disable=too-many-arguments
# pylint: disable=invalid-name
# pylint: disable=redefined-builtin

import copy
import datetime
import random

from lib import factory, users
from lib.constants import (
    objects, roles, value_aliases, messages, object_states, element,
    str_formats)
from lib.constants.element import AdminWidgetCustomAttributes, ReviewStates
from lib.decorator import lazy_property
from lib.entities import entity
from lib.utils import date_utils, help_utils, string_utils
from lib.utils.string_utils import StringMethods


class EntitiesFactory(object):
  """Common factory class for entities."""
  # pylint: disable=too-few-public-methods

  def __init__(self, obj_name):
    self.obj_name = obj_name
    self.obj_type = objects.get_obj_type(self.obj_name)
    self.obj_title = self.generate_string(self.obj_type)
    self.obj_entity_cls = factory.get_cls_obj_entity(object_name=self.obj_name)
    self.obj_slug = None
    self._acl_roles = []

  def obj_inst(self):
    """Create object's instance and set value for attribute type."""
    return self.obj_entity_cls().update_attrs(
        is_allow_none=False, type=self.obj_type)

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates object's instance with random attributes' values."""
    pass

  def create(self, is_add_rest_attrs=False, **attrs):
    """Create random object's instance, if 'is_add_rest_attrs' then add
    attributes for REST, if 'attrs' then update attributes accordingly and
    update acl roles.
    """
    obj = self._set_attrs(is_add_rest_attrs, **attrs)
    if "custom_roles" in attrs:
      self._acl_roles.extend(attrs["custom_roles"])
    elif "admins" in attrs:
      for acr_name, role_id, default_list in self._acl_roles:
        if acr_name == "admins":
          default_list.extend(attrs["admins"])
    for acr_name, role_id, default_list in self._acl_roles:
      if acr_name in attrs:
        people_list = attrs[acr_name]
      else:
        people_list = default_list
      self.set_acl(obj, acr_name, people_list, role_id, is_add_rest_attrs)
    return obj

  def _set_attrs(self, is_add_rest_attrs=False, **attrs):
    """Create obj and update attrs."""
    return self._create_random_obj(
        is_add_rest_attrs=is_add_rest_attrs).update_attrs(
        is_allow_none=False, **attrs)

  @classmethod
  def generate_string(cls, first_part, second_part=None, add_timestamp=False,
                      allowed_chars=StringMethods.ALLOWED_CHARS):
    """Generate random string in unicode format according to mandatory
    'first_part' string and optional 'second_part'. 'third part' may be a
    timestamp in milliseconds if 'add_timestamp' is True, or a random string.
    Symbols allowed in random part may be specified by `allowed_chars`
    argument."""
    second_part = second_part if second_part else StringMethods.random_uuid()
    third_part = (str(datetime.datetime.now().microsecond) if add_timestamp
                  else StringMethods.random_string(chars=allowed_chars))
    return unicode("_".join([first_part, second_part, third_part]))

  @classmethod
  def generate_external_id(cls):
    """Generate external id."""
    return random.randint(10000, 99999)

  @classmethod
  def generate_slug(cls):
    """Generate slug in unicode format according str part and random data."""
    return unicode("{slug}".format(slug=StringMethods.random_uuid()))

  @classmethod
  def generate_email(cls, domain=users.DEFAULT_EMAIL_DOMAIN):
    """Generate email in unicode format according to domain."""
    return unicode("{mail_name}@{domain}".format(
        mail_name=StringMethods.random_uuid(), domain=domain))

  @staticmethod
  def set_acl(obj, acr_name, person_list, role_id, is_add_rest_attrs,
              rewrite_acl=False):
    """Sets `access_control_list` and `acr_name` attributes, optionally
    rewrites roles in 'access_control_list'.
    """
    if not hasattr(obj, "access_control_list"):
      obj.access_control_list = []
    attrs_to_set = {
        acr_name: PeopleFactory.extract_people_emails(person_list)
    }
    if rewrite_acl:
      obj.access_control_list = [
          i for i in obj.access_control_list if i['ac_role_id'] != role_id]
    if is_add_rest_attrs:
      attrs_to_set["access_control_list"] = (
          obj.access_control_list +
          PeopleFactory.get_acl_members(role_id, person_list))
    obj.update_attrs(**attrs_to_set)


class PeopleFactory(EntitiesFactory):
  """Factory class for Persons entities."""

  def __init__(self):
    super(PeopleFactory, self).__init__(objects.PEOPLE)

  class __metaclass__(type):
    # pylint: disable=no-self-use

    @lazy_property
    def superuser(cls):
      """Return Person instance for default system superuser."""
      from lib.service import rest_service
      return rest_service.ObjectsInfoService().get_person(
          users.FAKE_SUPER_USER.email)

    @lazy_property
    def external_app_user(cls):
      """Return Person instance for default system external app user."""
      from lib.service import rest_service
      return rest_service.ObjectsInfoService().get_person(
          users.EXTERNAL_APP_USER.email)

  @staticmethod
  def extract_people_emails(people):
    """Extract values for person's email attributes."""
    return [
        person.email for person in help_utils.convert_to_list(people)
        if isinstance(person, entity.PersonEntity)]

  @staticmethod
  def get_acl_members(role_id, people):
    """Return ACL the same members as list of dicts:
    [{ac_role_id: *, person: {id: *}, ...]
    """
    def get_acl_member(role_id, person):
      """Return ACL member as dict: {ac_role_id: *, person: {id: *}."""
      if isinstance(person, entity.PersonEntity):
        return {"ac_role_id": role_id, "person": person.repr_min_dict()}
      else:
        raise ValueError(messages.CommonMessages.err_common.format(
            entity.PersonEntity, person))
    return [get_acl_member(role_id, person)
            for person in help_utils.convert_to_list(people)]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Person entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    person_obj = self.obj_inst().update_attrs(
        name=self.obj_title, email=self.generate_email(),
        system_wide_role=unicode(random.choice(roles.GLOBAL_ROLES)))
    return person_obj


class UserRolesFactory(EntitiesFactory):
  """Factory class for user roles."""

  def __init__(self):
    super(UserRolesFactory, self).__init__(objects.USER_ROLES)

  def _create_random_obj(self, is_add_rest_attrs):
    """Create user role entity."""
    return self.obj_inst()


class AccessControlRolesFactory(EntitiesFactory):
  """Factory class for ACL roles."""

  def __init__(self):
    super(AccessControlRolesFactory, self).__init__(objects.ACL_ROLES)

  def _create_random_obj(self, is_add_rest_attrs):
    """Create ACL role entity."""
    return self.obj_inst()


class CommentsFactory(EntitiesFactory):
  """Factory class for Comments entities."""

  def __init__(self):
    super(CommentsFactory, self).__init__(objects.COMMENTS)

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Comment entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    comment_obj = self.obj_inst().update_attrs(
        description=self.obj_title,
        modified_by=users.current_user().email)
    if is_add_rest_attrs:
      comment_obj.update_attrs(
          assignee_type=",".join((
              unicode(roles.PRIMARY_CONTACTS),
              unicode(roles.SECONDARY_CONTACTS))))
    return comment_obj


class CustomAttributeDefinitionsFactory(EntitiesFactory):
  """Factory class for entities."""

  def __init__(self):
    super(CustomAttributeDefinitionsFactory, self).__init__(
        objects.CUSTOM_ATTRIBUTES)

  @classmethod
  def generate_cav(cls, cad, attr_value=None):
    """Generate random CAV for CAD.
    Optionally set `attribute_value` of CAV to `attr_value`."""
    cad_type = cad.attribute_type
    attr_object = None
    attr_object_id = None
    if attr_value is None:
      if cad_type in (AdminWidgetCustomAttributes.TEXT,
                      AdminWidgetCustomAttributes.RICH_TEXT):
        attr_value = cls.generate_string(cad_type)
      if cad_type == AdminWidgetCustomAttributes.DATE:
        attr_value = datetime.datetime.today().strftime("%Y-%m-%d")
      if cad_type == AdminWidgetCustomAttributes.CHECKBOX:
        attr_value = random.choice((True, False))
      if cad_type in (AdminWidgetCustomAttributes.MULTISELECT,
                      AdminWidgetCustomAttributes.DROPDOWN):
        attr_value = unicode(
            random.choice(cad.multi_choice_options.split(",")))
    if cad_type == AdminWidgetCustomAttributes.PERSON:
      person_id = users.current_user().id
      attr_object = {"id": person_id, "type": "Person"}
      attr_object_id = person_id
      attr_value = "Person"
    return entity.CustomAttributeValueEntity(
        attribute_object=attr_object,
        attribute_object_id=attr_object_id,
        attribute_value=attr_value,
        custom_attribute_id=cad.id
    )

  @classmethod
  def generate_cavs(cls, cads):
    """Generate random CAVs for CADs."""
    return [cls.generate_cav(cad) for cad in cads]

  @classmethod
  def generate_custom_attributes(cls, cads):
    """Generate random dictionary of {cad.title: value}."""
    result_dict = {}
    for cad in cads:
      cad_type = cad.attribute_type
      if cad_type == AdminWidgetCustomAttributes.PERSON:
        attr_value = users.current_user().email
      else:
        attr_value = CustomAttributeDefinitionsFactory.generate_cav(
            cad).attribute_value
      result_dict[cad.title.upper()] = attr_value
    return result_dict

  @classmethod
  def generate_ca_title_id(cls, cads):
    """Generate dictionary of CAs from existing list of CAD objects.
    Example:
    cads = [{'attribute_type': 'Text', 'id': 1},
    {'attribute_type': 'Dropdown', 'id': 2, 'multi_choice_options': 'a,b,c'}]
    :return {"1": None, "2": None}
    """
    cas = {}
    for cad in cads:
      value = (
          None if cad.attribute_type != AdminWidgetCustomAttributes.CHECKBOX
          else False)
      cas[cad.id] = value
    return cas

  @staticmethod
  def generate_cads_for_asmt_tmpls(cads):
    """Generate list of dictionaries of CA random values from exist list CA
    definitions according to CA 'title', 'attribute_type',
    'multi_choice_options' and 'multi_choice_mandatory' for Dropdown.
    Return list of dictionaries of CA definitions that ready to use
    via REST API:
    Example:
    :return
    [{"title": "t1", "attribute_type": "Text", "multi_choice_options": "",
      "multi_choice_mandatory": ""},
     {"title":"t2", "attribute_type":"Rich Text", "multi_choice_options":"",
      "multi_choice_mandatory": ""}]
    """
    return [{k: (v if v else "") for k, v in cad.__dict__.items()
             if k in ("title", "attribute_type", "multi_choice_options",
                      "multi_choice_mandatory")}
            for cad in cads]

  def create_dashboard_ca(self, definition_type):
    """Create and return CA entity with valid filled fields for creating
    N'Dashboard'.
    """
    return self.create(
        title=self.generate_ca_title(value_aliases.DASHBOARD),
        attribute_type=AdminWidgetCustomAttributes.TEXT,
        definition_type=definition_type)

  def create(self, is_add_rest_attrs=False, **attrs):
    """Create random Custom Attribute object's instance, if
    'is_add_rest_attrs' then add attributes for REST, if 'attrs' then update
    attributes accordingly.
    """
    attrs = copy.deepcopy(attrs)
    attrs.setdefault("attribute_type",
                     random.choice(AdminWidgetCustomAttributes.ALL_CA_TYPES))
    attrs.setdefault("definition_type",
                     objects.get_singular(random.choice(objects.ALL_CA_OBJS)))
    attrs.setdefault("title",
                     self.generate_ca_title(attrs["attribute_type"]))
    if attrs["attribute_type"] in (AdminWidgetCustomAttributes.MULTISELECT,
                                   AdminWidgetCustomAttributes.DROPDOWN):
      attrs.setdefault("multi_choice_options",
                       StringMethods.random_list_strings())
    else:
      attrs["multi_choice_options"] = None
    if attrs["definition_type"] != objects.ASSESSMENTS.title():
      attrs.setdefault("mandatory", False)
    if attrs["definition_type"] in objects.ALL_SINGULAR_DISABLED_OBJS:
      attrs["id"] = attrs["external_id"] = self.generate_external_id()
      attrs["external_name"] = self.generate_string(
          attrs["definition_type"].capitalize(), attrs["attribute_type"],
          add_timestamp=True)
      attrs["external_type"] = objects.get_normal_form(
          objects.get_singular(objects.CUSTOM_ATTRIBUTES)).replace(" ", "")
    obj = self.obj_inst()
    obj.update_attrs(is_allow_none=False, **attrs)
    if is_add_rest_attrs:
      obj.modal_title = "Add Attribute to type {}".format(
          obj.definition_type.title())
    return obj

  def generate_ca_title(self, first_part):
    """Generate title of custom attribute
    (same as usual title but
    - without a star as it's disallowed, see GGRC-4954, GGRC-7024
    - replacing : with _ in the first part as map:, unmap:, delete are
    disallowed, see GGRC-5635)
    """
    chars = StringMethods.ALLOWED_CHARS.replace(string_utils.Symbols.STAR,
                                                string_utils.Symbols.BLANK)
    return self.generate_string(
        first_part.replace(':', '_'), allowed_chars=chars)


class ProgramsFactory(EntitiesFactory):
  """Factory class for Programs entities."""

  def __init__(self):
    super(ProgramsFactory, self).__init__(objects.PROGRAMS)
    self._acl_roles = [
        ("managers", roles.ACLRolesIDs.PROGRAM_MANAGERS,
         [users.current_user()]),
        ("editors", roles.ACLRolesIDs.PROGRAM_EDITORS, []),
        ("primary_contacts", roles.ACLRolesIDs.PROGRAM_PRIMARY_CONTACTS, [])
    ]

  def obj_inst(self):
    """Create program's instance and set value for attributes type, children
    and parents."""
    obj = self.obj_entity_cls().update_attrs(
        is_allow_none=False, type=self.obj_type)
    obj.parents, obj.children = [], []
    return obj

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Program entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    program_obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        review=ReviewsFactory().default_review()
    )
    program_obj.parents, program_obj.children = [], []
    if is_add_rest_attrs:
      program_obj.update_attrs(
          recipients=",".join((
              unicode(objects.get_plural(roles.PROGRAM_MANAGER, title=True)),
              unicode(objects.get_plural(roles.PROGRAM_EDITOR, title=True)),
              unicode(objects.get_plural(roles.PROGRAM_READER, title=True)),
              unicode(roles.PRIMARY_CONTACTS),
              unicode(roles.SECONDARY_CONTACTS))))
    return program_obj


class ControlsFactory(EntitiesFactory):
  """Factory class for Controls entities."""
  def __init__(self):
    super(ControlsFactory, self).__init__(objects.CONTROLS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.CONTROL_ADMINS, [users.current_user()])
    ]

  def _set_attrs(self, is_add_rest_attrs=False, **attrs):
    """Create random object's instance, if 'is_add_rest_attrs' then add
    attributes for REST, if 'attrs' then update attributes accordingly.
    """
    assertions = attrs.get("assertions", ["security"])
    obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        assertions=[entity.ControlEntity.ASSERTIONS[name]
                    for name in assertions],
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id(),
        review_status=ReviewStates.UNREVIEWED,
        review_status_display_name=ReviewStates.UNREVIEWED, **attrs)
    return obj


class ObjectivesFactory(EntitiesFactory):
  """Factory class for Objectives entities."""
  def __init__(self):
    super(ObjectivesFactory, self).__init__(objects.OBJECTIVES)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.OBJECTIVE_ADMINS, [users.current_user()])
    ]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Objective entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    objective_obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id()
    )
    if is_add_rest_attrs:
      objective_obj.update_attrs(
          recipients=",".join((
              unicode(roles.ADMIN), unicode(roles.PRIMARY_CONTACTS),
              unicode(roles.SECONDARY_CONTACTS))))
    return objective_obj


class ThreatsFactory(EntitiesFactory):
  """Factory class for Threats entities."""
  def __init__(self):
    super(ThreatsFactory, self).__init__(objects.THREATS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.THREAT_ADMINS, [users.current_user()])]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Threat entity with randomly and predictably filled fields."""
    obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id())
    return obj


class RisksFactory(EntitiesFactory):
  """Factory class for Risks entities."""

  def __init__(self):
    super(RisksFactory, self).__init__(objects.RISKS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.RISK_ADMINS, [users.current_user()])
    ]

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates Risk entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        description=self.generate_string("description"),
        risk_type=self.generate_string("risk_type"),
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id(),
        review_status=ReviewStates.UNREVIEWED,
        review_status_display_name=ReviewStates.UNREVIEWED)
    return obj


class ScopeObjectsFactory(EntitiesFactory):
  """Common factory class for Scope objects entities."""

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates Scope object entity with randomly and predictably filled
    fields."""
    return self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id())


class TechnologyEnvironmentsFactory(ScopeObjectsFactory):
  """Factory class for Technology Environments entities."""
  def __init__(self):
    super(TechnologyEnvironmentsFactory, self).__init__(
        objects.TECHNOLOGY_ENVIRONMENTS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.TECHNOLOGY_ENVIRONMENT_ADMINS,
         [users.current_user()])]


class ProductsFactory(ScopeObjectsFactory):
  """Factory class for Products entities."""
  def __init__(self):
    super(ProductsFactory, self).__init__(objects.PRODUCTS)
    self._acl_roles = [
        ("managers", roles.ACLRolesIDs.PRODUCT_MANAGERS,
         [users.current_user()])]


class ProjectsFactory(ScopeObjectsFactory):
  """Factory class for Projects entities."""
  def __init__(self):
    super(ProjectsFactory, self).__init__(objects.PROJECTS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.PROJECT_ADMINS, [users.current_user()]),
        ("assignees", roles.ACLRolesIDs.PROJECT_ASSIGNEES,
         [users.current_user()]),
        ("verifiers", roles.ACLRolesIDs.PROJECT_VERIFIERS,
         [users.current_user()])]


class KeyReportsFactory(ScopeObjectsFactory):
  """Factory class for Key Reports entities."""
  def __init__(self):
    super(KeyReportsFactory, self).__init__(objects.KEY_REPORTS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.KEY_REPORT_ADMINS,
         [users.current_user()])]


class AccessGroupsFactory(ScopeObjectsFactory):
  """Factory class for Access Groups entities."""
  def __init__(self):
    super(AccessGroupsFactory, self).__init__(objects.ACCESS_GROUPS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.ACCESS_GROUP_ADMINS,
         [users.current_user()])]


class AccountBalancesFactory(ScopeObjectsFactory):
  """Factory class for Account Balances entities."""

  def __init__(self):
    super(AccountBalancesFactory, self).__init__(objects.ACCOUNT_BALANCES)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.ACCOUNT_BALANCE_ADMINS,
         [users.current_user()])]


class DataAssetsFactory(ScopeObjectsFactory):
  """Factory class for Data Assets entities."""

  def __init__(self):
    super(DataAssetsFactory, self).__init__(objects.DATA_ASSETS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.DATA_ASSET_ADMINS,
         [users.current_user()])]


class FacilitiesFactory(ScopeObjectsFactory):
  """Factory class for Facilities entities."""

  def __init__(self):
    super(FacilitiesFactory, self).__init__(objects.FACILITIES)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.FACILITY_ADMINS, [users.current_user()])]


class MarketsFactory(ScopeObjectsFactory):
  """Factory class for Markets entities."""

  def __init__(self):
    super(MarketsFactory, self).__init__(objects.MARKETS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.MARKET_ADMINS, [users.current_user()])]


class MetricsFactory(ScopeObjectsFactory):
  """Factory class for Metrics entities."""

  def __init__(self):
    super(MetricsFactory, self).__init__(objects.METRICS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.METRIC_ADMINS, [users.current_user()])]


class ProcessesFactory(ScopeObjectsFactory):
  """Factory class for Processes entities."""

  def __init__(self):
    super(ProcessesFactory, self).__init__(objects.PROCESSES)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.PROCESS_ADMINS, [users.current_user()])]


class ProductGroupsFactory(ScopeObjectsFactory):
  """Factory class for Products Groups entities."""
  def __init__(self):
    super(ProductGroupsFactory, self).__init__(objects.PRODUCT_GROUPS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.PRODUCT_GROUP_ADMINS,
         [users.current_user()])]


class SystemsFactory(ScopeObjectsFactory):
  """Factory class for Systems entities."""
  def __init__(self):
    super(SystemsFactory, self).__init__(objects.SYSTEMS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.SYSTEM_ADMINS, [users.current_user()])]


class VendorsFactory(ScopeObjectsFactory):
  """Factory class for Vendors entities."""
  def __init__(self):
    super(VendorsFactory, self).__init__(objects.VENDORS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.VENDOR_ADMINS, [users.current_user()])]


class OrgGroupsFactory(ScopeObjectsFactory):
  """Factory class for Org Groups entities."""

  def __init__(self):
    super(OrgGroupsFactory, self).__init__(objects.ORG_GROUPS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.ORG_GROUPS_ADMINS, [users.current_user()])
    ]


class AuditsFactory(EntitiesFactory):
  """Factory class for Audit entity."""
  def __init__(self):
    super(AuditsFactory, self).__init__(objects.AUDITS)
    self._acl_roles = [
        ("audit_captains", roles.ACLRolesIDs.AUDIT_CAPTAINS,
         [users.current_user()]),
        ("auditors", roles.ACLRolesIDs.AUDITORS, [])
    ]

  @staticmethod
  def clone(audit, count_to_clone=1):
    """Clone Audit entity (count depends on 'count_to_clone')
    and set attributes' values related to parallelization to None, title will
    be predicted.
    """
    # pylint: disable=anomalous-backslash-in-string
    return [copy.deepcopy(audit).update_attrs(
        title=unicode(audit.title + " - copy " + str(num)), slug=None,
        created_at=None, updated_at=None, href=None, url=None, id=None)
        for num in xrange(1, count_to_clone + 1)]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Audit entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    audit_obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.PLANNED))
    return audit_obj


class AssessmentTemplatesFactory(EntitiesFactory):
  """Factory class for Assessment Templates entities."""

  def __init__(self):
    super(AssessmentTemplatesFactory, self).__init__(
        objects.ASSESSMENT_TEMPLATES)

  @staticmethod
  def clone(asmt_tmpl, count_to_clone=1):
    """Clone Assessment Template entity (count depends on 'count_to_clone')
    and set attributes' values related to parallelization to None.
    """
    return [copy.deepcopy(asmt_tmpl).update_attrs(
        slug=None, updated_at=None, href=None, url=None, id=None)
        for _ in xrange(1, count_to_clone + 1)]

  @staticmethod
  def generate_cad(**attrs):
    """Generates CAD for asmt template."""
    is_dropdown = (attrs["cad_type"] == AdminWidgetCustomAttributes.DROPDOWN)
    if is_dropdown and "dropdown_types_list" in attrs:
      asmt_tmpl_factory = AsmtTemplateWithDropdownFactory()
    else:
      asmt_tmpl_factory = AsmtTemplateWithAttrFactory()
    return asmt_tmpl_factory.generate_cad(**attrs)

  def _set_attrs(self, is_add_rest_attrs=False, **attrs):
    """Creates random object's instance, if 'is_add_rest_attrs' then add
    attributes for REST, if 'attrs' then update attributes accordingly.
    """
    attrs = copy.deepcopy(attrs)
    attrs.setdefault("title", self.obj_title)
    attrs.setdefault("status", object_states.DRAFT)
    attrs.setdefault("template_object_type", "Control")
    default_people = {"assignees": roles.PRINCIPAL_ASSIGNEES,
                      "verifiers": roles.AUDITORS}
    for acr_name in default_people:
      person_list = attrs.get(acr_name, default_people[acr_name])
      if isinstance(person_list, list):
        default_people[acr_name] = [person.id for person in person_list]
        person_list = PeopleFactory.extract_people_emails(person_list)
      else:
        default_people[acr_name] = person_list
      attrs.setdefault(acr_name, person_list)
    obj = self.obj_inst()
    obj.update_attrs(is_allow_none=False, **attrs)
    if is_add_rest_attrs:
      obj.update_attrs(default_people=default_people)
    return obj


class AsmtTemplateWithDropdownFactory(AssessmentTemplatesFactory):
  """Class for assesment template with Dropdown option."""

  @classmethod
  def generate_cad(cls, **attrs):
    """Creates multi-choice dropdown CAD for asmt template."""
    multi_choice_opts = {"file": "2", "url": "4", "comment": "1",
                         "file_url": "6", "url_comment": "5",
                         "file_comment": "3", "file_url_comment": "7",
                         "nothing": "0"}
    dropdown_types_list = attrs["dropdown_types_list"]
    cad_factory = CustomAttributeDefinitionsFactory()
    cad = cad_factory.create(
        attribute_type=AdminWidgetCustomAttributes.DROPDOWN,
        definition_type="",
        multi_choice_mandatory=(",".join(
            multi_choice_opts[dropdown_type]
            for dropdown_type in dropdown_types_list)),
        multi_choice_options=(
            StringMethods.random_list_strings(
                list_len=len(dropdown_types_list))))
    return cad_factory.generate_cads_for_asmt_tmpls([cad])[0]


class AsmtTemplateWithAttrFactory(AssessmentTemplatesFactory):
  """Class for assesment template with text option."""

  @classmethod
  def generate_cad(cls, **attrs):
    """Creates CAD for asmt template."""
    cad_factory = CustomAttributeDefinitionsFactory()
    cad = cad_factory.create(attribute_type=attrs["cad_type"])
    return cad_factory.generate_cads_for_asmt_tmpls([cad])[0]


class AssessmentsFactory(EntitiesFactory):
  """Factory class for Assessments entities."""

  def __init__(self):
    super(AssessmentsFactory, self).__init__(objects.ASSESSMENTS)
    self.admins = [users.current_user()]
    self._acl_roles = [
        ("creators", roles.ACLRolesIDs.ASSESSMENT_CREATORS,
         [users.current_user()]),
        ("assignees", roles.ACLRolesIDs.ASSESSMENT_ASSIGNEES,
         [users.current_user()]),
        ("verifiers", roles.ACLRolesIDs.ASSESSMENT_VERIFIERS, [])
    ]

  def obj_inst(self):
    """Create Assessment object's instance and set values for attributes:
    type, verified, status.
    """
    return self.obj_entity_cls().update_attrs(
        is_allow_none=False, type=self.obj_type, verified=False,
        status=unicode(object_states.NOT_STARTED))

  def generate(self, mapped_objects, audit, asmt_tmpl=None):
    """Generate Assessment objects' instances under 'audit' based on info
    about 'mapped_objects' and 'asmt_tmpl' use generation logic accordingly.
    """
    mapped_objects = help_utils.convert_to_list(mapped_objects)
    asmts_cas_def = getattr(asmt_tmpl, "custom_attribute_definitions", None)
    asmts_type = (
        mapped_objects[0].type
        if all(getattr(mapped_obj, "type") for mapped_obj in mapped_objects)
        else None)
    if asmt_tmpl:
      if asmts_type != asmt_tmpl.template_object_type:
        raise ValueError(
            "Mapped objects' type: {} have to be the same with Assessment "
            "Template's type: {}".format(
                asmts_type, asmt_tmpl.template_object_type))
    asmts_objs = []
    for mapped_object in mapped_objects:
      asmt = self.obj_inst().update_attrs(
          title=mapped_object.title + " assessment for " + audit.title,
          audit=audit.title, mapped_objects=[mapped_object],
          assessment_type=asmts_type,
          custom_attribute_definitions=asmts_cas_def,
          **self.acl_roles_from_template(audit, asmt_tmpl, mapped_object))
      asmts_objs.append(asmt)
    return asmts_objs

  def acl_roles_from_template(self, audit, template, snapshot):
    """Returns dict with roles as keys and assigned users as values according
    to template settings."""
    acl = {"creators": PeopleFactory.extract_people_emails(self.admins),
           "verifiers": None, "assignees": None}
    asmt_template_roles_mapping = {
        element.CommonAudit.AUDIT_CAPTAIN: audit.audit_captains,
        roles.AUDITORS: audit.auditors,
        roles.PRINCIPAL_ASSIGNEES: snapshot.principal_assignees}
    # handle other roles if needed
    if template:
      for role in ("assignees", "verifiers"):
        people = getattr(template, role)
        if people in asmt_template_roles_mapping.keys():
          people = asmt_template_roles_mapping[people]
        acl[role] = people
    if not acl["assignees"]:
      acl["assignees"] = audit.audit_captains
    return acl

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Assessment entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    asmt_obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.NOT_STARTED),
        assessment_type=objects.get_obj_type(objects.CONTROLS), verified=False)
    if is_add_rest_attrs:
      asmt_obj.update_attrs(
          recipients=",".join((
              unicode(roles.ASSIGNEES), unicode(roles.CREATORS),
              unicode(roles.VERIFIERS))))
    return asmt_obj


class IssuesFactory(EntitiesFactory):
  """Factory class for Issues entities."""

  def __init__(self):
    super(IssuesFactory, self).__init__(objects.ISSUES)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.ISSUE_ADMINS, [users.current_user()])
    ]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Issue entity with randomly and predictably filled fields, if
    'is_add_rest_attrs' then add attributes for REST."""
    issue_obj = self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        due_date=date_utils.first_working_day_after_today())
    if is_add_rest_attrs:
      issue_obj.update_attrs(
          recipients=",".join((
              unicode(roles.ADMIN), unicode(roles.PRIMARY_CONTACTS),
              unicode(roles.SECONDARY_CONTACTS))))
    return issue_obj


class ProposalsFactory(EntitiesFactory):
  """Factory class for Proposals entities."""

  def __init__(self):
    super(ProposalsFactory, self).__init__(objects.PROPOSALS)

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Proposal entity."""
    return self.obj_inst().update_attrs(
        is_allow_none=False, author=users.current_user().email,
        status=unicode(object_states.PROPOSED))


class ReviewsFactory(EntitiesFactory):
  """Factory class for Review entities."""

  def __init__(self):
    super(ReviewsFactory, self).__init__(objects.REVIEWS)
    self._acl_roles = [("reviewers", roles.ACLRolesIDs.REVIEWERS, [])]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Review entity."""
    return self.obj_inst().update_attrs(
        status=unicode(ReviewStates.UNREVIEWED),
        type=self.obj_type)

  def default_review(self):
    """Returns default review value as dict."""
    return self.create().convert_review_to_dict()


class DirectivesFactory(EntitiesFactory):
  """Common factory class for Directive objects entities."""

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates Directive entity."""
    return self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT))


class StandardsFactory(DirectivesFactory):
  """Factory class for Standard entities."""

  def __init__(self):
    super(StandardsFactory, self).__init__(objects.STANDARDS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.STANDARD_ADMINS, [users.current_user()])]


class RegulationsFactory(DirectivesFactory):
  """Factory class for regulations."""

  def __init__(self):
    super(RegulationsFactory, self).__init__(objects.REGULATIONS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.REGULATION_ADMINS,
         [users.current_user()])]


class RequirementsFactory(DirectivesFactory):
  """Factory class for requirements."""

  def __init__(self):
    super(RequirementsFactory, self).__init__(objects.REQUIREMENTS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.REQUIREMENT_ADMINS,
         [users.current_user()])]

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates Requirement object entity."""
    return self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id())


class PoliciesFactory(DirectivesFactory):
  """Factory class for policies."""

  def __init__(self):
    super(PoliciesFactory, self).__init__(objects.POLICIES)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.POLICY_ADMINS, [users.current_user()])]

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates Policy object entity."""
    return self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id())


class ContractsFactory(DirectivesFactory):
  """Factory class for contracts."""

  def __init__(self):
    super(ContractsFactory, self).__init__(objects.CONTRACTS)
    self._acl_roles = [
        ("admins", roles.ACLRolesIDs.CONTRACT_ADMINS, [users.current_user()])]

  def _create_random_obj(self, is_add_rest_attrs):
    """Creates Contract object entity."""
    return self.obj_inst().update_attrs(
        title=self.obj_title,
        status=unicode(object_states.DRAFT),
        external_slug=self.generate_slug(),
        external_id=self.generate_external_id())


class EvidenceFactory(EntitiesFactory):
  """Factory class for Evidence entities."""

  def __init__(self):
    super(EvidenceFactory, self).__init__(objects.EVIDENCE)
    self._acl_roles = [("admins", roles.ACLRolesIDs.EVIDENCE_ADMINS,
                        [users.current_user()])]

  def _create_random_obj(self, is_add_rest_attrs):
    """Create Evidence URL entity with randomly and predictably filled fields,
    if 'is_add_rest_attrs' then add attributes for REST."""
    return self.obj_inst().update_attrs(
        title=self.obj_title, link=self.obj_title, kind="URL")


class ChangeLogItemsFactory(EntitiesFactory):
  """Factory class for ChangeLogItem entities."""

  def __init__(self):
    super(ChangeLogItemsFactory, self).__init__(objects.CHANGE_LOG_ITEMS)

  _attrs_to_exclude_from_log = (
      "tree_view_attrs_to_exclude", "people_attrs_names",
      "custom_attribute_definitions", "access_control_list", "url",
      "type", "selfLink", "review_status_display_name", "id", "href",
      "external_slug", "external_id", "modified_by", "audit",
      "bulk_update_modal_tree_view_attrs_to_exclude", "context", "kind",
      "review")

  def _generate_creation_entry_dict(self, obj):
    """Returns dict of obj's attributes that is expected to be displayed
    in change log entry related to obj creation."""
    displayed_attrs = {}
    for attr_name, attr_value in entity.Representation.repr_obj_to_dict(
            obj).iteritems():
      if attr_name not in self._attrs_to_exclude_from_log and attr_value:
        if isinstance(attr_value, list):
          displayed_attrs.update({attr_name: ", ".join(attr_value)})
        elif attr_name in ["created_at", "updated_at"]:
          displayed_attrs.update(
              {attr_name: date_utils.iso8601_to_ui_str_date(attr_value)})
        elif attr_name == element.CommonAssessment.RECIPIENTS.lower():
          # 'recipients' need to be sorted as their order is different in
          # object from rest and its UI representation
          displayed_attrs.update(
              {attr_name: ", ".join(sorted(attr_value.split(",")))})
        elif attr_name == "custom_attributes" and isinstance(attr_value, dict):
          displayed_attrs.update(
              {ca_name: ca_val for ca_name, ca_val in attr_value.iteritems()
               if ca_val})
        else:
          displayed_attrs.update({attr_name: attr_value})
    return displayed_attrs

  def generate_obj_creation_entity(self, obj):
    """Create and return expected ChangeLogItemEntity instance for newly
    created object according to its attributes."""
    expected_changes = []
    for attr_name, attr_value in (self._generate_creation_entry_dict(
                                  obj).iteritems()):
      expected_changes.append({"attribute_name": attr_name,
                               "original_value": None,
                               "new_value": attr_value})
    return self.obj_inst().update_attrs(author=users.current_user().email,
                                        changes=sorted(expected_changes))

  def generate_log_entity_for_mapping(self, source_obj):
    """Create and return expected ChangeLogItem entity for object mapping to
    source object."""
    return self.obj_inst().update_attrs(
        author=users.current_user().email,
        changes=[{
            "attribute_name": str_formats.CHANGE_LOG_MAPPING_MSG.format(
                obj_name=source_obj.type,
                obj_title=source_obj.title),
            "original_value": None,
            "new_value": value_aliases.CREATED}])

  def generate_log_entity_for_automapping(self, src_obj, mapped_obj,
                                          automapped_obj, user):
    """Create and return expected ChangeLogItem entity which describes
    automapping of automapped_obj to src_obj after mapping of mapped_obj to
    src_obj."""
    return self.obj_inst().update_attrs(
        author=roles.SYSTEM,
        changes=[{
            "attribute_name": str_formats.CHANGE_LOG_MAPPING_MSG.format(
                obj_name=automapped_obj.type,
                obj_title=automapped_obj.title),
            "original_value": None,
            "new_value": value_aliases.CREATED}],
        additional_info=str_formats.CHANGE_LOG_AUTOMAPPING_MSG.format(
            user_name=user.email,
            src_obj_name=src_obj.type,
            src_obj_title=src_obj.title,
            mapped_obj_name=mapped_obj.type,
            mapped_obj_title=mapped_obj.title))
