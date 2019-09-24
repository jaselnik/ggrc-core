# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Facade for Web UI services"""
# pylint: disable=invalid-name
import copy
import random
import re

from lib import url, users, base, browsers, factory
from lib.constants import objects, element
from lib.entities import entities_factory
from lib.page import dashboard
from lib.page.modal import unified_mapper
from lib.page.widget import (generic_widget, object_modal, import_page,
                             related_proposals, version_history)
from lib.service import (webui_service, rest_service, rest_facade,
                         admin_webui_service)
from lib.utils import selenium_utils, ui_utils, string_utils


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


def assert_can_edit_control(selenium, cntrl, can_edit):
  """Assert that current user cannot edit control via UI."""
  info_page = webui_service.ControlsService(
      selenium).open_info_page_of_obj(cntrl)
  els_shown_for_editor = info_page.els_shown_for_editor()
  exp_list = [can_edit] * (len(els_shown_for_editor))
  # Add comment btn exists on all control pages
  exp_list[0] = True
  # Request review button doesn't exist on all control pages
  exp_list[1] = False
  # Edit button doesn't exist on all control pages
  exp_list[2] = False
  assert [item.exists for item in els_shown_for_editor] == exp_list
  if info_page.three_bbs.exists:
    assert info_page.three_bbs.edit_option.exists is False


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


def assert_cannot_delete_control(selenium, cntrl):
  """Assert that current user cannot delete control via UI."""
  cntrl_info_page = webui_service.ControlsService(
      selenium).open_info_page_of_obj(cntrl)
  if cntrl_info_page.three_bbs.exists:
    assert cntrl_info_page.three_bbs.delete_option.exists is False


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
          reviewers=users.current_user()))


def undo_obj_review_approval(selenium, obj):
  """Cancel approved obj review.
  Returns obj with reverted to unreviewed status review."""
  _get_ui_service(selenium, obj).undo_review_approval(obj)
  return obj.update_attrs(review=entities_factory.ReviewsFactory().create(
      last_reviewed_by=users.current_user().email,
      last_reviewed_at=rest_facade.get_last_review_date(obj),
      reviewers=users.current_user()))


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


def map_object_via_unified_mapper(
    selenium, obj_name, dest_objs_type=None, obj_to_map=None,
    return_tree_items=False, open_in_new_frontend=False,
    proceed_in_new_tab=False
):
  """Maps selected obj to dest_obj_type via Unified Mapper.
  Returns:
    MapObjectsModal instance.
  """
  assert dest_objs_type or obj_to_map, ("At least one of params "
                                        "should be provided.")
  if not dest_objs_type:
    dest_objs_type = obj_to_map._obj_name()
  map_modal = unified_mapper.MapObjectsModal(driver=selenium,
                                             obj_name=obj_name)
  map_modal.search_dest_objs(dest_objs_type=dest_objs_type,
                             return_tree_items=return_tree_items)
  if open_in_new_frontend:
    map_modal.open_in_new_frontend_btn.click()
  else:
    if obj_to_map:
      dest_obj_modal = map_modal.click_create_and_map_obj()
      dest_obj_modal.submit_obj(obj_to_map)
    if proceed_in_new_tab:
      object_modal.WarningModal().proceed_in_new_tab()
  return map_modal


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


def edit_gca(selenium, old_ca_type, new_ca_type):
  """Create Global Custom attribute via rest api and edit it via web ui.

  Returns:
    dict with actual edited CA and expected CA.
  """
  new_ca = rest_facade.create_gcad(definition_type=objects.get_singular(
      random.choice(objects.OBJS_SUPPORTING_MANDATORY_CA)),
      attribute_type=old_ca_type, mandatory=True)
  expected_ca = entities_factory.CustomAttributeDefinitionsFactory().create(
      attribute_type=new_ca_type, definition_type=new_ca.definition_type,
      helptext=element.Common.TITLE_EDITED_PART, mandatory=False)
  if new_ca_type in (element.AdminWidgetCustomAttributes.TEXT,
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


def soft_assert_cannot_view_version_history(obj, soft_assert, selenium):
  """Performs soft assertion that user cannot view Version History for disabled
  object."""
  info_page = factory.get_cls_webui_service(objects.get_plural(
      obj.type))(selenium).open_info_page_of_obj(obj)
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


def export_objects(path_to_export_dir, obj_type, src_obj=None,
                   is_versions_widget=False):
  """Opens generic widget of objects or mapped objects
    and exports objects to test's temporary directory as CSV file.
    Returns: list of objects from CSV file in test's temporary directory
    'path_to_export_dir'."""
  ui_service = factory.get_cls_webui_service(
      objects.get_plural(singular=obj_type, title=True))(is_versions_widget)
  widget = (ui_service.open_widget_of_mapped_objs(src_obj) if src_obj
            else ui_service.open_obj_dashboard_tab())
  return ui_service.exported_objs_via_tree_view(path_to_export_dir, widget)
