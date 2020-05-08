/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canDefineMap from 'can-define/map/map';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-table-row.stache';
import {getPlainText} from '../../../../plugins/ggrc-utils';

const ViewModel = canDefineMap.extend({seal: false}, {
  rowData: {
    value: () => ({}),
  },
  isReadyForCompletion: {
    value: false,
  },
  validateAttribute(attribute) {
    if (!attribute.isApplicable) {
      return;
    }

    if (attribute.type === 'dropdown') {
      return;
    } else {
      this.performDefaultValidation(attribute);
    }
  },
  performDefaultValidation(attribute) {
    let {type, value, validation} = attribute;

    if (!validation.mandatory) {
      return;
    }

    switch (type) {
      case 'text':
        value = getPlainText(value);
        break;
      case 'person':
        value = value && value.length;
        break;
    }

    validation.valid = !!(value);
  },
  attributeValueChanged(value, index) {
    const attribute = this.rowData.attributes[index];
    attribute.value = value;
    this.validateAttribute(attribute);
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-table-row',
  view: canStache(template),
  ViewModel,
  events: {
    init() {
      this.viewModel.rowData.attributes.forEach((attribute) => {
        this.viewModel.validateAttribute(attribute);
      });
    },
  },
});
