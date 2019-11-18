/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import {splitTrim, filteredMap} from '../../../plugins/ggrc-utils';
import loZip from 'lodash/zip';
import loRange from 'lodash/range';
import loFind from 'lodash/find';
import canStache from 'can-stache';
import canMap from 'can-map';
import canBatch from 'can-event/batch/batch';
import canComponent from 'can-component';
import {
  ddValidationValueToMap,
  ddValidationMapToValue,
} from '../../../plugins/utils/ca-utils';
import template from './template-field.stache';
import {isSox302Flow} from '../../../plugins/utils/verification-flow-utils';

const TEXT_FIELDS = [
  'Text',
  'Rich Text',
];

/*
 * Template field
 *
 * Represents each `field` passed from assessment-template-attributes `fields`
 */
export default canComponent.extend({
  tag: 'template-field',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    types: [],
    attrs: [],
    instance: {},
    editMode: true,
    field: null,
    define: {
      isDropdownOrMultiselect: {
        get() {
          const fieldType = this.attr('field.attribute_type');
          return fieldType === 'Dropdown' || fieldType === 'Multiselect';
        },
      },
      isTextFieldOptionsVisible: {
        get() {
          const isTextField =
            TEXT_FIELDS.includes(this.attr('field.attribute_type'));
          return isTextField && isSox302Flow(this.attr('instance'));
        },
      },
    },
    /*
     * Removes `field` from `fields`
     */
    removeField: function (el, ev) {
      // CAUTION: In order for the event to not get lost, triggering it
      // must happen before changing any of the viewModel attributes that
      // cause changes in the template.
      this.dispatch({
        type: 'remove',
        field: this.attr('field'),
      });
    },
    /*
     * Denormalize field.multi_choice_mandatory into opts
     * "0, 1, 2" is normalized into
     * [
     * {value: 0, attachment: false, comment: false},
     * {value: 1, attachment: false, comment: true},
     * {value: 2, attachment: true, comment: false},
     * ]
     */
    denormalizeMandatory: function (field) {
      let options = splitTrim(field.attr('multi_choice_options'));
      let vals = splitTrim(field.attr('multi_choice_mandatory'));
      let isEqualLength = options.length === vals.length;
      let range;

      if (!isEqualLength && options.length < vals.length) {
        vals.length = options.length;
      } else if (!isEqualLength && options.length > vals.length) {
        range = loRange(options.length - vals.length);
        range = range.map(function () {
          return '0';
        });
        vals = vals.concat(range);
      }

      return loZip(options, vals).map(function (zip) {
        let attr = new canMap();
        let val = parseInt(zip[1], 10);
        attr.attr('type', field.attr('attribute_type'));
        attr.attr('value', zip[0]);
        attr.attr(ddValidationValueToMap(val));
        return attr;
      });
    },
    /*
     * Normalize opts into field.multi_choice_mandatory
     * [
     * {value: 0, attachment: true, comment: false},
     * {value: 1, attachment: true, comment: true},
     * ]
     * is normalized into "2, 3" (10b, 11b).
     */
    normalizeMandatory: function (attrs) {
      return filteredMap(attrs, ddValidationMapToValue).join(',');
    },
    initTextFieldOptions() {
      // the field has already options
      if (this.attr('field.multi_choice_options')) {
        return;
      }

      canBatch.start();
      this.attr('field.multi_choice_options', 'Not empty,Empty');
      this.attr('field.multi_choice_mandatory', '0,0');
      canBatch.stop();
    },
  }),
  events: {
    /**
     * The component's entry point.
     *
     * @param {Object} element - the (unwrapped) DOM element that triggered
     *   creating the component instance
     */
    init(element) {
      const vm = this.viewModel;

      if (vm.attr('isTextFieldOptionsVisible')) {
        vm.initTextFieldOptions();
      }

      const field = vm.attr('field');
      const denormalized = vm.denormalizeMandatory(field);
      const types = vm.attr('types');
      const item = loFind(types, function (obj) {
        return obj.type === field.attr('attribute_type');
      });
      field.attr('attribute_name', item.name);

      vm.attr('attrs').replace(denormalized);
      vm.attr('$rootEl', $(element));
    },
    '{attrs} change'() {
      const attrs = this.viewModel.attr('attrs');
      const normalized = this.viewModel.normalizeMandatory(attrs);
      this.viewModel.field.attr('multi_choice_mandatory', normalized);
    },
    '{viewModel.instance} verification_workflow'() {
      const vm = this.viewModel;
      if (!vm.attr('isTextFieldOptionsVisible')) {
        return;
      }

      vm.initTextFieldOptions();

      const field = vm.attr('field');
      const denormalized = vm.denormalizeMandatory(field);
      vm.attr('attrs').replace(denormalized);
    },
  },
});
