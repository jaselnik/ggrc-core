/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import '../clipboard-link/clipboard-link';
import canStache from 'can-stache';
import canDefineMap from 'can-define/map/map';
import canComponent from 'can-component';
import '../three-dots-menu/three-dots-menu';
import '../change-request-link/change-request-link';
import '../assessment/assessments-bulk-completion-button/assessments-bulk-completion-button';
import '../assessment/assessments-bulk-verify-button/assessments-bulk-verify-button';
import '../assessment/assessment-tree-actions/assessment-tree-actions';
import {
  isMyAssessments,
  isMyWork,
} from '../../plugins/utils/current-page-utils';
import {
  isAuditor,
} from '../../plugins/utils/acl-utils';
import {
  isSnapshotRelated,
} from '../../plugins/utils/snapshot-utils';
import {getAsmtCountForVerify} from '../../plugins/utils/bulk-update-service';
import {
  isAllowed,
  isAllowedFor,
} from '../../permission';
import template from './templates/tree-actions.stache';
import pubSub from '../../pub-sub';

const ViewModel = canDefineMap.extend({
  parentInstance: {
    value: null,
  },
  options: {
    value: null,
  },
  model: {
    value: null,
  },
  showedItems: {
    value: () => [],
  },
  searchPermalinkEnabled: {
    value: false,
  },
  pubSub: {
    value: () => pubSub,
  },
  addItem: {
    get() {
      return (this.options.objectVersion
        || this.parentInstance.attr('_is_sox_restricted')
        || this.isUpdateDenied())
        ? false
        : this.options.add_item_view ||
        this.model.tree_view_options.add_item_view ||
        'base_objects/tree-add-item';
    },
  },
  show3bbs: {
    get() {
      let modelName = this.model.model_singular;
      return !isMyAssessments()
        && modelName !== 'Document'
        && modelName !== 'Evidence';
    },
  },
  isSnapshots: {
    get() {
      let parentInstance = this.parentInstance;
      let model = this.model;

      return (isSnapshotRelated(parentInstance.type, model.model_singular)
        || this.options.objectVersion);
    },
  },
  isAssessmentOnAudit: {
    get() {
      let parentInstance = this.parentInstance;
      let model = this.model;

      return parentInstance.attr('type') === 'Audit' &&
        model.model_singular === 'Assessment';
    },
  },
  showBulkUpdate: {
    get() {
      return this.options.showBulkUpdate;
    },
  },
  showChangeRequest: {
    get() {
      const isCycleTask = (
        this.model.model_singular === 'CycleTaskGroupObjectTask'
      );

      return (
        isCycleTask &&
        isMyWork() &&
        !!GGRC.config.CHANGE_REQUEST_URL
      );
    },
  },
  showCreateTaskGroup: {
    get() {
      const isActiveTab =
        this.options.countsName === 'cycles:active';
      const isActiveWorkflow =
        this.parentInstance.status === 'Active';
      const isOneTimeWorkflow =
        this.parentInstance.repeat === 'off';
      return isActiveWorkflow
        && isOneTimeWorkflow
        && isActiveTab
        && !this.isUpdateDenied();
    },
  },
  showImport: {
    get() {
      let instance = this.parentInstance;
      let model = this.model;
      return !this.isSnapshots &&
        !model.isChangeableExternally &&
        (isAllowed(
          'update', model.model_singular, instance.context)
          || isAuditor(instance, GGRC.current_user));
    },
  },
  showExport: {
    get() {
      return this.showedItems.length;
    },
  },
  showBulkVerify: {
    value: false,
  },
  applySavedSearchPermalink() {
    pubSub.dispatch({
      type: 'applySavedSearchPermalink',
      widgetId: this.options.widgetId,
    });
  },
  setShowBulkVerify() {
    if (!this.isAssessmentOnAudit) {
      this.showBulkVerify = false;
      return;
    }

    const parentInstance = this.parentInstance;
    const relevant = {
      type: parentInstance.type,
      id: parentInstance.id,
      operation: 'relevant',
    };

    getAsmtCountForVerify(relevant).then((count) => {
      this.showBulkVerify = count > 0;
    });
  },
  isUpdateDenied() {
    const instance = this.parentInstance;
    return (instance.type === 'Workflow')
      && !isAllowedFor('update', instance);
  },
});

export default canComponent.extend({
  tag: 'tree-actions',
  view: canStache(template),
  leakScope: true,
  ViewModel,
  events: {
    inserted() {
      this.viewModel.setShowBulkVerify();
    },
    '{pubSub} triggerSearchPermalink'(scope, ev) {
      const widgetId = ev.widgetId;

      if (widgetId === this.viewModel.options.widgetId) {
        this.viewModel.searchPermalinkEnabled = ev.searchPermalinkEnabled;
      }
    },
  },
  export() {
    this.dispatch('export');
  },
});
