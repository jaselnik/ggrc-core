/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loResult from 'lodash/result';
import loIncludes from 'lodash/includes';
import loIsEmpty from 'lodash/isEmpty';
import loForEach from 'lodash/forEach';
import loFind from 'lodash/find';
import loIsEqual from 'lodash/isEqual';
import canBatch from 'can-event/batch/batch';
import canMap from 'can-map';
import {
  getMappingList,
} from '../../models/mappers/mappings';
import {
  getInstance,
  groupTypes,
} from '../../plugins/utils/models-utils';
import * as businessModels from '../../models/business-models';

/**
 *  @typedef SpecialConfig
 *  @type {Object}
 *  @property {String[]} types - An array contains typenames for which is set a
 *                               special config.
 *  @property {Object} config - Has fields with special values for viewModel.
 */

/**
 *  @typedef SpecialConfig
 *  @type {Object}
 *  @property {String[]} types - An array contains typenames for which is set a
 *                               special config.
 *  @property {Object} config - Has fields with special values for viewModel.
 */

const ObjectOperationsBaseVM = canMap.extend({
  /**
   * Extract certain config for passed type from config.
   * If there is special config for type then return it else return
   * general config.
   *
   * @param {String} type - Type for search.
   * @param {SpecialConfig} config - Config with general and special config cases.
   * @param {Object} config.general - Default config.
   * @param {SpecialConfig[]} config.special - Has array of special configs.
   * @return {Object} - extracted config.
   */
  extractConfig: function (type, config) {
    let resultConfig;
    let special = loResult(
      loFind(
        config.special,
        function (special) {
          return loIncludes(special.types, type);
        }),
      'config'
    );

    resultConfig = !loIsEmpty(special) ? special : config.general;
    return resultConfig;
  },
}, {
  define: {
    parentInstance: {
      get: function () {
        return getInstance(this.attr('object'), this.attr('join_object_id'));
      },
    },
    model: {
      get: function () {
        return businessModels[this.attr('type')];
      },
    },
    type: {
    /*
     * When object type is changed it should be needed to change a config.
     * For example, if not set a special config for type [TYPE] then is used
     * general config, otherwise special config.
     */
      set(mapType) {
        if (mapType === this.attr('type')) {
          return mapType;
        }

        let config = this.attr('config') || {};
        let resultConfig = ObjectOperationsBaseVM.extractConfig(
          mapType,
          config.serialize()
        );

        // We remove type because update action can make recursion (when we set
        // type)
        delete resultConfig.type;

        this.update(resultConfig);
        this.attr('currConfig', resultConfig);
        this.attr('resultsRequested', false);
        this.attr('entriesTotalCount', '');

        return mapType;
      },
    },
  },
  /**
   * Config is an object with general and special settings.
   *
   * @namespace
   * @property {Object} general - Has fields with general values for viewModel.
   * @property {SpecialConfig[]} special - Has array of special configs.
   */
  config: {
    general: {},
    special: [],
  },
  currConfig: null,
  showSearch: true,
  showResults: true,
  resultsRequested: false,
  type: 'Control', // We set default as Control
  availableTypes: function () {
    let list = getMappingList(this.attr('object'));
    return groupTypes(list);
  },
  object: '',
  is_loading: false,
  is_saving: false,
  join_object_id: '',
  selected: [],
  entries: [],
  entriesTotalCount: '',
  options: [],
  relevant: [],
  useSnapshots: false,
  onSearchCallback: $.noop(),
  onSubmit: function () {
    this.attr('is_loading', true);
    this.attr('entries').replace([]);
    this.attr('resultsRequested', true);
    this.attr('showResults', true);

    if (this.onSearchCallback) {
      this.onSearchCallback();
    }
  },
  onLoaded(element) {
    // set focus on the top modal window
    $('.modal:visible')
      .last()
      .focus();
  },
  /**
   * Updates view model fields to values from config.
   *
   * @param {Object} config - Plain object with values for updating
   */
  update: function (config) {
    canBatch.start();

    // do not update fields with the same values in VM and config
    loForEach(config, (value, key) => {
      let vmValue = this.attr(key);
      let hasSerialize = Boolean(vmValue && vmValue.serialize);

      if (hasSerialize) {
        vmValue = vmValue.serialize();
      }

      if (!loIsEqual(vmValue, value)) {
        this.attr(key, value);
      }
    });

    canBatch.stop();
  },
});

export default ObjectOperationsBaseVM;
