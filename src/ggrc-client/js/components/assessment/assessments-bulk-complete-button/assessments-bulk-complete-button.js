/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-button.stache';
import {isMyAssessments} from '../../../plugins/utils/current-page-utils';

const viewModel = canMap.extend({
  isButtonView: false,
  parentInstance: null,
  async openBulkCompleteModal(el) {
    const {AssessmentsBulkComplete} = await import(
      /* webpackChunkName: "mapper" */
      '../../../controllers/mapper/mapper'
    );

    AssessmentsBulkComplete.launch($(el), this.getModalConfig());
  },
  getModalConfig() {
    const parentInstance = this.attr('parentInstance');
    return {
      isMyAssessmentsView: isMyAssessments(),
      mappedToItems: parentInstance ? [{
        id: parentInstance.attr('id'),
        type: parentInstance.attr('type'),
        title: parentInstance.attr('title'),
      }] : [],
    };
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-button',
  view: canStache(template),
  viewModel,
});
