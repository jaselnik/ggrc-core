/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-completion-button.stache';
import BulkUpdatableButton from '../view-models/bulk-updatable-button-vm';

const ViewModel = BulkUpdatableButton.extend({
  async openBulkCompleteModal(el) {
    const {AssessmentsBulkComplete} = await import(
      /* webpackChunkName: "mapper" */
      '../../../controllers/mapper/mapper'
    );

    AssessmentsBulkComplete.launch($(el), this.getModalConfig());
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-completion-button',
  view: canStache(template),
  ViewModel,
});
