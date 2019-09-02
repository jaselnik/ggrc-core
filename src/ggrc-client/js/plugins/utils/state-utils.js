/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loDifference from 'lodash/difference';
import {
  isMyAssessments,
  isMyWork,
} from './current-page-utils';
import QueryParser from '../../generated/ggrc_filter_query_parser';

/**
 * Utils for state.
 */
let snapshotableObject = GGRC.config.snapshotable_objects;

const STATES_KEYS = {
  BULK_COMPLETE: Symbol(
    `States which are available
     for bulk complete operation`
  ),
};

let statesModels = [
  {
    models: ['AssessmentTemplate', 'Project', 'Program']
      .concat(snapshotableObject),
    states: ['Active', 'Draft', 'Deprecated'],
  },
  {
    models: ['Assessment'],
    states: [
      'Not Started', 'In Progress', 'In Review', 'Rework Needed',
      'Completed (no verification)', 'Completed and Verified', 'Deprecated',
    ],
    [STATES_KEYS.BULK_COMPLETE]: ['Not Started', 'In Progress',
      'Rework Needed'],
  },
  {
    models: ['Audit'],
    states: [
      'Planned', 'In Progress', 'Manager Review',
      'Ready for External Review', 'Completed', 'Deprecated',
    ],
  },
  {
    models: [
      'Person', 'Workflow', 'TaskGroup', 'Cycle',
    ],
    states: [],
  },
  {
    models: [
      'CycleTaskGroupObjectTask',
    ],
    states: [
      'Assigned', 'In Progress', 'Finished',
      'Declined', 'Deprecated', 'Verified',
    ],
    bulkStates: [
      'In Progress', 'Finished',
      'Declined', 'Deprecated', 'Verified',
    ],
  },
  {
    models: ['Issue'],
    states: [
      'Active', 'Draft', 'Deprecated', 'Fixed', 'Fixed and Verified',
    ],
  }, {
    models: ['Evidence', 'Document'],
    states: [
      'Active', 'Deprecated',
    ],
  },
];

/**
 * Check if model has state.
 * @param {String} model - The model name
 * @return {Boolean} True or False
 */
function hasState(model) {
  let pair = getStatesModelsPair(model);

  if (!pair) {
    return false;
  }

  return pair.states.length > 0;
}

/**
 * Check if model should have filter by state.
 * @param {String} model - The model name
 * @return {Boolean} True or False
 */
function hasFilter(model) {
  return hasState(model);
}

/**
 * Check if tooltip should be shown for filter by state
 * @param {String} model - The model name
 * @return {Boolean} True or False
 */
function hasFilterTooltip(model) {
  return model === 'Product' || model === 'System';
}

/**
 * Get States-Models pair.
 * @param {String} model - The model name
 * @return {Object} object with 'models' and 'states' properties
 */
function getStatesModelsPair(model) {
  let pairs = statesModels.filter(function (item) {
    return item.models.indexOf(model) > -1;
  });

  return pairs.length > 0 ? pairs[0] : null;
}

/**
 * Get states for model.
 * @param {String} model - The model name
 * @param {Symbol=} statesCollectionKey - describes key of collection with
 * states for certain model.
 * @return {Array} array of strings
 */
function getStatesForModel(model, statesCollectionKey = null) {
  let pair = getStatesModelsPair(model);

  if (!pair) {
    return [];
  }

  return pair[statesCollectionKey]
    ? pair[statesCollectionKey]
    : pair.states; // use "states" collection by default
}

/**
 * Get states for model that can be used
 * as target in Bulk Update modal.
 * @param {String} model - The model name
 * @return {Array} array of strings
 */
function getBulkStatesForModel(model) {
  let pair = getStatesModelsPair(model);
  return pair && pair.bulkStates ? pair.bulkStates : [];
}

/**
 * Transform query for objects into query which filter them by state.
 * @param {Array} statuses - array of active statuses
 * @param {String} modelName - model name
 * @param {Boolean} inverse - the flag indicathes whether filter should be inversed
 * @param {Symbol=} statesCollectionKey - Describes key of collection which
 * will be used to get list of available statuses for certain model.
 * @return {String} The transformed query
 */
function buildStatusFilter(
  statuses,
  modelName,
  inverse,
  statesCollectionKey = null
) {
  if (inverse) {
    let allStatuses = getStatesForModel(modelName, statesCollectionKey);
    statuses = loDifference(allStatuses, statuses);
  }

  let filter = modelName === 'Assessment' ?
    buildAssessmentFilter(statuses, buildFilterExpression) :
    buildFilterExpression(statuses, modelName);

  return filter;
}

/**
 * Return query for unlocked objects
 * @return {String} The unlocked query
 */
function unlockedFilter() {
  return '"Archived"="False"';
}

function buildFilterExpression(statuses, modelName) {
  let statusFieldName = getStatusFieldName(modelName);

  let filter = {
    expression: {
      left: statusFieldName,
      op: {name: 'IN'},
      right: statuses,
    },
  };

  return filter;
}

/**
* Return status field name for model
* @param {String} modelName - model name
* @return {String} status field name
*/
function getStatusFieldName(modelName) {
  let modelToStateFieldMap = {
    CycleTaskGroupObjectTask: 'Task State',
  };
  let fieldName = modelToStateFieldMap[modelName] || 'Status';

  return fieldName;
}

/**
 * Build statuses filter for Assessment model
 * @param {Array} statuses - array of active statuses
 * @param {function} builder - function building a query
 * @return {String} statuses filter
 */
function buildAssessmentFilter(statuses, builder) {
  // copy array. Do not change original
  statuses = statuses.slice();

  let verifiedIndex = statuses.indexOf('Completed and Verified');
  let completedIndex = statuses.indexOf('Completed (no verification)');

  // do not update statuses
  if (verifiedIndex === -1 && completedIndex === -1) {
    return builder(statuses, 'Assessment');
  }

  if (verifiedIndex > -1 && completedIndex > -1) {
    // server doesn't know about "Completed (no verification)"
    // we replace it with "Completed"
    statuses.splice(completedIndex, 1, 'Completed');

    // database doesn't have "Verified" status
    // remove it
    statuses.splice(verifiedIndex, 1);

    return builder(statuses, 'Assessment');
  }

  let isVerified;
  if (completedIndex > -1 && verifiedIndex === -1) {
    isVerified = false;
    statuses.splice(completedIndex, 1);
  } else if (verifiedIndex > -1 && completedIndex === -1) {
    isVerified = true;
    statuses.splice(verifiedIndex, 1);
  }

  let completedStateExpression = {
    expression: {
      left: {
        left: 'Status',
        op: {name: '='},
        right: 'Completed',
      },
      op: {name: 'AND'},
      right: {
        left: 'verified',
        op: {name: '='},
        right: isVerified.toString(),
      },
    },
  };

  let result = statuses.length ? QueryParser.joinQueries(
    builder(statuses, 'Assessment'), completedStateExpression, 'OR')
    : completedStateExpression;

  return result;
}

/**
 * Get default states for model.
 * @param {String} model - The model name
 * @return {Array} List of default states for model
 */
function getDefaultStatesForModel(model) {
  let states;

  if (isMyAssessments()) {
    states = ['Not Started', 'In Progress'];
  } else if (isMyWork() && model === 'CycleTaskGroupObjectTask') {
    states = ['Assigned', 'In Progress'];
  } else {
    states = getStatesForModel(model);
  }

  return states;
}

export {
  STATES_KEYS,
  hasState,
  hasFilter,
  hasFilterTooltip,
  unlockedFilter,
  getStatesForModel,
  getBulkStatesForModel,
  getDefaultStatesForModel,
  buildStatusFilter,
  getStatusFieldName,
};
