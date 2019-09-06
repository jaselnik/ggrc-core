/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import * as AdvancedSearch from '../../plugins/utils/advanced-search-utils';
import * as StateUtils from '../../plugins/utils/state-utils';
import QueryParser from '../../generated/ggrc_filter_query_parser';
import loEndsWith from 'lodash/endsWith';

describe('AdvancedSearch', () => {
  describe('buildFilter() method', () => {
    it('builds correct filter string', () => {
      let items = [
        AdvancedSearch.create.state({
          items: ['Active', 'Draft'],
          operator: 'ANY',
        }),
        AdvancedSearch.create.operator('AND'),
        AdvancedSearch.create.attribute({
          field: 'Title',
          operator: '~',
          value: ' test',
        }),
        AdvancedSearch.create.operator('OR'),
        AdvancedSearch.create.group([
          AdvancedSearch.create.attribute({
            field: 'Para',
            operator: '=',
            value: 'meter',
          }),
          AdvancedSearch.create.operator('AND'),
          AdvancedSearch.create.attribute({
            field: 'Other',
            operator: '~=',
            value: 'value ',
          }),
        ]),
      ];
      let expectedResult = {
        expression: {
          left: {
            left: {
              left: 'Other',
              op: {name: '~='},
              right: 'value',
            },
            op: {name: 'AND'},
            right: {
              left: 'Para',
              op: {name: '='},
              right: 'meter',
            },
          },
          op: {name: 'OR'},
          right: {
            left: {
              left: 'Title',
              op: {name: '~'},
              right: 'test',
            },
            op: {name: 'AND'},
            right: {
              left: 'Status',
              op: {name: 'IN'},
              right: ['Active', 'Draft'],
            },
          },
        },
      };

      let result = AdvancedSearch.buildFilter(items);

      expect(result).toEqual(expectedResult);
    });

    it('builds correct mapping filters', () => {
      let items = [
        AdvancedSearch.create.mappingCriteria({
          objectName: 'product',
          filter: AdvancedSearch.create.attribute({
            field: 'title',
            operator: '~',
            value: 'A',
          }),
          mappedTo: AdvancedSearch.create.mappingCriteria({
            objectName: 'system',
            filter: AdvancedSearch.create.attribute({
              field: 'title',
              operator: '~',
              value: 'B',
            }),
          }),
        }),
        AdvancedSearch.create.operator('AND'),
        AdvancedSearch.create.mappingCriteria({
          objectName: 'control',
          filter: AdvancedSearch.create.attribute({
            field: 'title',
            operator: '~',
            value: 'C',
          }),
          mappedTo: AdvancedSearch.create.group([
            AdvancedSearch.create.mappingCriteria({
              objectName: 'system',
              filter: AdvancedSearch.create.attribute({
                field: 'title',
                operator: '~',
                value: 'D',
              }),
            }),
            AdvancedSearch.create.operator('OR'),
            AdvancedSearch.create.mappingCriteria({
              objectName: 'system',
              filter: AdvancedSearch.create.attribute({
                field: 'title',
                operator: '~',
                value: 'E',
              }),
            }),
          ]),
        }),
      ];
      let expectedFilters = {
        expression: {
          left: {
            object_name: '__previous__',
            op: {name: 'relevant'},
            ids: [4],
          },
          op: {name: 'AND'},
          right: {
            object_name: '__previous__',
            op: {name: 'relevant'},
            ids: [1],
          },
        },
      };
      let expectedRequest = [
        {
          object_name: 'system',
          type: 'ids',
          filters: {
            expression: {
              left: 'title',
              op: {name: '~'},
              right: 'B',
            },
          },
        },
        {
          object_name: 'product',
          type: 'ids',
          filters: {
            expression: {
              left: {
                left: 'title',
                op: {name: '~'},
                right: 'A',
              },
              op: {name: 'AND'},
              right: {
                object_name: '__previous__',
                op: {name: 'relevant'},
                ids: [0],
              },
            },
          },
        },
        {
          object_name: 'system',
          type: 'ids',
          filters: {
            expression: {
              left: 'title',
              op: {name: '~'},
              right: 'D',
            },
          },
        },
        {
          object_name: 'system',
          type: 'ids',
          filters: {
            expression: {
              left: 'title',
              op: {name: '~'},
              right: 'E',
            },
          },
        },
        {
          object_name: 'control',
          type: 'ids',
          filters: {
            expression: {
              left: {
                left: 'title',
                op: {name: '~'},
                right: 'C',
              },
              op: {name: 'AND'},
              right: {
                left: {
                  object_name: '__previous__',
                  op: {name: 'relevant'},
                  ids: [3],
                },
                op: {name: 'OR'},
                right: {
                  object_name: '__previous__',
                  op: {name: 'relevant'},
                  ids: [2],
                },
              },
            },
          },
        },
      ];
      let request = [];

      let result = AdvancedSearch.buildFilter(items, request);

      expect(result).toEqual(expectedFilters);
      expect(request).toEqual(expectedRequest);
    });

    it('uses group builder', () => {
      spyOn(AdvancedSearch.builders, 'group').and.returnValue('result');
      let data = 'data';
      let request = 'request';

      let result = AdvancedSearch.buildFilter(data, request);

      expect(AdvancedSearch.builders.group).toHaveBeenCalledWith(data, request);
      expect(result).toBe('result');
    });
  });

  describe('reversePolishNotation() method', () => {
    it('builds correct expression', () => {
      let items = [
        AdvancedSearch.create.state({
          items: ['Active', 'Draft'],
          operator: 'ANY',
        }),
        AdvancedSearch.create.operator('AND'),
        AdvancedSearch.create.attribute({
          field: 'Title',
          operator: '~',
          value: ' test',
        }),
        AdvancedSearch.create.operator('OR'),
        AdvancedSearch.create.group([
          AdvancedSearch.create.attribute({
            field: 'Para',
            operator: '=',
            value: 'meter',
          }),
          AdvancedSearch.create.operator('AND'),
          AdvancedSearch.create.attribute({
            field: 'Other',
            operator: '~=',
            value: 'value ',
          }),
        ]),
      ];
      let expectedResult = [{
        type: 'state',
        value: {
          items: ['Active', 'Draft'],
          operator: 'ANY',
        },
      }, {
        type: 'attribute',
        value: {
          field: 'Title',
          operator: '~',
          value: ' test',
        },
      }, {
        type: 'operator',
        value: 'AND',
      }, {
        type: 'group',
        value: [{
          type: 'attribute',
          value: {
            field: 'Para',
            operator: '=',
            value: 'meter',
          },
        }, {
          type: 'operator',
          value: 'AND',
        }, {
          type: 'attribute',
          value: {
            field: 'Other',
            operator: '~=',
            value: 'value ',
          },
        }]}, {
        type: 'operator',
        value: 'OR',
      }];

      let result = AdvancedSearch.reversePolishNotation(items);

      expect(result).toEqual(expectedResult);
    });
  });

  describe('builders', () => {
    describe('attribute builder', () => {
      it('builds correct filter expression', () => {
        let item = AdvancedSearch.create.attribute({
          field: 'field',
          operator: 'operator',
          value: 'value',
        });

        let expression = AdvancedSearch.builders.attribute(item.value);

        expect(expression).toEqual({
          expression: {
            left: 'field',
            op: {name: 'operator'},
            right: 'value',
          },
        });
      });
    });

    describe('state builder', () => {
      let item;
      let expectedResult;
      beforeEach(() => {
        item = AdvancedSearch.create.state({
          modelName: 'testModelName',
          items: ['test'],
          operator: 'ANY',
          statesCollectionKey: null,
        });
        expectedResult = {test: 'result'};
        spyOn(StateUtils, 'buildStatusFilter').and.returnValue(expectedResult);
      });

      it('correctly call buildStatusFilter() if operator is ANY', () => {
        let result = AdvancedSearch.builders.state(item.value);

        expect(StateUtils.buildStatusFilter)
          .toHaveBeenCalledWith(['test'], 'testModelName', false, null);
        expect(result).toBe(expectedResult);
      });

      it('correctly call buildStatusFilter() if operator is NONE', () => {
        item.value.operator = 'NONE';

        let result = AdvancedSearch.builders.state(item.value);

        expect(StateUtils.buildStatusFilter)
          .toHaveBeenCalledWith(['test'], 'testModelName', true, null);
        expect(result).toBe(expectedResult);
      });

      it('correctly call buildStatusFilter() if custom collection of ' +
       'statuses is used', () => {
        item.value.statesCollectionKey = 'CustomKey';

        let result = AdvancedSearch.builders.state(item.value);

        expect(StateUtils.buildStatusFilter)
          .toHaveBeenCalledWith(['test'], 'testModelName', false, 'CustomKey');
        expect(result).toBe(expectedResult);
      });
    });

    describe('group builder', () => {
      let items;
      beforeEach(() => {
        items = [
          AdvancedSearch.create.state({
            modelName: 'testModelName',
            items: ['test'],
          }),
          AdvancedSearch.create.operator('AND'),
          AdvancedSearch.create.attribute({
            field: 'field',
            operator: 'operator',
            value: 'value',
          }),
        ];
      });

      it('calls corresponding builder for each item', () => {
        let expression = {expression: {}};
        spyOn(AdvancedSearch.builders, 'state').and.returnValue(expression);
        spyOn(AdvancedSearch.builders, 'attribute').and.returnValue(expression);

        AdvancedSearch.builders.group(items);

        expect(AdvancedSearch.builders.state).toHaveBeenCalled();
        expect(AdvancedSearch.builders.attribute).toHaveBeenCalled();
      });

      it('joins results to single expression', () => {
        spyOn(QueryParser, 'joinQueries').and.returnValue('joined');

        let result = AdvancedSearch.builders.group(items);

        expect(QueryParser.joinQueries).toHaveBeenCalled();
        expect(result).toBe('joined');
      });
    });
  });

  describe('setDefaultStatusConfig() function', () => {
    let statesSpy;
    const emptyStatusConfig = new canMap(AdvancedSearch.create.state());
    const createDummyStatusConfig = () => (
      AdvancedSearch.setDefaultStatusConfig(emptyStatusConfig, 'someModel')
    );

    beforeEach(() => {
      statesSpy = spyOn(StateUtils, 'getStatesForModel');
    });

    it("assigns states to items of statusConfig if items aren't defined",
      () => {
        let states = ['state1', 'state2', 'state3'];
        statesSpy.and.returnValue(states);
        const statusConfig = createDummyStatusConfig();

        expect(statusConfig.attr('items').serialize()).toEqual(states);
      }
    );

    it('assigns "ANY" to operator if it is not defined', () => {
      const statusConfig = createDummyStatusConfig();

      expect(statusConfig.attr('operator')).toBe('ANY');
    });
  });

  describe('buildSearchPermalink() function', () => {
    it('should set correct URL hash', () => {
      const widgetId = 'regulation';
      const searchId = '12345';
      const expectedHash = '#!regulation&saved_search=12345';

      const permaLink = AdvancedSearch.buildSearchPermalink(searchId, widgetId);
      expect(loEndsWith(permaLink, expectedHash)).toBeTruthy();
    });
  });
});
