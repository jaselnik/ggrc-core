/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loDebounce from 'lodash/debounce';
import loFindIndex from 'lodash/findIndex';
import loSortBy from 'lodash/sortBy';
import loIsEmpty from 'lodash/isEmpty';
import makeArray from 'can-util/js/make-array/make-array';
import canStache from 'can-stache';
import canMap from 'can-map';
import canDefineMap from 'can-define/map/map';
import canComponent from 'can-component';
import './tree-header-selector';
import './sub-tree-expander';
import './sub-tree-wrapper';
import './sub-tree-item';
import './sub-tree-models';
import './tree-item-extra-info';
import './tree-item-actions';
import './tree-item-map';
import './tree-view';
import './tree-item';
import './tree-actions';
import './tree-header';
import './tree-item-status-for-workflow';
import './tree-no-results';
import './tree-field-wrapper';
import './tree-field';
import './tree-people-with-role-list-field';
import '../bulk-update-button/bulk-update-button';
import '../assessment-template-clone-button/assessment-template-clone-button';
import '../create-document-button/create-document-button';
import '../assessment/assessment-generator-button';
import '../last-comment/last-comment';
import '../tree-view-filter/tree-view-filter';
import loGet from 'lodash/get';
import template from './templates/tree-widget-container.stache';
import * as StateUtils from '../../plugins/utils/state-utils';
import {
  REFRESH_RELATED,
  REFRESH_MAPPING,
} from '../../events/event-types';
import * as TreeViewUtils from '../../plugins/utils/tree-view-utils';
import {
  initMappedInstances,
  isAllObjects,
  isMyWork,
  isMyAssessments,
} from '../../plugins/utils/current-page-utils';
import {
  initCounts,
  getCounts,
  refreshCounts,
  getWidgetModels,
} from '../../plugins/utils/widgets-utils';
import {getMegaObjectRelation} from '../../plugins/utils/mega-object-utils';
import Pagination from '../base-objects/pagination';
import tracker from '../../tracker';
import router from '../../router';
import {notifier} from '../../plugins/utils/notifiers-utils';
import Cacheable from '../../models/cacheable';
import Relationship from '../../models/service-models/relationship';
import Comment from '../../models/service-models/comment';
import * as businessModels from '../../models/business-models';
import exportMessage from './templates/export-message.stache';
import {isSnapshotType} from '../../plugins/utils/snapshot-utils';
import pubSub from '../../pub-sub';
import {concatFilters} from '../../plugins/utils/query-api-utils';

const ViewModel = canDefineMap.extend({
  modelName: {
    get() {
      return this.model && this.model.model_singular;
    },
  },
  statusTooltipVisible: {
    get() {
      return StateUtils.hasFilterTooltip(this.modelName);
    },
  },
  cssClasses: {
    get() {
      let classes = [];

      if (this.loading) {
        classes.push('loading');
      }

      return classes.join(' ');
    },
  },
  parent_instance: {
    Type: canMap,
    get() {
      return this.options && this.options.parent_instance;
    },
  },
  noResults: {
    get() {
      return !this.loading && !this.showedItems.length;
    },
  },
  pageInfo: {
    value() {
      return new Pagination({
        pageSizeSelect: [10, 25, 50],
        pageSize: 10});
    },
  },
  selectedItem: {
    set(newValue) {
      this.selectedItemHandler(newValue);
      return newValue;
    },
  },
  sortingInfo: {
    value: () => ({
      sortDirection: null,
      sortBy: null,
    }),
  },
  model: {
    value: null,
  },
  showedItems: {
    value: () => [],
  },
  limitDepthTree: {
    value: 0,
  },
  /**
   * Legacy options which were built for a previous implementation of TreeView based on TreeView controller
   */
  options: {
    value: () => ({}),
  },
  router: {
    value: null,
  },
  $el: {
    value: null,
  },
  loading: {
    value: false,
  },
  refetch: {
    value: false,
  },
  columns: {
    value: () => ({
      selected: [],
      available: [],
    }),
  },
  canOpenInfoPin: {
    value: true,
  },
  pubSub: {
    value: () => pubSub,
  },
  currentFilter: {
    value: () => ({}),
  },
  isSubTreeItem: {
    value: false,
  },
  isDirectlyRelated: {
    value: false,
  },
  filters: {
    value: () => [],
  },
  loadItems() {
    const modelName = this.modelName;
    const pageInfo = this.pageInfo;
    const sortingInfo = this.sortingInfo;
    const parent = this.parent_instance;
    const filter = this.currentFilter.filter;
    const page = {
      current: pageInfo.current,
      pageSize: pageInfo.pageSize,
      sort: [{
        key: sortingInfo.sortBy,
        direction: sortingInfo.sortDirection,
      }],
    };
    const request = this.currentFilter.request;
    const stopFn = tracker.start(modelName,
      tracker.USER_JOURNEY_KEYS.TREEVIEW,
      tracker.USER_ACTIONS.TREEVIEW.TREE_VIEW_PAGE_LOADING(page.pageSize));

    pageInfo.attr('disabled', true);
    this.loading = true;

    const loadSnapshots = this.options.objectVersion;
    const operation = this.options.megaRelated
      ? getMegaObjectRelation(this.options.widgetId).relation
      : null;

    return TreeViewUtils
      .loadFirstTierItems(
        modelName,
        parent,
        page,
        filter,
        request,
        loadSnapshots,
        operation)
      .then((data) => {
        const total = data.total;

        this.showedItems = data.values;
        this.pageInfo.attr('total', total);
        this.pageInfo.attr('disabled', false);
        this.loading = false;
        this.pubSub.dispatch('refreshItemsList');
      })
      .then(stopFn, stopFn.bind(null, true));
  },
  refresh(destinationType) {
    if (!destinationType || this.modelName === destinationType) {
      this.closeInfoPane();
      return this.loadItems();
    }

    return Promise.resolve();
  },
  setColumnsConfiguration() {
    const columns = TreeViewUtils.getColumnsForModel(
      this.modelName,
      this.options.widgetId
    );

    this.addServiceColumns(columns);

    this.columns.available = columns.available;
    this.columns.selected = columns.selected;
    this.columns.mandatory = columns.mandatory;
    this.columns.disableConfiguration = columns.disableConfiguration;
  },
  addServiceColumns(columns) {
    if (this.modelName === 'Person') {
      const serviceCols =
        this.model.tree_view_options.service_attr_list;

      columns.available = columns.available.concat(serviceCols);
      columns.selected = columns.selected.concat(serviceCols);

      columns.available = loSortBy(columns.available, 'order');
      columns.selected = loSortBy(columns.selected, 'order');
    }
  },
  setSortingConfiguration() {
    let sortingInfo = TreeViewUtils
      .getSortingForModel(this.modelName);

    this.sortingInfo.sortBy = sortingInfo.key;
    this.sortingInfo.sortDirection = sortingInfo.direction;
  },
  onUpdateColumns(event) {
    const selectedColumns = event.columns;
    const columns = TreeViewUtils.setColumnsForModel(
      this.modelName,
      selectedColumns,
      this.options.widgetId
    );

    this.addServiceColumns(columns);

    this.columns.selected = columns.selected;
  },
  onSort(event) {
    this.sortingInfo.sortBy = event.field;
    this.sortingInfo.sortDirection = event.sortDirection;

    this.pageInfo.attr('current', 1);
    this.refresh();
  },
  onFilter() {
    const stopFn = tracker.start(this.modelName,
      tracker.USER_JOURNEY_KEYS.TREEVIEW,
      tracker.USER_ACTIONS.TREEVIEW.FILTER);
    this.pageInfo.attr('current', 1);
    this.refresh().then(stopFn);
  },
  getDepthFilter(deepLevel) {
    const filters = makeArray(this.get('filters'));

    return filters.filter((options) => {
      return options.query &&
        options.depth &&
        options.filterDeepLimit > deepLevel;
    }).reduce(concatFilters, null);
  },
  _widgetHidden() {
    this._triggerListeners(true);
  },
  _widgetShown() {
    const countsName = this.options.countsName;
    const total = this.pageInfo.attr('total');
    const counts = loGet(getCounts(), countsName);
    this._triggerListeners();

    if (this.refetch ||
      router.attr('refetch') ||
      this.options.forceRefetch ||
      // this condition is mostly for Issues, Documents and Evidence as they can be created from other object info pane
      (total !== counts)) {
      this.loadItems();
      this.refetch = false;
    }
  },
  _needToRefreshAfterRelRemove(relationship) {
    const parentInstance = this.parent_instance;
    const {
      source,
      destination,
    } = relationship;

    const isRelForCurrentInstance = (
      (
        source.type === parentInstance.attr('type') &&
        source.id === parentInstance.attr('id')
      ) || (
        destination.type === parentInstance.attr('type') &&
        destination.id === parentInstance.attr('id')
      )
    );

    return isRelForCurrentInstance;
  },
  _isRefreshNeeded(instance) {
    let needToRefresh = true;

    if (instance instanceof Relationship) {
      needToRefresh = this._needToRefreshAfterRelRemove(instance);
    }

    return needToRefresh;
  },
  _triggerListeners: (function () {
    let activeTabModel;
    let self;

    function onCreated(ev, instance) {
      if (activeTabModel === instance.type) {
        _refresh(true);
      } else if (!(instance instanceof Relationship)
      && !(instance instanceof Comment)) {
        _refreshCounts();
      }
    }

    function onDestroyed(ev, instance) {
      const activeTabType = businessModels[activeTabModel].model_singular;
      const isSnapshotTab =
        isSnapshotType(instance) &&
        instance.child_type === activeTabType;

      if (_verifyRelationship(instance, activeTabModel) ||
        instance instanceof businessModels[activeTabModel] ||
        isSnapshotTab) {
        if (self.showedItems.length === 1) {
          const current = self.pageInfo.attr('current');
          self.pageInfo.attr('current', current > 1 ? current - 1 : 1);
        }

        if (self._isRefreshNeeded(instance)) {
          _refresh();

          // TODO: This is a workaround.We need to update communication between
          //       info-pin and tree views through Observer
          if (!self.$el.closest('.pin-content').length) {
            $('.pin-content').control().unsetInstance();
          }
        } else {
          _refreshCounts();
        }
      } else {
        // reinit mapped instances (subTree uses mapped instances)
        initMappedInstances();
      }
    }

    const _refresh = async (sortByUpdatedAt) => {
      if (self.loading) {
        return;
      }
      if (sortByUpdatedAt) {
        self.sortingInfo.sortDirection = 'desc';
        self.sortingInfo.sortBy = 'updated_at';
        self.pageInfo.attr('current', 1);
      }
      await self.loadItems();

      if (!self.isCurrentFilterEmpty()) {
        _refreshCounts();
      } else {
        const countsName = self.options.countsName;
        const total = self.pageInfo.attr('total');
        getCounts().attr(countsName, total);
      }
      self.closeInfoPane();
    };

    // timeout required to let server correctly calculate changed counts
    const _refreshCounts = loDebounce(() => {
      // do not refresh counts for Workflow. There are additional filters
      // for history and active tabs which are handled in workflow components
      if (self.parent_instance.type === 'Workflow') {
        return;
      }

      // No need to refresh counts for My Assessments page
      if (isMyAssessments()) {
        return;
      }

      if (isMyWork() || isAllObjects()) {
        const location = window.location.pathname;
        const widgetModels = getWidgetModels('Person', location);
        initCounts(widgetModels, 'Person', GGRC.current_user.id);
      } else {
        refreshCounts();
      }
    }, 250);

    function _verifyRelationship(instance, shortName, parentInstance) {
      if (!(instance instanceof Relationship)) {
        return false;
      }

      if (parentInstance && instance.destination && instance.source) {
        if (instance.source.type === parentInstance.type &&
          (instance.destination.type === shortName ||
            instance.destination.type === 'Snapshot')) {
          return true;
        }
        return false;
      }
      if (instance.destination &&
        (instance.destination.type === shortName ||
          instance.destination.type === 'Snapshot')) {
        return true;
      }
      if (instance.source &&
        (instance.source.type === shortName ||
          instance.source.type === 'Snapshot')) {
        return true;
      }
      return false;
    }

    return function (needDestroy) {
      activeTabModel = this.options.model.model_singular;
      self = this;
      if (needDestroy) {
        // Remove listeners for inactive tabs
        Cacheable.unbind('created', onCreated);
        Cacheable.unbind('destroyed', onDestroyed);
      } else {
        // Add listeners on creations instance or mappings objects for current tab
        // and refresh page after that.
        Cacheable.bind('created', onCreated);
        Cacheable.bind('destroyed', onDestroyed);
      }
    };
  })(),
  closeInfoPane() {
    $('.pin-content').control().close();
  },
  getAbsoluteItemNumber(instance) {
    const showedItems = this.showedItems;
    const pageInfo = this.pageInfo;
    const startIndex = pageInfo.pageSize * (pageInfo.current - 1);
    const relativeItemIndex = loFindIndex(showedItems,
      {id: instance.id, type: instance.type});
    return relativeItemIndex > -1 ?
      startIndex + relativeItemIndex :
      relativeItemIndex;
  },
  getRelativeItemNumber(absoluteNumber, pageSize) {
    const pageNumber = Math.floor(absoluteNumber / pageSize);
    const startIndex = pageSize * pageNumber;
    return absoluteNumber - startIndex;
  },
  getNextItemPage(absoluteNumber, pageInfo) {
    const pageNumber = Math.floor(absoluteNumber / pageInfo.pageSize) + 1;
    let promise = Promise.resolve();

    if (pageInfo.current !== pageNumber) {
      this.loading = true;
      this.pageInfo.attr('current', pageNumber);
      promise = this.loadItems();
    }

    return promise;
  },
  updateActiveItemIndicator(index) {
    const element = this.$el;
    element
      .find('.item-active')
      .removeClass('item-active');
    element
      .find('tree-item:nth-of-type(' + (index + 1) +
        ') .tree-item-content')
      .addClass('item-active');
  },
  showLastPage() {
    const lastPageIndex = this.pageInfo.attr('count');
    this.pageInfo.attr('current', lastPageIndex);
  },
  export() {
    const modelName = this.modelName;
    const parent = this.parent_instance;
    const filter = this.currentFilter.filter;
    const request = this.currentFilter.request;
    const loadSnapshots = this.options.objectVersion;
    const operation = this.options.megaRelated ?
      getMegaObjectRelation(this.options.widgetId).relation :
      null;

    TreeViewUtils.startExport(
      modelName,
      parent,
      filter,
      request,
      loadSnapshots,
      operation,
    );

    notifier('info', exportMessage, {data: true});
  },
  selectedItemHandler(itemIndex) {
    const componentSelector = 'assessment-info-pane';
    const pageInfo = this.pageInfo;

    const relativeIndex = this
      .getRelativeItemNumber(itemIndex, pageInfo.attr('pageSize'));
    const pageLoadPromise = this.getNextItemPage(itemIndex, pageInfo);
    const pinControl = $('.pin-content').control();

    if (!this.canOpenInfoPin) {
      return;
    }

    pinControl.setLoadingIndicator(componentSelector, true);

    pageLoadPromise
      .then(() => {
        const items = this.showedItems;
        const newInstance = items[relativeIndex];

        if (!newInstance) {
          this.closeInfoPane();
          this.showLastPage();

          return $.Deferred().resolve();
        }

        return newInstance
          .refresh();
      })
      .then((newInstance) => {
        if (!newInstance) {
          return;
        }

        pinControl
          .updateInstance(componentSelector, newInstance);
        newInstance.dispatch('refreshRelatedDocuments');
        newInstance.dispatch({
          ...REFRESH_RELATED,
          model: 'Assessment',
        });

        this.updateActiveItemIndicator(relativeIndex);
      })
      .catch(() => {
        notifier('error', 'Failed to fetch an object.');
      })
      .finally(() => {
        pinControl.setLoadingIndicator(componentSelector, false);
      });
  },
  isCurrentFilterEmpty() {
    const currentFilter = this.currentFilter.serialize();
    return !currentFilter.filter && loIsEmpty(currentFilter.request);
  },
});

export default canComponent.extend({
  tag: 'tree-widget-container',
  view: canStache(template),
  leakScope: true,
  ViewModel,
  init() {
    this.viewModel.setColumnsConfiguration();
    this.viewModel.setSortingConfiguration();
  },
  events: {
    '{viewModel.pageInfo} current'() {
      if (!this.viewModel.loading) {
        this.viewModel.refresh();
      }
    },
    '{viewModel.pageInfo} pageSize'() {
      this.viewModel.loadItems();
    },
    ' selectTreeItem'(el, ev, selectedEl, instance) {
      const parent = this.viewModel.parent_instance;
      const infoPaneOptions = new canMap({
        instance: instance,
        parent_instance: parent,
        options: this.viewModel,
      });
      const itemNumber = this.viewModel.getAbsoluteItemNumber(instance);
      const isSubTreeItem = itemNumber === -1;

      ev.stopPropagation();

      if (!this.viewModel.canOpenInfoPin) {
        return;
      }

      if (!isSubTreeItem) {
        this.viewModel.selectedItem = itemNumber;
      }

      this.viewModel.canOpenInfoPin = false;
      this.viewModel.isSubTreeItem = isSubTreeItem;
      el.find('.item-active').removeClass('item-active');
      selectedEl.addClass('item-active');

      const setInstancePromise = $('.pin-content').control()
        .setInstance(infoPaneOptions, selectedEl, true);

      setInstancePromise.then(() => {
        this.viewModel.canOpenInfoPin = true;
      });
    },
    ' refreshTree'(el, ev) {
      ev.stopPropagation();
      this.viewModel.refresh();
    },
    [`{viewModel.parent_instance} ${REFRESH_MAPPING.type}`](
      [scope], {destinationType}
    ) {
      this.viewModel.refresh(destinationType);
    },
    inserted() {
      const viewModel = this.viewModel;
      viewModel.$el = this.element;
      viewModel.router = router;

      this.element.closest('.widget')
        .on('widget_hidden', viewModel._widgetHidden.bind(viewModel));
      this.element.closest('.widget')
        .on('widget_shown', viewModel._widgetShown.bind(viewModel));
      viewModel._triggerListeners();
    },
    '{viewModel.parent_instance} displayTree'([scope], {destinationType}) {
      this.viewModel.refresh(destinationType);
    },
    '{pubSub} createdCycleTaskGroup'() {
      this.viewModel.loadItems();
    },
    '{pubSub} refetchOnce'(scope, event) {
      if (event.modelNames.includes(this.viewModel.modelNam)) {
        // refresh widget content when tab is opened
        this.viewModel.refetch = true;
      }
    },
  },
});
