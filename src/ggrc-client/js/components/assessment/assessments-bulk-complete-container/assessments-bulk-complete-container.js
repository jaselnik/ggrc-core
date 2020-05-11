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
import '../../required-info-modal/required-info-modal';

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
  isDataLoaded: {
    value: false,
  },
  pubSub: {
    value: () => pubSub,
  },
  isAttributeModified: {
    value: false,
  },
  isCompleteButtonEnabled: {
    get() {
      return this.countAssessmentsToComplete > 0;
    },
  },
  assessmentIdsToComplete: {
    value: () => new Set(),
  },
  countAssessmentsToComplete: {
    value: 0,
  },
  headersData: {
    value: () => [],
  },
  rowsData: {
    value: () => [],
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
    this.isDataLoaded = true;
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

      this.viewModel.countAssessmentsToComplete =
        this.viewModel.assessmentIdsToComplete.size;
    },
    '{pubSub} assessmentReadyToComplete'(pubSub, {assessmentId}) {
      this.viewModel.assessmentIdsToComplete.add(assessmentId);
      this.viewModel.countAssessmentsToComplete =
        this.viewModel.assessmentIdsToComplete.size;
    },
  },
});
