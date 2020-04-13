/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import makeArray from 'can-util/js/make-array/make-array';
import canList from 'can-list';
import canMap from 'can-map';
import {
  makeFakeInstance,
  makeFakeModel,
} from '../../../../js_specs/spec-helpers';
import * as TreeViewUtils from '../../../plugins/utils/tree-view-utils';
import * as WidgetsUtils from '../../../plugins/utils/widgets-utils';
import * as NotifierUtils from '../../../plugins/utils/notifiers-utils';
import * as MegaObjectUtils from '../../../plugins/utils/mega-object-utils';
import tracker from '../../../tracker';
import {REFRESH_ITEMS_LIST} from '../../../events/event-types';
import {getComponentVM} from '../../../../js_specs/spec-helpers';
import Component from '../tree-widget-container';
import Relationship from '../../../models/service-models/relationship';
import exportMessage from '../templates/export-message.stache';
import router from '../../../router';
import Cacheable from '../../../models/cacheable';
import Program from '../../../models/business-models/program';
import Assessment from '../../../models/business-models/assessment';

describe('tree-widget-container component', () => {
  let vm;

  beforeEach(() => {
    vm = getComponentVM(Component);
  });

  describe('onSort() method', () => {
    let onSort;

    beforeEach(() => {
      onSort = vm.onSort.bind(vm);
      vm.pageInfo.attr('count', 3);

      spyOn(vm, 'loadItems');
      spyOn(vm, 'closeInfoPane');
    });

    it('sets current order properties', () => {
      onSort({
        field: 'col1',
        sortDirection: 'asc',
      });

      expect(vm.sortingInfo.sortBy).toEqual('col1');
      expect(vm.sortingInfo.sortDirection).toEqual('asc');
      expect(vm.pageInfo.attr('current')).toEqual(1);
      expect(vm.loadItems).toHaveBeenCalled();
      expect(vm.closeInfoPane).toHaveBeenCalled();
    });
  });

  describe('loadItems() method', () => {
    let loadItems;
    let modelName;
    let parent;
    let page;
    let filter;
    let request;
    let loadSnapshots;

    beforeEach(() => {
      modelName = 'testModelName';
      parent = new canMap({testParent: true});
      page = {
        current: 1,
        pageSize: 10,
        sort: [{
          key: null,
          direction: null,
        }],
      },
      filter = new canMap({testFilter: true});
      request = new canList([{testRequest: true}]);

      vm.model = {
        model_singular: modelName,
      };
      vm.options = {
        parent_instance: parent,
      };
      vm.currentFilter = {
        filter,
        request,
      };

      loadItems = vm.loadItems.bind(vm);
      spyOn(tracker, 'start').and.returnValue(() => {});
      spyOn(MegaObjectUtils, 'getMegaObjectRelation')
        .and.returnValue({relation: 'child'});
    });

    it('should call TreeViewUtils.loadFirstTierItems with specified ' +
    'arguments if "options.megaRelated" attr is truthy', (done) => {
      vm.options.megaRelated = true;
      spyOn(TreeViewUtils, 'loadFirstTierItems')
        .and.returnValue($.Deferred().resolve({
          total: 100,
          values: [],
        }));
      loadItems().then(() => {
        expect(TreeViewUtils.loadFirstTierItems).toHaveBeenCalledWith(
          modelName, parent, page, filter, request, loadSnapshots, 'child');
        expect(vm.pageInfo.attr('total')).toEqual(100);
        expect(makeArray(vm.showedItems)).toEqual([]);
        done();
      });
    });

    it('should call TreeViewUtils.loadFirstTierItems with specified ' +
    'arguments if "options.megaRelated" attr is falsy', (done) => {
      vm.options.megaRelated = false;
      spyOn(TreeViewUtils, 'loadFirstTierItems')
        .and.returnValue($.Deferred().resolve({
          total: 100,
          values: [],
        }));
      loadItems().then(() => {
        expect(TreeViewUtils.loadFirstTierItems).toHaveBeenCalledWith(
          modelName, parent, page, filter, request, loadSnapshots, null);
        expect(vm.pageInfo.attr('total')).toEqual(100);
        expect(makeArray(vm.showedItems)).toEqual([]);
        done();
      });
    });

    it('should dispatch REFRESH_ITEMS_LIST event', (done) => {
      vm.options.megaRelated = false;
      vm.model = {
        model_singular: 'Assessment',
      };
      vm.pubSub = {};
      vm.pubSub.dispatch = jasmine.createSpy('dispatch');
      vm.currentFilter = {id: 1};

      spyOn(TreeViewUtils, 'loadFirstTierItems')
        .and.returnValue($.Deferred().resolve({
          total: 100,
          values: [],
        }));
      loadItems().then(() => {
        expect(vm.pubSub.dispatch).toHaveBeenCalledWith({
          ...REFRESH_ITEMS_LIST,
          currentFilter: vm.currentFilter,
          modelName: vm.modelName,
        });
        done();
      });
    });
  });

  describe('on widget appearing', () => {
    let _widgetShown;

    beforeEach(() => {
      _widgetShown = vm._widgetShown.bind(vm);
      spyOn(vm, '_triggerListeners');
      spyOn(vm, 'loadItems');
    });

    beforeEach(() => {
      let modelName = 'Model';
      spyOn(WidgetsUtils, 'getCounts').and.returnValue({[modelName]: 123});
      vm.options = {
        countsName: modelName,
      };
      vm.pageInfo = new canMap({
        total: 123,
      });
    });

    it('should add listeners', () => {
      _widgetShown();
      expect(vm._triggerListeners).toHaveBeenCalled();
      expect(vm.loadItems).not.toHaveBeenCalled();
    });

    it('should load items if refetch flag is true', () => {
      vm.refetch = true;
      router.attr('refetch', false);
      vm.options.forceRefetch = false;

      _widgetShown();
      expect(vm.loadItems).toHaveBeenCalled();
    });

    it('should load items if url has refetch param', () => {
      vm.refetch = false;
      router.attr('refetch', true);
      vm.options.forceRefetch = false;

      _widgetShown();
      expect(vm.loadItems).toHaveBeenCalled();
      expect(vm.refetch).toBeFalsy();
    });

    it('should load items if widget has forceRefetch option', () => {
      vm.refetch = false;
      router.attr('refetch', false);
      vm.options.forceRefetch = true;

      _widgetShown();
      expect(vm.loadItems).toHaveBeenCalled();
    });

    it('should load items if count has changed', () => {
      vm.refetch = false;
      router.attr('refetch', false);
      vm.options.forceRefetch = false;
      vm.pageInfo.attr('total', 100); // less than current count

      _widgetShown();
      expect(vm.loadItems).toHaveBeenCalled();
    });
  });

  describe('getAbsoluteItemNumber() method', () => {
    beforeEach(() => {
      vm.pageInfo = new canMap({
        pageSize: 10,
        count: 5,
      });
      vm.showedItems = [
        {id: 1, type: 'object'},
        {id: 2, type: 'object'},
        {id: 3, type: 'object'},
      ];
      vm.pageInfo.attr('current', 3);
    });

    it('should return correct item number when item is on page',
      () => {
        let result;

        result = vm.getAbsoluteItemNumber({id: 2, type: 'object'});

        expect(result).toEqual(21);
      });

    it('should return "-1" when item is not on page',
      () => {
        let result;

        result = vm.getAbsoluteItemNumber({id: 4, type: 'object'});

        expect(result).toEqual(-1);
      });
    it('should return "-1" when item is of different type',
      () => {
        let result;

        result = vm.getAbsoluteItemNumber({id: 3, type: 'snapshot'});

        expect(result).toEqual(-1);
      });
    it('should return correct item number for first item on non first page',
      () => {
        let result;

        result = vm.getAbsoluteItemNumber({id: 1, type: 'object'});

        expect(result).toEqual(20);
      });
  });

  describe('getRelativeItemNumber() method', () => {
    it('should return correct item number on page', () => {
      let result = vm.getRelativeItemNumber(12, 5);

      expect(result).toEqual(2);
    });
  });

  describe('getNextItemPage() method', () => {
    beforeEach(() => {
      spyOn(vm, 'loadItems');
    });

    it('should load items for appropriate page when item is not loaded',
      () => {
        vm.getNextItemPage(10, {current: 2, pageSize: 5});

        expect(vm.loading).toBeTruthy();
        expect(vm.loadItems).toHaveBeenCalled();
      });

    it('shouldn\'t load items when current item was already loaded',
      () => {
        vm.getNextItemPage(10, {current: 3, pageSize: 5});

        expect(vm.loading).toBeFalsy();
        expect(vm.loadItems).not.toHaveBeenCalled();
      });
  });

  describe('setSortingConfiguration() method', () => {
    beforeEach(() => {
      vm.model = {
        model_singular: 'shortModelName',
      };
    });

    it('sets up default sorting configuration', () => {
      vm.sortingInfo = {};
      spyOn(TreeViewUtils, 'getSortingForModel')
        .and.returnValue({
          key: 'key',
          direction: 'direction',
        });

      vm.setSortingConfiguration();

      expect(vm.sortingInfo.sortBy).toEqual('key');
      expect(vm.sortingInfo.sortDirection).toEqual('direction');
    });
  });

  describe('init() method', () => {
    let method;

    beforeEach(() => {
      vm.model = {
        model_singular: 'shortModelName',
      };
      method = Component.prototype.init.bind({viewModel: vm});
      spyOn(vm, 'setSortingConfiguration');
      spyOn(vm, 'setColumnsConfiguration');
    });

    it('sets up columns configuration', () => {
      method();
      expect(vm.setColumnsConfiguration).toHaveBeenCalled();
    });

    it('sets up sorting configuration', () => {
      method();
      expect(vm.setSortingConfiguration).toHaveBeenCalled();
    });
  });

  describe('getDepthFilter() method', () => {
    it('returns an empty string if depth is not set for filter', () => {
      let result;
      spyOn(vm, 'get')
        .and.returnValue([{
          query: {
            expression: {
              left: 'task assignees',
              op: {name: '='},
              right: 'user@example.com',
            },
          },
          name: 'custom',
        }, {
          query: {
            expression: {
              left: 'state',
              op: {name: '='},
              right: 'Assigned',
            },
          },
          name: 'custom',
        }]);

      result = vm.getDepthFilter();

      expect(result).toBe(null);
    });

    it('returns filter that applied for depth', () => {
      let result;
      spyOn(vm, 'get')
        .and.returnValue([{
          query: {
            expression: {
              left: 'task assignees',
              op: {name: '='},
              right: 'user@example.com',
            },
          },
          name: 'custom',
          depth: true,
          filterDeepLimit: 2,
        }, {
          query: {
            expression: {
              left: 'state',
              op: {name: '='},
              right: 'Assigned',
            },
          },
          name: 'custom',
          depth: true,
          filterDeepLimit: 1,
        }]);

      result = vm.getDepthFilter(1);

      expect(result).toEqual({
        expression: {
          left: 'task assignees',
          op: {name: '='},
          right: 'user@example.com',
        },
      });
    });
  });

  describe('_needToRefreshAfterRelRemove() method', () => {
    let relationship;

    beforeEach(() => {
      relationship = {
        source: {},
        destination: {},
      };
      vm.options.parent_instance = new canMap({
        type: 'Type',
        id: 1,
      });
    });

    describe('returns true', () => {
      it('if source of passed relationship is current instance', () => {
        const source = {
          type: 'SomeType',
          id: 12345,
        };
        vm.parent_instance.attr(source);
        Object.assign(relationship.source, source);
        const result = vm._needToRefreshAfterRelRemove(relationship);
        expect(result).toBe(true);
      });

      it('if source of passed relationship is current instance', () => {
        const destination = {
          type: 'SomeType',
          id: 12345,
        };
        vm.parent_instance.attr(destination);
        Object.assign(relationship.destination, destination);
        const result = vm._needToRefreshAfterRelRemove(relationship);
        expect(result).toBe(true);
      });
    });

    it('returns false when there are no need to refresh', () => {
      const result = vm._needToRefreshAfterRelRemove(relationship);
      expect(result).toBe(false);
    });
  });

  describe('_isRefreshNeeded() method', () => {
    describe('if instance is relationship then', () => {
      let instance;

      beforeEach(() => {
        instance = makeFakeInstance({model: Relationship})();
      });

      it('returns result of the relationship check', () => {
        const expectedResult = true;
        spyOn(vm, '_needToRefreshAfterRelRemove')
          .and.returnValue(expectedResult);
        const result = vm._isRefreshNeeded(instance);
        expect(result).toBe(expectedResult);
        expect(vm._needToRefreshAfterRelRemove)
          .toHaveBeenCalledWith(instance);
      });
    });

    it('returns true by default', () => {
      const result = vm._isRefreshNeeded();
      expect(result).toBe(true);
    });
  });

  describe('showLastPage() method', () => {
    beforeEach(() => {
    });

    it('assigns last page index to pageInfo.current', () => {
      const count = 711;
      vm.pageInfo.attr('count', count);
      vm.pageInfo.attr('current', count + 1);

      vm.showLastPage();

      expect(vm.pageInfo.attr('current')).toBe(count);
    });
  });

  describe('export() method', () => {
    let modelName;
    let parent;
    let filter;
    let request;
    let loadSnapshots;
    const operation = null;

    beforeEach(() => {
      spyOn(TreeViewUtils, 'startExport');
      spyOn(NotifierUtils, 'notifier');

      modelName = 'testModelName';
      parent = new canMap({testParent: true});
      filter = new canMap({testFilter: true});
      request = new canList([{testRequest: true}]);

      vm.model = {
        model_singular: modelName,
      };
      vm.options = {
        parent_instance: parent,
      };
      vm.currentFilter = {
        filter,
        request,
      };
    });

    it('starts export correctly', () => {
      vm.export();

      expect(TreeViewUtils.startExport).toHaveBeenCalledWith(
        modelName, parent, filter, request, loadSnapshots, operation);
    });

    it('shows info message', () => {
      vm.export();

      expect(NotifierUtils.notifier).toHaveBeenCalledWith(
        'info',
        exportMessage,
        {data: true});
    });
  });

  describe('setColumnsConfiguration() method', () => {
    it('should call addServiceColumns() method', () => {
      vm.model = {
        model_singular: 'test model',
      };
      spyOn(TreeViewUtils, 'getColumnsForModel')
        .and.returnValue([]);
      spyOn(vm, 'addServiceColumns');

      vm.setColumnsConfiguration();

      expect(vm.addServiceColumns).toHaveBeenCalled();
    });
  });

  describe('onUpdateColumns() method', () => {
    it('should call addServiceColumns() method', () => {
      vm.model = {
        model_singular: 'test model',
      };
      spyOn(TreeViewUtils, 'setColumnsForModel')
        .and.returnValue([]);
      spyOn(vm, 'addServiceColumns');

      vm.onUpdateColumns({});

      expect(vm.addServiceColumns).toHaveBeenCalled();
    });
  });

  describe('addServiceColumns() method', () => {
    const columns = {};

    beforeEach(() => {
      columns.available = [{
        name: 'col1',
      }, {
        name: 'col2',
      }];
      columns.selected = [{
        name: 'col1',
      }, {
        name: 'col2',
      }];

      const fakeModel = makeFakeModel({
        model: Cacheable,
        staticProps: {
          model_singular: 'Person',
          tree_view_options: {
            service_attr_list: [{
              name: 'serviceCol1',
            }],
          },
        },
      });

      vm.model = fakeModel;
    });

    it('should work for Persons', () => {
      vm.addServiceColumns(columns);

      const expectedOutput = {
        available: [{
          name: 'col1',
        }, {
          name: 'col2',
        }, {
          name: 'serviceCol1',
        }],
        selected: [{
          name: 'col1',
        }, {
          name: 'col2',
        }, {
          name: 'serviceCol1',
        }],
      };

      expect(columns).toEqual(expectedOutput);
    });

    it('should not work for models except Person', () => {
      const expectedOutput = {
        available: [{
          name: 'col1',
        }, {
          name: 'col2',
        }],
        selected: [{
          name: 'col1',
        }, {
          name: 'col2',
        }],
      };

      vm.model = Assessment;
      vm.addServiceColumns(columns);
      expect(columns).toEqual(expectedOutput);

      vm.model = Program;
      vm.addServiceColumns(columns);
      expect(columns).toEqual(expectedOutput);
    });

    it('should sort columns by order', () => {
      columns.available = [{
        name: 'col1',
      }, {
        name: 'col2',
        order: 2,
      }];
      columns.selected = [{
        name: 'col1',
      }, {
        name: 'col2',
        order: 2,
      }];

      vm.model.tree_view_options.service_attr_list = [{
        name: 'serviceCol1',
        order: 1,
      }];

      const expectedOutput = {
        available: [{
          name: 'serviceCol1',
          order: 1,
        }, {
          name: 'col2',
          order: 2,
        }, {
          name: 'col1',
        }],
        selected: [{
          name: 'serviceCol1',
          order: 1,
        }, {
          name: 'col2',
          order: 2,
        }, {
          name: 'col1',
        }],
      };

      vm.addServiceColumns(columns);
      expect(columns).toEqual(expectedOutput);
    });
  });
});
