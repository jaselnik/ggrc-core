/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canComponent from 'can-component';
import template from './templates/assessments-bulk-complete-popover-content.stache';
import canDefineMap from 'can-define/map/map';

const ViewModel = canDefineMap.extend({seal: false}, {
  relatedObjectsPromise: {
    value: null,
  },
  relatedObjects: {
    value: [],
  },
  assessmentType: {
    value: '',
  },
  isLoading: {
    value: false,
  },
  async initRelatedObjects() {
    try {
      this.isLoading = true;
      const values = await this.relatedObjectsPromise;
      this.relatedObjects = values;
    } finally {
      this.isLoading = false;
    }
  },
  init() {
    this.initRelatedObjects();
  },
});


export default canComponent.extend({
  tag: 'assessments-bulk-complete-popover-content',
  view: canStache(template),
  ViewModel,
});
