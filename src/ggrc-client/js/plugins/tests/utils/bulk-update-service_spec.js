/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import * as AjaxExtensions from '../../ajax-extensions';
import service, {getAsmtCountForVerify, getFiltersForCompletion, getAsmtCountForCompletion} from '../../utils/bulk-update-service';
import * as QueryApiUtils from '../../utils/query-api-utils';
import * as BulkUpdateService from '../../utils/bulk-update-service';

describe('GGRC BulkUpdateService', function () {
  let filtersForCompletion;

  beforeEach(() => {
    filtersForCompletion = [{
      expression: {
        left: {
          left: 'assignees',
          op: {
            name: '~',
          },
          right: GGRC.current_user.email,
        },
        op: {
          name: 'AND',
        },
        right: {
          left: {
            left: 'status',
            op: {
              name: 'IN',
            },
            right: [
              'Not Started',
              'In Progress',
              'Rework Needed',
            ],
          },
          op: {
            name: 'AND',
          },
          right: {
            left: {
              left: 'sox_302_enabled',
              op: {
                name: '=',
              },
              right: 'yes',
            },
            op: {
              name: 'AND',
            },
            right: {
              left: 'archived',
              op: {
                name: '=',
              },
              right: 'No',
            },
          },
        },
      },
    }];
  });

  describe('update() method', function () {
    let method;
    let ajaxRes;

    beforeEach(function () {
      method = service.update;
      ajaxRes = {
      };
      ajaxRes.done = jasmine.createSpy().and.returnValue(ajaxRes);
      ajaxRes.fail = jasmine.createSpy().and.returnValue(ajaxRes);

      spyOn(AjaxExtensions, 'ggrcAjax')
        .and.returnValue(ajaxRes);
    });

    it('makes ajax call with transformed data', function () {
      let model = {
        table_plural: 'some_model',
      };
      let data = [{
        id: 1,
      }];

      method(model, data, {state: 'In Progress'});

      expect(AjaxExtensions.ggrcAjax)
        .toHaveBeenCalledWith({
          url: '/api/some_model',
          method: 'PATCH',
          contentType: 'application/json',
          data: '[{"id":1,"state":"In Progress"}]',
        });
    });
  });

  describe('getAsmtCountForVerify() method', () => {
    let dfd;
    let filters;

    beforeEach(() => {
      dfd = $.Deferred();
      filters = {
        expression: {
          left: {
            object_name: 'Person',
            op: {
              name: 'relevant',
            },
            ids: [
              GGRC.current_user.id,
            ],
          },
          op: {
            name: 'AND',
          },
          right: {
            left: {
              left: 'status',
              op: {
                name: '=',
              },
              right: 'In Review',
            },
            op: {
              name: 'AND',
            },
            right: {
              left: {
                left: 'archived',
                op: {
                  name: '=',
                },
                right: 'No',
              },
              op: {
                name: 'AND',
              },
              right: {
                left: 'verifiers',
                op: {
                  name: '~',
                },
                right: GGRC.current_user.email,
              },
            },
          },
        },
      };
    });

    it('returns deferred object with assessments count', (done) => {
      spyOn(QueryApiUtils, 'buildParam').withArgs(
        'Assessment',
        {},
        null,
        [],
        filters)
        .and.returnValue({});
      spyOn(QueryApiUtils, 'batchRequests').withArgs({type: 'count'})
        .and.returnValue(dfd);

      dfd.resolve({
        Assessment: {
          count: 3,
        },
      });

      getAsmtCountForVerify().then((count) => {
        expect(count).toEqual(3);
        done();
      });
    });
  });

  describe('getFiltersForCompletion() method', () => {
    it('returns correct filter when current filter is undefined', () => {
      expect(getFiltersForCompletion(undefined)).toEqual(filtersForCompletion);
    });

    it('returns correct filter when current filter is defined', () => {
      const currentFilter = {
        filter: {
          type: 'Audit',
          id: '1',
        },
      };
      filtersForCompletion.push(currentFilter.filter);
      expect(getFiltersForCompletion(new canMap(currentFilter)))
        .toEqual(filtersForCompletion);
    });
  });

  describe('getAsmtCountForCompletion() method', () => {
    it('returns deferred object with assessments count', async () => {
      spyOn(BulkUpdateService, 'getFiltersForCompletion')
        .and.returnValue(filtersForCompletion);
      spyOn(QueryApiUtils, 'buildParam').withArgs(
        'Assessment',
        {},
        null,
        [],
        filtersForCompletion)
        .and.returnValue({});
      spyOn(QueryApiUtils, 'batchRequests').withArgs({
        type: 'count',
        permissions: 'update',
      })
        .and.returnValue(Promise.resolve({
          Assessment: {
            count: 3,
          },
        }));

      const count = await getAsmtCountForCompletion();
      expect(count).toEqual(3);
    });
  });
});
