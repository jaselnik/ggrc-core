/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loMap from 'lodash/map';
import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../dropdown/multiselect-dropdown';
import * as StateUtils from '../../plugins/utils/state-utils';
import template from './advanced-search-filter-state.stache';
import {isScopeModel} from '../../plugins/utils/models-utils';

/**
 * Filter State view model.
 * Contains logic used in Filter State component
 * @constructor
 */
let viewModel = canMap.extend({
  define: {
    label: {
      get() {
        return isScopeModel(this.attr('modelName')) ?
          'Launch Status' : 'State';
      },
    },
    /**
     * Contains available states for specific model.
     * @type {string}
     * @example
     * Active
     * Draft
     */
    filterStates: {
      get() {
        let items = this.attr('stateModel.items') || [];

        let allStates = StateUtils.getStatesForModel(
          this.attr('modelName'),
          this.attr('statesCollectionKey')
        );

        let filterStates = allStates.map((filterState) => {
          return {
            value: filterState,
            checked: (items.indexOf(filterState) > -1),
          };
        });

        return filterStates;
      },
    },
    /**
     * Indicates whether status tooltip should be displayed
     * @type {boolean}
     */
    statusTooltipVisible: {
      type: 'boolean',
      value: false,
      get: function () {
        return StateUtils.hasFilterTooltip(this.attr('modelName'));
      },
    },
    /**
     * Indicates whether operator should be displayed.
     * @type {boolean}
     */
    showOperator: {
      type: 'boolean',
      value: true,
    },
  },
  /**
   * Contains criterion's fields: operator, modelName, items.
   * Initializes filterStates.
   * @type {canMap}
  */
  stateModel: null,
  /**
   * Contains specific model name.
   * @type {string}
   * @example
   * Requirement
   * Regulation
   */
  modelName: null,
  /**
   * Contains key of collection which will be used to get list of available
   * statuses for certain model.
   * @type {Symbol|null}
   */
  statesCollectionKey: null,
  /**
   * Saves selected states.
   * @param {Array} selectedStates - selected states.
   */
  saveTreeStates: function (selectedStates) {
    let states;

    // in this case we save previous states
    if (!selectedStates) {
      return;
    }

    states = loMap(selectedStates, 'value');

    this.attr('stateModel.items', states);
  },
  /**
   * handler is passed to child component, which is dispatched when items changed
   * @param {Object} event - event which contains array of selected items.
   */
  statesChanged(event) {
    this.saveTreeStates(event.selected);
  },
});

/**
 * Filter State is a specific kind of Advanced Search Filter items.
 */
export default canComponent.extend({
  tag: 'advanced-search-filter-state',
  view: canStache(template),
  leakScope: true,
  viewModel: viewModel,
});
