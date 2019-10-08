/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../../dropdown/dropdown-component';
import '../../dropdown/dropdown-wrap-text';
import template from './dropdown-form-field.stache';

export default canComponent.extend({
  tag: 'dropdown-form-field',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    define: {
      isNoneSelected: {
        get: function () {
          return this.attr('value') === null &&
            this.attr('disabled');
        },
      },
      inputValue: {
        set: function (newValue) {
          let oldValue = this.attr('_value');

          if (newValue === oldValue) {
            return;
          }

          this.attr('_value', newValue);
          this.valueChanged(newValue);
        },
        get() {
          return this.attr('_value');
        },
      },
      value: {
        set: function (newValue) {
          this.attr('_value', newValue);
        },
        get() {
          return this.attr('_value');
        },
      },
      fieldId: {
        type: 'number',
        value: null,
      },
    },
    isLocalCa: false,
    _value: '',
    options: [],
    isGroupedDropdown: false,
    dropdownOptionsGroups: {},
    noValue: true,
    valueChanged: function (newValue) {
      this.dispatch({
        type: 'valueChanged',
        fieldId: this.attr('fieldId'),
        value: newValue,
      });
    },
  }),
});
