/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import moment from 'moment';
import canStache from 'can-stache';
import canDefineMap from 'can-define/map/map';
import canComponent from 'can-component';
import '../object-tasks/object-tasks';
import '../mapped-counter/mapped-counter';
import Requirement from '../../models/business-models/requirement';
import {externalDirectiveObjects} from '../../plugins/models-types-collections';
import CycleTaskGroupObjectTask from '../../models/business-models/cycle-task-group-object-task';
import CycleTaskGroup from '../../models/business-models/cycle-task-group';
import Cycle from '../../models/business-models/cycle';
import {formatDate} from '../../plugins/utils/date-utils';
import template from './templates/tree-item-extra-info.stache';

const TYPES_TO_SHOW_REQUIREMENT = ['Contract', 'Policy',
  ...externalDirectiveObjects];

const ViewModel = canDefineMap.extend({
  triggered: {
    value: false,
  },
  active: {
    value: false,
  },
  spin: {
    value: false,
  },
  pendingContent: {
    value: () => [],
  },
  contentPromises: {
    value: () => [],
  },
  dfdReady: {
    value: () => $.Deferred(),
  },
  classes: {
    value: () => [],
  },
  instance: {
    value: null,
  },
  isLoading: {
    type: 'boolean',
    value: false,
  },
  readyStatus: {
    type: 'boolean',
    value: false,
  },
  isActive: {
    get() {
      return this.drawStatuses
        || this.isShowRequirement
        || this.isCycleTasks
        || this.isRequirement;
    },
  },
  isShowRequirement: {
    get() {
      return TYPES_TO_SHOW_REQUIREMENT.includes(this.instance.type);
    },
  },
  isRequirement: {
    get() {
      return this.instance instanceof Requirement;
    },
  },
  isCycleTaskGroupObjectTask: {
    get() {
      return this.instance instanceof CycleTaskGroupObjectTask;
    },
  },
  isCycleTaskGroup: {
    get() {
      return this.instance instanceof CycleTaskGroup;
    },
  },
  isCycleTasks: {
    get() {
      return this.isCycleTaskGroup
        || this.isCycleTaskGroupObjectTask
        || this.instance instanceof Cycle;
    },
  },
  raisePopover: {
    value: false,
    get() {
      return this.hovered || this.readyStatus;
    },
  },
  disablePopover: {
    get() {
      return this.instance instanceof Cycle;
    },
  },
  drawStatuses: {
    get() {
      return !!this.instance.attr('workflow_state');
    },
  },
  isShowOverdue: {
    get() {
      return this.isCycleTaskGroup || this.isCycleTaskGroupObjectTask;
    },
  },
  isOverdue: {
    get() {
      let isWorkflowOverdue =
        this.drawStatuses && this.instance.attr('workflow_state') === 'Overdue';

      let isCycleTasksOverdue = this.isCycleTasks
        && this.instance.attr('isOverdue');

      return isWorkflowOverdue || isCycleTasksOverdue;
    },
  },
  endDate: {
    get() {
      let date = this.instance.attr('end_date');
      let today = moment().startOf('day');
      let startOfDate = moment(date).startOf('day');
      if (!date || today.diff(startOfDate, 'days') === 0) {
        return 'Today';
      }
      return formatDate(date, true);
    },
  },
  cssClasses: {
    get() {
      let classes = [];

      if (this.isOverdue) {
        classes.push('state-overdue');
      }

      if (this.spin) {
        classes.push('fa-spinner');
        classes.push('fa-spin');
      } else if (this.active) {
        classes.push('active');
        classes.push('fa-info-circle');
      } else {
        classes.push('fa-info-circle');
      }

      return classes.join(' ');
    },
  },
  onEnter() {
    this.processPendingContent();
    this.active = true;
    if (!this.triggered) {
      this.triggered = true;
    }
  },
  onLeave() {
    this.active = false;
  },
  processPendingContent() {
    const extractedPendingContent = this.pendingContent.splice(0);
    const resolvedContent = extractedPendingContent.map((pending) => pending());

    this.addContent(...Array.from(resolvedContent));
  },
  addPromiseContent({callback}) {
    this.pendingContent.push(callback);
  },
  addContent(...dataPromises) {
    let dfds = this.contentPromises;
    let dfdReady = this.dfdReady;

    this.spin = true;
    dfds.push(...dataPromises);

    dfdReady = $.when(...Array.from(dfds)).then(() => {
      this.spin = false;
    });

    this.dfdReady = dfdReady;
  },
});

export default canComponent.extend({
  tag: 'tree-item-extra-info',
  view: canStache(template),
  leakScope: true,
  ViewModel,
});
