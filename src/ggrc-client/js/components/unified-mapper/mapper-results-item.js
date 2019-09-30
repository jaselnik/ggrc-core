/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import './mapper-results-item-status';
import './mapper-results-item-details';
import './mapper-results-item-attrs';
import '../object-selection/object-selection-item';
import template from './templates/mapper-results-item.stache';
import Snapshot from '../../models/service-models/snapshot';
import * as businessModels from '../../models/business-models';

const viewModel = canMap.extend({
  define: {
    showOpenButton: {
      get() {
        return this.attr('searchOnly') || this.attr('isBulkUpdateView');
      },
    },
    isBulkUpdateView: {
      get() {
        return this.attr('itemDetailsViewType') === 'bulk-update';
      },
    },
    viewClass: {
      get() {
        return this.attr('isBulkUpdateView') ? 'bulk-update-view' : '';
      },
    },
  },
  itemData: {},
  searchOnly: false,
  drawRelatedAssessments: false,
  selectedColumns: [],
  serviceColumns: [],
  showDetails: false,
  itemDetailsViewType: '',
  title() {
    let displayItem = this.displayItem();
    return displayItem.title ||
      displayItem.name ||
      displayItem.email;
  },
  displayItem() {
    let itemData = this.attr('itemData');
    return itemData.revision ?
      itemData.revision.content :
      itemData;
  },
  objectTypeIcon() {
    let objectType = this.objectType();
    let Model = businessModels[objectType];
    return 'fa-' + Model.table_singular;
  },
  toggleIconCls() {
    return this.attr('showDetails') ? 'fa-caret-down' : 'fa-caret-right';
  },
  toggleDetails() {
    this.attr('showDetails', !this.attr('showDetails'));
  },
  isSnapshot() {
    return this.attr('itemData.type') === Snapshot.model_singular;
  },
  objectType() {
    if (this.isSnapshot()) {
      return this.attr('itemData.child_type');
    }
    return this.attr('itemData.type');
  },
  showRelatedAssessments() {
    this.dispatch({
      type: 'showRelatedAssessments',
      instance: this.displayItem(),
    });
  },
});

const events = {
  // When item was deleted
  '{viewModel.itemData} destroyed'() {
    const viewModel = this.viewModel;

    viewModel.dispatch({
      type: 'itemDataDestroyed',
      itemId: viewModel.attr('itemData.id'),
    });
  },
};

export default canComponent.extend({
  tag: 'mapper-results-item',
  view: canStache(template),
  leakScope: true,
  viewModel,
  events,
});
