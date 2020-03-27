/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-container.stache';

const viewModel = canMap.extend({
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-container',
  view: canStache(template),
  viewModel,
});
