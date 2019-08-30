/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import '../clipboard-link/clipboard-link';
import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../three-dots-menu/three-dots-menu';
import '../change-request-link/change-request-link';
import '../assessment/assessments-bulk-complete-button/assessments-bulk-complete-button';
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
import {requestAssessmentsCount} from '../../plugins/utils/bulk-update-service';
import {isAllowed} from '../../permission';
import template from './templates/tree-actions.stache';
import pubSub from '../../pub-sub';

export default canComponent.extend({
  tag: 'tree-actions',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    define: {
      addItem: {
        type: String,
        get: function () {
          return this.attr('options.objectVersion') ?
            false :
            this.attr('options').add_item_view ||
            this.attr('model').tree_view_options.add_item_view ||
            'base_objects/tree_add_item';
        },
      },
      show3bbs: {
        type: Boolean,
        get: function () {
          let modelName = this.attr('model').model_singular;
          return !isMyAssessments()
            && modelName !== 'Document'
            && modelName !== 'Evidence';
        },
      },
      isSnapshots: {
        type: Boolean,
        get: function () {
          let parentInstance = this.attr('parentInstance');
          let model = this.attr('model');

          return (isSnapshotRelated(parentInstance.type, model.model_singular)
            || this.attr('options.objectVersion'));
        },
      },
      isAssessmentOnAudit: {
        get() {
          let parentInstance = this.attr('parentInstance');
          let model = this.attr('model');

          return parentInstance.type === 'Audit' &&
            model.model_singular === 'Assessment';
        },
      },
      showBulkUpdate: {
        type: 'boolean',
        get: function () {
          return this.attr('options.showBulkUpdate');
        },
      },
      showChangeRequest: {
        get() {
          const isCycleTask = (
            this.attr('model').model_singular === 'CycleTaskGroupObjectTask'
          );

          return (
            isCycleTask &&
            isMyWork() &&
            !!GGRC.config.CHANGE_REQUEST_URL
          );
        },
      },
      showCreateTaskGroup: {
        type: 'boolean',
        get() {
          const isActiveTab =
            this.attr('options.countsName') === 'cycles:active';
          const isActiveWorkflow =
            this.attr('parentInstance.status') === 'Active';
          const isOneTimeWorkfow =
            this.attr('parentInstance.repeat') === 'off';
          return isActiveWorkflow && isOneTimeWorkfow && isActiveTab;
        },
      },
      showImport: {
        type: 'boolean',
        get() {
          let instance = this.attr('parentInstance');
          let model = this.attr('model');
          return !this.attr('isSnapshots') &&
            !model.isChangeableExternally &&
            (isAllowed(
              'update', model.model_singular, instance.context)
              || isAuditor(instance, GGRC.current_user));
        },
      },
      showExport: {
        type: 'boolean',
        get() {
          return this.attr('showedItems').length;
        },
      },
      showBulkComplete: {
        value: false,
        get(lastSetValue, setAttrValue) {
          setAttrValue(lastSetValue); // set default value before request

          if (this.attr('isAssessmentOnAudit')) {
            const parentInstance = this.attr('parentInstance');
            const relevant = {
              type: parentInstance.type,
              id: parentInstance.id,
              operation: 'relevant',
            };

            requestAssessmentsCount(relevant)
              .then((count) => {
                setAttrValue(count > 0);
              });
          }
        },
      },
    },
    parentInstance: null,
    options: null,
    model: null,
    showedItems: [],
    savedSearchPermalink: '',
    pubSub,
  }),
  events: {
    '{pubSub} savedSearchPermalinkSet'(scope, event) {
      const widgetId = event.widgetId;
      if (widgetId === this.viewModel.attr('options.widgetId')) {
        this.viewModel.attr('savedSearchPermalink', event.permalink);
      }
    },
  },
  export() {
    this.dispatch('export');
  },
});
