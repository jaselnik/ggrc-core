/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessment-template-save-button.stache';
import {confirm} from '../../../plugins/utils/modals';
import {ddValidationValueToMap} from '../../../plugins/utils/ca-utils';
import {isSox302Flow} from '../../../plugins/utils/verification-flow-utils';

const NEGATIVE_RESPONSE_TYPES = [
  'Dropdown',
  'Text',
  'Rich Text',
];

export default canComponent.extend({
  tag: 'assessment-template-save-button',
  view: canStache(template),
  viewModel: canMap.extend({
    instance: null,
    getNegativeResponseDefinitions() {
      const definitions = this
        .attr('instance.custom_attribute_definitions')
        .serialize();

      return definitions.filter((definitions) =>
        NEGATIVE_RESPONSE_TYPES.includes(definitions.attribute_type));
    },
    save(saveButtonElement, ev) {
      ev.stopPropagation();

      if (!isSox302Flow(this.attr('instance'))) {
        this.saveInstance(saveButtonElement);
        return;
      }

      const negativeResponseDefs = this.getNegativeResponseDefinitions();
      const invalidDefinitions =
        this.validateNegativeResponses(negativeResponseDefs);

      if (!invalidDefinitions) {
        this.saveInstance(saveButtonElement);
        return;
      }

      this.showConfirm(saveButtonElement, invalidDefinitions);
    },
    saveInstance(saveButtonElement) {
      // trigger submit event from modals-controller.js
      $(saveButtonElement).trigger('submit');
    },
    showConfirm(saveButtonElement, invalidDefinitions) {
      const buttonView = '/modals/assessment-template-warning-buttons.stache';
      const contentView = '/modals/assessment-template-warning.stache';

      confirm({
        modal_title: 'Warning!',
        button_view: buttonView,
        content_view: contentView,
        skip_refresh: true,
        invalidDefinitions,
      }, () => {
        this.saveInstance(saveButtonElement);
      });
    },
    validateNegativeResponses(negativeResponseDefs) {
      const noPositiveAnswers = [];
      const allPositiveAnswers = [];
      let validationResult = null;

      negativeResponseDefs.forEach((definition) => {
        const mandatoryValues = definition
          .multi_choice_mandatory.split(',');

        const negativeResponsesCount = mandatoryValues
          .filter((item) => ddValidationValueToMap(item).isNegativeResponse)
          .length;

        if (negativeResponsesCount === 0) {
          allPositiveAnswers.push(definition.title);
        } else if (negativeResponsesCount === mandatoryValues.length) {
          noPositiveAnswers.push(definition.title);
        }
      });

      if (noPositiveAnswers.length > 0 || allPositiveAnswers.length > 0) {
        validationResult = {
          noPositiveAnswers,
          allPositiveAnswers,
        };
      }

      return validationResult;
    },
  }),
});
