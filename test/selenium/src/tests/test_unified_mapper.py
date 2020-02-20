# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Unified mapper tests."""
# pylint: disable=no-self-use
# pylint: disable=invalid-name
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest

from lib import base, browsers, url, factory
from lib.constants import objects
from lib.entities.entity import Representation
from lib.page.modal import unified_mapper
from lib.service import webui_service, webui_facade
from lib.utils import test_utils


class TestProgramPage(base.Test):
  """Tests of unified mapper for Program."""

  @pytest.mark.smoke_tests
  def test_destructive_mapping_controls_to_program_via_unified_mapper(
      self, program, controls, selenium
  ):
    """Check if Controls can be mapped to Program from Controls widget under
    Program page via unified mapper.
    Preconditions:
    - Program, Controls created via REST API.
    """
    expected_controls = [
        expected_control.repr_ui() for expected_control
        in controls]
    controls_ui_service = webui_service.ControlsService(selenium)
    controls_ui_service.map_objs_via_tree_view(
        src_obj=program, dest_objs=expected_controls)
    actual_controls_tab_count = controls_ui_service.get_count_objs_from_tab(
        src_obj=program)
    assert len(expected_controls) == actual_controls_tab_count
    actual_controls = controls_ui_service.get_list_objs_from_tree_view(
        src_obj=program)
    # 'actual_controls': created_at, updated_at, custom_attributes (None)
    self.general_equal_assert(
        sorted(expected_controls), sorted(actual_controls),
        *Representation.tree_view_attrs_to_exclude)


class TestDisabledObjectsPage(base.Test):
  """Tests of unified mapper for disabled objects.

  Test cases are parametrized with the type of objects under test.
  As there is too much disabled objects to test all of them, in each test case
  one object of each disabled objects section is used.
  """

  @pytest.mark.parametrize("obj", objects.SINGULAR_CONTROL_AND_RISK +
                           [next(objects.SINGULAR_SCOPE_OBJS_ITERATOR)],
                           indirect=True)
  @pytest.mark.parametrize("mapped_obj", [
      objects.get_plural(next(
          objects.SINGULAR_STANDARDS_AND_REGULATIONS_ITERATOR)),
      objects.get_plural(next(objects.SINGULAR_SCOPE_OBJS_ITERATOR))])
  def test_cannot_map_disabled_obj_via_unified_mapper(self, obj, mapped_obj,
                                                      selenium):
    """Tests that user cannot map disabled object to existent "mapped_obj"
    via Unified Mapper."""
    obj_name = objects.get_plural(obj.type)
    service = factory.get_cls_webui_service(obj_name)()
    (service.open_obj_dashboard_tab().tree_view
     .open_tree_actions_dropdown_by_title(title=obj.title).select_map())
    map_modal = webui_facade.perform_disabled_mapping(
        factory.get_cls_entity_factory(mapped_obj)().create())
    browsers.get_browser().windows()[1].use()
    assert not map_modal.is_present, (
        "There should be no modal windows in new browser tab.")

  @pytest.mark.parametrize("obj", objects.SINGULAR_CONTROL_AND_RISK +
                           [next(objects.SINGULAR_SCOPE_OBJS_ITERATOR)],
                           indirect=True)
  @pytest.mark.parametrize("mapped_obj", [
      objects.get_plural(next(
          objects.SINGULAR_STANDARDS_AND_REGULATIONS_ITERATOR)),
      objects.get_plural(next(objects.SINGULAR_SCOPE_OBJS_ITERATOR))])
  def test_cannot_map_created_disabled_obj_via_um(self, obj, mapped_obj,
                                                  soft_assert, selenium):
    """Tests that user cannot map disabled object to newly created "mapped_obj"
    via Unified Mapper."""
    service = factory.get_cls_webui_service(objects.get_plural(obj.type))()
    (service.open_obj_dashboard_tab().tree_view
     .open_tree_actions_dropdown_by_title(title=obj.title).select_map())
    map_modal = webui_facade.perform_disabled_mapping(
        factory.get_cls_entity_factory(mapped_obj)().create(),
        create_new_obj=True)
    _, new_tab = browsers.get_browser().windows()
    test_utils.wait_for(lambda: new_tab.url.endswith(url.Widget.INFO))
    soft_assert.expect(new_tab.url == url.Urls().dashboard_info_tab,
                       "Dashboard info page should be opened in new tab.")
    webui_facade.soft_assert_no_modals_present(map_modal, soft_assert)
    soft_assert.expect(not any(
        [name.startswith(objects.get_normal_form(mapped_obj))
         for name in service.open_info_page_of_obj(obj).top_tabs.tab_names]),
        "There should be no {} mapped to {}.".format(mapped_obj, obj.type))
    soft_assert.assert_expectations()

  @pytest.mark.parametrize(
      "obj", objects.CONTROLS_AND_RISKS +
      (objects.get_plural(next(objects.SINGULAR_SCOPE_OBJS_ITERATOR)),))
  def test_cannot_create_disabled_obj_from_mapper(self, obj, program,
                                                  soft_assert, selenium):
    """Check that 'New object' modal is not opened when creator adds
    disabled object to a program."""
    webui_service.ProgramsService().open_tab_via_add_tab_btn(
        program, objects.get_normal_form(obj))
    webui_facade.soft_assert_no_modals_present(
        webui_facade.perform_disabled_mapping(
            factory.get_cls_entity_factory(obj)().create(),
            return_tree_items=True, create_new_obj=True),
        soft_assert)
    soft_assert.assert_expectations()

  @pytest.mark.parametrize("obj", objects.SINGULAR_CONTROL_AND_RISK +
                           [next(objects.SINGULAR_SCOPE_OBJS_ITERATOR)],
                           indirect=True)
  def test_objects_mapping_via_add_tab_restrictions(
          self, obj, soft_assert, selenium):
    """Tests that user cannot map disabled objects to scope objects/directives
    and standard/regulation objects to scope/disabled objects via 'Add Tab'
    menu."""
    info_page = factory.get_cls_webui_service(objects.get_plural(
        obj.type))().open_info_page_of_obj(obj)
    for h_item in info_page.get_hidden_items_from_add_tab():
      info_page.open_add_tab_dropdown()
      h_item.click()
      test_utils.wait_for(lambda: browsers.get_browser().windows()[1]
                          .url.endswith(url.Widget.INFO))
      soft_assert.expect(webui_facade.are_tabs_urls_equal(),
                         "Tabs urls should be equal.")
      webui_facade.soft_assert_no_modals_present(
          unified_mapper.BaseUnifiedMapperModal(), soft_assert)
      old_tab, new_tab = browsers.get_browser().windows()
      old_tab.use()
      new_tab.close()
    soft_assert.assert_expectations()
