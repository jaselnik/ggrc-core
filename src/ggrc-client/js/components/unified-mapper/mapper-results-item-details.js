/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../related-objects/related-people-access-control';
import '../related-objects/related-people-access-control-group';
import '../people/deletable-people-group';
import '../unarchive-link';
import '../assessment/assessment-mapped-objects/assessment-mapped-objects';
import template from './templates/mapper-results-item-details.stache';
import * as businessModels from '../../models/business-models';

export default canComponent.extend({
  tag: 'mapper-results-item-details',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    init() {
      let instance = this.attr('instance');
      if (instance.snapshotObject) {
        this.attr('instance', instance.snapshotObject);
      } else {
        this.attr('model', businessModels[instance.type]);
      }
    },
    define: {
      assessmentType: {
        get() {
          const instance = this.attr('instance');
          return businessModels[instance.assessment_type].title_plural;
        },
      },
    },
    item: null,
    instance: null,
    model: null,
    isMapperDetails: true,
    adminRole: ['Admin'],
    deletableAdmin: false,
  }),
});
