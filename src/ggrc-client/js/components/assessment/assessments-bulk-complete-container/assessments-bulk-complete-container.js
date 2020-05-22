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

const ViewModel = canDefineMap.extend({
  currentFilter: {
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
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-container',
  view: canStache(template),
  ViewModel,
  events: {
    inserted() {
      this.viewModel.buildAsmtListRequest();
      this.viewModel.loadItems();
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
