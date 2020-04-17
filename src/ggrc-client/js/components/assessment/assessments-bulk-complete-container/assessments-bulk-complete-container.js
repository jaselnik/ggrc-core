/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canDefineMap from 'can-define/map/map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-container.stache';
import pubSub from '../../../pub-sub';
import {request} from '../../../plugins/utils/request-utils';
import {getFiltersForCompletion} from '../../../plugins/utils/bulk-update-service';
import {buildParam} from '../../../plugins/utils/query-api-utils';
import {isMyAssessments} from '../../../plugins/utils/current-page-utils';
import '../assessments-bulk-complete-table/assessments-bulk-complete-table';
import './assessments-bulk-complete-popover/assessments-bulk-complete-popover';
import './assessments-bulk-complete-popover/assessments-bulk-complete-popover-content';
import {confirm} from '../../../plugins/utils/modals';

const ViewModel = canDefineMap.extend({
  currentFilter: {
    value: null,
  },
  _beforeUnloadHandler: {
    value: null,
  },
  parentInstance: {
    value: null,
  },
  asmtListRequest: {
    value: null,
  },
  assessmentsList: {
    value: () => [],
  },
  attributesList: {
    value: () => [],
  },
  isLoading: {
    value: false,
  },
  isDataLoaded: {
    value: false,
  },
  pubSub: {
    value: () => pubSub,
  },
  isAttributeModified: {
    value: false,
  },
  isCompleteButtonEnabled: {
    get() {
      return this.countAssessmentsToComplete > 0;
    },
  },
  assessmentIdsToComplete: {
    value: () => new Set(),
  },
  countAssessmentsToComplete: {
    value: 0,
  },
  buildAsmtListRequest() {
    let relevant = null;
    if (!isMyAssessments()) {
      const parentInstance = this.parentInstance;
      relevant = {
        type: parentInstance.type,
        id: parentInstance.id,
        operation: 'relevant',
      };
    }
    const filter =
      getFiltersForCompletion(this.currentFilter, relevant);
    const param = buildParam('Assessment', {}, relevant, [], filter);
    param.type = 'ids';
    this.asmtListRequest = param;
  },
  async loadItems() {
    this.isLoading = true;
    const {assessments, attributes} =
      await request('/api/bulk_operations/cavs/search',
        [this.asmtListRequest.serialize()]);
    this.assessmentsList = assessments;
    this.attributesList = attributes;
    this.isLoading = false;
    this.isDataLoaded = true;
  },
  exitBulkCompletionMode() {
    const disableBulkCompletionMode = () => pubSub.dispatch({
      type: 'enableBulkCompleteMode',
      enable: false,
    });
    if (this.isAttributeModified) {
      confirm({
        modal_title: 'Warning',
        modal_description: `Changes you made might not be saved.<br>
         Do you want to exit the bulk completion mode?`,
        button_view: '/modals/confirm-cancel-buttons.stache',
        modal_confirm: 'Proceed',
        extraCssClass: 'exit-bulk-completion-modal',
      }, disableBulkCompletionMode);
    } else {
      disableBulkCompletionMode();
    }
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-container',
  view: canStache(template),
  ViewModel,
  events: {
    inserted() {
      this.viewModel.buildAsmtListRequest();
      this.viewModel.loadItems();
      const beforeUnloadHandler = (event) => {
        if (this.viewModel.isAttributeModified) {
          event.preventDefault();
          event.returnValue = '';
        }
      };
      this.viewModel._beforeUnloadHandler = beforeUnloadHandler.bind(this);
      window.addEventListener('beforeunload',
        this.viewModel._beforeUnloadHandler);
    },
    removed() {
      window.removeEventListener('beforeunload',
        this.viewModel._beforeUnloadHandler);
    },
    '{pubSub} attributeModified'(pubSub, {assessmentData}) {
      this.viewModel.isAttributeModified = true;

      if (assessmentData.isReadyToComplete) {
        this.viewModel.assessmentIdsToComplete.add(assessmentData.asmtId);
      } else {
        this.viewModel.assessmentIdsToComplete.delete(assessmentData.asmtId);
      }

      this.viewModel.countAssessmentsToComplete =
        this.viewModel.assessmentIdsToComplete.size;
    },
    '{pubSub} assessmentReadyToComplete'(pubSub, {assessmentId}) {
      this.viewModel.assessmentIdsToComplete.add(assessmentId);
      this.viewModel.countAssessmentsToComplete =
        this.viewModel.assessmentIdsToComplete.size;
    },
  },
});
