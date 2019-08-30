/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-button.stache';

export default canComponent.extend({
  tag: 'assessments-bulk-complete-button',
  view: canStache(template),
  viewModel: canMap.extend({
    isButtonView: false,
  }),
});
