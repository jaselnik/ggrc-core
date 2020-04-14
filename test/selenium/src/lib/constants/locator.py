# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Locators for all elements."""
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-lines
# pylint: disable=invalid-name
# pylint: disable=super-init-not-called

from selenium.webdriver.common.by import By

from lib.constants import objects


class Common(object):
  """Common locators."""
  TITLE = " .title"
  DESCRIPTION = " .description"
  SPINNER = ".spinner"
  SPINNER_CSS = (By.CSS_SELECTOR, SPINNER)
  # modal
  MODAL_CREATE = ".modal-wide"
  MODAL_CONFIRM = ".modal.hide"
  MODAL_MAPPER = ".modal-selector"
  MODAL_FOOTER = " .modal-footer"
  MODAL_BODY = " .modal-body"
  MODAL_FILTER = " .modal-filter"
  MODAL_HEADER = " .modal-header"
  # info page (panel)
  _INFO = "info"
  INFO = "." + _INFO
  _INFO_WIDGET = "info"
  INFO_WIDGET_ID = "#" + _INFO_WIDGET
  # dropdown
  DROPDOWN_MENU = ".dropdown-menu"
  # tree
  TREE_LIST = " .tree-action"
  TREE_HEADER = ".tree-header"
  TREE_ITEM = " .object-list__item"
  TREE_SPINER = " .tree-spinner"
  # base
  BUTTON = "BUTTON_"
  BUTTON_CREATE_NEW = "BUTTON_CREATE_NEW_"
  COUNT = "COUNT_"
  SPINNY = "SPINNY_"
  ACCORDION_MEMBERS = "ACCORDION_MEMBERS_"
  TOGGLE = "TOGGLE_"
  # attrs values
  DISABLED_VALUE = "disabled-original"
  MAX = "max"
  NORMAL = "normal"
  DOWN = "down"
  # list item delimiter
  HTML_LIST_CSS = (By.CSS_SELECTOR, 'ul')
  # xpath helper
  XPATH_NOT_HIDDEN = "[not(ancestor::section[contains(@class, 'hidden')])]"
  INFO_WIDGET_XPATH = (
      "//section[contains(@class,'{}')]".format(_INFO) + XPATH_NOT_HIDDEN)
  INFO_PAGE_XPATH = (
      "//section[contains(@class,'{}')]".format(_INFO_WIDGET) +
      XPATH_NOT_HIDDEN)
  # import / export pages
  CONTENT = ".content"
  OPTION = "option"
  # panel locator
  PANEL_CSS = (By.CSS_SELECTOR, ".pin-content.pin-content")
  OBJECT_AREA_CSS = (By.CSS_SELECTOR, ".object-area")
  # widgets
  WDG_NOT_HIDDEN = ".widget:not(.hidden) "


class CommonAssessment(object):
  """Common Assessment locators for Modal and Info."""
  MAP_OBJS_BTN = " map-button-using-assessment-type"
  MAP_OBJS_BTN_CSS = (By.CSS_SELECTOR, MAP_OBJS_BTN)
  MAPPED_SNAPSHOTS = " .mapped-objects__item.mapped-snapshot-item"
  MAPPED_SNAPSHOTS_CSS = (By.CSS_SELECTOR, MAPPED_SNAPSHOTS)
  MAPPED_SNAPSHOT_TITLE_CSS = (
      By.CSS_SELECTOR, MAPPED_SNAPSHOTS + Common.TITLE)
  MAPPED_SNAPSHOT_DESCRIPTION_CSS = (
      By.CSS_SELECTOR, MAPPED_SNAPSHOTS + Common.DESCRIPTION)


class Login(object):
  """Locators for Login page."""
  BUTTON_LOGIN = (By.CSS_SELECTOR, "a.btn.btn-large.btn-lightBlue")


class PageHeader(object):
  """Locators for Dashboard header."""
  _CONTENT = ".header-content"
  SRC_OBJ_TITLE = (By.CSS_SELECTOR, _CONTENT + " .entity-name")
  TOGGLE_LHN = (By.CSS_SELECTOR, ".lhn-trigger")
  BUTTON_DASHBOARD = (
      By.CSS_SELECTOR, _CONTENT + ' .to-my-work[href="/dashboard"]')
  BUTTON_SEARCH = (
      By.CSS_SELECTOR, _CONTENT + ' [data-toggle="unified-search"]')
  BUTTON_MY_TASKS = (
      By.CSS_SELECTOR, _CONTENT + ' [href="/dashboard#!task"]')
  BUTTON_ALL_OBJECTS = (
      By.CSS_SELECTOR, _CONTENT + ' [href^="/objectBrowser"]')
  TOGGLE_USER_DROPDOWN = (By.CSS_SELECTOR, _CONTENT + " .dropdown-toggle")
  GENERIC_SUCCESS_ALERT = (By.CSS_SELECTOR, ".alert-success")
  BUTTON_DATA_IMPORT = (
      By.CSS_SELECTOR, _CONTENT + ' [href="/import"]')
  BUTTON_DATA_EXPORT = (
      By.CSS_SELECTOR, _CONTENT + ' [href="/export"]')
  # dropdown toggle
  USER_MENU = ".menu " + Common.DROPDOWN_MENU
  BUTTON_HELP = (By.CSS_SELECTOR, Common.DROPDOWN_MENU +
                 ' [href="#set_GGRC_EXTERNAL_HELP_URL_env_var"]')
  BUTTON_LOGOUT = (By.CSS_SELECTOR, Common.DROPDOWN_MENU + ' [href="/logout"]')
  NOTIFICATIONS = (By.CSS_SELECTOR, USER_MENU + ' notifications-menu-item')
  EMAIL = (By.CSS_SELECTOR, USER_MENU + ' .dropdown-menu__user-name')
  BUTTON_ADMIN_DASHBOARD = (
      By.CSS_SELECTOR,
      Common.DROPDOWN_MENU + ' [href="/admin#!people_list"]')
  CHECKBOX_DAILY_DIGEST = (By.CSS_SELECTOR, USER_MENU + ' input')
  CHECKBOX_DISABLED = (By.CSS_SELECTOR, USER_MENU + ' input.disabled')


class Dashboard(object):
  """Locators for Dashboard page."""
  _GET_LIST = ".get-started__list"
  # get started (user input elements)
  START_NEW_PROGRAM_BTN_CSS = (
      By.CSS_SELECTOR, _GET_LIST + ' [data-object-singular="Program"]')
  START_NEW_AUDIT_BTN_CSS = (
      By.CSS_SELECTOR, _GET_LIST + ' [data-object-singular="Audit"]')
  START_NEW_WORKFLOW_BTN_CSS = (
      By.CSS_SELECTOR, _GET_LIST + ' [data-object-singular="Workflow"]')
  CREATE_TASK_BTN_CSS = (
      By.CSS_SELECTOR, _GET_LIST +
      ' [data-object-singular="CycleTaskGroupObjectTask"]')
  CREATE_OBJECT_BTN_CSS = (
      By.CSS_SELECTOR, _GET_LIST + ' [href="javascript:void(0)"]')
  ALL_OBJECTS_BTN_CSS = (
      By.CSS_SELECTOR, _GET_LIST + ' [href="/objectBrowser"]')


class LhnMenu(object):
  """Locators for Menu in header"""
  class _Locator(object):
    """Locators for LHN menu."""

    @staticmethod
    def get_accordion_button(label):
      return (By.CSS_SELECTOR, '[data-model-name="{}"]>a'.format(label))

    @staticmethod
    def get_create_new_button(label):
      # Controls cannot be created from UI.
      if label == objects.get_singular(objects.CONTROLS, title=True):
        return(By.CSS_SELECTOR,
               ('[data-model-name="{}"] '
                'ul.sub-actions li.add-new a').format(label))
      if label == objects.get_singular(objects.ASSESSMENTS, title=True):
        return(By.CSS_SELECTOR,
               ('[data-model-name="{}"] '
                '[data-object-singular="{}"]').format(label, label))
      return (
          By.CSS_SELECTOR,
          '[data-model-name="{}"] [class="add-new oneline"]'.format(label))

    @staticmethod
    def get_accordion_count(label):
      return (
          By.CSS_SELECTOR, '[data-model-name="{}"] .item-count'.format(label))

    @staticmethod
    def get_accordion_members(object_name):
      return (
          By.CSS_SELECTOR,
          '[data-model-name="{}"]>.content>.sub-level>li'.format(object_name))

    @staticmethod
    def get_spinny(object_name):
      return (
          By.CSS_SELECTOR,
          '[data-model-name="{}"] .spinny .spinner'.format(object_name))

  class __metaclass__(type):
    def __init__(cls, *args):
      for object_singular, object_plural in (zip(objects.ALL_SINGULAR,
                                                 objects.ALL_PLURAL)):
        capitalized_name = object_singular.title()
        # handle underscore in object names
        if "_" in capitalized_name:
          capitalized_name = capitalized_name.title().replace("_", "")
        # set lhn items
        setattr(cls, Common.TOGGLE + object_plural,
                cls._Locator.get_accordion_button(capitalized_name))
        setattr(cls, Common.BUTTON_CREATE_NEW + object_plural,
                cls._Locator.get_create_new_button(capitalized_name))
        setattr(cls, Common.COUNT + object_plural,
                cls._Locator.get_accordion_count(capitalized_name))
        setattr(cls, Common.SPINNY + object_plural,
                cls._Locator.get_spinny(capitalized_name))
        setattr(cls, Common.ACCORDION_MEMBERS + object_plural,
                cls._Locator.get_accordion_members(capitalized_name))
  # user input elements
  LHN_MENU = (By.ID, "lhn")
  MODAL = (By.CSS_SELECTOR, '[id="ajax-lhn_modal-javascript:--"]')
  EXTENDED_INFO = (By.CSS_SELECTOR, ".extended-info.in")
  HOLDER = (By.CSS_SELECTOR, '.lhs-holder')
  FILTER = (By.CSS_SELECTOR, ".lhs-search")
  FILTER_TEXT_BOX = (By.CSS_SELECTOR, ".lhs-search>.widgetsearch")
  FILTER_SUBMIT_BUTTON = (By.CSS_SELECTOR, ".lhs-search>.widgetsearch-submit")
  FILTER_CLEAR_BUTTON = (
      By.CSS_SELECTOR, '.lhs-search [data-title="Clear filters"]')
  ALL_OBJECTS = (By.CSS_SELECTOR, '[data-test-id="all_objects_e0345ec4"]')
  MY_OBJECTS = (By.CSS_SELECTOR, '[data-test-id="my_objects_6fa95ae1"]')
  PIN = (By.CSS_SELECTOR, ".lhn-pin")
  # LHN items
  DIRECTIVES = (By.CSS_SELECTOR, '[data-test-id="directives_66116337"]')
  CONTROLS_OR_OBJECTIVES = (
      By.CSS_SELECTOR, '[data-test-id="controls/objectives_66116337"]')
  PEOPLE_OR_GROUPS = (
      By.CSS_SELECTOR, '[data-test-id="people/groups_66116337"]')
  SCOPE = (
      By.CSS_SELECTOR, '[data-test-id="scope_66116337"]')
  RISK_OR_THREATS = (
      By.CSS_SELECTOR, '[data-test-id="risk/threats_66116337"]')
  # workflows labels
  BUTTON_WORKFLOWS_ACTIVE = (
      By.CSS_SELECTOR, '[data-for="Workflow"]>[data-value="Active"]')
  BUTTON_WORKFLOWS_DRAFT = (
      By.CSS_SELECTOR, '[data-for="Workflow"]>[data-value="Draft"]')
  BUTTON_WORKFLOWS_INACTIVE = (
      By.CSS_SELECTOR, '[data-for="Workflow"]>[data-value="Inactive"]')
  BUTTON_CREATE_NEW_NO = (By.CSS_SELECTOR, '.sub-actions.in')


class ExportItem(object):
  """Locators for Export items on Export page."""
  DOWNLOAD_CSV_XPATH = (
      By.XPATH, ".//button[normalize-space()='Download CSV']")


class ExportPage(object):
  """Locators for Export page."""
  _CONTENT = Common.CONTENT
  _EXPORT_PAGE = _CONTENT + " #csv_export"
  EXPORT_PAGE_CSS = (By.CSS_SELECTOR, _EXPORT_PAGE)
  ADD_OBJECT_TYPE_BTN_XPATH = (
      By.XPATH, "//button[normalize-space()='Add Object Type']")
  EXPORT_OBJECTS_BTN_CSS = (By.CSS_SELECTOR, "#export-csv-button")
  EXPORT_ITEM_CSS = (By.CSS_SELECTOR, ".current-exports__item")


class ExtendedInfo(object):
  """Locators for Extended info tooltip in LHN after hovering over
 member object."""
  # labels
  TITLE = (By.CSS_SELECTOR, "#extended-info .main-title")


class CommonModalUnifiedMapper(object):
  """Common locators for unified mapper modals."""
  # pylint: disable=invalid-name
  MODAL = Common.MODAL_MAPPER
  MODAL_CSS = (By.CSS_SELECTOR, MODAL)
  MODAL_FILTER = Common.MODAL_FILTER
  FILTER_TOGGLE_CSS = (By.CSS_SELECTOR,
                       MODAL_FILTER +
                       " button.collapsible-panel-header__toggle-button")
  FILTER_ADD_ATTRIBUTE_BTN = (By.XPATH, "//button[text()='Add Attribute']")
  FILTER_ROW_CSS = (By.CSS_SELECTOR, ".filter-container__attribute")
  FILTER_OPERATOR = (By.CSS_SELECTOR, ".filter-operator__content select")
  FILTER_ATTRIBUTE_NAME = (
      By.CSS_SELECTOR, ".filter-attribute__name autocomplete-dropdown")
  FILTER_ATTRIBUTE_COMPARE = (
      By.CSS_SELECTOR, ".filter-attribute__operator select")
  FILTER_ATTRIBUTE_VALUE = (By.CSS_SELECTOR, ".filter-attribute__value input")
  MODAL_TITLE = (By.CSS_SELECTOR, MODAL + " h2")
  OBJ_TYPE = (By.CSS_SELECTOR, MODAL + " .object-controls__type h6")
  # user input elements
  OBJ_TYPE_DROPDOWN = (By.CSS_SELECTOR, MODAL + " .input-block-level")
  BUTTON_SEARCH = (By.CSS_SELECTOR, MODAL + " button[type='submit']")
  FOUND_MAPPER_RESULTS_CSS = "mapper-results .list-object-item"
  FOUND_OBJECTS_TITLES = (
      By.CSS_SELECTOR, MODAL + " .flex-box .attr:first-child")
  FOUND_OBJECTS_CHECKBOXES = (By.CSS_SELECTOR,
                              MODAL + ' .flex-box [type="checkbox"]')
  BUTTON_MAP_SELECTED = (By.CSS_SELECTOR, MODAL + Common.MODAL_FOOTER +
                         " .btn-map")
  RESULT_TOGGLE_CSS = (By.CSS_SELECTOR, MODAL + Common.MODAL_FOOTER +
                       " button.collapsible-panel-header__toggle-button")
  CLOSE_BTN_CSS = (By.CSS_SELECTOR,
                   MODAL + Common.MODAL_HEADER + " a.modal-dismiss")
  MODAL_SECTIONS = (By.CLASS_NAME, 'body-inner')


class ModalMapObjects(CommonModalUnifiedMapper):
  """Locators for map objects modals."""
  MODAL = Common.MODAL_MAPPER
  # user input elements
  BUTTON_CREATE_OBJ = (By.CSS_SELECTOR, MODAL + " .create-control")


class ModalSearchObjects(CommonModalUnifiedMapper):
  """Locators for search objects modals."""
  MODAL = Common.MODAL_MAPPER


class ModalGenerateAssessments(CommonModalUnifiedMapper):
  """Locators for generate Assessments modal."""
  MODAL = Common.MODAL_MAPPER


class ModalCloneOrCreateAssessmentTemplates(CommonModalUnifiedMapper):
  """Locators for clone or create Assessment Templates modal."""
  MODAL = Common.MODAL_MAPPER
  CREATE_ASMT_TMPL_BTN_CSS = (By.CSS_SELECTOR, MODAL + " .create-control")


class ModalCustomAttribute(object):
  """Locators for generic custom attributes modal in Admin Dashboard."""
  MODAL_CSS = (By.CSS_SELECTOR, Common.MODAL_CONFIRM)
  MODAL_TITLE_LBL_CSS = (By.CSS_SELECTOR, Common.MODAL_HEADER + " h2")
  ATTR_TITLE_UI_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + ' input[name="title"]')
  SAVE_AND_CLOSE_BTN_CSS = (
      By.CSS_SELECTOR,
      Common.MODAL_FOOTER + ' .confirm-buttons [data-toggle="modal-submit"]')
  ATTR_TITLE_LBL_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + " div:nth-child(1)>label")
  ATTR_TYPE_CSS = (By.CSS_SELECTOR, Common.MODAL_HEADER + " h2")
  ATTR_TYPE_SELECTOR_DD_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + " dropdown-component select")
  MANDATORY_LBL_CSS = (By.CSS_SELECTOR, Common.MODAL_BODY + " .span2 label")
  MANDATORY_CB_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + ' [type="checkbox"]')
  INLINE_HELP_LBL_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + " div:nth-child(2)>label")
  INLINE_HELP_UI_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + ' [name="helptext"]')
  PLACEHOLDER_LBL_CSS = (By.CSS_SELECTOR, Common.MODAL_BODY + " .span6 label")
  PLACEHOLDER_UI_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + ' [name="placeholder"]')
  POSSIBLE_VALUES_UI_CSS = (
      By.CSS_SELECTOR, Common.MODAL_BODY + ' [name="multi_choice_options"]')
  ADD_ANOTHER_BTN_CSS = (
      By.CSS_SELECTOR,
      Common.MODAL_FOOTER +
      ' .confirm-buttons [data-toggle="modal-submit-addmore"]')


class ModalSetVisibleFields(object):
  """Locators for Set visible fields modals."""
  MODAL = ".open .visible-columns-list"
  # labels
  MODAL_TITLE = MODAL + " h5"
  ATTR_LIST = " .attr-list"
  FIELDS_TITLES = MODAL + ATTR_LIST + " .checkbox-inline"
  # user input elements
  FIELDS_CHECKBOXES = MODAL + ATTR_LIST + " .attr-checkbox"
  BUTTON_SET_FIELDS = MODAL + " .set-tree-attrs"


class ModalSetVisibleFieldsMapper(ModalSetVisibleFields):
  """Locators for Set visible fields modals."""
  MODAL = ".modal"
  # labels
  MODAL_TITLE = MODAL + " h5"
  ATTR_LIST = ModalSetVisibleFields.ATTR_LIST
  FIELDS_TITLES = MODAL + ATTR_LIST + " .checkbox-inline"
  # user input elements
  FIELDS_CHECKBOXES = MODAL + ATTR_LIST + " .attr-checkbox"
  BUTTON_SET_FIELDS = MODAL + " .set-tree-attrs"


class ModalRelatedAssessments(object):
  """Locators for related assessments modal on Control and Objective pages"""
  MODAL = (By.CSS_SELECTOR, ".related-assessments")


class ModalSetValueForAsmtCA(object):
  """Locators for set value for assessment custom attribute."""
  MODAL = "//div[@class = 'in']//div[@class = 'simple-modal ']"
  MODAL_LOCATOR = (By.XPATH, MODAL)
  MODAL_HEADER = (
      By.XPATH, MODAL + "//div[@class = 'simple-modal__header-text']")
  BUTTON_CLOSE = (By.XPATH, MODAL + "//button[text() = 'Close']")
  BUTTON_SAVE = (By.XPATH, MODAL + "//button[text() = 'Save']")
  INPUT_COMMENT = (By.XPATH, MODAL + "//div[text() = 'Comment']/parent::div"
                                     "//div[contains(@class, 'ql-editor')]")
  BUTTON_ADD_URL = (By.XPATH, MODAL + "//div[text() = 'Evidence url']"
                                      "/parent::div//button[text() = 'Add']")
  INPUT_EVIDENCE_URL = (By.XPATH, MODAL + "//div[text() = 'Evidence url']"
                                          "/parent::div//input")
  BUTTON_CONFIRM_URL = (
      By.XPATH, MODAL + "//div[text() = 'Evidence url']/parent::div"
                        "//button[@class = 'create-form__confirm']")


class WidgetBar(object):
  """Locators for bar containing widgets/tabs."""

  class _Locator(object):
    """Locators for Menu in header."""
    @staticmethod
    def get_widget(object_name):
      return (By.CSS_SELECTOR,
              '#inner-nav [href$="#!{}"]'.format(object_name))

  class __metaclass__(type):
    def __init__(cls, *args):
      for object_singular, object_plural in (zip(objects.ALL_SINGULAR,
                                                 objects.ALL_PLURAL)):
        name = object_singular.lower()
        setattr(cls, object_plural, cls._Locator.get_widget(name))
  BUTTON_ADD = (
      By.CSS_SELECTOR, '[data-test-id="button_widget_add_2c925d94"]')
  TAB_WIDGET = (By.CSS_SELECTOR, "#inner-nav .active")
  ADMIN_PEOPLE = _Locator.get_widget("people_list")
  ADMIN_ROLES = _Locator.get_widget("roles_list")
  ADMIN_EVENTS = _Locator.get_widget("events_list")
  ADMIN_CUSTOM_ATTRIBUTE = _Locator.get_widget("custom_attribute")
  ADMIN_CUSTOM_ROLES = _Locator.get_widget("custom_roles")
  INFO = _Locator.get_widget("info")
  CUSTOM_ATTRIBUTES = _Locator.get_widget("custom_attribute")
  EVENTS = _Locator.get_widget("events_list")
  ROLES = _Locator.get_widget("roles_list")
  TASKS = _Locator.get_widget("task")
  DASHBOARD_TAB = _Locator.get_widget("dashboard")


class WidgetBarButtonAddDropdown(object):
  """Locators for button/dropdown "Add widget" in Widget bar."""
  class _Locator(object):
    """Toggle locators for Widget custom attributes in Admin Dashboard."""
    @staticmethod
    def get_dropdown_item(object_name):
      return (
          By.CSS_SELECTOR,
          '[data-test-id="button_widget_add_2c925d94"] '
          '#inner-nav [href$="#{}"]'.format(object_name))

  class __metaclass__(type):
    def __init__(cls, *args):
      for object_ in objects.ALL_PLURAL:
        name = object_.lower()
        setattr(cls, object_, cls._Locator.get_dropdown_item(name))
  THREAD_ACTORS = _Locator.get_dropdown_item("threat_actor")
  WORKFLOW_TASKS = _Locator.get_dropdown_item("workflow_task")
  ALL_MAPPABLE_WIDGETS_OBJS = (
      By.CSS_SELECTOR, ".inner-nav-item a[data-toggle='unified-mapper']")


class ObjectWidget(object):
  """Locators for Generic objects widget."""
  _HEADER = '.header [class^="span"]'
  _STATE = 'div.state-value'
  HEADER_TITLE = (By.CSS_SELECTOR, _HEADER + ' [data-field="title"]')
  HEADER_OWNER = (
      By.CSS_SELECTOR, _HEADER + ' [data-field="owners"]')
  HEADER_STATE = (By.CSS_SELECTOR, _STATE)
  HEADER_STATE_IN_PROGRESS = (By.CSS_SELECTOR, _STATE + '.state-inprogress')
  HEADER_STATE_COMPLETED = (By.CSS_SELECTOR, _STATE + '.state-completed')
  HEADER_STATE_READY_FOR_REVIEW = (
      By.CSS_SELECTOR, _STATE + '.state-readyforreview')
  HEADER_STATE_VERIFIED = (By.CSS_SELECTOR, _STATE + '.state-verified')

  HEADER_LAST_ASSESSMENT_DATE = (
      By.CSS_SELECTOR, _HEADER + ' [data-field="last_assessment_date"]')
  MEMBERS_TITLE_LIST = (
      By.CSS_SELECTOR,
      '.object-area .widget.treeview:not(.hidden) .tree-item-element '
      '.selectable-attrs .attr-cell:first-child .attr-content')
  INFO_PANE = (By.CSS_SELECTOR, '.sticky-info-panel')
  LOADING = (By.CSS_SELECTOR, '.new-tree_loading')


class ModalCommonConfirmAction(object):
  """Locators for Confirm actions with objects modals."""
  MODAL = Common.MODAL_CONFIRM
  # labels
  MODAL_TITLE = (By.CSS_SELECTOR, "{} .modal-header h2".format(MODAL))
  CONFIRMATION_TEXT = (By.CSS_SELECTOR, "{} .modal-body p".format(MODAL))
  # user input elements
  BUTTON_CONFIRM = (By.CSS_SELECTOR,
                    "{} .modal-footer .btn-small".format(MODAL))


class ModalDeleteObject(ModalCommonConfirmAction):
  """Locators for Delete object modals."""
  MODAL = Common.MODAL_CONFIRM
  OBJECT_TITLE = (By.CSS_SELECTOR, "{} .modal-body span".format(MODAL))
  BUTTON_DELETE = ModalCommonConfirmAction.BUTTON_CONFIRM


class ModalCloneAudit(ModalCommonConfirmAction):
  """Locators for Clone object modals."""
  MODAL = Common.MODAL_CONFIRM
  CHECKBOX_CLONE_ASMT_TMPLS = (
      By.CSS_SELECTOR, '{} .modal-body input[type="checkbox"]'.format(MODAL))


class TabContainer(object):
  TAB_CONTROLLER_CSS = (By.CSS_SELECTOR, "ul.nav.nav-tabs")
  TAB_CONTENT_CSS = (By.CSS_SELECTOR, '.tab-pane.active')


class WidgetAdminRoles(object):
  """Locators for Roles widget on Admin Dashboard."""


class WidgetAdminEvents(object):
  """Locators for Events widget on Admin Dashboard."""
  _BASE_CSS_SELECTOR = 'section#events_list:not([class~="hidden"])'
  TREE_VIEW_ITEMS = "{0} .tree-item[data-model]".format(_BASE_CSS_SELECTOR)
  TREE_VIEW_HEADER = (
      By.CSS_SELECTOR, "{} header".format(_BASE_CSS_SELECTOR))
  TREE_VIEW_ITEMS_W_PPL = (
      By.XPATH,
      "//section[@id='events_list']" +
      "//*[@class='person-name' and contains(text(), '@')]")


class WidgetAdminPeople(object):
  """Locators for People widget on Admin Dashboard."""
  FILTER_BY_NAME_EMAIL_COM_FIELD_SELECTOR = (
      By.CSS_SELECTOR, "[name=search]")
  CREATE_PERSON_BUTTON_SELECTOR = (
      By.CSS_SELECTOR, '.create-button')


class CommonDropdownMenu(object):
  """Locators for common drop down elements."""
  _DROPDOWN_MAIN = 'ul'
  _DROPDOWN_ITEMS = 'li'
  _DROPDOWN_ITEM_ICON = 'i'
  DROPDOWN_MAIN_CSS = (By.CSS_SELECTOR, _DROPDOWN_MAIN)
  DROPDOWN_ITEMS_CSS = (By.CSS_SELECTOR, _DROPDOWN_ITEMS)
  DROPDOWN_ITEM_ICON_CSS = (By.CSS_SELECTOR, _DROPDOWN_ITEM_ICON)
  DROPDOWN_OPTIONS = (By.CSS_SELECTOR, Common.OPTION)


class CommonDropdown3bbsInfoWidget(CommonDropdownMenu):
  """Locators for common settings 3BBS dropdown on Info widget and Info page.
  """
  _INFO_3BBS_DD_XPATH = (
      Common.INFO_WIDGET_XPATH +
      "//*[contains(@class, 'tree-action-list-items')]")
  INFO_WDG_3BBS_DD_XPATH = (By.XPATH, _INFO_3BBS_DD_XPATH)


class AuditsDropdown3bbsInfoWidget(CommonDropdown3bbsInfoWidget):
  """Locators for Audit settings 3BBS dropdown on Info page and Info panel.
  """


class CommonDropdown3bbsTreeView(CommonDropdownMenu):
  """Locators for common settings 3BBS dropdown on Tree View."""
  TREE_VIEW_3BBS_DD = (
      Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .tree-action-list-items")
  # user input elements
  TREE_VIEW_3BBS_DD_CSS = (By.CSS_SELECTOR, TREE_VIEW_3BBS_DD)
  BTN_3BBS_IMPORT_CSS = (By.CSS_SELECTOR,
                         TREE_VIEW_3BBS_DD + " .fa-cloud-upload")
  BTN_3BBS_EXPORT_CSS = (By.CSS_SELECTOR, TREE_VIEW_3BBS_DD + " .fa-download")
  BTN_3BBS_SELECT_CHILD_TREE_CSS = (By.CSS_SELECTOR,
                                    TREE_VIEW_3BBS_DD + " .fa-share-alt")


class AssessmentsDropdown3bbsTreeView(CommonDropdown3bbsTreeView):
  """Locators for Assessments settings 3BBS dropdown on Tree View."""
  BTN_3BBS_GENERATE_CSS = (
      By.CSS_SELECTOR,
      CommonDropdown3bbsTreeView.TREE_VIEW_3BBS_DD + " .fa-magic")


class Assessments(object):
  SHOW_GENERATED_ASSESSMENTS = (By.CSS_SELECTOR, ".reload-link")


class TreeView(object):
  """Locators for Tree View components."""
  # common
  TREE_VIEW_CONTAINER_CSS = (
      By.CSS_SELECTOR, Common.WDG_NOT_HIDDEN + " tree-widget-container>div")
  ITEMS = Common.WDG_NOT_HIDDEN + " .tree-item-element"
  HEADER = Common.WDG_NOT_HIDDEN + Common.TREE_HEADER
  ITEM_LOADING_CSS = (By.CSS_SELECTOR, " .tree-item-placeholder")
  ITEM_EXPAND_BTN = " tree-item-actions"
  ITEM_DD_MENU_CSS = Common.HTML_LIST_CSS
  TREE_SPINNER_CSS = (By.CSS_SELECTOR, Common.TREE_SPINER)
  NO_RESULTS_MSG_CSS = (
      By.CSS_SELECTOR, Common.WDG_NOT_HIDDEN + " .tree-no-results-message")
  SHOW_FIELDS_BTN_CSS = (
      By.CSS_SELECTOR,
      Common.WDG_NOT_HIDDEN + Common.TREE_HEADER + " .fa-bars")
  # user input elements
  BTN_3BBS_CSS = (By.CSS_SELECTOR,
                  Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .details-wrap")
  CREATE_BTN_CSS = (
      By.CSS_SELECTOR,
      Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .create-button")
  MAP_BTN_CSS = (By.CSS_SELECTOR,
                 Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .map-button")
  ITEM_DD_BTN_CSS = (
      By.CSS_SELECTOR, Common.WDG_NOT_HIDDEN + ITEM_EXPAND_BTN)


class AdminTreeView(object):
  """Locators for Tree View components in Admin dashboard."""
  # common
  ITEMS = "li.tree-item .item-main"
  ITEM_LOADING_CSS = (By.CSS_SELECTOR, " .tree-item-placeholder")
  ITEM_EXPAND_BTN = " .openclose"
  TREE_SPINNER_CSS = (By.CSS_SELECTOR, Common.TREE_SPINER)
  NO_RESULTS_MSG_CSS = (By.CSS_SELECTOR, ".tree-no-results-message")
  SHOW_FIELDS_BTN_CSS = (
      By.CSS_SELECTOR,
      Common.WDG_NOT_HIDDEN + Common.TREE_HEADER + " .fa-bars")
  # user input elements
  BTN_3BBS_CSS = (By.CSS_SELECTOR,
                  Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .btn-draft")
  CREATE_BTN_CSS = (
      By.CSS_SELECTOR,
      Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .create-button")
  MAP_BTN_CSS = (By.CSS_SELECTOR,
                 Common.WDG_NOT_HIDDEN + Common.TREE_LIST + " .map-button")


class UnifiedMapperTreeView(TreeView):
  """Common locators for UnifiedMapper from Tree View"""
  MODAL = ".object-modal"
  HEADER = MODAL + " .list-header"
  ITEMS = MODAL + " mapper-results-item"
  SHOW_FIELDS_BTN_CSS = (By.CSS_SELECTOR, HEADER + " .fa-bars")
  NO_RESULTS_MSG_CSS = (By.CSS_SELECTOR,
                        "object-selection .well-small:not(.hidden)")
  MAPPER_TREE_SPINNER_NO_RESULT = (
      By.CSS_SELECTOR, ".no-items-spinner-wrapper spinner-component")
  MAPPER_TREE_SPINNER_ITEMS = (
      By.CSS_SELECTOR, ".spinner-section.spinner-section_grid  .spinner-icon")


class BaseWidgetGeneric(object):
  """Locators for non Info and Admin widgets."""
  # pylint: disable=invalid-name
  _FILTER_BTN = (
      Common.WDG_NOT_HIDDEN + "tree-filter-input .tree-filter__actions")
  _FILTER_DD = Common.WDG_NOT_HIDDEN + "tree-status-filter"
  _FILTER_DD_ELEMENTS = (_FILTER_DD + " .multiselect-dropdown__element")
  TXTFIELD_TO_FILTER_CSS = (By.CSS_SELECTOR,
                            Common.WDG_NOT_HIDDEN + ".tree-filter__input")
  FILTER_BTN_CSS = (By.CSS_SELECTOR, _FILTER_BTN + ' [type="submit"]')
  HELP_BTN_CSS = (By.CSS_SELECTOR, _FILTER_BTN + " #page-help")
  DD_CSS = (By.CSS_SELECTOR,
            _FILTER_DD + " .multiselect-dropdown__input-container")
  DD_STATES_CSS = (By.CSS_SELECTOR, _FILTER_DD_ELEMENTS)
  PAGINATION_CONTROLLERS_CSS = (
      By.CSS_SELECTOR, Common.WDG_NOT_HIDDEN + ".tree-pagination.flex-box")


class AdminCustomAttributes(object):
  """Locators for Widget custom attributes on Admin Dashboard."""

  class _Locator(object):
    """Locators for Widget custom attributes on Admin Dashboard."""
    @staticmethod
    def get_toggle(child_id):
      return (By.CSS_SELECTOR, '#custom_attribute li:nth-child({}) '
              '.openclose'.format(child_id))

    @staticmethod
    def get_programs_label(child_id):
      return (
          By.CSS_SELECTOR,
          '.tree-structure li:nth-child(5) div thead>tr>th:nth-child({})'
            .format(child_id))

  class __metaclass__(type):
    def __init__(cls, *args):
      items = (
          objects.WORKFLOWS, objects.THREATS,
          objects.RISKS, objects.PROGRAMS, objects.AUDITS,
          objects.OBJECTIVES, objects.REQUIREMENTS, objects.CONTROLS,
          objects.ISSUES, objects.ASSESSMENTS, objects.STANDARDS,
          objects.REGULATIONS, objects.POLICIES, objects.CONTRACTS,
          objects.VENDORS, objects.PEOPLE,
          objects.ACCESS_GROUPS, objects.ACCOUNT_BALANCES, objects.ORG_GROUPS,
          objects.PRODUCTS, objects.MARKETS, objects.PROCESSES,
          objects.FACILITIES, objects.KEY_REPORTS, objects.PROJECTS,
          objects.DATA_ASSETS, objects.SYSTEMS)
      for id_, name in enumerate(items, start=1):
        setattr(cls,
                Common.TOGGLE + name.upper(),
                cls._Locator.get_toggle(id_))
  FILTER_INPUT_FIELD = (By.CLASS_NAME, 'tree-filter__expression-holder')
  FILTER_BUTTON_SUBMIT = (By.CSS_SELECTOR,
                          '.tree-filter__button>[type="submit"]')
  FILTER_BUTTON_RESET = (By.CSS_SELECTOR,
                         '.tree-filter__button>[type="reset"]')
  # programs dropdown
  PROGRAMS_LABEL_ATTRIBUTE_NAME = _Locator.get_programs_label(1)
  PROGRAMS_LABEL_ATTRIBUTE_TYPE = _Locator.get_programs_label(2)
  PROGRAMS_LABEL_MANDATORY = _Locator.get_programs_label(3)
  PROGRAMS_LABEL_EDIT = _Locator.get_programs_label(4)
  LISTED_MEMBERS = (
      By.CSS_SELECTOR, '.tree-structure li:nth-child(5) div tbody>tr')
  BUTTON_LISTED_MEMBERS_EDIT = (
      By.CSS_SELECTOR,
      '.tree-structure li:nth-child(5) div tbody>tr>td>ul .fa-pencil-square-o')
  CA_ADDED_SUCCESS_ALERT = PageHeader.GENERIC_SUCCESS_ALERT


class CustomAttributesItemContent(AdminCustomAttributes):
  """Locators for expanded view of custom attribute group
  in admin dashboard."""
  _TREE_ITEM = ".tree-item"
  TREE_ITEM_EL_OPENED_CSS = (By.CSS_SELECTOR, _TREE_ITEM + ".item-open")
  CONTENT_OPEN = ".content-open .tier-2-info-content"
  TREE_STRUCTURE = (
      CONTENT_OPEN + " .tree-structure .tree-view-node")
  TITLES_ROW_CSS = (By.CSS_SELECTOR, CONTENT_OPEN + " thead tr")
  ROW_CSS = (By.CSS_SELECTOR, TREE_STRUCTURE)
  CELL_IN_ROW_CSS = (By.CSS_SELECTOR, "td")
  ADD_BTN_CSS = (By.CSS_SELECTOR, CONTENT_OPEN + " .add-item .btn")
  TREE_SPINNER_CSS = (By.CSS_SELECTOR, Common.TREE_SPINER)


class MultiInputField(object):
  """Locators for multi input field."""
  _form = ".create-form__layout"
  ADD_BTN_CSS = (By.CSS_SELECTOR, ".btn")
  TXT_CSS = (By.CSS_SELECTOR, _form + " input")
  APPLY_BTN_CSS = (By.CSS_SELECTOR, _form + " [type='submit']")
  CANCEL_BTN_CSS = (By.CSS_SELECTOR, _form + " [type='button']")
  ITEMS = (By.CSS_SELECTOR, ".document-object-item")


class MultiInputItem(object):
  """Locators for single item in multi input field."""
  LINK_CSS = (By.CSS_SELECTOR, "a")
  DATE = (By.CSS_SELECTOR, "data")


class CommentsPanel(object):
  """Locators for comments' panel."""
  ITEMS_CSS = (By.CSS_SELECTOR, "comment-list-item")


class CommentItem(object):
  """Locators for single item in comments' panel."""
  AUTHOR_CSS = (By.CSS_SELECTOR, ".person-holder")
  DATETIME_CSS = (By.CSS_SELECTOR, ".comment-object-item__header-author-info")
  CONTENT_CSS = (By.CSS_SELECTOR, ".comment-object-item__text")


class AssessmentRelatedTable(object):
  """Locators for RelatedAssessments Tab elements on Assessment InfoWidget."""
  HEADERS = (By.CSS_SELECTOR, ".grid-data-header")
  ROWS = (By.CSS_SELECTOR, ".grid-data-row")
  CELLS = (By.CSS_SELECTOR, "div")
  TAB_BUTTON = (By.CSS_SELECTOR, ".btn.btn-small")


class DashboardWidget(object):
  """Locators for DashboardWidget."""
  _TAB_CONTAINER = ".dashboard-widget.info"
  TAB_CONTAINER_CSS = (By.CSS_SELECTOR, _TAB_CONTAINER)
  TAB_CONTROLLER_CSS = (By.CSS_SELECTOR, ".dashboard-list")
  TAB_CONTENT_CSS = (By.CSS_SELECTOR, _TAB_CONTAINER + " iframe")
