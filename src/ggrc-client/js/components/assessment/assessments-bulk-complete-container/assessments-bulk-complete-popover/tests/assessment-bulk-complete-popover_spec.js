/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../assessments-bulk-complete-popover';
import {getComponentVM} from '../../../../../../js_specs/spec-helpers';
import * as QueryApiUtils from '../../../../../plugins/utils/query-api-utils';

describe('assessments-bulk-complete-popover component', () => {
  let viewModel;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
    viewModel.rowData = {
      asmtType: 'Control',
      asmtId: 1,
    };
  });

  describe('loadMappedObjects() method', () => {
    it('returns correct list of mappedObjects',
      async () => {
        const filters = {
          expression: {
            left: {
              left: 'child_type',
              op: {
                name: '=',
              },
              right: 'Control',
            },
            op: {
              name: 'AND',
            },
            right: {
              object_name: 'Assessment',
              op: {
                name: 'relevant',
              },
              ids: [1],
            },
          },
        };
        const fields = ['id', 'revision'];
        const param = {filter: '1'};
        spyOn(QueryApiUtils, 'buildParam')
          .withArgs('Snapshot', {}, null, fields, filters)
          .and.returnValue(param);

        spyOn(QueryApiUtils, 'batchRequests').withArgs(param)
          .and.returnValue(Promise.resolve({
            Snapshot: {
              values: [{
                id: 1,
                revision: {
                  content: {
                    title: 'Control 1',
                    description: 'description',
                  },
                  resource_type: 'Control',
                },
              }],
            },
          }));

        const expectedObjects = [{
          id: 1,
          title: 'Control 1',
          type: 'control',
          description: 'description',
        }];
        const actualObjects = await viewModel.loadMappedObjects();
        expect(actualObjects).toEqual(expectedObjects);
      });
  });

  describe('initRelatedObjectsPopover() method', () => {
    beforeEach(() => {
      viewModel.popovers = {
        relObjectsHeader: null,
        relObjectsContent: null,
      };
    });

    it('initializes "popovers.relObjectsHeader"', () => {
      viewModel.initRelatedObjectsPopover();
      expect(viewModel.popovers.relObjectsHeader).not.toBeNull();
    });

    it('initializes "popovers.relObjectsContent"', () => {
      viewModel.initRelatedObjectsPopover();
      expect(viewModel.popovers.relObjectsContent).not.toBeNull();
    });
  });
});
