/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../related-comments/related-comments';
import '../custom-attributes/custom-attributes-field-view';
import '../object-list-item/comment-list-item';
import '../form/form-validation-icon';
import '../tabs/tab-container';
import '../show-more/show-more';
import './object-popover';
import {convertValuesToFormFields} from '../../plugins/utils/ca-utils';
import template from './related-assessment-popover.stache';

/**
 * Simple wrapper component to load Related to Parent Object Snapshots of Controls and Objectives
 */
export default canComponent.extend({
  tag: 'related-assessment-popover',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    selectedAssessment: {},
    popoverTitleInfo: 'Assessment Title: ',
    define: {
      popoverDirection: {
        type: String,
        value: 'right',
      },
      selectedAssessmentTitle: {
        get: function () {
          return this.attr('selectedAssessment.data.title');
        },
      },
      selectedAssessmentLink: {
        get: function () {
          return this.attr('selectedAssessment.data.viewLink');
        },
      },
      selectedAssessmentFields: {
        get: function () {
          let caValues =
            this.attr('selectedAssessment.data.custom_attribute_values');
          const convertedValues = convertValuesToFormFields(caValues);
          this.applyValidation(convertedValues);

          return convertedValues;
        },
      },
    },
    applyValidation(fields) {
      fields.forEach((field) => {
        field.attr('validation.valid', !!field.attr('value'));
      });
    },
  }),
});
