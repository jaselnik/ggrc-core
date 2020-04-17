/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canStache from 'can-stache';
import canDefineMap from 'can-define/map/map';
import template from './assessments-bulk-completion-button.stache';
import pubSub from '../../../pub-sub';

const ViewModel = canDefineMap.extend({
  enabled: {
    value: false,
  },
  parentInstance: {
    value: null,
  },
  openBulkCompleteMode() {
    pubSub.dispatch({
      type: 'enableBulkCompleteMode',
      enable: true,
    });
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-completion-button',
  view: canStache(template),
  ViewModel,
});
