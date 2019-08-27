/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/


import '../../collapsible-panel/collapsible-panel';

import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-complete.stache';
import ObjectOperationsBaseVM from '../../view-models/object-operations-base-vm';

const viewModel = ObjectOperationsBaseVM.extend({
  showSearch: false,
  showFields: false,
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete',
  view: canStache(template),
  viewModel,
});
