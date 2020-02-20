# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Facade for Web UI services"""
# pylint: disable=invalid-name
import copy
import random
import re

import inflection

from lib import url, users, base, browsers, factory, decorator
from lib.constants import (objects, element, str_formats, messages,
                           object_states, roles)
from lib.entities import entities_factory
from lib.page import dashboard
from lib.page.modal import bulk_update, unified_mapper, request_review
from lib.page.widget import (generic_widget, object_modal, import_page,
                             related_proposals, version_history, widget_base)
from lib.rest_facades import roles_rest_facade
from lib.service import (webui_service, rest_service, rest_facade,
                         admin_webui_service, change_log_ui_service)
from lib.utils import (
    selenium_utils, ui_utils, string_utils, test_utils, file_utils)


def create_control_in_program_scope(selenium, program):
  """Create control via UI."""
  controls_service = webui_service.ControlsService(selenium)
  controls_service.open_widget_of_mapped_objs(
      program).tree_view.open_map().click_create_and_map_obj()
  control = entities_factory.ControlsFactory().create()
  controls_service.submit_obj_modal(control)
  return control


def open_create_obj_modal(obj_type):
  """Opens create object modal for selected type."""
  selenium_utils.open_url(url.dashboard())
  obj_modal = dashboard.Dashboard().open_create_obj_modal(obj_type=obj_type)
  return obj_modal


def create_asmt(selenium, audit):
  """Create assessment via UI."""
  expected_asmt = entities_factory.AssessmentsFactory().create()
  asmts_ui_service = webui_service.AssessmentsService(selenium)
  asmts_ui_service.create_obj_via_tree_view(
      src_obj=audit, obj=expected_asmt)
  asmt_tree_view = generic_widget.TreeView(
      selenium, None, objects.ASSESSMENTS)
  expected_asmt.url = (
      asmt_tree_view.get_obj_url_from_tree_view_by_title(expected_asmt.title))
  expected_asmt.id = expected_asmt.url.split('/')[-1]
  expected_asmt_rest = rest_facade.get_obj(expected_asmt)
  expected_asmt.assignees = audit.audit_captains
  expected_asmt.creators = [users.current_user().email]
  expected_asmt.verifiers = audit.auditors
  expected_asmt.created_at = expected_asmt_rest.created_at
  expected_asmt.modified_by = users.current_user().email
  expected_asmt.updated_at = expected_asmt_rest.updated_at
  expected_asmt.slug = expected_asmt_rest.slug
  return expected_asmt


def assert_can_edit_asmt(selenium, asmt):
  """Assert that current user can edit asmt via UI."""
  asmts_ui_service = webui_service.AssessmentsService(selenium)
  info_page = asmts_ui_service.open_info_page_of_obj(asmt)
  _assert_title_editable(asmt, selenium, info_page)


def assert_can_view(selenium, obj):
  """Assert that current user can view object via UI.
  We go through all elements of the page in order to check that user
  has access to them.
  """
  actual_obj = _get_ui_service(selenium, obj).get_obj_from_info_page(obj)
  obj_copy = copy.deepcopy(obj)
  # Code for working with custom attributes appears to be buggy
  base.Test.general_equal_assert(
      obj_copy.repr_ui(), actual_obj, "audit", "custom_attributes",
      "program", "external_slug", "external_id")


def assert_cannot_view(obj):
  """Assert that current user cannot view object via UI"""
  selenium_utils.open_url(obj.url)
  assert ui_utils.is_error_403()


def assert_can_edit(selenium, obj, can_edit):
  """If `can_edit` is True, assert that current user can edit object via UI
  otherwise check that user cannot edit object via UI
  """
  ui_service = _get_ui_service(selenium, obj=obj)
  info_page = ui_service.open_info_page_of_obj(obj)
  els_shown_for_editor = info_page.els_shown_for_editor()
  assert [item.exists for item in els_shown_for_editor] == \
         [can_edit] * len(els_shown_for_editor)
  if can_edit:
    _assert_title_editable(obj, selenium, info_page)


def assert_can_delete(selenium, obj, can_delete):
  """If `can_delete` is True, assert that current user can delete object via UI
  otherwise check that user cannot delete object via UI
  """
  info_page = _get_ui_service(selenium, obj=obj).open_info_page_of_obj(obj)
  assert info_page.three_bbs.delete_option.exists == can_delete
  if can_delete:
    info_page.three_bbs.select_delete().confirm_delete()
    selenium_utils.open_url(obj.url)
    assert ui_utils.is_error_404()


def _get_ui_service(selenium, obj):
  """Get webui_service for object"""
  obj_type = objects.get_plural(obj.type)
  return webui_service.BaseWebUiService(obj_type, selenium)


def _assert_title_editable(obj, selenium, info_page):
  """Assert that user can edit object's title"""
  new_title = "[EDITED]" + obj.title
  info_page.three_bbs.select_edit()
  modal = object_modal.get_modal_obj(obj.type, selenium)
  modal.fill_form(title=new_title)
  modal.save_and_close()
  obj.update_attrs(
      title=new_title, modified_by=users.current_user().email,
      updated_at=rest_service.ObjectsInfoService().get_obj(
          obj=obj).updated_at)
  new_ui_obj = _get_ui_service(selenium, obj).get_obj_from_info_page(obj)
  base.Test.general_equal_assert(
      obj.repr_ui(), new_ui_obj, "audit", "custom_attributes")


def check_base_objects_have_numbers(lhn_menu):
  """Check LHN list of the upper objects have numbers in brackets."""
  for item in element.Lhn.BASE_OBJS:
    lhn_item = getattr(lhn_menu, 'toggle_' + item)
    assert re.match(item.upper() + r' \((\d*)\)',
                    lhn_item.text) is not None


def check_objects_have_numbers(lhn_menu):
  """Check LHN list of the middle objects have numbers in brackets."""
  for item in element.Lhn.SUB_OBJS:
    assert getattr(lhn_menu, 'toggle_' + item).text == item.replace(
        '_or_', '/').upper()
    lhn_item = getattr(lhn_menu, 'select_' + item)()
    lhn_item.update_members()
    for item_sub in getattr(element.Lhn, item.upper() + '_MEMBERS'):
      lhn_item_sub = getattr(lhn_item, 'toggle_' + item_sub)
      assert re.match(item_sub.replace('_', ' ').title() + r' \((\d*)\)',
                      lhn_item_sub.text) is not None


def can_base_objects_expand(lhn_menu):
  """Check LHN list of the upper objects can expand."""
  for item in element.Lhn.BASE_OBJS:
    getattr(lhn_menu, 'select_' + item)()
    assert getattr(lhn_menu, 'toggle_' + item).is_activated is True


def can_objects_expand(lhn_menu):
  """Check LHN list of the middle objects can expand."""
  for item in element.Lhn.SUB_OBJS:
    lhn_item = getattr(lhn_menu, 'select_' + item)()
    for item_sub in getattr(element.Lhn, item.upper() + '_MEMBERS'):
      getattr(lhn_item, 'select_' + item_sub)()
      assert getattr(lhn_item, 'toggle_' + item_sub).is_activated is True


def check_user_menu_has_icons(user_menu):
  """Check user menu list has icons."""
  for item in user_menu.user_menu_items:
    assert item.element.find_element_by_class_name(
        'fa').get_attribute('class') != ''
  assert user_menu.email.text == users.current_user().name


def submit_obj_for_review(selenium, obj, reviewer):
  """Submit object for review scenario.
  Returns obj with assigned review."""
  review_comment = string_utils.StringMethods.random_string()
  _get_ui_service(selenium, obj).submit_for_review(
      obj, reviewer.email, review_comment)
  obj.update_attrs(
      review=entities_factory.ReviewsFactory().create(reviewers=reviewer))
  exp_comment = entities_factory.CommentsFactory().create(
      description=element.Common.REVIEW_COMMENT_PATTERN.format(
          # reviewers emails in review comment message need to be sorted
          # as they are displayed in UI in random order
          emails=', '.join(sorted(obj.review["reviewers"])),
          comment=review_comment))
  exp_comment.created_at = rest_service.ObjectsInfoService().get_comment_obj(
      paren_obj=obj, comment_description=review_comment).created_at
  obj.comments = [exp_comment.repr_ui()]
  return obj


def approve_obj_review(selenium, obj):
  """Approve obj review.
  Returns obj with approved review."""
  _get_ui_service(selenium, obj).approve_review(obj)
  return obj.update_attrs(
      review=entities_factory.ReviewsFactory().create(
          status=element.ReviewStates.REVIEWED,
          last_reviewed_by=users.current_user().email,
          last_reviewed_at=rest_facade.get_last_review_date(obj),
          reviewers=users.current_user()),
      updated_at=rest_facade.get_obj_review(obj).updated_at)


def undo_obj_review_approval(selenium, obj):
  """Cancel approved obj review.
  Returns obj with reverted to unreviewed status review."""
  _get_ui_service(selenium, obj).undo_review_approval(obj)
  return obj.update_attrs(
      review=entities_factory.ReviewsFactory().create(
          last_reviewed_by=users.current_user().email,
          last_reviewed_at=rest_facade.get_last_review_date(obj),
          reviewers=users.current_user()),
      updated_at=rest_facade.get_obj_review(obj).updated_at)


def cancel_review_by_editing_obj(selenium, obj):
  """Edit obj title and revert obj review to unreviewed state.
  Returns updated obj with reverted to unreviewed status review."""
  new_title = element.Common.TITLE_EDITED_PART + obj.title
  _get_ui_service(selenium, obj).edit_obj(obj, title=new_title)
  return obj.update_attrs(
      title=new_title,
      updated_at=rest_facade.get_obj(obj).updated_at,
      modified_by=users.current_user().email,
      review=entities_factory.ReviewsFactory().create())


def get_object(selenium, obj):
  """Get and return object from Info page."""
  return _get_ui_service(selenium, obj).get_obj_from_info_page(obj)


def perform_disabled_mapping(
    dest_obj, return_tree_items=False, create_new_obj=False
):
  """Maps selected obj to dest_obj via Unified Mapper.
  If return_tree_items then expects search results presence in tree view.
  If create_new_obj then tries to create a new object based on passed
  dest_obj entity.
  Returns:
    MapObjectsModal instance.
  """
  map_modal = unified_mapper.MapObjectsModal(
      driver=browsers.get_browser(),
      obj_name=objects.get_plural(dest_obj.type))
  map_modal.search_dest_objs(dest_objs_type=dest_obj.type,
                             return_tree_items=return_tree_items)
  if create_new_obj:
    dest_obj_modal = map_modal.click_create_and_map_obj()
    if objects.get_plural(dest_obj.type) not in objects.ALL_DISABLED_OBJECTS:
      dest_obj_modal.submit_obj(dest_obj)
    confirm_modal = object_modal.CommonConfirmModal()
    check_ggrc_8484(dest_obj, confirm_modal.exists)
    confirm_modal.confirm()
  else:
    map_modal.open_in_new_frontend_btn.click()
  return map_modal


def check_ggrc_8484(dest_obj, condition):
  """Check if Confirm modal is visible when Regulations and Standards are
  disabled."""
  if objects.get_plural(dest_obj.type) in objects.STANDARDS_AND_REGULATIONS:
    base.Test().check_xfail_or_fail(
        condition, "GGRC-8484.\n",
        "Confirm modal should be visible when Regulations and Standards are"
        " disabled.")


def create_audit(selenium, program, **kwargs):
  """Create audit via UI."""
  audit = entities_factory.AuditsFactory().create(**kwargs)
  audits_service = webui_service.AuditsService(selenium)
  audits_service.create_obj_via_tree_view(program, audit)
  audit.url = audits_service.open_widget_of_mapped_objs(
      program).tree_view.tree_view_items()[0].url()
  return audit


def get_controls_snapshots_count(selenium, src_obj):
  """Return dictionary with controls snapshots actual count and count taken
  from tab title."""
  controls_ui_service = webui_service.ControlsService(selenium)
  return {
      "controls_tab_count": controls_ui_service.get_count_objs_from_tab(
          src_obj=src_obj),
      "controls_count": len(controls_ui_service.get_list_objs_from_tree_view(
          src_obj=src_obj))}


def get_available_templates_list():
  """Returns list of objects templates available for downloading from
  import page."""
  page = import_page.ImportPage()
  page.open()
  return page.open_download_template_modal().available_templates_list


def edit_gca(selenium, ca_type):
  """Create Global Custom attribute via rest api and edit it via web ui.

  Returns:
    dict with actual edited CA and expected CA.
  """
  new_ca = rest_facade.create_gcad(definition_type=objects.get_singular(
      random.choice(objects.OBJS_SUPPORTING_MANDATORY_CA)),
      attribute_type=ca_type, mandatory=True)
  expected_ca = copy.deepcopy(new_ca)
  expected_ca.update_attrs(helptext=element.Common.TITLE_EDITED_PART,
                           mandatory=False)
  if ca_type in (element.AdminWidgetCustomAttributes.TEXT,
                 element.AdminWidgetCustomAttributes.RICH_TEXT):
    expected_ca.update_attrs(placeholder=element.Common.TITLE_EDITED_PART)
  actual_ca = admin_webui_service.CustomAttributeWebUiService(
      selenium).edit_custom_attribute(new_ca, expected_ca)
  return {"actual_ca": actual_ca, "expected_ca": expected_ca}


def are_tabs_urls_equal():
  """Returns whether 2 tab urls are equal."""
  old_tab, new_tab = browsers.get_browser().windows()
  return old_tab.url == new_tab.url


def soft_assert_cannot_make_proposal(info_page, soft_assert):
  """Performs soft assertion that user cannot make a proposal for disabled
  object."""
  soft_assert.expect(not info_page.is_propose_changes_btn_exists,
                     "'Propose Changes' button should not be displayed.")


def soft_assert_cannot_view_proposals(info_page, soft_assert):
  """Performs soft assertion that user cannot view proposals for disabled
  object."""
  info_page.click_change_proposals()
  soft_assert.expect(
      info_page.proposals_tab_or_link_name not in info_page.tabs.tab_names,
      "'Change Proposals' tab should not be displayed.")
  soft_assert.expect(are_tabs_urls_equal(), "Tabs urls should be equal.")
  for tab_num, tab in enumerate(browsers.get_browser().windows(), start=1):
    tab.use()
    soft_assert.expect(
        not related_proposals.RelatedProposals().are_proposals_displayed(),
        "Proposals should not be displayed in browser tab number {}.".
        format(tab_num))


def soft_assert_cannot_view_version_history(obj, soft_assert):
  """Performs soft assertion that user cannot view Version History for disabled
  object."""
  info_page = factory.get_cls_webui_service(objects.get_plural(
      obj.type))().open_info_page_of_obj(obj)
  info_page.click_version_history()
  soft_assert.expect(are_tabs_urls_equal(), "Tabs urls should be equal.")
  soft_assert.expect(
      info_page.version_history_tab_or_link_name
      not in info_page.tabs.tab_names,
      "'Version History' tab should not be displayed.")
  for tab_num, tab in enumerate(browsers.get_browser().windows(), start=1):
    tab.use()
    soft_assert.expect(
        not version_history.VersionHistory().is_version_history_displayed(),
        "Version history should not be displayed in browser tab number {}.".
        format(tab_num))


def soft_assert_no_modals_present(modal_obj, soft_assert):
  """Performs soft assertion that there is no modal objects in 2 browser
  tabs."""
  assert issubclass(modal_obj.__class__, object_modal.BaseObjectModal), (
      "Object should be derived from BaseObjectModal.")
  tabs = browsers.get_browser().windows()
  soft_assert.expect(
      len(tabs) == 2, "Only 2 window tabs should be opened but it is found "
                      "{} tab(s).".format(len(tabs)))
  for tab_num, tab in enumerate(tabs, start=1):
    tab.use()
    soft_assert.expect(not modal_obj.is_present,
                       "There should be no modal windows in browser "
                       "tab number {}.".format(tab_num))


def export_obj_scopes(path_to_export_dir, obj_type, src_obj=None,
                      is_versions_widget=False, **kwargs):
  """Opens generic widget of objects or mapped objects
  and exports objects to test's temporary directory as CSV file.
  Returns: list of objects scopes (dicts with keys as exportable field
  names, values as values of this field for current instance)."""
  ui_service = factory.get_cls_webui_service(
      objects.get_plural(singular=obj_type, title=True))(
          is_versions_widget, **kwargs)
  widget = (ui_service.open_widget_of_mapped_objs(src_obj) if src_obj
            else ui_service.open_obj_dashboard_tab())
  return file_utils.get_list_objs_scopes_from_csv(
      ui_service.export_objs_via_tree_view(path_to_export_dir, widget))


def export_objects(path_to_export_dir, obj_type, src_obj=None,
                   is_versions_widget=False, **kwargs):
  """Opens generic widget of objects or mapped objects
  and exports objects to test's temporary directory as CSV file.
  Returns: list of objects from CSV file in test's temporary directory
  'path_to_export_dir'."""
  ui_service = factory.get_cls_webui_service(
      objects.get_plural(singular=obj_type, title=True))(
          is_versions_widget, **kwargs)
  dict_list_objs_scopes = export_obj_scopes(
      path_to_export_dir, obj_type, src_obj, is_versions_widget, **kwargs)
  return ui_service.build_objs_from_csv_scopes(dict_list_objs_scopes)


def soft_assert_gca_fields_disabled_for_editing(soft_assert, ca_type):
  """Soft assert that following fields are disabled in 'Edit Custom Attribute
  Definition' modal: 'Title', 'Attribute type', 'Possible values'.
  """
  modal = widget_base.EditCustomAttributeModal()
  soft_assert.expect(not modal.title_field.enabled,
                     "'Title' field should be disabled.")
  soft_assert.expect(not modal.attribute_type_field.enabled,
                     "'Attribute type' field should be disabled.")
  if ca_type in (element.AdminWidgetCustomAttributes.MULTISELECT,
                 element.AdminWidgetCustomAttributes.DROPDOWN):
    soft_assert.expect(not modal.multi_choice_options_field.enabled,
                       "'Possible values' field should be disabled.")


def soft_assert_bulk_complete_for_completed_asmts(soft_assert, asmts, page):
  """Performs soft assert that 'Bulk complete' option/button is not
  displayed for several assessments when all of them are in one of the
  completed states."""
  for asmt, status in zip(asmts, object_states.COMPLETED_STATES):
    roles_rest_facade.add_verifier_to_set_obj_state(asmt, status,
                                                    users.current_user())
    rest_facade.update_object(asmt, status=status)
    browsers.get_browser().refresh()
    ui_utils.wait_for_spinner_to_disappear()
    soft_assert.expect(
        not page.is_bulk_complete_displayed(),
        "'Bulk complete' for assessment with '{}' status should not be "
        "available.".format(status))


def soft_assert_bulk_complete_for_opened_asmts(soft_assert, asmts, page,
                                               is_displayed=True):
  """Performs soft assert that 'Bulk complete' option/button is displayed or
  not for several assessments when at least one of them is in one of the opened
  states."""
  for status in object_states.OPENED_STATES:
    roles_rest_facade.add_verifier_to_set_obj_state(asmts[-1], status,
                                                    users.current_user())
    rest_facade.update_object(asmts[-1], status=status)
    browsers.get_browser().refresh()
    ui_utils.wait_for_spinner_to_disappear()
    soft_assert.expect(
        page.is_bulk_complete_displayed() == is_displayed,
        "'Bulk complete' for assessment with '{}' status should {}be "
        "available.".format(status, "" if is_displayed else "not "))


def soft_assert_objects_are_mapped(
    selenium, soft_assert, src_obj, objs, *args, **kwargs
):
  """Performs soft assertion that object is mapped to another one.

  Args and kwargs are optional arguments for initialization of webui_service
  object.
  """
  ui_service_cls = factory.get_cls_webui_service(
      objects.get_plural(objs[0].type))
  mapped_objs = (ui_service_cls(driver=selenium, *args, **kwargs).
                 get_list_objs_from_tree_view(src_obj=src_obj))
  soft_assert.expect(
      [obj.tree_item_representation() for obj in objs] == mapped_objs,
      messages.AssertionMessages.OBJS_SHOULD_BE_MAPPED_TO_OBJ.format(
          mapped_objs_names=[obj.title for obj in objs],
          src_obj_name=src_obj.title))


def soft_assert_tab_with_number_exists(info_page, soft_assert, tab_name, num):
  """Soft assert that there is tab with number on page."""
  soft_assert.expect(
      str_formats.TAB_WITH_NUM.format(tab_name=tab_name, num=num)
      in info_page.top_tabs.tab_names,
      messages.AssertionMessages.TAB_WITH_NUM_SHOULD_EXIST.format(
          tab_name=tab_name, num=num))


def soft_assert_automapping_in_change_log(
    src_obj, mapped_obj, automapped_obj, user, soft_assert
):
  """Soft assert automapping of automapped_obj (which is mapped to mapped_obj)
  to src_obj which is performed after mapping mapped_obj to src_obj by user."""
  expected_entry = (entities_factory.ChangeLogItemsFactory().
                    generate_log_entity_for_automapping(
                        src_obj, mapped_obj, automapped_obj, user))
  actual_changelog = (change_log_ui_service.ChangeLogService().
                      get_obj_changelog(src_obj))
  soft_assert.expect(
      expected_entry in actual_changelog,
      messages.AssertionMessages.AUTOMAPPING_IN_CHANGE_LOG.format(
          obj_name=automapped_obj.type))


def soft_assert_bulk_verify_for_not_in_review_state(page, asmts, soft_assert):
  """Soft assert 'Bulk Verify' availability for assessments with different from
  'In Review' status."""
  statuses = object_states.ASSESSMENT_STATUSES_NOT_READY_FOR_REVIEW
  for asmt, status in zip(asmts, statuses):
    if status == object_states.COMPLETED:
      # normally assessment cannot be in completed state if it has verifiers
      # GGRC-7802: validation should be added on backend side
      rest_facade.update_acl([asmt], [], rewrite_acl=True,
                             **roles_rest_facade.get_role_name_and_id(
                                 asmt.type, roles.VERIFIERS))
    rest_facade.update_object(asmt, status=status)
    browsers.get_browser().refresh()
    ui_utils.wait_for_spinner_to_disappear()
    soft_assert.expect(
        not page.is_bulk_verify_displayed(),
        "Bulk Verify should not be available if assessment is in "
        "'{}' status.".format(status))


def soft_assert_bulk_verify_for_in_review_state(page, asmt, soft_assert,
                                                is_available):
  """Soft assert 'Bulk Verify' availability for assessments in 'In Review'
  status."""
  rest_facade.update_object(asmt, status=object_states.READY_FOR_REVIEW)
  browsers.get_browser().refresh()
  ui_utils.wait_for_spinner_to_disappear()
  soft_assert.expect(
      page.is_bulk_verify_displayed() == is_available,
      "Bulk Verify should {} be available if assessment is in '{}' status."
      .format("" if is_available else "not", object_states.READY_FOR_REVIEW))


def bulk_verify_all(widget, wait_for_completion=True):
  """Bulk verify all available assessments in specified widget. Refreshes page
  after actions to see actual items."""
  bulk_verify_modal = bulk_update.BulkVerifyModal()
  if not bulk_verify_modal.is_displayed:
    widget.open_bulk_verify_modal()
  bulk_verify_modal.select_assessments_section.click_select_all()
  bulk_verify_modal.click_verify()
  if wait_for_completion:
    widget.submit_message.wait_until(lambda e: e.exists)
    widget.finish_message.wait_until(lambda e: e.exists)
  browsers.get_browser().refresh()


def soft_assert_statuses_on_tree_view(status, is_verified, src_obj,
                                      soft_assert):
  """Soft assert that statuses of items on tree view are correct and items are
  verified if expected."""
  asmts_from_ui = (webui_service.AssessmentsService()
                   .get_list_objs_from_tree_view(src_obj))
  soft_assert.expect(
      all([asmt.status == status and asmt.verified is is_verified
           for asmt in asmts_from_ui]),
      "All assessments should {} be verified and have '{}' state.".format(
          "not" if is_verified is False else "",
          status))


def soft_assert_bulk_verify_filter_ui_elements(modal, soft_assert):
  """Checks that filter section of bulk verify modal has 'Reset to Default'
  button, exactly 2 states options: 'Select all', 'In Review', and default
  filter for current user as a verifier."""
  filter_section_element = modal.filter_section.expand()
  soft_assert.expect(
      filter_section_element.reset_to_default_button.exists,
      "'Reset to Default' button should be displayed in filter section.")
  soft_assert.expect(
      filter_section_element.get_state_filter_options() == [
          'Select All', 'In Review'],
      "Filter should contain exactly 2 options: 'Select All', 'In Review'.")
  expected_filters = [{"attr_name": "Verifiers", "compare_op": "Contains",
                       "value": users.current_user().email}]
  soft_assert.expect(
      filter_section_element.get_filters_dicts() == expected_filters,
      "Modal should contain default filter for current user as a verifier.")


def soft_assert_bulk_verify_filter_functionality(page, modal, exp_asmt,
                                                 soft_assert):
  """Checks that filter functionality on bulk verify modal works correctly
  comparing assessment from modal with the expected one.
  Depending on opened page this method either soft asserts that 'Filter by
  Mapping' section contains title of opened audit or set mapping filter with
  provided audit and apply it."""
  filter_section_element = modal.filter_section.expand()
  if not isinstance(page, dashboard.MyAssessments):
    soft_assert.expect(
        filter_section_element.get_mapped_to_audit_filter() == exp_asmt.audit,
        "'Filter by Mapping' section should contain title of opened audit.")
  else:
    filter_section_element.add_mapping_filter(
        objects.get_singular(objects.AUDITS, title=True),
        element.Common.TITLE, exp_asmt.audit)
  filter_section_element.apply()
  base.Test.general_equal_soft_assert(
      soft_assert, [exp_asmt],
      webui_service.AssessmentsService().get_objs_from_bulk_update_modal(
          modal, with_second_tier_info=True),
      *exp_asmt.bulk_update_modal_tree_view_attrs_to_exclude)


def soft_assert_detailed_page_of_asmt_tree_view_item_is_readonly(
    soft_assert, asmt_tree_view_item
):
  """Soft assert detailed page of assessment tree view item is readonly.

  Function checks attributes which matches pattern
  "is_*section_name*_section_editable" of AssessmentTreeViewItem obj and
  verifies that it is False.
  """
  attrs = [attr for attr in dir(asmt_tree_view_item)
           if attr.endswith("_section_editable")]
  if attrs:
    for attr in attrs:
      soft_assert.expect(
          getattr(asmt_tree_view_item, attr) is False,
          '{} section should be not editable'.format(
              re.search(r"\bis_(.+?)_section_editable\b", attr).group(1).
              replace('_', ' ').capitalize()))
  else:
    raise ValueError("No needed attributes found.")


def soft_assert_asmt_tree_view_items_on_bulk_verify_modal(
    soft_assert, modal, exp_asmt
):
  """Checks assessment tree view items from bulk verify modal.

  Firstly checks opening of assessment info page through open button, then
  checks that mapped controls section and evidence urls section from second
  tier are read-only."""
  for asmt_tree_view_item in (
      modal.select_assessments_section.tree_view.tree_view_items()
  ):
    asmt_tree_view_item.open()
    _, new_tab = browsers.get_browser().windows()
    test_utils.wait_for(lambda nt=new_tab: nt.url.endswith(url.Widget.INFO))
    soft_assert.expect(
        new_tab.url == exp_asmt.url + url.Widget.INFO,
        '{} info page should be opened in new tab'.format(exp_asmt.title))
    new_tab.close()
    soft_assert_detailed_page_of_asmt_tree_view_item_is_readonly(
        soft_assert, asmt_tree_view_item)


def soft_assert_asmts_list_on_bulk_verify_modal(modal, soft_assert, exp_asmts):
  """Checks that assessments list is displayed on bulk verify modal with
  correct columns by default and that checkboxes are displayed near every
  assessment and all of them are unchecked and enabled.
  """
  asmt_section = modal.select_assessments_section
  actual_column_names = tuple(asmt_section.tree_view.column_names())
  soft_assert.expect(
      actual_column_names ==
      element.AssessmentModalSetVisibleFields.INITIAL_FIELDS,
      'There are wrong default column names. Expected: {}. Actual: {}.'.format(
          element.AssessmentModalSetVisibleFields.INITIAL_FIELDS,
          actual_column_names))
  soft_assert_tree_view_checkboxes(asmt_section, soft_assert)
  base.Test.general_equal_soft_assert(
      soft_assert,
      sorted(exp_asmts),
      sorted(webui_service.AssessmentsService().
             get_objs_from_bulk_update_modal(modal)),
      *exp_asmts[0].bulk_update_modal_tree_view_attrs_to_exclude)


@decorator.execute_on_all_pagination_pages
def soft_assert_tree_view_checkboxes(el_w_tree_view, soft_assert):
  """Soft asserts that all checkboxes from all items from tree view are
  unchecked and enabled."""
  for item in el_w_tree_view.tree_view.tree_view_items():
    soft_assert.expect(
        not item.is_checkbox_checked, 'Checkbox should be unchecked')
    soft_assert.expect(
        not item.is_checkbox_disabled, 'Checkbox should be enabled')


def soft_assert_role_cannot_be_edited(soft_assert, obj):
  """Performs soft assert that click on role's pencil icon doesn't open
  an input field."""
  info_widget = factory.get_cls_webui_service(
      objects.get_plural(obj.type))().open_info_page_of_obj(obj)
  role_field_element = info_widget.role_to_edit
  role_field_element.inline_edit.open()
  # wait until new tab contains info page url
  _, new_tab = browsers.get_browser().windows()
  test_utils.wait_for(lambda: new_tab.url.endswith(url.Widget.INFO))
  soft_assert.expect(not role_field_element.add_person_text_field.exists,
                     "There should be no input field.")


def check_mega_program_icon_in_unified_mapper(selenium, child_program,
                                              parent_program):
  """Performs assert that a mega program has a blue flag icon in unified mapper:
  open a parent program tab -> click the Map btn -> assert blue flag is visible
  """
  program_mapper = (webui_service.ProgramsService(
                    obj_name=objects.PROGRAM_PARENTS, driver=selenium)
                    .get_unified_mapper(child_program))
  parent_program_row = program_mapper.tree_view.get_item_by_obj_name(
      parent_program.title)
  assert parent_program_row.has_mega_program_icon


def open_propose_changes_modal(obj, selenium):
  """Opens propose changes modal of obj."""
  (_get_ui_service(selenium, obj).open_info_page_of_obj(obj).
   click_propose_changes())
  modal = object_modal.BaseObjectModal(selenium)
  modal.wait_until_present()
  return modal


def open_request_review_modal(obj, selenium):
  """Opens request review modal of obj."""
  (_get_ui_service(selenium, obj).open_info_page_of_obj(obj).
   open_submit_for_review_popup())
  modal = request_review.RequestReviewModal(selenium)
  modal.wait_until_present()
  return modal


def soft_assert_cannot_add_comment(soft_assert, info_page):
  """Performs soft assert that user can't add a comment:
    - input field is not displayed
    - "Add Comment" button is not displayed for Scope objects and opens a new
     browser tab for other disabled objects."""
  soft_assert.expect(
      not info_page.comments_panel.comment_input.exists,
      "There should be no input field in comments panel.")
  if inflection.underscore(info_page.child_cls_name) in objects.SCOPE_OBJECTS:
    soft_assert.expect(not info_page.comments_panel.add_btn.exists,
                       "'Add Comment' button should not be displayed.")
  else:
    info_page.comments_panel.click_add_button()
    # wait until new tab contains info page url
    _, new_tab = browsers.get_browser().windows()
    test_utils.wait_for(lambda: new_tab.url.endswith(url.Widget.INFO))
    soft_assert.expect(are_tabs_urls_equal(), "Tabs urls should be equal.")


def open_dashboard(selenium):
  """Opens My Work Dashboard URL and
  Returns:
    Dashboard page objects model."""
  selenium_utils.open_url(url.dashboard())
  return dashboard.Dashboard(selenium)


def soft_assert_cannot_update_predefined_field(soft_assert, obj):
  """Performs soft assert that click on predefined field's pencil icon doesn't
  open an input field."""
  field_element = factory.get_cls_webui_service(objects.get_plural(
      obj.type))().open_info_page_of_obj(obj).predefined_field
  field_element.inline_edit.open()
  soft_assert.expect(not field_element.input.exist,
                     "There should be no input field.")


def check_order_and_removing_of_searches(soft_assert, objs, search_modal):
  """Create searches for objs (order shoud be descending, so list of
  titles is reversed after creating searches) -> verify order is correct ->
  verify search can be removed."""
  created_searches_by_desc = search_modal.create_and_save_searches(objs)[::-1]
  actual_searches = search_modal.saved_searches_titles[slice(len(
      created_searches_by_desc))]
  soft_assert.expect(created_searches_by_desc == actual_searches,
                     messages.AssertionMessages.format_err_msg_equal(
                         actual_searches, created_searches_by_desc))
  search_to_remove = created_searches_by_desc[0]
  search_modal.remove_saved_search(search_to_remove)
  soft_assert.expect(search_to_remove not in
                     search_modal.saved_searches_titles,
                     "Saved search is not removed.")


def soft_assert_permalink_of_search_works(soft_assert, selenium, permalink,
                                          filtered_objs, src_obj):
  """Open permalink in a new tab -> assert filter's page is opened (tree view
  contains only expected items)."""
  selenium_utils.open_url_in_new_tab(permalink)
  actual_objs_in_tree_view = (
      factory.get_cls_webui_service(objects.get_plural(filtered_objs[0].type))(
          driver=selenium).
      get_list_objs_from_tree_view(src_obj=src_obj))
  for actual, expected in zip(actual_objs_in_tree_view, filtered_objs):
    soft_assert.expect(expected.tree_item_representation() == actual,
                       messages.AssertionMessages.format_err_msg_equal(
                           expected.title, actual.title))


def create_save_and_apply_advanced_search(page, object_to_search):
  """Creates, saves and applies advanced search on mapped object page."""
  search_modal = page.open_advanced_search()
  search_modal.create_and_save_search(object_to_search)
  search_modal.search_filter_area.click_apply()


def check_advanced_search_permalink_works(soft_assert, page_obj, selenium,
                                          src_obj, object_to_search):
  """Checks if a copied permalink of search works.

  Copies a permalink. As it is impossible to open url directly from buffer,
  a copied link is pasted to input_to_paste_link and value of the input is
  used like url to open. Verifies if there are only expected items in tree
  view on an opened page."""
  page_obj.copy_permalink()
  input_to_paste_link = (open_dashboard(selenium).header.open_global_search().
                         search_filter_area.filter_value)
  selenium_utils.paste_from_clipboard(input_to_paste_link)
  soft_assert_permalink_of_search_works(soft_assert, selenium,
                                        input_to_paste_link.value,
                                        [object_to_search], src_obj)


def start_and_cancel_bulk_verifying(page):
  """Opens a Bulk Verify modal, selects all the items and cancels the modal.
  Refreshes page after actions to see actual items."""
  modal = page.open_bulk_verify_modal()
  modal.select_assessments_section.click_select_all()
  modal.click_cancel()
  browsers.get_browser().refresh()


def check_ca_creating(soft_assert, selenium, def_type, ca_type):
  """Creates custom attribute. Checks a mandatory checkbox visibility."""
  expected_ca = entities_factory.CustomAttributeDefinitionsFactory().create(
      attribute_type=ca_type, definition_type=def_type)
  ca_admin_service = admin_webui_service.CustomAttributeWebUiService(
      selenium)
  add_ca_modal = ca_admin_service.ca_widget.expand_collapse_group(
      def_type, expand=True).open_add_new_ca_modal()
  soft_assert.expect(
      add_ca_modal.mandatory_checkbox.exists
      if def_type != objects.get_normal_form(objects.ASSESSMENTS)
      else not add_ca_modal.mandatory_checkbox.exists,
      "Mandatory checkbox should {} be visible.".format(
          "" if def_type != objects.get_normal_form(
              objects.ASSESSMENTS) else "not"))
  add_ca_modal.submit_obj(expected_ca)
  actual_cas = ca_admin_service.ca_widget.get_custom_attributes_list(
      obj_type=expected_ca.definition_type)
  base.Test.general_contain_soft_assert(soft_assert, expected_ca, actual_cas,
                                        "multi_choice_options")


def soft_assert_pagination(
    soft_assert, pagination, exp_page_size, exp_page_sizes
):
  """Soft asserts current page size and available page sizes are equal to
  exp_page_size and exp_page_sizes respectively."""
  soft_assert.expect(pagination.page_size == exp_page_size,
                     'There should be {} items per page'.format(exp_page_size))
  soft_assert.expect(
      pagination.page_size_options == exp_page_sizes,
      'Page size options are incorrect. \nActual: {}, \nExpected: {}'.format(
          pagination.page_size_options, exp_page_sizes))
