/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import makeArray from 'can-util/js/make-array/make-array';
import canMap from 'can-map';
import {
  buildRelevantIdsQuery,
  batchRequestsWithPromise as batchRequests,
} from './query-api-utils';
import {
  isSnapshotRelated,
  transformQueryToSnapshot,
} from './snapshot-utils';
import {getMappingList} from '../../models/mappers/mappings';
import {inferObjectType} from './models-utils';
import PersistentNotifier from '../persistent-notifier';
import {changeUrl, reloadPage} from '../../router';

/**
 * Util methods for work with Current Page.
 */

let relatedToCurrentInstance = new canMap({
  initialized: false,
});

function getPageModel() {
  if (GGRC.page_object) {
    return inferObjectType(GGRC.page_object);
  }
  return null;
}

let pageInstance = null;
function getPageInstance() {
  if (!pageInstance && GGRC.page_object) {
    pageInstance = inferObjectType(GGRC.page_object)
      .model($.extend({}, GGRC.page_object));
  }
  return pageInstance;
}

function initMappedInstances() {
  const currentPageInstance = getPageInstance();
  const reqParams = [];
  let models = getMappingList(currentPageInstance.type);

  relatedToCurrentInstance.attr('initialized', true);
  models = makeArray(models);

  models.forEach(function (model) {
    let query = buildRelevantIdsQuery(
      model,
      {},
      {
        type: currentPageInstance.type,
        id: currentPageInstance.id,
        operation: 'relevant',
      });
    if (isSnapshotRelated(currentPageInstance.type, model)) {
      query = transformQueryToSnapshot(query);
    }
    reqParams.push(batchRequests(query));
  });

  return Promise.all(reqParams)
    .then((response) => {
      models.forEach((model, idx) => {
        const ids = response[idx][model] ?
          response[idx][model].ids :
          response[idx].Snapshot.ids;
        const map = ids.reduce((mapped, id) => {
          mapped[id] = true;
          return mapped;
        }, {});
        relatedToCurrentInstance.attr(model, map);
      });
      return relatedToCurrentInstance;
    });
}

// To identify pages like My Work, My Assessments and Admin Dashboard on the Server-side
// was defined variable GGRC.pageType, because for all of them getPageInstance().type = 'Person'.
// For other pages using getPageInstance() object.
function getPageType() {
  return GGRC.pageType ? GGRC.pageType : getPageInstance().type;
}

function isMyAssessments() {
  return getPageType() === 'MY_ASSESSMENTS';
}

function isMyWork() {
  return getPageType() === 'MY_WORK';
}

function isAllObjects() {
  return getPageType() === 'ALL_OBJECTS';
}

function isAdmin() {
  return getPageType() === 'ADMIN';
}

function isAuditPage() {
  return getPageInstance().type === 'Audit';
}
/**
 *
 * @return {boolean} False for My Work, All Objects and My Assessments pages and True for the rest.
 */
function isObjectContextPage() {
  return !GGRC.pageType;
}

function _beforeUnloadHandler(event) {
  event.preventDefault();
  event.returnValue = '';
}

const notifier = new PersistentNotifier({
  whileQueueHasElements() {
    window.addEventListener('beforeunload', _beforeUnloadHandler);
  },
  whenQueueEmpties() {
    window.removeEventListener('beforeunload', _beforeUnloadHandler);
  },
});

const delayLeavingPageUntil = $.proxy(notifier, 'queue');

function navigate(url) {
  notifier.onEmpty(_goToUrl.bind(null, url));
}

function _goToUrl(url) {
  if (!url) {
    reloadPage();
  } else {
    changeUrl(url);
  }
}

export {
  relatedToCurrentInstance as related,
  getPageModel,
  getPageInstance,
  initMappedInstances,
  getPageType,
  isMyAssessments,
  isMyWork,
  isAuditPage,
  isAllObjects,
  isAdmin,
  isObjectContextPage,
  navigate,
  delayLeavingPageUntil,
};
