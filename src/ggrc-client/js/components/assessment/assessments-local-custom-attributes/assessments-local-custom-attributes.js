/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/
import '../../form/form-validation-icon';
import '../../custom-attributes/custom-attributes-field';

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-local-custom-attributes.stache';

const viewModel = canMap.extend({
  fields: [],
  getFieldClass(type) {
    return type === 'checkbox' ? 'custom-attribute-checkbox' : '';
  },
  updateFieldValue(value, fieldIndex) {
    this.attr('fields')[fieldIndex].attr('value', value);
  },
});

export default canComponent.extend({
  tag: 'assessments-local-custom-attributes',
  view: canStache(template),
  viewModel,
});
