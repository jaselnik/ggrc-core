/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canMap from 'can-map';
import template from './issue-tracker-enable.stache';
import logger from './issue-tracker-log';
import {getPageInstance} from '../current-page-utils';
import Assessment from '../../../models/business-models/assessment';
import QueryParser from '../../../generated/ggrc_filter_query_parser';
import {request} from '../request-utils';

/* eslint-disable no-console */

const audit = getPageInstance();

let isButtonActivated = false;

let vm;

const relevantToAuditFilter = {
  expression: {
    object_name: audit.type,
    op: {name: 'relevant'},
    ids: [audit.id],
  },
};

const getRelatedAssessmentsIds = async (filters = relevantToAuditFilter,
  limit) => {
  let query = {
    object_name: 'Assessment',
    filters,
    type: 'ids',
  };

  if (limit) {
    query.limit = limit;
  }
  let response = await request('/query', [query]);
  return response[0].Assessment.ids;
};
const updateAssessments = (assessments) => {
  let result = $.Deferred().resolve([]);

  return Array.from(assessments).reduce((dfd, assessment) => {
    return dfd.then((updated) => {
      let deferred = new $.Deferred();

      assessment.save().then((assessment) => {
        logger.add({
          id: assessment.id,
          status: 'loaded',
        });

        Assessment.removeFromCacheById(assessment.id);

        deferred.resolve([...updated, assessment]);
      }, () => {
        logger.add({
          id: assessment.id,
          status: 'error',
        });

        deferred.resolve([...updated, {
          error: 'Assessment not updated',
          id: assessment.id,
        }]);
      });

      return deferred;
    });
  }, result);
};

const IssueTrackerEnabler = canMap.extend({
  state: {
    open: false,
  },
  from: 0,
  to: 300,
  isStopped: false,
  slugsString: '',
  done: false,
  audit: audit,
  statesMap: {},
  statesList: [],
  slugs: [],
  checked: 0,
  ids: [],
  logs: [],
  open() {
    this.attr('state.open', true);
  },
  stop() {
    this.attr('isStopped', true);
  },
  showLog() {
    let log = logger.readLog();
    console.warn(`Show log, items in the log: ${log.length}`);

    this.attr('logs').replace(log);
  },
  initIds(ids) {
    this.attr('statesList').replace([]);
    this.attr('checked', 0);
    ids.forEach((id) => {
      let state = new canMap({
        id,
        state: 'unchecked',
      });
      this.attr('statesList').push(state);
      this.attr(`statesMap.${id}`, state);
    });

    this.attr('ids', ids);
  },
  async enableITForAll() {
    let from = this.attr('from');
    let to = this.attr('to');
    let ids = await getRelatedAssessmentsIds(relevantToAuditFilter, [from, to]);

    this.initIds(ids);

    logger.reset();

    this.enableByIds(ids);
  },
  async enableForSlugs() {
    let slugString = this.attr('slugsString');
    let slugs = slugString.split(',').map((slug) => slug.trim());

    this.attr('slugs', slugs);

    let query = {
      expression: {
        left: 'slug',
        op: {name: 'IN'},
        right: slugs,
      },
    };
    let filter = QueryParser.joinQueries(relevantToAuditFilter, query);

    let ids = await getRelatedAssessmentsIds(filter);

    this.initIds(ids);

    logger.reset();

    this.enableByIds(ids);
  },
  enableByIds(ids) {
    let assessmentsForUpdate = ids.splice(0, 5)
      .map((id) => Assessment.findOne({id}));

    return $.when(...assessmentsForUpdate)
      .then((...assessments) => {
        let assessmentWithoutIT = assessments.filter((asmt) => {
          let isTrackerDisabled = !asmt.attr('issue_tracker')
            || !asmt.attr('issue_tracker.enabled');

          let checked = this.attr('checked');

          this.attr('checked', checked + 1);
          if (!isTrackerDisabled) {
            logger.add({
              id: asmt.id,
              status: 'skipped',
            });

            this.attr(`statesMap.${asmt.id}.state`, 'skipped');
          }

          return isTrackerDisabled;
        });

        if (!assessmentWithoutIT.length) {
          return [];
        }

        let updatingAsmts = assessmentWithoutIT.map((asmt) => {
          let it = asmt.attr('issue_tracker');
          let parentIT = audit.attr('issue_tracker');

          it.attr('issue_priority', it.attr('issue_priority')
            || parentIT.attr('issue_priority'));
          it.attr('issue_severity', it.attr('issue_severity')
            || parentIT.attr('issue_severity'));
          it.attr('component_id', it.attr('component_id')
            || parentIT.attr('component_id'));
          it.attr('hotlist_id', it.attr('hotlist_id')
            || parentIT.attr('hotlist_id'));
          it.attr('issue_type', it.attr('issue_type')
            || parentIT.attr('issue_type'));
          it.attr('title', it.attr('title') || asmt.attr('title'));
          it.attr('enabled', true);
          return asmt;
        });

        return updateAssessments(updatingAsmts);
      }, () => {
        // got an error on
        ids.forEach((id) => {
          this.attr(`statesMap.${id}.state`, 'error');
        });
      })
      .then((updateReady) => {
        updateReady.forEach((a) => {
          if (!a.error) {
            this.attr(`statesMap.${a.id}.state`, 'loaded');
          } else {
            this.attr(`statesMap.${a.id}.state`, 'error');
          }
        });
      })
      .always(() => {
        let isStopped = this.attr('isStopped');

        if (ids.length && !isStopped) {
          return this.enableByIds(ids);
        } else {
          this.attr('done', true);
        }
      });
  },
});

GGRC.enableIssueTracker = () => {
  if (audit.type !== 'Audit') {
    console.warn(`This function is applicable only in Audit scope.
      Please open the Audit page and try again!`);
    return;
  }

  if (!audit.issue_tracker
    || audit.issue_tracker && !audit.issue_tracker.enabled) {
    console.warn('Issue tracker must be enabled for this Audit!');
    return;
  }

  if (isButtonActivated) {
    console.warn('Issue tracker script has already activated!');
    vm.open();
  } else {
    isButtonActivated = true;

    let renderer = canStache(template);
    let fragment = renderer(new IssueTrackerEnabler());

    $('section.footer').append(fragment);
  }
};
