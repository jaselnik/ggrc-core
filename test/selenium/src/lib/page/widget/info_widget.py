# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Info widgets."""
# pylint: disable=useless-super-delegation
# pylint: disable=too-many-lines

import re
import time

import inflection

from lib import base
from lib.app_entity_factory import entity_factory_common
from lib.constants import (
    locator, objects, element, roles, regex, messages)
from lib.element import (
    info_widget_three_bbs, page_elements, tables, tab_element)
from lib.page.modal import (
    apply_decline_proposal, set_value_for_asmt_ca, snapshoted_controls_info)
from lib.page.widget import info_panel, object_modal, object_page, page_mixins
from lib.utils import selenium_utils, help_utils, ui_utils


class ReadOnlyInfoWidget(page_mixins.WithPageElements, base.Widget,
                         object_page.ObjectPage):
  """Common class for disabled object's Info pages and Info panels
  which don't have edit elements."""
  # pylint: disable=too-many-instance-attributes
  # pylint: disable=too-many-public-methods
  _elements = element.Common
  _dropdown_settings_cls = info_widget_three_bbs.InfoWidgetThreeBbbs
  locator_headers_and_values = None
  _reference_url_label = "Reference URL"
  _evidence_url_label = "Evidence URL"

  def __init__(self, _driver=None):
    super(ReadOnlyInfoWidget, self).__init__()
    self.child_cls_name = self.__class__.__name__
    self.obj_name = objects.get_singular(self.child_cls_name)
    self.list_all_headers_txt = []
    self.list_all_values_txt = []
    self.inline_edit_controls = self._browser.elements(
        class_name="set-editable-group")
    self.tabs = tab_element.Tabs(self._browser, tab_element.Tabs.INTERNAL)
    self._attributes_tab_name = "Attributes"
    self._changelog_tab_name = "Change Log"
    # for overridable methods
    if self.__class__ in [Controls, Risks]:
      if self.is_info_page:
        self.tabs.ensure_tab(self._attributes_tab_name)

  @property
  def _root(self):
    """Returns root element (including title, 3bbs)."""
    if self.is_info_page:
      return self._browser.element(class_name="widget", id="info")
    return self._browser.element(class_name="sticky-info-panel")

  @property
  def _active_tab_root(self):
    """Returns a wrapper el for active internal tab."""
    return self._root.element(class_name=["tab-pane", "active"])

  @property
  def panel(self):
    """Returns info panel."""
    if self.is_snapshot_panel:
      return info_panel.SnapshotInfoPanel(self._root)
    return info_panel.InfoPanel(self._root)

  @property
  def is_info_page(self):
    """Returns whether the page is info page."""
    return (self.get_current_url_fragment() == self._url_fragment() and
            not apply_decline_proposal.CompareApplyDeclineModal().modal.exists)

  @property
  def is_snapshot_panel(self):
    """Returns whether this page object represents snapshot Info Panel."""
    return info_panel.SnapshotInfoPanel(self._root).snapshot_version_el.present

  @staticmethod
  def _url_fragment():
    """See superclass."""
    return "info"

  def title(self):
    """Returns object title."""
    return self._root.element(class_name="pane-header__title").h3().text

  @property
  def status_label(self):
    """Returns object's status label element."""
    return page_elements.StatusLabel(
        self._root.element(class_name=re.compile("state-value state")),
        with_inline_edit=(inflection.underscore(self.child_cls_name)
                          in objects.ALL_DISABLED_OBJECTS))

  def status(self):
    """Returns object status."""
    return self.status_label.text_content

  def code(self):
    """Returns code."""
    return self._simple_field("Code").text

  def created_at(self):
    """Return created date as shown in UI."""
    return self._extract_text_from_footer(1)

  def modified_by(self):
    """Return user that updated the object last."""
    return self._extract_text_from_footer(2)

  def updated_at(self):
    """Return last updated date."""
    return self._extract_text_from_footer(3)

  def _extract_text_from_footer(self, group_idx):
    """Returns some text part from footer."""
    footer_regexp = r"Created date (.+)   {4}Last updated by\n(.+)\non (.+)"
    footer_el = self._browser.element(class_name="info-widget-footer")
    footer_el.element(class_name="person-name").wait_until(lambda e: e.present)
    return re.search(footer_regexp, footer_el.text).group(group_idx)

  def show_related_assessments(self):
    """Click `Assessments` button on control or objective page and return
    related asmts table.
    """
    self._browser.link(title="Show Related Assessments").click()
    table_element = self._driver.find_element(
        *locator.ModalRelatedAssessments.MODAL)
    return tables.AssessmentRelatedAsmtsTable(self._driver, table_element)

  @property
  def three_bbs(self):
    """Returns info widget three bbs element."""
    return self._dropdown_settings_cls(self._root)

  def get_header_and_value_txt_from_people_scopes(self, header_text):
    """Get with controlling header and value text from people's scopes elements
    according to header text.

    Example:
    'header_text' = 'ASSIGNEE(S)', return: ['ASSIGNEE(S)', 'user@example.com']
    """
    # pylint: disable=invalid-name
    # pylint: disable=expression-not-assigned
    _header_msg, _value_msg = (
        "people header: {}, count: {}", "people list: {}, count: {}")
    people_scopes = self._active_tab_root.locate().elements(
        class_name="editable-people-group")
    matched_people_scopes = [people_scope for people_scope in people_scopes
                             if header_text in people_scope.text]
    if len(matched_people_scopes) != 1:
      raise ValueError(
          messages.ExceptionsMessages.err_results_are_different.format(
              _header_msg.format(header_text, "1"),
              _value_msg.format(
                  [matched_people_scope.text
                   for matched_people_scope in matched_people_scopes],
                  len(matched_people_scopes))))
    people_scope = matched_people_scopes[0]
    _people_header = people_scope.element(
        tag_name="editable-people-group-header").text
    _people_value = people_scope.element(
        tag_name="object-list").text
    _people_header_parts = _people_header.splitlines()
    people_header_txt = _people_header_parts[0]
    people_count_from_header = (
        int(re.search(regex.TEXT_WO_PARENTHESES,
                      _people_header_parts[1]).group(1)))
    # filter: "\nuser@example.com\n(Inactive user)" to 'user@example.com'
    people_value_txt = [person for person in _people_value.splitlines()
                        if person != roles.NO_ROLE_UI]
    # if counters are same or None
    if not ((people_count_from_header == len(people_value_txt)) or
       (people_count_from_header == 0 and people_value_txt == ["None"])):
      raise ValueError(
          messages.ExceptionsMessages.err_counters_are_different.format(
              _header_msg.format(
                  _people_header_parts, str(people_count_from_header)),
              _value_msg.format(people_value_txt, len(people_value_txt))))
    return (people_header_txt,
            None if people_value_txt == ["None"] else people_value_txt)

  def description(self):
    """Returns the text of description."""
    return self._simple_field("Description", self._root).text

  @property
  def admins(self):
    """Returns Admin page element."""
    return self._related_people_list("Admin", self._root)

  @property
  def primary_contacts(self):
    """Returns Primary Contacts page element"""
    return self._related_people_list("Primary Contacts", self._root)

  def global_custom_attributes(self):
    """Returns GCA values."""
    return self.get_custom_attributes()

  def get_custom_attributes(self, is_gcas_not_lcas=True):
    """Get text of all CAs headers and values and convert it to dictionary.
    If 'is_gcas_not_lcas' then get GCAs, if not 'is_gcas_not_lcas'
    then get LCAs.
    Example:
    :return {'ca_header1': 'ca_value1', 'ca_header2': 'ca_value2', ...}
    """
    custom_attributes = {}
    ca_manager = page_elements.CustomAttributeManager(
        self._root,
        obj_type=self.child_cls_name.lower(),
        is_global=is_gcas_not_lcas,
        is_inline=True)
    all_ca_titles = ca_manager.all_ca_titles()
    for ca_title in all_ca_titles:
      ca_elem = ca_manager.find_ca_elem_by_title(ca_title)
      custom_attributes[ca_title] = ca_elem.get_value()
    return custom_attributes

  def has_ca_inline_edit(self, attr_title):
    """Tries to open edit form for CA by its title
    and returns bool if edit exists."""
    ca_manager = page_elements.CustomAttributeManager(
        self._browser,
        obj_type=self.child_cls_name.lower(),
        is_global=True,
        is_inline=True)
    return ca_manager.find_ca_elem_by_title(
        attr_title).open_edit().is_inline_edit_opened

  def obj_scope(self):
    """Returns dict of object."""
    scope = {
        "description": self.description(),
        "custom_attributes": self.global_custom_attributes(),
        "url": self.get_url(),
        "id": self.get_obj_id(),
        "code": self.code(),
        "state": self.status(),
        "title": self.title()
    }
    if self.is_comments_panel_present and self.obj_name != "control":
      scope["comments"] = self.comments_panel.scopes
    if self.is_info_page:
      scope.update(
          created_at=self.created_at(),
          last_updated_by=self.modified_by(),
          updated_at=self.updated_at()
      )
    if self.has_review():
      scope.update(review_status=self.review_status,
                   review_status_display_name=self.review_status,
                   review=self.get_review_dict())
    self.update_obj_scope(scope)
    return scope

  def update_obj_scope(self, scope):
    """Updates obj scope. May be overridden in the child class."""
    pass

  def get_info_widget_obj_scope(self):
    """Get dict from object (text scope) which displayed on info page or
    info panel according to list of headers text and list of values text.
    """
    obj_scope = self.obj_scope()
    obj_scope.update(zip(self.list_all_headers_txt, self.list_all_values_txt))
    return obj_scope

  def _extend_list_all_scopes(self, headers, values):
    """Extend 'list all scopes' by headers' text and values' text."""
    self.list_all_headers_txt.extend(help_utils.convert_to_list(headers))
    self.list_all_values_txt.extend(help_utils.convert_to_list(values))

  @property
  def comments_panel(self):
    """Returns comments panel."""
    return base.ReadOnlyCommentsPanel(
        self._browser.element(tag_name="comment-data-provider"))

  @property
  def is_comments_panel_present(self):
    """Returns whether comments panel exists on the page."""
    return self.comments_panel.is_present

  @property
  def role_to_edit(self):
    """Returns a role for trying to edit."""
    return self._related_people_list(roles.PRIMARY_CONTACTS, self._root)

  @property
  def predefined_field(self):
    """Returns description element as a predefined field for object."""
    return page_elements.SimpleField(
        self._root, element.Common.DESCRIPTION, with_inline_edit=True)

  @property
  def permalink_floating_message(self):
    """Represents floating message about permalink copying to clipboard."""
    return self._browser.element(
        text="Link has been copied to your clipboard.")


class InfoWidget(page_mixins.WithObjectReview, ReadOnlyInfoWidget):
  """Common class for active object's Info pages and Info panels."""
  # pylint: disable=too-many-public-methods
  # pylint: disable=too-many-instance-attributes
  # pylint: disable=protected-access

  def __init__(self, _driver=None):
    super(InfoWidget, self).__init__()
    # for overridable methods
    if (self.__class__ in
        [Programs, Regulations, Objectives, Contracts, Policies, Standards,
         Threats, Requirements]):
      if self.is_info_page:
        self.tabs.ensure_tab(self._attributes_tab_name)
    self.inline_edit_controls = self._browser.elements(
        class_name="set-editable-group")
    self.edit_popup = object_modal.get_modal_obj(self.obj_name, self._driver)

  @staticmethod
  def wait_save():
    """Wait for object to be saved and page to be updated.
    Please note that in some cases spinner disappears before DOM changes
    are fully finished. So this code may need to be changed
    in case of a race condition.
    """
    ui_utils.wait_for_spinner_to_disappear()

  def fill_global_cas_in_popup(self, custom_attributes):
    """Fills GCAs using Edit popup."""
    self.three_bbs.select_edit()
    self.fill_ca_values(custom_attributes, is_global=True, is_inline=False)

  def fill_global_cas_inline(self, custom_attributes):
    """Fills GCAs inline."""
    self.fill_ca_values(custom_attributes, is_global=True, is_inline=True)

  def fill_ca_values(self, custom_attributes, is_global, is_inline):
    """Fills custom attributes with values."""
    ca_manager = page_elements.CustomAttributeManager(
        self._browser,
        obj_type=self.child_cls_name.lower(),
        is_global=is_global,
        is_inline=is_inline)
    for attr_title, attr_value in custom_attributes.iteritems():
      elem_class = ca_manager.find_ca_elem_by_title(attr_title)
      elem_class.set_value(attr_value)
      if is_inline:
        self.wait_save()
    if not is_inline:
      self.edit_popup.save_and_close()

  def edit_obj(self, **changes):
    """Makes changes `changes` to object."""
    self.three_bbs.select_edit()
    modal = object_modal.get_modal_obj(self.obj_name)
    modal.fill_form(**changes)
    modal.save_and_close()

  def delete_obj(self):
    """Deletes object."""
    self.three_bbs.select_delete().confirm_delete()

  @property
  def comments_panel(self):
    """Returns comments panel."""
    return base.CommentsPanel(
        self._browser.element(tag_name="comment-data-provider"))


class Programs(InfoWidget, page_mixins.WithProposals):
  """Model for program object Info pages and Info panels."""
  # pylint: disable=too-many-instance-attributes
  _elements = element.ProgramInfoWidget
  CHILD_PROGRAMS_TAB_NAME = 'Programs (Child)'
  PARENT_PROGRAMS_TAB_NAME = 'Programs (Parent)'

  def __init__(self, driver=None):
    super(Programs, self).__init__(driver)
    self.manager, self.manager_entered = (
        self.get_header_and_value_txt_from_people_scopes(
            self._elements.PROGRAM_MANAGERS.upper()))
    self._extend_list_all_scopes(
        self.manager, self.manager_entered)
    self.reference_urls = self._related_urls(self._reference_url_label)

  @property
  def mega_program_icon(self):
    return self._root.element(class_name='fa-bookmark')

  def description(self):
    """Returns the text of description."""
    return self._editable_simple_field("Description", self._root).text

  def els_shown_for_editor(self):
    """Elements shown for user with edit permissions"""
    return [self.request_review_btn,
            self.three_bbs.edit_option,
            self.comments_panel.add_btn,
            self.reference_urls.add_button] + list(self.inline_edit_controls)

  @property
  def program_editors(self):
    """Returns Program Editors page element."""
    return self._related_people_list(roles.PROGRAM_EDITORS, self._root)

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(primary_contacts=self.primary_contacts.get_people_emails(),
                 editors=self.program_editors.get_people_emails())


class Workflows(InfoWidget):
  """Model for Workflow object Info pages and Info panels."""
  _dropdown_settings_cls = info_widget_three_bbs.WorkflowInfoWidgetThreeBbbs

  def __init__(self, _driver=None):
    super(Workflows, self).__init__()

  def _extend_list_all_scopes_by_review_state(self):
    """Method overriding without action due to Workflows don't have
    'review states'.
    """
    # pylint: disable=invalid-name
    pass

  def obj_scope(self):
    """Returns obj scope."""
    return {
        "obj_id": self.get_obj_id(),
        "title": self.title(),
        "state": self.status(),
        "is_archived": self.is_archived,
        "description": self.description(),
        "admins": self.admins.get_people_emails(),
        "workflow_members": self.workflow_members.get_people_emails(),
        "code": self.code(),
        "created_at": self.created_at(),
        "modified_by": self.modified_by(),
        "updated_at": self.updated_at(),
        "repeat_workflow": self.repeat_workflow
    }

  @property
  def is_archived(self):
    """Returns whether workflow is archived."""
    return self._browser.element(class_name="state-archived").present

  def archive(self):
    """Archives the workflow."""
    self.three_bbs.select_archive()
    selenium_utils.wait_for_js_to_load(self._driver)

  @property
  def workflow_members(self):
    """Returns Workflow Members page element."""
    return self._related_people_list("Workflow Member")

  @property
  def repeat_workflow(self):
    """Returns repeat workflow."""
    return self._simple_field("Repeat Workflow", self._root).text


class CycleTasks(InfoWidget):
  """Model for CycleTask object Info panel."""
  def obj_scope(self):
    """Returns obj scope."""
    return {
        "title": self.title(),
        "state": self.status(),
        "assignees": self.assignees.get_people_emails(),
        "due_date": self.due_date,
        "comments": self.comments_panel.scopes
    }

  def wait_to_be_init(self):
    """Waits for page object to be initialized."""
    # Element with class `nav-tabs` appears in DOM at start of panel rendering.
    # But a class "tab-container_hidden-tabs" that makes it "display: none"
    #   is removed only at end.
    self._root.element(class_name="nav-tabs").wait_until(lambda e: e.present)

  @property
  def due_date(self):
    """Returns Task Due Date."""
    return self._simple_field("Task Due date").text

  def click_map_objs(self):
    """Clicks `Map Objects` button."""
    self._browser.link(text="Map Objects").click()

  def mapped_objs(self):
    """Returns objects mapped to the cycle task."""
    # HACK: it's not possible to determine by looking at DOM whether
    #   the list of mapped objects was fully loaded or not.
    time.sleep(1)
    objs = []
    row_els = self._browser.element(text="Mapped objects").next_sibling().lis()
    for obj_row in row_els:
      # link to the obj is for example 'http://localhost:8080/controls/1'
      # last number is obj id
      obj_id = int(obj_row.link().href.split("/")[-1])
      entity_obj_name = objects.get_singular(
          obj_row.link().href.split("/")[-2])
      obj_title = obj_row.text
      factory = entity_factory_common.get_factory_by_obj_name(
          entity_obj_name)()
      objs.append(factory.create_empty(obj_id=obj_id, title=obj_title))
    return objs

  @property
  def assignees(self):
    """Returns Task Assignees page element."""
    return self._related_people_list("Task Assignees")


class Audits(page_mixins.WithAssignFolder, InfoWidget):
  """Model for Audit object Info pages and Info panels."""
  # pylint: disable=too-many-instance-attributes
  _elements = element.AuditInfoWidget
  _dropdown_settings_cls = info_widget_three_bbs.AuditInfoWidgetThreeBbbs

  def __init__(self, driver):
    super(Audits, self).__init__(driver)
    self.audit_captain_lbl_txt, self.audit_captain_txt = (
        self.get_header_and_value_txt_from_people_scopes(
            self._elements.AUDIT_CAPTAINS.upper()))
    self.auditor_lbl_txt, self.auditor_txt = (
        self.get_header_and_value_txt_from_people_scopes(
            self._elements.AUDITORS.upper()))
    self._extend_list_all_scopes(
        [self.audit_captain_lbl_txt, self.auditor_lbl_txt],
        [self.audit_captain_txt, self.auditor_txt])
    self.evidence_urls = self._related_urls(self._evidence_url_label)

  def _extend_list_all_scopes_by_review_state(self):
    """Method overriding without action due to Audits don't have
    'review states'.
    """
    # pylint: disable=invalid-name
    pass

  def els_shown_for_editor(self):
    """Elements shown for user with edit permissions"""
    return [self.evidence_urls.add_button,
            self.assign_folder_button] + list(self.inline_edit_controls)


class Assessments(InfoWidget):
  """Model for Assessment object Info pages and Info panels."""
  # pylint: disable=invalid-name
  # pylint: disable=too-many-instance-attributes
  # pylint: disable=too-many-public-methods
  _elements = element.AssessmentInfoWidget
  _dropdown_settings_cls = info_widget_three_bbs.AssessmentInfoWidgetThreeBbbs

  def __init__(self, driver):
    super(Assessments, self).__init__(driver)
    self._assessment_tab_name = "Assessment"
    self._related_assessments_tab_name = "Related Assessments"
    self._related_issues_tab_name = "Related Issues"
    self._other_attributes_tab_name = "Other Attributes"

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(
        is_verified=self.is_verified,
        assessment_type=self.assessment_type,
        evidence_urls=self.evidence_urls.get_urls(),
        creators=self.creators.get_people_emails(),
        assignees=self.assignees.get_people_emails(),
        verifiers=self.verifiers.get_people_emails(),
        custom_attributes=self.custom_attributes(),
        primary_contacts=self.primary_contacts.get_people_emails(),
        mapped_objects=self.mapped_objects_titles()
    )

  @property
  def verify_icon(self):
    """Returns verify icon element."""
    return self._browser.element(class_name="verified-icon")

  @property
  def is_verified(self):
    """Returns whether assessment is verified (has verified icon)."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return self.verify_icon.exists

  @property
  def assessment_type(self):
    """Returns Assessment type."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return objects.get_singular(self._browser.element(
        class_name="action-toolbar__content-item").text, title=True)

  @property
  def evidence_urls(self):
    """Switch to tab with evidence urls and return a page element"""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return self._assessment_evidence_urls()

  @property
  def creators(self):
    """Switch to tab with creators and return a page element."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return self._related_people_list("Creators")

  @property
  def assignees(self):
    """Switch to tab with assignees and return a page element."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return self._related_people_list("Assignees")

  @property
  def verifiers(self):
    """Switch to tab with verifiers and return a page element."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return self._related_people_list("Verifiers")

  @property
  def comments_panel(self):
    """Returns comments panel."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return base.CommentsPanel(
        self._browser.element(class_name="assessment-comments"))

  @property
  def is_comments_panel_present(self):
    """Returns whether comments panel exists on the page."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    return self.comments_panel.is_present

  @property
  def primary_contacts(self):
    """Returns Primary Contacts page element"""
    self.tabs.ensure_tab(self._other_attributes_tab_name)
    return self._related_people_list("Primary Contacts")

  def description(self):
    """Switch to tab with description and return a text of description."""
    self.tabs.ensure_tab(self._other_attributes_tab_name)
    return self._assessment_form_field("Description").text

  def code(self):
    """Switch to tab with code and return the text of code."""
    self.tabs.ensure_tab(self._other_attributes_tab_name)
    return self._info_pane_form_field("Code").text

  def mapped_objects_titles(self):
    """Returns list of mapped snapshots' titles."""
    def titles_from_current_tab():
      """Returns list of mapped snapshots' titles on current tab."""
      els = self._active_tab_root.elements(class_name="mapped-snapshot-item")
      return [el.element(class_name="title").text for el in els]
    self.tabs.ensure_tab(self._assessment_tab_name)
    titles = titles_from_current_tab()
    self.tabs.ensure_tab(self._other_attributes_tab_name)
    return titles + titles_from_current_tab()

  def open_mapped_control_snapshot_info(self, control):
    """Click on control snapshot on assessment tab to open control snapshot
    info modal."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    self._active_tab_root.element(class_name="mapped-snapshot-item").element(
        text=control.title).click()
    return snapshoted_controls_info.SnapshotedControlsInfo()

  def custom_attributes(self):
    """Returns the dictionary of all custom attributes."""
    custom_attributes = self.global_custom_attributes()
    custom_attributes.update(self.local_custom_attributes())
    return custom_attributes

  def global_custom_attributes(self):
    """Switches to tab with GCA and returns their values."""
    self.tabs.ensure_tab(self._other_attributes_tab_name)
    return self.get_custom_attributes()

  def local_custom_attributes(self):
    """Switches to tab with LCA and returns their values."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    custom_attributes = self.get_custom_attributes(False)
    return {k.upper(): v for k, v in custom_attributes.iteritems()}

  def fill_local_cas(self, custom_attributes):
    """Fills LCAs on asmt page."""
    self.tabs.ensure_tab(self._assessment_tab_name)
    self.fill_ca_values(custom_attributes, is_global=False, is_inline=True)

  @property
  def related_assessments_table(self):
    """Switches to Related Assessments tab
    and returns AssessmentRelatedAsmtsTable.
    """
    self.tabs.ensure_tab(self._related_assessments_tab_name)
    return tables.AssessmentRelatedAsmtsTable(
        self._browser.driver, self._active_tab_root.wd)

  @property
  def related_issues_table(self):
    """Switches to Related Issues tab and returns RelatedIssuesTable."""
    self.tabs.ensure_tab(self._related_issues_tab_name)
    return tables.AssessmentRelatedIssuesTable(
        self._browser.driver, self._active_tab_root.wd)

  def fill_global_cas_inline(self, custom_attributes):
    """Fills GCAs inline."""
    self.tabs.ensure_tab(self._other_attributes_tab_name)
    self.fill_ca_values(custom_attributes, is_global=True, is_inline=True)

  def _extend_list_all_scopes_by_review_state(self):
    """Method overriding without action due to Assessments don't have
    'review states'.
    """
    pass

  @property
  def complete_button(self):
    """Returns 'Complete' button element."""
    return self._root.button(text="Complete")

  @property
  def verify_button(self):
    """Returns 'Verify' button element."""
    return self._root.button(text="Verify")

  @property
  def needs_rework_button(self):
    """Returns 'Needs Rework' button element."""
    return self._root.button(text="Needs Rework")

  def click_complete(self):
    """Click on 'Complete' button."""
    self.complete_button.click()

  def click_verify(self):
    """Click on 'Verify' button."""
    self.verify_button.click()

  def click_needs_rework(self):
    """Click on 'Needs Rework' button."""
    self.needs_rework_button.click()

  def set_value_of_dropdown_w_required_field(self, dropdown):
    """Sets value of Assessment dropdown with required url, file or comment.

    After that modal is opened for filling."""
    self.fill_ca_values({dropdown.title: dropdown.multi_choice_options},
                        is_global=False, is_inline=True)
    return set_value_for_asmt_ca.SetValueForAsmtDropdown(self._driver)

  def choose_and_fill_dropdown_lca(self, dropdown, **kwargs):
    """Choose and fill comment or url for Assessment dropdown."""
    self.set_value_of_dropdown_w_required_field(dropdown).fill_dropdown_lca(
        **kwargs)
    self.complete_button.wait_until(lambda e: e.enabled)

  def edit_answers(self):
    """Click to Edit Answers and Confirm"""
    self._browser.button(text="Edit Answers").click()
    self._browser.element(class_name="modal").link(text="Confirm").click()
    self.wait_save()


class AssessmentTemplates(InfoWidget):
  """Model for Assessment Template object Info pages and Info panels."""

  def __init__(self, driver):
    super(AssessmentTemplates, self).__init__(driver)

  def _extend_list_all_scopes_by_review_state(self):
    """Method overriding without action due to Assessment Templates don't have
    'review states'.
    """
    # pylint: disable=invalid-name
    pass


class Issues(InfoWidget):
  """Model for Issue object Info pages and Info panels."""

  def __init__(self, driver):
    super(Issues, self).__init__(driver)

  def description(self):
    """Returns the text of description."""
    return self._editable_simple_field("Description", self._root).text


class Regulations(ReadOnlyInfoWidget):
  """Model for Assessment object Info pages and Info panels."""

  def __init__(self, driver):
    super(Regulations, self).__init__(driver)


class Policies(InfoWidget):
  """Model for Policy object Info pages and Info panels."""

  def __init__(self, driver):
    super(Policies, self).__init__(driver)


class Standards(ReadOnlyInfoWidget):
  """Model for Standard object Info pages and Info panels."""

  def __init__(self, driver):
    super(Standards, self).__init__(driver)


class Contracts(InfoWidget):
  """Model for Contract object Info pages and Info panels."""

  def __init__(self, driver):
    super(Contracts, self).__init__(driver)


class Requirements(InfoWidget):
  """Model for Requirement object Info pages and Info panels."""

  def __init__(self, driver):
    super(Requirements, self).__init__(driver)


class Controls(page_mixins.WithAssignFolder, page_mixins.WithDisabledProposals,
               page_mixins.WithDisabledVersionHistory,
               page_mixins.WithDisabledObjectReview, ReadOnlyInfoWidget):
  """Model for Control object Info pages and Info panels."""
  # pylint: disable=too-many-instance-attributes
  _elements = element.ControlInfoWidget

  def __init__(self, driver):
    super(Controls, self).__init__(driver)
    self.admin_text = roles.ADMIN.upper()
    self.admin_entered_text = self.admins.get_people_emails()
    self.control_operator_text = roles.CONTROL_OPERATORS.upper()
    self.control_operator_entered_text = (
        self.control_operators.get_people_emails())
    self.assertions = self._assertions_dropdown()
    self.reference_urls = self._related_urls(
        self._reference_url_label, self._root)
    self._extend_list_all_scopes(
        [self.admin_text, self.control_operator_text, self.assertions.text],
        [self.admin_entered_text, self.control_operator_entered_text,
         self.assertions.assertions_values])

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(review_status=self.review_status,
                 review_status_display_name=self.review_status)
    if self.is_comments_panel_present and self.obj_name != "control":
      scope["comments"] = self.comments_panel.scopes

  @property
  def control_operators(self):
    """Returns Primary Contacts page element"""
    return self._related_people_list(
        roles.CONTROL_OPERATORS, self._root)

  @property
  def role_to_edit(self):
    """Returns a role for trying to edit."""
    return self.control_owners

  @property
  def control_owners(self):
    """Returns Control Owners page element."""
    return self._related_people_list(roles.CONTROL_OWNERS, self._root)


class Objectives(page_mixins.WithAssignFolder, InfoWidget):
  """Model for Objective object Info pages and Info panels."""

  def __init__(self, driver):
    super(Objectives, self).__init__(driver)
    self.reference_urls = self._related_urls(self._reference_url_label)

  def els_shown_for_editor(self):
    """Elements shown for user with edit permissions"""
    return [self.request_review_btn,
            self.three_bbs.edit_option,
            self.comments_panel.add_btn,
            self.reference_urls.add_button,
            self.assign_folder_button] + list(self.inline_edit_controls)

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(admin=self.admins.get_people_emails())


class ScopeObjects(ReadOnlyInfoWidget):
  """Model for Scope Objects Info pages and Info panels."""

  @property
  def role_to_edit(self):
    """Returns a role for trying to edit."""
    return self._related_people_list(roles.COMPLIANCE_CONTACT, self._root)


class OrgGroups(ScopeObjects):
  """Model for Org Group object Info pages and Info panels."""

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(admin=self.admins.get_people_emails())


class Vendors(ScopeObjects):
  """Model for Vendor object Info pages and Info panels."""


class TechnologyEnvironments(ScopeObjects):
  """Model for Technology Environment object Info pages and Info panels."""


class AccessGroups(ScopeObjects):
  """Model for Access Group object Info pages and Info panels."""


class AccountBalances(ScopeObjects):
  """Model for Account Balance object Info pages and Info panels."""


class Systems(ScopeObjects):
  """Model for System object Info pages and Info panels."""


class Processes(ScopeObjects):
  """Model for Process object Info pages and Info panels."""


class DataAssets(ScopeObjects):
  """Model for Data Asset object Info pages and Info panels."""


class Products(ScopeObjects):
  """Model for Product object Info pages and Info panels."""


class Projects(ScopeObjects):
  """Model for Project object Info pages and Info panels."""


class Facilities(ScopeObjects):
  """Model for Facility object Info pages and Info panels."""


class KeyReports(ScopeObjects):
  """Model for Key Report object Info pages and Info panels."""


class Markets(ScopeObjects):
  """Model for Market object Info pages and Info panels."""


class Metrics(ScopeObjects):
  """Model for Metric object Info pages and Info panels."""


class ProductGroups(ScopeObjects):
  """Model for Product object Info pages and Info panels."""


class Risks(page_mixins.WithDisabledProposals,
            page_mixins.WithDisabledObjectReview,
            page_mixins.WithDisabledVersionHistory, ReadOnlyInfoWidget):
  """Model for Risk object Info pages and Info panels."""

  def __init__(self, driver, root_elem=None):
    super(Risks, self).__init__(driver)
    self.root_element = root_elem if root_elem else self._browser

  @property
  def _root(self):
    """Returns root element (including title, 3bbs)."""
    if self.is_info_page:
      return self._browser.element(class_name="widget", id="info")
    if apply_decline_proposal.CompareApplyDeclineModal().modal.exists:
      return self.root_element
    return self._browser.element(class_name="sticky-info-panel")

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(
        admin=self.admins.get_people_emails(),
        risk_type=self.risk_type()
    )

  def risk_type(self):
    """Returns the text of risk type."""
    return self._simple_field("Risk Type").text

  @property
  def role_to_edit(self):
    """Returns a role for trying to edit."""
    return self.risk_owners

  @property
  def risk_owners(self):
    """Returns Risk Owners page element."""
    return self._related_people_list(roles.RISK_OWNERS, self._root)


class Threats(InfoWidget):
  """Model for Threats object Info pages and Info panels."""

  def __init__(self, driver=None):
    super(Threats, self).__init__(driver)

  def update_obj_scope(self, scope):
    """Updates obj scope."""
    scope.update(admins=self.admins.get_people_emails())
