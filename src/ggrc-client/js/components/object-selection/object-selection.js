/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canMap from 'can-map';
import canComponent from 'can-component';
/**
 * Object Selection component
 */
export default canComponent.extend({
  tag: 'object-selection',
  leakScope: true,
  viewModel: canMap.extend({
    state: null,
    selectedItems: [],
    items: [],
    // This is an array by default replace with deferred on actual load
    allItems: [],
    disabledIds: [],
    allSelected: false,
    selectAllCheckboxValue: false,
    select: function (item) {
      let id = item.attr('id');
      let type = item.attr('type');

      if (this.indexOfSelected(id, type) < 0) {
        this.attr('selectedItems').push(item);
        this.markItem(id, type, true);
      } else {
        console.warn(`Same Object is Selected Twice! id: ${id} type: ${type}`);
      }
    },
    deselect: function (item) {
      let id = item.attr('id');
      let type = item.attr('type');
      let list = this.attr('selectedItems');
      let index = this.indexOfSelected(id, type);
      if (index >= 0) {
        list.splice(index, 1);
        this.markItem(id, type, false);
        this.attr('allSelected', false);
      }
    },
    indexOfSelected: function (id, type) {
      let list = this.attr('selectedItems');
      let index = -1;
      list.each(function (item, i) {
        if (id === item.attr('id') && type === item.attr('type')) {
          index = i;
          return false;
        }
      });
      return index;
    },
    markItem: function (id, type, isSelected) {
      this.attr('items').each(function (item) {
        if (id === item.attr('id') && type === item.attr('type')) {
          item.attr('markedSelected', isSelected);
          return false;
        }
      });
    },
    toggleItems: function (isSelected) {
      this.attr('items').each(function (item) {
        if (!item.attr('isDisabled')) {
          item.attr('markedSelected', isSelected);
        }
      });
    },
    markSelectedItems: function () {
      this.attr('selectedItems').each(function (selected) {
        this.markItem(selected.attr('id'), selected.attr('type'), true);
      }.bind(this));
    },
    emptySelection: function () {
      this.attr('allSelected', false);
      // Remove all selected items
      this.attr('selectedItems').replace([]);
      // Remove visual selection
      this.toggleItems(false);
    },
    deselectAll: function () {
      this.emptySelection();
    },
    selectAll: function () {
      let selectedItems;
      let disabledIds = this.attr('disabledIds');
      this.attr('allSelected', true);
      // Replace with actual items loaded from Query API
      this.attr('allItems')
        .done(function (allItems) {
          selectedItems = allItems.filter(function (item) {
            return disabledIds.indexOf(item.id) < 0;
          });
          this.attr('selectedItems').replace(selectedItems);
          // Add visual selection
          this.toggleItems(true);
        }.bind(this))
        .fail(function () {
          this.clearSelection();
        }.bind(this));
    },
  }),
  events: {
    '{viewModel.state} resetSelection'() {
      this.viewModel.emptySelection();
    },
    '{viewModel.items} add': function () {
      this.viewModel.markSelectedItems();
    },
    'object-selection-item selectItem': function (el, ev, item) {
      this.viewModel.select(item);
    },
    'object-selection-item deselectItem': function (el, ev, item) {
      this.viewModel.deselect(item);
    },
    '{viewModel} selectAllCheckboxValue': function ([scope], ev, value) {
      if (value) {
        this.viewModel.selectAll();
      } else {
        this.viewModel.deselectAll();
      }
    },
  },
});
