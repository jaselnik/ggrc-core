/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canDefineMap from 'can-define/map/map';
import canComponent from 'can-component';
import {isMyAssessments, isAuditPage} from '../../../plugins/utils/current-page-utils';
import {getAsmtCountForVerify, getAsmtCountForCompletion} from '../../../plugins/utils/bulk-update-service';
import template from './assessment-tree-actions.stache';
import pubSub from '../../../pub-sub';

const ViewModel = canDefineMap.extend({
  instance: {
    value: null,
  },
  parentInstance: {
    value: null,
  },
  pubSub: {
    value: () => pubSub,
  },
  model: {
    value: null,
  },
  currentFilter: {
    value: () => {},
  },
  showBulkCompletion: {
    value: false,
  },
  showBulkVerify: {
    value: false,
  },
  showBulkSection: {
    get() {
      return isMyAssessments();
    },
  },
  setShowBulkVerify() {
    getAsmtCountForVerify().then((count) => {
      this.showBulkVerify = count > 0;
    });
  },
  setShowBulkCompletion() {
    let relevant = null;
    if (!isMyAssessments()) {
      const parentInstance = this.parentInstance;
      relevant = {
        type: parentInstance.type,
        id: parentInstance.id,
        operation: 'relevant',
      };
    }
    getAsmtCountForCompletion(relevant, this.currentFilter).then((count) => {
      this.showBulkCompletion = count > 0;
    });
  },
});

export default canComponent.extend({
  tag: 'assessment-tree-actions',
  view: canStache(template),
  ViewModel,
  events: {
    inserted() {
      this.viewModel.setShowBulkVerify();
    },
    '{pubSub} refreshItemsList'(scope, {modelName, currentFilter}) {
      if (modelName === 'Assessment' &&
      (isMyAssessments() || isAuditPage())) {
        this.viewModel.currentFilter = currentFilter
          || this.viewModel.currentFilter;
        this.viewModel.setShowBulkCompletion();
      }
    },
    '{pubSub} beforeLoadItems'() {
      this.viewModel.showBulkCompletion = false;
    },
  },
});
