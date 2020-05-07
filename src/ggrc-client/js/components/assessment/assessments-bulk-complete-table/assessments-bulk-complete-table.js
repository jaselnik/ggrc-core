/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canDefineMap from 'can-define/map/map';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-table.stache';

const ViewModel = canDefineMap.extend({seal: false}, {
  assessmentsList: {
    value: () => [],
  },
  attributesList: {
    value: () => [],
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-table',
  view: canStache(template),
  ViewModel,
});
