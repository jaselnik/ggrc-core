/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/


import '../../../components/advanced-search/advanced-search-filter-container';
import '../../../components/advanced-search/advanced-search-mapping-container';

import canComponent from 'can-component';
import canStache from 'can-stache';
import canMap from 'can-map';
import template from './advanced-search-container.stache';
import {getAvailableAttributes} from '../../../plugins/utils/tree-view-utils';

const viewModel = canMap.extend({
  filterItems: [],
  availableAttributes: [],
  mappingItems: [],
  modelName: null,
  mappedToItems: [],
  resetFilters() {
    this.attr('filterItems', []);
    this.attr('mappingItems', []);
  },
  onSubmit() {
    this.dispatch('onSubmit');
  },
  init() {
    this.attr('availableAttributes', getAvailableAttributes(
      this.attr('modelName')));
  },
});

export default canComponent.extend({
  tag: 'advanced-search-container',
  view: canStache(template),
  viewModel,
});
