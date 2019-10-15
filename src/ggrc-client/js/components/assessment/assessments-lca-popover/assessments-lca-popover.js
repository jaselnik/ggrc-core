/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import template from './assessments-lca-popover.stache';

export default canComponent.extend({
  tag: 'assessments-lca-popover',
  view: canStache(template),
  viewModel: canMap.extend({
    relatedObjectsDfd: null,
    isLoading: false,
    async initRelatedObjects() {
      try {
        this.attr('isLoading', true);
        const values = await this.attr('relatedObjectsDfd');

        const relatedObjects = values.map(({revision, id}) => ({
          id,
          title: revision.content.title,
          slug: revision.content.slug,
        }));
        this.attr('relatedObjects', relatedObjects);
      } finally {
        this.attr('isLoading', false);
      }
    },
    init() {
      this.initRelatedObjects();
    },
  }),
});
