/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canStache from 'can-stache';
import canMap from 'can-map';
import template from './url-edit-control.stache';
import {sanitizer} from '../../plugins/utils/url-utils';

const viewModel = canMap.extend({
  inputValue: null,
  onAccept() {
    const {isValid, value: sanitizedValue} = sanitizer(this.attr('inputValue'));

    if (!isValid) {
      return;
    }

    this.dispatch({
      type: 'accept',
      value: sanitizedValue,
    });
  },
  onDismiss() {
    this.attr('inputValue', null);
    this.dispatch('dismiss');
  },
});

export default canComponent.extend({
  tag: 'url-edit-control',
  view: canStache(template),
  viewModel,
});
