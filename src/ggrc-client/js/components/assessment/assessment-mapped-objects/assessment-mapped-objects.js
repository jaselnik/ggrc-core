/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import {
  buildParam,
  batchRequests,
} from '../../../plugins/utils/query-api-utils';
import template from './assessment-mapped-objects.stache';

export default canComponent.extend({
  tag: 'assessment-mapped-objects',
  view: canStache(template),
  viewModel: canMap.extend({
    instance: {},
    mappedObjects: [],
    isInitialized: false,
    isLoading: false,
    expanded: false,
    loadMappedObjects() {
      const instance = this.attr('instance');

      const filters = {
        expression: {
          left: {
            left: 'child_type',
            op: {
              name: '=',
            },
            right: instance.attr('assessment_type'),
          },
          op: {
            name: 'AND',
          },
          right: {
            object_name: 'Assessment',
            op: {
              name: 'relevant',
            },
            ids: [
              instance.attr('id'),
            ],
          },
        },
      };

      const fields = ['id', 'revision'];

      const param = buildParam('Snapshot', {}, null, fields, filters);

      return batchRequests(param).then(({Snapshot: {values}}) => values);
    },
    async initMappedObjects() {
      try {
        this.attr('isLoading', true);
        const objects = await this.loadMappedObjects();

        const mappedObjects = objects.map(({revision, id}) => ({
          id,
          revision,
          type: 'Snapshot',
          child_type: revision.content.type,
          child_id: revision.content.id,
        }));
        this.attr('mappedObjects', mappedObjects);

        this.attr('isInitialized', true);
      } finally {
        this.attr('isLoading', false);
      }
    },
  }),
  events: {
    '{viewModel} expanded'() {
      const needToMakeRequest = this.viewModel.attr('expanded') &&
        !this.viewModel.attr('isInitialized');
      if (needToMakeRequest) {
        this.viewModel.initMappedObjects();
      }
    },
  },
});
