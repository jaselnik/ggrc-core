/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loMap from 'lodash/map';
import loSortBy from 'lodash/sortBy';
import loLast from 'lodash/last';
import makeArray from 'can-util/js/make-array/make-array';
import canList from 'can-list';
import canMap from 'can-map';
import {
  isSnapshot,
  isSnapshotModel,
  isSnapshotRelated,
  toObject,
  transformQueryToSnapshot,
} from './snapshot-utils';
import {
  related,
  initMappedInstances,
  isObjectContextPage,
  getPageType,
  isMyWork,
} from './current-page-utils';
import {
  buildParam,
  batchRequests,
  buildCountParams,
} from './query-api-utils';
import {
  getWidgetConfigs,
  getWidgetConfig,
} from './widgets-utils';
import {
  transformQueryForMega,
} from './mega-object-utils';
import {getRolesForType} from './acl-utils';
import {getMappingList} from '../../models/mappers/mappings';
import {caDefTypeName} from './custom-attribute/custom-attribute-config';
import Cacheable from '../../models/cacheable';
import * as businessModels from '../../models/business-models';
import {
  fileSafeCurrentDate,
  runExport,
} from './import-export-utils';
import {
  getTreeViewHeaders,
  setTreeViewHeaders,
} from './display-prefs-utils';
import TreeViewConfig from '../../apps/base-widgets';

/**
* TreeView-specific utils.
*/

let baseWidgets = TreeViewConfig.attr('base_widgets_by_type');
let defaultOrderTypes = TreeViewConfig.attr('defaultOrderTypes');
let allTypes = Object.keys(baseWidgets.attr());
let orderedModelsForSubTier = {};


let SUB_TREE_ELEMENTS_LIMIT = 20;
let SUB_TREE_FIELDS = Object.freeze([
  'id',
  'type',
  'selfLink',
  'viewLink',
  'slug',

  // title fields
  'title',
  'email',
  'name',

  // snapshot fields
  'revision',
  'child_id',
  'child_type',
  'is_latest_revision',

  // edit rights
  'archived',
  'readonly',

  // AT fields
  'DEFAULT_PEOPLE_LABELS',

  // Workflow fields
  'workflow_state',

  // CTGOT fields
  'next_due_date',
  'end_date',
  'isOverdue',
  'is_verification_needed',
]);

let FULL_SUB_LEVEL_LIST = Object.freeze([
  'Cycle',
  'CycleTaskGroup',
  'CycleTaskGroupObjectTask',
]);

let NO_FIELDS_LIMIT_LIST = Object.freeze([
  'Assessment',
]);

const DEFAULT_SORT_KEY = 'updated_at';
const DEFAULT_SORT_DIRECTION = 'desc';
const NO_DEFAULT_SORTING_LIST = Object.freeze([
  'Cycle',
  'TaskGroup',
  'TaskGroupTask',
  'CycleTaskGroupObjectTask',
]);

allTypes.forEach(function (type) {
  let related = baseWidgets[type].slice(0);
  let types = loMap(related, (type) => {
    return {
      name: type,
      order: defaultOrderTypes[type],
    };
  });
  types = loSortBy(types, ['order', 'name']);
  orderedModelsForSubTier[type] = loMap(types, 'name');
});

// Define specific rules for Workflow models
orderedModelsForSubTier.Cycle = ['CycleTaskGroup'];
orderedModelsForSubTier.CycleTaskGroup = ['CycleTaskGroupObjectTask'];
orderedModelsForSubTier.CycleTaskGroupObjectTask =
  getMappingList('CycleTaskGroupObjectTask');

function getSubTreeFields(parent, child) {
  let noFieldsLimitOnChild = hasNoFieldsLimit(child);
  let noFieldsLimitOnParent = _isFullSubTree(parent);
  return noFieldsLimitOnChild || noFieldsLimitOnParent ?
    [] :
    SUB_TREE_FIELDS;
}

function hasNoFieldsLimit(type) {
  return NO_FIELDS_LIMIT_LIST.indexOf(type) > -1;
}

/**
 * Gets available attributes for Model type
 * @param {String} modelType model type
 * @return {Array} list of available columns for model
 */
function getAvailableAttributes(modelType) {
  let Model = businessModels[modelType];
  let modelDefinition = Model.root_object;
  let disableConfiguration =
    !!Model.tree_view_options.disable_columns_configuration;

  let attrs = makeArray(
    Model.tree_view_options.attr_list ||
    Cacheable.attr_list
  ).filter(function (attr) {
    return !attr.deny;
  }).map(function (attr) {
    attr = Object.assign({}, attr);
    if (!attr.attr_sort_field) {
      attr.attr_sort_field = attr.attr_name;
    }
    return attr;
  }).sort(function (a, b) {
    if (a.order && !b.order) {
      return -1;
    } else if (!a.order && b.order) {
      return 1;
    }
    return a.order - b.order;
  });

  // add custom attributes information
  let customAttrs = disableConfiguration ?
    [] :
    GGRC.custom_attr_defs
      .filter(function (def) {
        let include = def.definition_type === modelDefinition;

        return include;
      }).map(function (def) {
        let disableSorting = def.attribute_type === caDefTypeName.RichText;

        return {
          attr_title: def.title,
          attr_custom_attribute_id: def.id,
          attr_name: def.title,
          attr_sort_field: def.title,
          display_status: false,
          attr_type: 'custom',
          disable_sorting: disableSorting,
        };
      });

  // add custom roles information
  let modelRoles = getRolesForType(modelType);
  let roleAttrs = modelRoles.map(function (role) {
    return {
      attr_title: role.name,
      attr_name: role.name,
      attr_sort_field: role.name,
      display_status: false,
      attr_type: 'role',
    };
  });

  return attrs.concat(customAttrs, roleAttrs);
}

/**
 * Get available and selected columns for Model type
 * @param {String} modelType - Model type.
 * @param {String} modelName - Model name.
 * @return {Object} Table columns configuration.
 */
function getColumnsForModel(modelType, modelName) {
  let Model = businessModels[modelType];
  let mandatoryAttrNames =
    Model.tree_view_options.mandatory_attr_names ||
    Cacheable.tree_view_options.mandatory_attr_names;
  let savedAttrList = getTreeViewHeaders(modelName || Model.model_singular);
  let displayAttrNames =
    savedAttrList.length ? savedAttrList :
      (Model.tree_view_options.display_attr_names ||
      Cacheable.tree_view_options.display_attr_names);
  let disableConfiguration =
    !!Model.tree_view_options.disable_columns_configuration;
  let mandatoryColumns;
  let displayColumns;

  let allAttrs = getAvailableAttributes(modelType);

  if (disableConfiguration) {
    return {
      available: allAttrs,
      selected: allAttrs,
      disableConfiguration: true,
    };
  }

  displayAttrNames = displayAttrNames.concat(mandatoryAttrNames);

  allAttrs.forEach(function (attr) {
    attr.display_status = displayAttrNames.indexOf(attr.attr_name) !== -1;
    attr.mandatory = mandatoryAttrNames.indexOf(attr.attr_name) !== -1;
  });

  mandatoryColumns = allAttrs.filter(function (attr) {
    return attr.mandatory;
  });

  displayColumns = allAttrs.filter(function (attr) {
    return attr.display_status && !attr.mandatory;
  });

  return {
    available: allAttrs,
    selected: mandatoryColumns.concat(displayColumns),
    mandatory: mandatoryAttrNames,
    disableConfiguration: false,
  };
}

/**
 * Set selected columns for Model type
 * @param {String} modelType - Model type.
 * @param {Array} columnNames - Array of column names.
 * @param {String} modelName - Model name.
 * @return {Object} Table columns configuration.
 */
function setColumnsForModel(modelType, columnNames, modelName) {
  let availableColumns =
    getColumnsForModel(modelType, modelName).available;
  let selectedColumns = [];
  let selectedNames = [];

  availableColumns.forEach(function (attr) {
    if (columnNames.indexOf(attr.attr_name) !== -1) {
      attr.display_status = true;
      selectedColumns.push(attr);
      if (!attr.mandatory) {
        selectedNames.push(attr.attr_name);
      }
    } else {
      attr.display_status = false;
    }
  });

  setTreeViewHeaders(
    modelName || businessModels[modelType].model_singular,
    selectedNames
  );

  return {
    available: availableColumns,
    selected: selectedColumns,
  };
}

/**
 * Returns array of columns configs.
 * Each config contains 'name', 'title', 'mandatory', 'selected' properties
 * @param {Array} available - Full list of available columns.
 * @param {Array} selected - List of selected columns.
 * @return {Array} Array of columns configs.
 */
function getVisibleColumnsConfig(available, selected) {
  const selectedColumns = makeArray(selected);
  const availableColumns = makeArray(available);
  const columns = [];

  availableColumns.forEach(function (attr) {
    const isSelected = selectedColumns
      .some((selectedAttr) => selectedAttr.attr_name === attr.attr_name);
    columns.push(new canMap({
      title: attr.attr_title,
      name: attr.attr_name,
      mandatory: attr.mandatory,
      selected: isSelected,
      order: attr.order,
    }));
  });

  return columns;
}

/**
 * Get sorting configuration for Model type
 * @param {String} modelType - Model type.
 * @return {Object} sorting configuration.
 */
function getSortingForModel(modelType) {
  let key = DEFAULT_SORT_KEY;
  let direction = DEFAULT_SORT_DIRECTION;

  if (NO_DEFAULT_SORTING_LIST.indexOf(modelType) !== -1) {
    key = null;
    direction = null;
  }

  return {
    key,
    direction,
  };
}

/**
 * Get available and selected models for the Model sub tier
 * @param {String} modelName - Model name.
 * @return {Object} Sub tier filter configuration.
 */
function getModelsForSubTier(modelName) {
  let Model = businessModels[modelName];
  let selectedModels;

  let availableModels = orderedModelsForSubTier[modelName] || [];

  if (Model.sub_tree_view_options.default_filter) {
    selectedModels = Model.sub_tree_view_options.default_filter;
  } else {
    selectedModels = availableModels;
  }

  return {
    available: availableModels,
    selected: selectedModels,
  };
}

/**
 *
 * @param {String} modelName - Name of requested objects.
 * @param {Object} parent - Information about parent object.
 * @param {String} parent.type - Type of parent object.
 * @param {Number} parent.id - ID of parent object.
 * @param {Object} pageInfo - Information about pagination, sorting and filtering
 * @param {Number} pageInfo.current -
 * @param {Number} pageInfo.pageSize -
 * @param {Number} pageInfo.sortBy -
 * @param {Number} pageInfo.sortDirection -
 * @param {Object} filter -
 * @param {Object} request - Collection of QueryAPI sub-requests
 * @param {Boolean} transformToSnapshot - Transform query to Snapshot
 * @param {String|null} operation - Type of operation
 * @return {Promise} Deferred Object
 */
function loadFirstTierItems(modelName,
  parent,
  pageInfo,
  filter,
  request,
  transformToSnapshot,
  operation) {
  let params = buildParam(
    modelName,
    pageInfo,
    makeRelevantExpression(modelName, parent.type, parent.id, operation),
    null,
    filter,
  );

  let requestData = request.slice() || canList();

  if (transformToSnapshot ||
    isSnapshotRelated(parent.type, modelName)) {
    params = transformQueryToSnapshot(params);
  }

  let requestedType = params.object_name;
  requestData.push(params);
  return $.when(...requestData.attr().map((el) => batchRequests(el)))
    .then((...response) => {
      response = loLast(response)[requestedType];

      response.values = response.values.map(function (source) {
        return _createInstance(source, modelName);
      });

      return response;
    });
}

/**
 *
 * @param {Array} widgetIds - Array of models for load in sub tree
 * @param {String} type - Type of parent object.
 * @param {Number} id - ID of parent object.
 * @param {String} filter - Filter.
 * @param {Object} pageInfo - Information about pagination, sorting and filtering
 * @return {Promise} - Items for sub tier.
 */
function loadItemsForSubTier(widgetIds, type, id, filter, pageInfo) {
  let relevant = {
    type: type,
    id: id,
    operation: 'relevant',
  };
  let showMore = false;
  let loadedModelObjects = [];

  return _buildSubTreeCountMap(widgetIds, relevant, filter)
    .then(function (result) {
      loadedModelObjects = getWidgetConfigs(Object.keys(result.countsMap));
      showMore = result.showMore;

      let dfds = loadedModelObjects.map(function (modelObject) {
        let subTreeFields = getSubTreeFields(type, modelObject.name);

        let params = buildParam(
          modelObject.name,
          pageInfo,
          relevant,
          subTreeFields,
          filter
        );

        params = _transformQuery(params, relevant, modelObject);

        return batchRequests(params);
      });

      let resultDfd = $.when(...dfds).promise();

      if (!related.initialized) {
        let mappedDfd = initMappedInstances();

        return $.when(mappedDfd, dfds).then(function () {
          return resultDfd;
        });
      }

      return resultDfd;
    })
    .then(function () {
      let directlyRelated = [];
      let notRelated = [];
      let response = makeArray(arguments);
      let total;

      loadedModelObjects.forEach(function (modelObject, index) {
        let values;

        if (isSnapshotModel(modelObject.name) &&
          response[index].Snapshot) {
          values = response[index].Snapshot.values;
          total = response[index].Snapshot.total;
        } else {
          values = response[index][modelObject.name].values;
          total = response[index][modelObject.name].total;
        }

        values.forEach(function (source) {
          let instance = _createInstance(source, modelObject.name);

          if (isDirectlyRelated(instance)) {
            directlyRelated.push(instance);
          } else {
            notRelated.push(instance);
          }
        });
      });

      return {
        directlyItems: directlyRelated,
        notDirectlyItems: notRelated,
        showMore: showMore,
        total: total,
      };
    });
}

/**
 * Transforms query params for Snapshots and Mega related objects
 * @param {Object} params query params
 * @param {Object} relevant parent object
 * @param {Object} widgetConfig initial config for query
 * @return {Object} query params
 */
function _transformQuery(params, relevant, widgetConfig) {
  if (isSnapshotRelated(relevant.type, params.object_name) ||
    widgetConfig.isObjectVersion) {
    params = transformQueryToSnapshot(params);
  } else if (widgetConfig.isMegaObject) {
    params = transformQueryForMega(params, widgetConfig.relation);
  }

  return params;
}

/**
 *
 * @param {String} requestedType - Type of requested object.
 * @param {String} relevantToType - Type of parent object.
 * @param {Number} relevantToId - ID of parent object.
 * @param {String|null} operation - Type of operation
 * @return {object} Returns expression for load items for 1st level of tree view.
 */
function makeRelevantExpression(requestedType,
  relevantToType,
  relevantToId,
  operation) {
  let isObjectBrowser = /^\/objectBrowser\/?$/
    .test(window.location.pathname);
  let expression;

  if (!isObjectBrowser) {
    expression = {
      type: relevantToType,
      id: relevantToId,
    };

    expression.operation = operation ? operation :
      _getTreeViewOperation(requestedType, relevantToType);
  }
  return expression;
}

/**
 * Check if object directly mapped to the current context.
 * @param {Object} instance - Instance of model.
 * @private
 * @return {Boolean} Is associated with the current context.
 */
function isDirectlyRelated(instance) {
  let needToSplit = isObjectContextPage() &&
    getPageType() !== 'Workflow';
  let relates = related.attr(instance.type);
  let result = true;
  let instanceId = isSnapshot(instance) ?
    instance.snapshot.id :
    instance.id;

  if (needToSplit) {
    result = !!(relates && relates[instanceId]);
  }

  return result;
}

/**
 *
 * @param {Array} widgetIds - selected widget id.
 * @param {Object} relevant - Relevant description
 * @param {String} filter - Filter string.
 * @return {Promise} - Counts for limitation load items for sub tier
 * @private
 */
function _buildSubTreeCountMap(widgetIds, relevant, filter) {
  let countQuery = [];
  let result;
  let countMap = {};

  if (_isFullSubTree(relevant.type)) {
    widgetIds.forEach(function (widgetId) {
      countMap[widgetId] = false;
    });
    return $.Deferred().resolve({
      countsMap: countMap,
      showMore: false,
    });
  }

  widgetIds.forEach((widgetId) => {
    let widgetConfig = getWidgetConfig(widgetId);
    let modelName = widgetConfig.name;

    let query = buildCountParams([modelName], relevant, filter);
    countQuery.push(_transformQuery(query[0], relevant, widgetConfig));
  });

  result = $.when(...countQuery.map((query) => batchRequests(query)))
    .then((...response) => {
      let total = 0;
      let showMore = widgetIds.some(function (model, index) {
        const count = Object.values(response[index])[0].total;

        if (!count) {
          return false;
        }

        if (total + count < SUB_TREE_ELEMENTS_LIMIT) {
          countMap[model] = count;
        } else {
          countMap[model] = SUB_TREE_ELEMENTS_LIMIT - total;
        }

        total += count;

        return total >= SUB_TREE_ELEMENTS_LIMIT;
      });

      return {
        countsMap: countMap,
        showMore: showMore,
      };
    });

  return result;
}

function _isFullSubTree(type) {
  return FULL_SUB_LEVEL_LIST.indexOf(type) >= 0;
}

/**
 * @param {Object} source - Instance object.
 * @param {String} modelName - Name of model.
 * @return {Cacheable} - Instance of model.
 * @private
 */
function _createInstance(source, modelName) {
  let instance;

  if (source.type === 'Snapshot') {
    instance = toObject(source);
  } else {
    instance = businessModels[modelName].model(source);
  }
  return instance;
}

function _getTreeViewOperation(objectName, relevantToType) {
  let isDashboard = isMyWork();

  if (!isDashboard && objectName === 'Person') {
    return 'related_people';
  }
  if (isDashboard) {
    return 'owned';
  }
  if (objectName === 'Evidence' && relevantToType === 'Audit') {
    return 'related_evidence';
  }
}

function startExport(
  modelName, parent, filter, request, transformToSnapshot, operation) {
  let params = buildParam(
    modelName,
    {},
    makeRelevantExpression(modelName, parent.type, parent.id, operation),
    'all',
    filter
  );

  if (transformToSnapshot || isSnapshotRelated(parent.type, modelName)) {
    params = transformQueryToSnapshot(params);
  }

  let requestData = request.slice() || canList();
  requestData.push(params);

  runExport({
    objects: requestData.serialize(),
    current_time: fileSafeCurrentDate(),
    exportable_objects: [requestData.length - 1],
  });
}

export {
  getAvailableAttributes,
  getColumnsForModel,
  setColumnsForModel,
  getSortingForModel,
  getModelsForSubTier,
  loadFirstTierItems,
  loadItemsForSubTier,
  makeRelevantExpression,
  getVisibleColumnsConfig,
  isDirectlyRelated,
  startExport,
};
