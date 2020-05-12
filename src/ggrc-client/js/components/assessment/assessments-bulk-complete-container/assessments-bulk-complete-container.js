/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canDefineMap from 'can-define/map/map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-bulk-complete-container.stache';
import pubSub from '../../../pub-sub';
import {request} from '../../../plugins/utils/request-utils';
import {getFiltersForCompletion} from '../../../plugins/utils/bulk-update-service';
import {buildParam} from '../../../plugins/utils/query-api-utils';
import {isMyAssessments} from '../../../plugins/utils/current-page-utils';
import './assessments-bulk-complete-popover/assessments-bulk-complete-popover';
import './assessments-bulk-complete-popover/assessments-bulk-complete-popover-content';
import {confirm} from '../../../plugins/utils/modals';
import '../assessments-bulk-complete-table/assessments-bulk-complete-table-header/assessments-bulk-complete-table-header';
import '../assessments-bulk-complete-table/assessments-bulk-complete-table-row/assessments-bulk-complete-table-row';
import '../../required-info-modal/required-info-modal';
import {getCustomAttributeType} from '../../../plugins/utils/ca-utils';
import {backendGdriveClient} from '../../../plugins/ggrc-gapi-client';
import {ggrcPost} from '../../../plugins/ajax-extensions';
import {notifier} from '../../../plugins/utils/notifiers-utils';
import {trackStatus} from '../../../plugins/utils/background-task-utils';

const COMPLETION_MESSAGES = {
  start: `Completing certifications is in progress.
   Once it is done you will get a notification. 
   You can continue working with the app.`,
  success: 'Certifications are completed successfully.',
  fail: `Failed to complete certifications in bulk. 
   Please refresh the page and start bulk complete again.`,
};
const SAVE_ANSWERS_MESSAGES = {
  start: `Saving answers to the certifications. 
   Once it is done you will get a notification. 
   You can continue working with the app.`,
  success: 'Answers to the certifications are saved successfully.',
  fail: `Failed to save certifications' answers.
   Please try to save them again.`,
};

const ViewModel = canDefineMap.extend({
  currentFilter: {
    value: null,
  },
  _beforeUnloadHandler: {
    value: null,
  },
  parentInstance: {
    value: null,
  },
  asmtListRequest: {
    value: null,
  },
  assessmentsList: {
    value: () => [],
  },
  attributesList: {
    value: () => [],
  },
  isLoading: {
    value: false,
  },
  pubSub: {
    value: () => pubSub,
  },
  isAttributeModified: {
    value: false,
  },
  isSaveAnswersButtonEnabled: {
    get() {
      return this.isAttributeModified
      && !this.isBackgroundTaskInProgress;
    },
  },
  isCompleteButtonEnabled: {
    get() {
      return this.assessmentsCountsToComplete > 0
      && !this.isBackgroundTaskInProgress;
    },
  },
  assessmentIdsToComplete: {
    value: () => new Set(),
  },
  assessmentsCountsToComplete: {
    value: 0,
  },
  isGridEmpty: {
    value: false,
  },
  headersData: {
    value: () => [],
  },
  rowsData: {
    value: () => [],
  },
  isBackgroundTaskInProgress: {
    value: false,
  },
  requiredInfoModal: {
    value: () => ({
      title: '',
      state: {
        open: false,
      },
      content: {
        attribute: null,
        requiredInfo: null,
        comment: null,
        urls: [],
        files: [],
      },
    }),
  },
  onSaveAnswersClick() {
    backendGdriveClient.withAuth(
      () => ggrcPost(
        '/api/bulk_operations/cavs/save',
        this.buildBulkRequest(true)),
      {responseJSON: {message: 'Unable to Authorize'}})
      .then(({id}) => {
        if (id) {
          this.isAttributeModified = false;
          this.isBackgroundTaskInProgress = true;
          this.trackBackgroundTask(id, SAVE_ANSWERS_MESSAGES);
          this.cleanUpGridAfterSaveAnswers();
        } else {
          notifier('error', SAVE_ANSWERS_MESSAGES.fail);
        }
      });
  },
  onCompleteClick() {
    confirm({
      modal_title: 'Confirmation',
      modal_description: `Please confirm the bulk completion request 
      for ${this.assessmentsCountsToComplete} highlighted assessment(s).<br>
      Answers to all other assessments will be saved.`,
      button_view: '/modals/confirm-cancel-buttons.stache',
      modal_confirm: 'Proceed',
    }, () => this.completeAssessments());
  },
  completeAssessments() {
    backendGdriveClient.withAuth(
      () => ggrcPost(
        '/api/bulk_operations/complete',
        this.buildBulkRequest()),
      {responseJSON: {message: 'Unable to Authorize'}})
      .then(({id}) => {
        if (id) {
          this.assessmentsCountsToComplete = 0;
          this.isBackgroundTaskInProgress = true;
          this.isAttributeModified = false;
          this.trackBackgroundTask(id, COMPLETION_MESSAGES);
          this.cleanUpGridAfterCompletion();
        } else {
          notifier('error', COMPLETION_MESSAGES.fail);
        }
      });
  },
  buildBulkRequest(isSaveAnswersRequest = false) {
    const attributesListToSave = [];
    this.rowsData.forEach(({asmtId, asmtSlug, attributes}) => {
      const attributesList = [];

      attributes.forEach((attribute) => {
        if (attribute.isApplicable && attribute.modified) {
          let extra = {};
          const {attachments} = attribute;
          if (attachments) {
            const urls = attachments.urls.serialize();
            const files = attachments.files.serialize().map((file) => ({
              title: file.title,
              source_gdrive_id: file.id,
            }));
            const comment = attachments.comment ? {
              description: attachments.comment,
              modified_by: {type: 'Person', id: GGRC.current_user.id},
            } : {};
            extra = {
              urls,
              files,
              comment,
            };
          }
          attributesList.push({
            value: this.getValForCompleteRequest(
              attribute.type,
              attribute.value),
            title: attribute.title,
            type: attribute.type,
            definition_id: asmtId,
            id: attribute.id,
            extra,
          });
        }
      });

      if (attributesList.length ||
        (!isSaveAnswersRequest && this.assessmentIdsToComplete.has(asmtId))) {
        const assessmentAttributes = {
          assessment: {id: asmtId, slug: asmtSlug},
          values: attributesList,
        };
        attributesListToSave.push(assessmentAttributes);
      }
    });

    return {
      assessments_ids: isSaveAnswersRequest
        ? []: [...this.assessmentIdsToComplete],
      attributes: attributesListToSave,
    };
  },
  getValForCompleteRequest(type, value) {
    switch (type) {
      case 'checkbox':
        return value ? '1' : '0';
      case 'date':
        return value || '';
      default:
        return value;
    }
  },
  cleanUpGridAfterCompletion() {
    const rowsData = this.rowsData.filter(
      (item) => !this.assessmentIdsToComplete.has(item.asmtId))
      .forEach((asmt) => {
        asmt.attributes = asmt.attributes.attr().map((attr) => {
          attr.modified = false;
          attr.validation.hasUnsavedAttachments = false;
          return attr;
        });
      });
    if (!rowsData.length) {
      this.isGridEmpty = true;
    }

    this.assessmentIdsToComplete = new Set();
    this.rowsData = rowsData;
  },
  cleanUpGridAfterSaveAnswers() {
    const rowsData = this.rowsData
      .forEach((asmt) => {
        asmt.attributes = asmt.attributes.attr().map((attr) => {
          attr.modified = false;
          return attr;
        });
      });
    this.rowsData = rowsData;
  },
  trackBackgroundTask(taskId, messages) {
    notifier('progress', messages.start);
    const url = `/api/background_tasks/${taskId}`;
    trackStatus(
      url,
      () => {
        notifier('success', messages.success);
        this.isBackgroundTaskInProgress = false;
      },
      () => {
        notifier('error', messages.fail);
        this.isBackgroundTaskInProgress = false;
      });
  },
  buildAsmtListRequest() {
    let relevant = null;
    if (!isMyAssessments()) {
      const parentInstance = this.parentInstance;
      relevant = {
        type: parentInstance.type,
        id: parentInstance.id,
        operation: 'relevant',
      };
    }
    const filter =
      getFiltersForCompletion(this.currentFilter, relevant);
    const param = buildParam('Assessment', {}, relevant, [], filter);
    param.type = 'ids';
    this.asmtListRequest = param;
  },
  async loadItems() {
    this.isLoading = true;
    const {assessments, attributes} =
      await request('/api/bulk_operations/cavs/search',
        [this.asmtListRequest.serialize()]);
    this.assessmentsList = assessments;
    this.attributesList = attributes;
    this.isLoading = false;
    this.headersData = this.buildHeadersData();
    this.rowsData = this.buildRowsData();
  },
  buildHeadersData() {
    return this.attributesList.map((attribute) => ({
      title: attribute.title,
      mandatory: attribute.mandatory,
    }));
  },
  buildRowsData() {
    const rowsData = [];

    this.assessmentsList.forEach((assessment) => {
      const assessmentData = {
        asmtId: assessment.id,
        asmtTitle: assessment.title,
        asmtStatus: assessment.status,
        asmtSlug: assessment.slug,
        asmtType: assessment.assessment_type,
        urlsCount: assessment.urls_count,
        filesCount: assessment.files_count,
        isReadyToComplete: false,
      };
      const attributesData = [];

      this.attributesList.forEach((attribute) => {
        let id = null;
        let value = null;
        let optionsList = [];
        let optionsConfig = new Map();
        let isApplicable = false;
        let errorsMap = {
          attachment: false,
          url: false,
          comment: false,
        };
        const type = getCustomAttributeType(attribute.attribute_type);
        const defaultValue = this.prepareAttributeValue(type,
          attribute.default_value);

        const assessmentAttributeData = attribute.values[assessment.id];
        if (assessmentAttributeData) {
          id = assessmentAttributeData.attribute_definition_id;
          value = this.prepareAttributeValue(type,
            assessmentAttributeData.value,
            assessmentAttributeData.attribute_person_id);
          ({optionsList, optionsConfig} = this.prepareMultiChoiceOptions(
            assessmentAttributeData.multi_choice_options,
            assessmentAttributeData.multi_choice_mandatory)
          );
          isApplicable = true;

          if (assessmentAttributeData.preconditions_failed) {
            const errors =
              assessmentAttributeData.preconditions_failed.serialize();
            errorsMap = {
              attachment: errors.includes('evidence'),
              url: errors.includes('url'),
              comment: errors.includes('comment'),
            };
          }
        }

        attributesData.push({
          id,
          type,
          value,
          defaultValue,
          isApplicable,
          errorsMap,
          title: attribute.title,
          mandatory: attribute.mandatory,
          multiChoiceOptions: {
            values: optionsList,
            config: optionsConfig,
          },
          attachments: {
            files: [],
            urls: [],
            comment: null,
          },
          modified: false,
          validation: {
            mandatory: attribute.mandatory,
            valid: (isApplicable ? !attribute.mandatory : true),
            requiresAttachment: false,
            hasMissingInfo: false,
            hasUnsavedAttachments: false,
          },
        });
      });

      rowsData.push({attributes: attributesData, ...assessmentData});
    });

    return rowsData;
  },
  prepareAttributeValue(type, value, personId = null) {
    switch (type) {
      case 'checkbox':
        return value === '1';
      case 'date':
        return value || null;
      case 'dropdown':
        return value || '';
      case 'multiselect':
        return value || '';
      case 'person':
        return personId
          ? [{
            id: personId,
            type: 'Person',
            href: `/api/people/${personId}`,
            context_id: null,
          }]
          : null;
      default:
        return value;
    }
  },
  prepareMultiChoiceOptions(multiChoiceOptions, multiChoiceMandatory) {
    const optionsList = this.convertToArray(multiChoiceOptions);
    const optionsStates = this.convertToArray(multiChoiceMandatory);
    const optionsConfig = optionsStates.reduce((config, state, index) => {
      const optionValue = optionsList[index];
      return config.set(optionValue, Number(state));
    }, new Map());

    return {optionsList, optionsConfig};
  },
  convertToArray(value) {
    return typeof value === 'string' ? value.split(',') : [];
  },
  exitBulkCompletionMode() {
    const disableBulkCompletionMode = () => pubSub.dispatch({
      type: 'updateBulkCompleteMode',
      enable: false,
    });
    if (this.isAttributeModified) {
      confirm({
        modal_title: 'Warning',
        modal_description: `Changes you made might not be saved.<br>
         Do you want to exit the bulk completion mode?`,
        button_view: '/modals/confirm-cancel-buttons.stache',
        modal_confirm: 'Proceed',
        extraCssClass: 'exit-bulk-completion-modal',
      }, disableBulkCompletionMode);
    } else {
      disableBulkCompletionMode();
    }
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-container',
  view: canStache(template),
  ViewModel,
  events: {
    inserted() {
      this.viewModel.buildAsmtListRequest();
      this.viewModel.loadItems();
      const beforeUnloadHandler = (event) => {
        if (this.viewModel.isAttributeModified) {
          event.preventDefault();
          event.returnValue = '';
        }
      };
      this.viewModel._beforeUnloadHandler = beforeUnloadHandler.bind(this);
      window.addEventListener('beforeunload',
        this.viewModel._beforeUnloadHandler);
    },
    removed() {
      window.removeEventListener('beforeunload',
        this.viewModel._beforeUnloadHandler);
    },
    '{pubSub} attributeModified'(pubSub, {assessmentData}) {
      this.viewModel.isAttributeModified = true;

      if (assessmentData.isReadyToComplete) {
        this.viewModel.assessmentIdsToComplete.add(assessmentData.asmtId);
      } else {
        this.viewModel.assessmentIdsToComplete.delete(assessmentData.asmtId);
      }

      this.viewModel.assessmentsCountsToComplete =
        this.viewModel.assessmentIdsToComplete.size;
    },
    '{pubSub} assessmentReadyToComplete'(pubSub, {assessmentId}) {
      this.viewModel.assessmentIdsToComplete.add(assessmentId);
      this.viewModel.assessmentsCountsToComplete =
        this.viewModel.assessmentIdsToComplete.size;
    },
  },
});
