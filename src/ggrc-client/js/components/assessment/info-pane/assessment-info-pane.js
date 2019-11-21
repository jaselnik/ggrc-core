/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loKeyBy from 'lodash/keyBy';
import loCapitalize from 'lodash/capitalize';
import loFindIndex from 'lodash/findIndex';
import makeArray from 'can-util/js/make-array/make-array';
import canBatch from 'can-event/batch/batch';
import canStache from 'can-stache';
import canList from 'can-list';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../controls-toolbar/assessment-controls-toolbar';
import '../assessment-local-ca';
import '../assessment-custom-attributes';
import '../assessment-people';
import '../assessment-object-type-dropdown';
import '../attach-button';
import '../info-pane-save-status';
import '../../comment/comment-add-form';
import '../../comment/mapped-comments';
import '../../comment/comments-paging';
import '../mapped-controls/assessment-mapped-controls';
import '../../assessment/map-button-using-assessment-type';
import '../../ca-object/ca-object-modal-content';
import '../../comment/comment-add-form';
import '../../custom-attributes/custom-attributes';
import '../../custom-attributes/custom-attributes-field';
import '../../custom-attributes/custom-attributes-status';
import '../../prev-next-buttons/prev-next-buttons';
import '../../inline/inline-form-control';
import '../../object-change-state/object-change-state';
import '../../related-objects/related-assessments';
import '../../related-objects/related-issues';
import '../../issue-tracker/issue-tracker-switcher';
import './ticket-id-checker';
import '../../item-edit-control/item-edit-control';
import '../../object-list-item/editable-document-object-list-item';
import '../../object-state-toolbar/object-state-toolbar';
import '../../loading/loading-status';
import './info-pane-issue-tracker-fields';
import '../../tabs/tab-container';
import './assessment-inline-item';
import './create-url';
import './confirm-edit-action';
import '../../multi-select-label/multi-select-label';
import {
  buildParam,
  batchRequests,
} from '../../../plugins/utils/query-api-utils';
import {loadComments} from '../../../plugins/utils/comments-utils';
import {
  getCustomAttributes,
  getLCAPopupTitle,
  CUSTOM_ATTRIBUTE_TYPE as CA_UTILS_CA_TYPE,
  convertValuesToFormFields,
} from '../../../plugins/utils/ca-utils';
import {getRole} from '../../../plugins/utils/acl-utils';
import DeferredTransaction from '../../../plugins/utils/deferred-transaction-utils';
import tracker from '../../../tracker';
import {
  RELATED_ITEMS_LOADED,
  REFRESH_MAPPING,
  REFRESH_RELATED,
  REFRESHED,
} from '../../../events/event-types';
import {isAllowedFor} from '../../../permission';
import {
  getPageInstance,
} from '../../../plugins/utils/current-page-utils';
import {initCounts} from '../../../plugins/utils/widgets-utils';
import template from './assessment-info-pane.stache';
import {CUSTOM_ATTRIBUTE_TYPE} from '../../../plugins/utils/custom-attribute/custom-attribute-config';
import pubSub from '../../../pub-sub';
import {relatedAssessmentsTypes} from '../../../plugins/utils/models-utils';
import {notifier, notifierXHR} from '../../../plugins/utils/notifiers-utils';
import Evidence from '../../../models/business-models/evidence';
import * as businessModels from '../../../models/business-models';
import {getAjaxErrorInfo} from '../../../plugins/utils/errors-utils';
import {
  isMultiLevelFlow,
  getFirstUnreviewedLevel,
} from '../../../plugins/utils/verification-flow-utils';

const SEMI_RESTRICTED_STATUSES = ['Deprecated', 'Completed'];

/**
 * Assessment Specific Info Pane View Component
 */
export default canComponent.extend({
  tag: 'assessment-info-pane',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    define: {
      verifiers: {
        get() {
          let acl = this.attr('instance.access_control_list');
          let verifierRoleId = this.attr('_verifierRoleId');
          let verifiers;

          if (!verifierRoleId) {
            return [];
          }

          verifiers = acl
            .filter((item) =>
              String(item.ac_role_id) === String(verifierRoleId)
            ).map(
              // Getter of 'verifiers' is called when access_control_list(ACL) length
              // is changed or object itself is changed.
              // When we save new ACL, after getting response from BE,
              // order of items in ACL can differ from original. In this case
              // verifiers won't be recalculated and we can get invalid list
              // after merging ACL data which we get from BE.
              // To prevent this we returns copies of persons which won't be modified
              // in scenario described above.
              ({person}) => ({
                id: person.id,
                type: person.type,
              }));

          return verifiers;
        },
      },
      showProcedureSection: {
        get() {
          return this.instance.attr('test_plan') ||
            this.instance.attr('issue_tracker.issue_url');
        },
      },
      isLoading: {
        type: 'boolean',
        value: false,
      },
      mappedSnapshots: {
        Value: canList,
      },
      assessmentTypeNameSingular: {
        get() {
          let type = this.attr('instance.assessment_type');
          return businessModels[type].title_singular;
        },
      },
      assessmentTypeNamePlural: {
        get() {
          let type = this.attr('instance.assessment_type');
          return businessModels[type].title_plural;
        },
      },
      assessmentTypeObjects: {
        get() {
          let self = this;
          return this.attr('mappedSnapshots')
            .filter(function (item) {
              return item.child_type === self
                .attr('instance.assessment_type');
            });
        },
      },
      relatedInformation: {
        get() {
          let self = this;
          return this.attr('mappedSnapshots')
            .filter(function (item) {
              return item.child_type !== self
                .attr('instance.assessment_type');
            });
        },
      },
      comments: {
        Value: canList,
      },
      urls: {
        Value: canList,
      },
      files: {
        Value: canList,
      },
      editMode: {
        type: 'boolean',
        get() {
          if (this.attr('instance.archived')) {
            return false;
          }

          // instance's state is changed before sending a request to server
          const instanceStatus = this.attr('instance.status');

          // current state is changed after receiving a server's response
          const currentState = this.attr('currentState');

          // the state when a request was sent, but a response wasn't received
          if (currentState !== instanceStatus) {
            return false;
          }
          const editModeStatuses = this.attr('instance')
            .constructor.editModeStatuses;
          return editModeStatuses.includes(instanceStatus);
        },
        set() {
          this.onStateChange({state: 'In Progress', undo: false});
        },
      },
      isEditDenied: {
        get() {
          return !isAllowedFor('update', this.attr('instance')) ||
            this.attr('instance.archived');
        },
      },
      isAllowedToMap: {
        get() {
          let audit = this.attr('instance.audit');
          return !!audit && isAllowedFor('read', audit);
        },
      },
      isRestricted: {
        get() {
          return this.attr('isEditDenied')
            || this.attr('instance._is_sox_restricted');
        },
      },
      isSemiRestrictedOnStatus: {
        get() {
          const isSemiRestrictedStatus = SEMI_RESTRICTED_STATUSES
            .includes(this.attr('instance.status'))
            && this.attr('instance._is_sox_restricted');

          return this.attr('isEditDenied') || isSemiRestrictedStatus;
        },
      },
      isReuseNeeded: {
        get() {
          return !this.attr('isSemiRestrictedOnStatus');
        },
      },
      instance: {},
      isInfoPaneSaving: {
        get() {
          if (this.attr('isUpdatingRelatedItems') ||
            this.attr('isLoadingComments')) {
            return false;
          }

          return this.attr('isUpdatingFiles') ||
            this.attr('isUpdatingState') ||
            this.attr('isUpdatingEvidences') ||
            this.attr('isUpdatingUrls') ||
            this.attr('isUpdatingComments') ||
            this.attr('isAssessmentSaving');
        },
      },
      noItemsText: {
        get() {
          return this.attr('isSemiRestrictedOnStatus') ? 'None' : '';
        },
      },
    },
    modal: {
      state: {
        open: false,
      },
    },
    pubSub,
    _verifierRoleId: undefined,
    isUpdatingRelatedItems: false,
    isUpdatingState: false,
    isAssessmentSaving: false,
    onStateChangeDfd: {},
    formState: {},
    currentState: '',
    previousStatus: undefined,
    initialState: 'Not Started',
    deprecatedState: 'Deprecated',
    assessmentMainRoles: ['Creators', 'Assignees', 'Verifiers'],
    commentsTotalCount: 0,
    commentsPerPage: 10,
    newCommentsCount: 0,
    stateDisplayName: '',
    refreshCounts: function (types) {
      let pageInstance = getPageInstance();
      initCounts(
        types,
        pageInstance.attr('type'),
        pageInstance.attr('id')
      );
    },
    setUrlEditMode: function (value) {
      this.attr('urlsEditMode', value);
    },
    setInProgressState: function () {
      this.onStateChange({state: 'In Progress', undo: false});
    },
    isReadOnlyAttribute: function (propName) {
      const readOnlyAttributes = this.attr('instance._readonly_fields');
      const isEditDenied = this.attr('isEditDenied');
      const isReadOnly = [...readOnlyAttributes].includes(propName);
      return isReadOnly || isEditDenied;
    },
    getQuery: function (type, sortObj, additionalFilter) {
      let relevantFilters = [{
        type: this.attr('instance.type'),
        id: this.attr('instance.id'),
        operation: 'relevant',
      }];
      return buildParam(type,
        sortObj || {},
        relevantFilters,
        [],
        additionalFilter || []);
    },
    getSnapshotQuery: function () {
      return this.getQuery('Snapshot');
    },
    getEvidenceQuery: function (kind) {
      let query = this.getQuery(
        'Evidence',
        {sort: [{key: 'created_at', direction: 'desc'}]},
        this.getEvidenceAdditionFilter(kind));
      return query;
    },
    requestQuery: function (query, type) {
      let dfd = $.Deferred();
      type = type || '';
      this.attr('isUpdating' + loCapitalize(type), true);

      batchRequests(query)
        .done(function (response) {
          let type = Object.keys(response)[0];
          let values = response[type].values;
          dfd.resolve(values);
        })
        .fail(function () {
          dfd.resolve([]);
        })
        .always(function () {
          this.attr('isUpdating' + loCapitalize(type), false);

          tracker.stop(this.attr('instance.type'),
            tracker.USER_JOURNEY_KEYS.INFO_PANE,
            tracker.USER_ACTIONS.INFO_PANE.OPEN_INFO_PANE);
        }.bind(this));
      return dfd;
    },
    loadSnapshots: function () {
      let query = this.getSnapshotQuery();
      return this.requestQuery(query);
    },
    loadFiles: function () {
      let query = this.getEvidenceQuery('FILE');
      return this.requestQuery(query, 'files');
    },
    loadUrls: function () {
      let query = this.getEvidenceQuery('URL');
      return this.requestQuery(query, 'urls');
    },
    updateItems: function () {
      makeArray(arguments).forEach(function (type) {
        this.attr(type).replace(this['load' + loCapitalize(type)]());
      }.bind(this));
    },
    removeItems: function (event, type) {
      let items = this.attr(type);

      canBatch.start();
      let resultItems = items.filter((item) => {
        let newItemIndex = loFindIndex(event.items, (newItem) => {
          return newItem === item;
        });
        return newItemIndex < 0;
      });

      items.replace(resultItems);
      canBatch.stop();
    },
    addItems: function (event, type) {
      let items = event.items;
      this.attr('isUpdating' + loCapitalize(type), true);
      return this.attr(type).unshift(...makeArray(items));
    },
    getEvidenceAdditionFilter: function (kind) {
      return kind ?
        {
          expression: {
            left: 'kind',
            op: {name: '='},
            right: kind,
          },
        } :
        [];
    },
    addAction: function (actionType, related) {
      let assessment = this.attr('instance');
      let path = 'actions.' + actionType;

      if (!assessment.attr('actions')) {
        assessment.attr('actions', {});
      }
      if (assessment.attr(path)) {
        assessment.attr(path).push(related);
      } else {
        assessment.attr(path, [related]);
      }
    },
    addRelatedItem: function (event, type) {
      let self = this;
      let assessment = this.attr('instance');
      let relatedItemType = event.item.attr('type');
      let related = {
        id: event.item.attr('id'),
        type: relatedItemType,
      };

      this.attr('deferredSave').execute(function () {
        self.addAction('add_related', related);
      })
        .done(() => {
          if (type === 'comments') {
            tracker.stop(assessment.type,
              tracker.USER_JOURNEY_KEYS.INFO_PANE,
              tracker.USER_ACTIONS.INFO_PANE.ADD_COMMENT_TO_LCA);
            tracker.stop(assessment.type,
              tracker.USER_JOURNEY_KEYS.INFO_PANE,
              tracker.USER_ACTIONS.INFO_PANE.ADD_COMMENT);

            let commentsTotalCount = this.attr('commentsTotalCount');
            this.attr('commentsTotalCount', ++commentsTotalCount);
            let newCommentsCount = this.attr('newCommentsCount');
            this.attr('newCommentsCount', ++newCommentsCount);
          }
        })
        .fail(function (instance, xhr) {
          notifierXHR('error', xhr);

          if (type === 'comments') {
            tracker.stop(assessment.type,
              tracker.USER_JOURNEY_KEYS.INFO_PANE,
              tracker.USER_ACTIONS.INFO_PANE.ADD_COMMENT_TO_LCA,
              false);
            tracker.stop(assessment.type,
              tracker.USER_JOURNEY_KEYS.INFO_PANE,
              tracker.USER_ACTIONS.INFO_PANE.ADD_COMMENT,
              false);
          }

          self.removeItems({
            items: [event.item],
          }, type);
        })
        .always(function (assessment) {
          assessment.removeAttr('actions');
          self.attr('isUpdating' + loCapitalize(type), false);

          // dispatching event on instance to pass to the auto-save-form
          self.attr('instance').dispatch(RELATED_ITEMS_LOADED);

          if (relatedItemType === 'Evidence') {
            self.refreshCounts(['Evidence']);
          }
        });
    },
    removeRelatedItem: function (item, type) {
      let self = this;
      let related = {
        id: item.attr('id'),
        type: item.attr('type'),
      };
      let items = self.attr(type);
      let index = items.indexOf(item);
      this.attr('isUpdating' + loCapitalize(type), true);
      items.splice(index, 1);

      this.attr('deferredSave').push(function () {
        self.addAction('remove_related', related);
      })
        .fail(function () {
          notifier('error', 'Unable to remove URL.');
          items.splice(index, 0, item);
        })
        .always(function (assessment) {
          assessment.removeAttr('actions');
          self.attr('isUpdating' + loCapitalize(type), false);

          self.refreshCounts(['Evidence']);
        });
    },
    updateRelatedItems: function () {
      this.attr('isUpdatingRelatedItems', true);

      return this.attr('instance').getRelatedObjects()
        .then((data) => {
          this.attr('mappedSnapshots').replace(data.Snapshot);
          this.attr('files')
            .replace(data['Evidence:FILE'].map((file) => new Evidence(file)));
          this.attr('urls')
            .replace(data['Evidence:URL'].map((url) => new Evidence(url)));

          this.attr('isUpdatingRelatedItems', false);
          this.attr('instance').dispatch(RELATED_ITEMS_LOADED);

          tracker.stop(this.attr('instance.type'),
            tracker.USER_JOURNEY_KEYS.INFO_PANE,
            tracker.USER_ACTIONS.INFO_PANE.OPEN_INFO_PANE);
        });
    },
    async loadFirstComments(count) {
      let instance = this.attr('instance');
      let newCommentsCount = this.attr('newCommentsCount');

      // load more comments as they can be added by other users before or after current user's new comments
      let pageSize = (count || this.attr('commentsPerPage')) + newCommentsCount;

      let response = await loadComments(instance, 'Comment', 0, pageSize);
      let {values: comments, total} = response.Comment;

      this.attr('comments').splice(0, newCommentsCount);
      this.attr('comments').unshift(...comments);

      this.attr('commentsTotalCount', total);
      this.attr('newCommentsCount', 0);
    },
    async loadMoreComments(startIndex) {
      this.attr('isLoadingComments', true);

      let instance = this.attr('instance');
      let index = startIndex || this.attr('comments').length;
      let pageSize = this.attr('commentsPerPage');

      try {
        let response = await loadComments(instance, 'Comment', index, pageSize);
        let {values: comments, total} = response.Comment;

        let totalCount = this.attr('commentsTotalCount');
        if (totalCount !== total) {
          // new comments were added by other users
          let newCommentsCount = total - totalCount;
          await Promise.all([
            this.loadFirstComments(newCommentsCount),
            this.loadMoreComments(index + newCommentsCount)]);
        } else {
          this.attr('comments').push(...comments);
        }
      } finally {
        this.attr('isLoadingComments', false);
      }
    },
    hideComments() {
      // remain only first comments
      this.attr('comments').splice(this.attr('commentsPerPage'));
    },
    addReusableEvidence(event) {
      this.attr('deferredSave').push(() => {
        event.items.forEach((item) => {
          let related = {
            id: item.attr('id'),
            type: item.attr('type'),
          };

          this.addAction('add_related', related);
        });
      })
        .done(() => {
          this.updateItems('urls', 'files');
          this.refreshCounts(['Evidence']);
        })
        .always(() => {
          this.attr('instance').removeAttr('actions');
        });
    },
    initializeFormFields: function () {
      const cavs =
      getCustomAttributes(
        this.attr('instance'),
        CA_UTILS_CA_TYPE.LOCAL
      );
      this.attr('formFields',
        convertValuesToFormFields(cavs)
      );
    },
    reinitFormFields() {
      const cavs = getCustomAttributes(
        this.attr('instance'),
        CA_UTILS_CA_TYPE.LOCAL
      );

      let updatedFormFields = convertValuesToFormFields(cavs);
      let updatedFieldsIds = loKeyBy(updatedFormFields, 'id');

      this.attr('formFields').forEach((field) => {
        let updatedField = updatedFieldsIds[field.attr('id')];

        if (updatedField &&
          field.attr('value') !== updatedField.attr('value')) {
          field.attr('value', updatedField.attr('value'));
        }
      });
    },
    initGlobalAttributes: function () {
      const instance = this.attr('instance');
      const caObjects = instance
        .customAttr({type: CUSTOM_ATTRIBUTE_TYPE.GLOBAL});
      this.attr('globalAttributes', caObjects);
    },
    initializeDeferredSave: function () {
      this.attr('deferredSave', new DeferredTransaction(
        function (resolve, reject) {
          this.attr('instance').save().done(resolve).fail(reject);
        }.bind(this), 1000));
    },
    refreshAssessment() {
      this.attr('instance').refresh().then((response) => {
        this.setCurrentState(response.status);
      });
    },
    beforeStatusSave(newStatus, isUndo) {
      const instance = this.attr('instance');

      if (isUndo) {
        instance.attr('status', this.attr('previousStatus'));
        this.attr('previousStatus', undefined);
      } else {
        this.attr('previousStatus', instance.attr('status'));
        instance.attr('status', newStatus);
      }
    },
    afterStatusSave(savedStatus) {
      this.attr('instance.status', savedStatus);
      this.setCurrentState(savedStatus);
    },
    setCurrentState(state) {
      this.attr('currentState', state);

      const stateDisplayName = this.getStateDisplayName(
        this.attr('instance'),
        state
      );
      this.attr('stateDisplayName', stateDisplayName);
    },
    getStateDisplayName(instance, currentState) {
      if (!isMultiLevelFlow(instance) || currentState !== 'In Review') {
        return currentState;
      }

      const reviewLevelCount = instance.attr('review_levels_count');
      const firstUnreviewedLevel = getFirstUnreviewedLevel(instance);
      const levelNumber = firstUnreviewedLevel.level_number;

      const stateDisplayName =
        `${currentState} ${levelNumber} of ${reviewLevelCount}`;

      return stateDisplayName;
    },
    onStateChange: function (event) {
      const isUndo = event.undo;
      const newStatus = event.state;
      const instance = this.attr('instance');
      const status = instance.attr('status');
      const initialState = this.attr('initialState');
      const deprecatedState = this.attr('deprecatedState');
      const isArchived = instance.attr('archived');
      const previousStatus = this.attr('previousStatus');
      const doneStatuses = instance.constructor.doneStatuses;
      const stopFn = tracker.start(instance.type,
        tracker.USER_JOURNEY_KEYS.INFO_PANE,
        tracker.USER_ACTIONS.ASSESSMENT.CHANGE_STATUS);

      if (isArchived && [initialState, deprecatedState].includes(newStatus)) {
        return $.Deferred().resolve();
      }

      if (doneStatuses.includes(newStatus) && !instance.validateGCAs()) {
        notifier('error', `Please fill in the required fields at
          'Other Attributes' tab to complete assessment.`);
        return $.Deferred().reject();
      }

      this.attr('onStateChangeDfd', $.Deferred());
      this.attr('isUpdatingState', true);

      return this.attr('deferredSave').execute(
        this.beforeStatusSave.bind(this, newStatus, isUndo)
      ).then((resp) => {
        const newStatus = resp.status;
        this.afterStatusSave(newStatus);

        this.attr('isUndoButtonVisible', !isUndo);

        if (newStatus === 'In Review' && !isUndo) {
          notifier('info', 'The assessment is complete. ' +
          'The verifier may revert it if further input is needed.');
        }

        this.attr('onStateChangeDfd').resolve();
        pubSub.dispatch({
          type: 'refetchOnce',
          modelNames: relatedAssessmentsTypes,
        });
        stopFn();
      }).fail((object, xhr) => {
        if (xhr && xhr.status === 409 && xhr.remoteObject) {
          instance.attr('status', xhr.remoteObject.status);
        } else {
          this.afterStatusSave(status);
          this.attr('previousStatus', previousStatus);
          notifier('error', getAjaxErrorInfo(xhr).details);
        }
      }).always(() => {
        this.attr('isUpdatingState', false);
      });
    },
    saveGlobalAttributes: function (event) {
      this.attr('deferredSave').push(() => {
        const instance = this.attr('instance');
        const globalAttributes = event.globalAttributes;

        globalAttributes.each((value, caId) => {
          instance.customAttr(caId, value);
        });
      });
    },
    showRequiredInfoModal: function (e, field) {
      let scope = field || e.field;
      let errors = scope.attr('errorsMap');
      let errorsList = canMap.keys(errors)
        .map(function (error) {
          return errors[error] ? error : null;
        })
        .filter(function (errorCode) {
          return !!errorCode;
        });
      let data = {
        options: scope.attr('options'),
        contextScope: scope,
        fields: errorsList,
        value: scope.attr('value'),
        title: scope.attr('title'),
        type: scope.attr('type'),
        saveDfd: e.saveDfd || $.Deferred().resolve(),
      };

      let title = 'Required ' + getLCAPopupTitle(errors);

      canBatch.start();
      this.attr('modal.content', data);
      this.attr('modal.modalTitle', title);
      canBatch.stop();
      this.attr('modal.state.open', true);
    },
    setVerifierRoleId: function () {
      let verifierRole = getRole('Assessment', 'Verifiers');

      let verifierRoleId = verifierRole ? verifierRole.id : null;
      this.attr('_verifierRoleId', verifierRoleId);
    },
    resetCurrentState() {
      this.setCurrentState(this.attr('instance.status'));
      this.attr('previousStatus', undefined);
      this.attr('isUndoButtonVisible', false);
    },
  }),
  async init() {
    this.viewModel.initializeFormFields();
    this.viewModel.initGlobalAttributes();
    this.viewModel.updateRelatedItems();
    this.viewModel.initializeDeferredSave();
    this.viewModel.setVerifierRoleId();

    try {
      this.viewModel.attr('isLoadingComments', true);
      await this.viewModel.loadFirstComments();
    } finally {
      this.viewModel.attr('isLoadingComments', false);
    }
  },
  events: {
    inserted() {
      this.viewModel.resetCurrentState();
    },
    [`{viewModel.instance} ${REFRESH_MAPPING.type}`]([scope], event) {
      const viewModel = this.viewModel;
      viewModel.attr('mappedSnapshots')
        .replace(this.viewModel.loadSnapshots());
      viewModel.attr('instance').dispatch({
        ...REFRESH_RELATED,
        model: event.destinationType,
      });
    },
    [`{viewModel.instance} ${REFRESHED.type}`]() {
      const status = this.viewModel.attr('instance.status');
      this.viewModel.setCurrentState(status);
    },
    '{viewModel.instance} updated'([instance]) {
      const vm = this.viewModel;
      const isPending = vm.attr('deferredSave').isPending();
      instance.backup();
      if (!isPending) {
        // reinit LCA when queue is empty
        // to avoid rewriting of changed values
        vm.reinitFormFields();
      }
    },
    '{viewModel.instance} modelBeforeSave': function () {
      this.viewModel.attr('isAssessmentSaving', true);
    },
    '{viewModel.instance} modelAfterSave': function () {
      this.viewModel.attr('isAssessmentSaving', false);
      this.viewModel.setCurrentState(this.viewModel.attr('instance.status'));
    },
    '{viewModel.instance} assessment_type'() {
      const onSave = () => {
        this.viewModel.instance.dispatch({
          ...REFRESH_RELATED,
          model: 'Related Assessments',
        });
        this.viewModel.instance.unbind('updated', onSave);
      };
      this.viewModel.instance.bind('updated', onSave);
    },
    async '{viewModel} instance'() {
      this.viewModel.initializeFormFields();
      this.viewModel.initGlobalAttributes();
      this.viewModel.updateRelatedItems();
      this.viewModel.resetCurrentState();

      try {
        this.viewModel.attr('comments', []);
        this.viewModel.attr('commentsTotalCount', 0);
        this.viewModel.attr('isLoadingComments', true);
        await this.viewModel.loadFirstComments();
      } finally {
        this.viewModel.attr('isLoadingComments', false);
      }
    },
    '{pubSub} objectDeleted'(pubSub, event) {
      let instance = event.instance;
      // handle removing evidence on Evidence tab
      // evidence on Assessment tab should be updated
      if (instance instanceof Evidence) {
        this.viewModel.updateItems('files', 'urls');
      }
    },
    '{pubSub} relatedItemSaved'(pubSub, event) {
      this.viewModel.addRelatedItem(event, event.itemType);
    },
    '{pubSub} relatedItemBeforeSave'(pubSub, event) {
      this.viewModel.addItems(event, event.itemType);
    },
  },
});
