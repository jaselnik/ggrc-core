/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import Component from '../assessments-bulk-complete-container';
import {getComponentVM} from '../../../../../js_specs/spec-helpers';
import * as RequestUtils from '../../../../plugins/utils/request-utils';
import * as BulkUpdateService from '../../../../plugins/utils/bulk-update-service';
import * as CurrentPageUtils from '../../../../plugins/utils/current-page-utils';
import * as QueryApiUtils from '../../../../plugins/utils/query-api-utils';

describe('assessments-bulk-complete-container component', () => {
  let viewModel;
  let filter;
  let param;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
    filter = {id: 1};
    param = {type: 'Assessments'};
    spyOn(BulkUpdateService, 'getFiltersForCompletion')
      .and.returnValue(filter);
  });

  describe('buildAsmtListRequest() method', () => {
    beforeEach(() => {
      viewModel.parentInstance = {
        type: 'Audit',
        id: '1',
      };
    });
    it('sets asmtListRequest on My Assessment page', () => {
      spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(true);

      spyOn(QueryApiUtils, 'buildParam')
        .withArgs('Assessment', {}, null, [], filter)
        .and.returnValue(param);
      viewModel.buildAsmtListRequest();
      param.type = 'ids';
      expect(viewModel.asmtListRequest.serialize()).toEqual(param);
    });

    it('sets asmtListRequest on Audit page', () => {
      spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(false);

      const relevant = {
        type: viewModel.parentInstance.type,
        id: viewModel.parentInstance.id,
        operation: 'relevant',
      };

      spyOn(QueryApiUtils, 'buildParam')
        .withArgs('Assessment', {}, relevant, [], filter)
        .and.returnValue(param);

      viewModel.buildAsmtListRequest();
      param.type = 'ids';
      expect(viewModel.asmtListRequest.serialize()).toEqual(param);
    });
  });

  describe('loadItems() method', () => {
    beforeEach(() => {
      viewModel.asmtListRequest = new canMap();
    });

    it('sets "isLoading" attr to true before request', () => {
      spyOn(RequestUtils, 'request');
      viewModel.isLoading = false;
      viewModel.loadItems();

      expect(viewModel.isLoading).toBe(true);
    });

    it('calls request() method with specified params', () => {
      spyOn(RequestUtils, 'request');
      viewModel.loadItems();

      expect(RequestUtils.request).toHaveBeenCalledWith(
        '/api/bulk_operations/cavs/search', [{}]
      );
    });

    it('sets assessments and attributes attributes', async () => {
      const response = {
        assessments: [1],
        attributes: [2],
      };
      spyOn(RequestUtils, 'request')
        .and.returnValue(Promise.resolve(response));
      await viewModel.loadItems();

      expect(viewModel.assessmentsList.serialize())
        .toEqual(response.assessments);
      expect(viewModel.attributesList.serialize())
        .toEqual(response.attributes);
    });

    it('sets "isLoading" attr to false after request', async () => {
      viewModel.isLoading = true;
      spyOn(RequestUtils, 'request')
        .and.returnValue(Promise.resolve({}));
      await viewModel.loadItems();

      expect(viewModel.isLoading).toBe(false);
    });
  });

  describe('events', () => {
    let events;

    beforeAll(() => {
      events = Component.prototype.events;
    });

    describe('inserted() method', () => {
      let handler;

      beforeEach(() => {
        handler = events.inserted.bind({
          element: $('<assessments-bulk-complete-container/>'),
          viewModel,
        });
      });

      it('calls buildAsmtListRequest()', () => {
        spyOn(viewModel, 'buildAsmtListRequest');
        handler();

        expect(viewModel.buildAsmtListRequest).toHaveBeenCalled();
      });

      it('calls loadItems()', () => {
        spyOn(viewModel, 'buildAsmtListRequest');
        spyOn(viewModel, 'loadItems');
        handler();

        expect(viewModel.loadItems).toHaveBeenCalled();
      });
    });
  });
});
