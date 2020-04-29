/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../assessment-tree-actions';
import {getComponentVM} from '../../../../../js_specs/spec-helpers';
import * as BulkUpdateService from '../../../../plugins/utils/bulk-update-service';
import * as CurrentPageUtils from '../../../../plugins/utils/current-page-utils';

describe('assessment-tree-actions component', () => {
  let viewModel;
  let getAsmtCountForVerifySpy;
  let getCountForCompletionSpy;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
    getAsmtCountForVerifySpy =
      spyOn(BulkUpdateService, 'getAsmtCountForVerify');
    getCountForCompletionSpy =
      spyOn(BulkUpdateService, 'getAsmtCountForCompletion');
  });

  describe('setShowBulkVerify() method', () => {
    it('should set "showBulkVerify" to false when "getAsmtCountForVerify" ' +
    'returns count === 0', (done) => {
      const dfd = $.Deferred();

      getAsmtCountForVerifySpy.and.returnValue(dfd);
      viewModel.setShowBulkVerify();

      dfd.resolve(0);
      dfd.then(() => {
        expect(viewModel.showBulkVerify).toBeFalsy();
        done();
      });
    });

    it('should set "showBulkVerify" to true when "getAsmtCountForVerify" ' +
    'returns count > 0', (done) => {
      const dfd = $.Deferred();

      getAsmtCountForVerifySpy.and.returnValue(dfd);
      viewModel.setShowBulkVerify();

      dfd.resolve(5);
      dfd.then(() => {
        expect(viewModel.showBulkVerify).toBeTruthy();
        done();
      });
    });
  });

  describe('setShowBulkCompletion() method', () => {
    beforeEach(() => {
      viewModel.parentInstance = {
        type: 'Audit',
        id: '1',
      };
    });

    it('should set "showBulkCompletion" to false ' +
    'when "getAsmtCountForCompletion" returns count === 0', async () => {
      spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(true);
      getCountForCompletionSpy.and.returnValue(Promise.resolve(0));
      await viewModel.setShowBulkCompletion();
      expect(viewModel.showBulkCompletion).toBeFalsy();
    });

    it('should set "showBulkCompletion" to true ' +
    'when "getAsmtCountForCompletion" returns count > 0', async () => {
      spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(true);
      getCountForCompletionSpy.and.returnValue(Promise.resolve(5));
      await viewModel.setShowBulkCompletion();
      expect(viewModel.showBulkCompletion).toBeTruthy();
    });

    it('calls "getAsmtCountForCompletion" with "relevant" value on Audit page',
      async () => {
        spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(false);
        getCountForCompletionSpy.and.returnValue(Promise.resolve(5));
        const relevant = {
          type: viewModel.parentInstance.type,
          id: viewModel.parentInstance.id,
          operation: 'relevant',
        };
        await viewModel.setShowBulkCompletion();
        expect(getCountForCompletionSpy)
          .toHaveBeenCalledWith(relevant, undefined);
      });

    it('calls "getAsmtCountForCompletion" with undefined "relevant" '+
    'value on My Assessment page', async () => {
      spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(true);
      getCountForCompletionSpy.and.returnValue(Promise.resolve(5));
      await viewModel.setShowBulkCompletion();
      expect(getCountForCompletionSpy)
        .toHaveBeenCalledWith(null, undefined);
    });

    it('calls "getAsmtCountForCompletion" with currentFilter value',
      async () => {
        spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(true);
        getCountForCompletionSpy.and.returnValue(Promise.resolve(5));
        viewModel.currentFilter = {id: 1};
        await viewModel.setShowBulkCompletion();
        expect(getCountForCompletionSpy)
          .toHaveBeenCalledWith(null, viewModel.currentFilter);
      });
  });

  describe('events', () => {
    let events;

    beforeAll(() => {
      events = Component.prototype.events;
    });

    describe('refreshItemsList event', () => {
      let event;
      let currentFilter;

      beforeEach(() => {
        const eventName = '{pubSub} refreshItemsList';
        const fakeComponent = {viewModel};
        event = events[eventName].bind(fakeComponent);
        spyOn(viewModel, 'setShowBulkCompletion');
        currentFilter = {id: 1};
      });

      it('calls setShowBulkCompletion() for Assessment model ' +
      'on My Assessments page', () => {
        spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(true);
        event({}, {
          modelName: 'Assessment',
          currentFilter,
        });
        expect(viewModel.setShowBulkCompletion).toHaveBeenCalled();
      });
      it('does not call setShowBulkCompletion() for Audit model ' +
       'on Audit page', () => {
        spyOn(CurrentPageUtils, 'isMyAssessments').and.returnValue(false);
        spyOn(CurrentPageUtils, 'isAuditPage').and.returnValue(true);
        event({}, {
          modelName: 'Audit',
          currentFilter,
        });

        expect(viewModel.setShowBulkCompletion).not.toHaveBeenCalled();
      });
    });
  });
});
