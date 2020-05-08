/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canDefineMap from 'can-define/map/map';
import canStache from 'can-stache';
import canBatch from 'can-event/batch/batch';
import loFind from 'lodash/find';
import template from './assessments-bulk-complete-table-row.stache';
import pubSub from '../../../../pub-sub';
import {getPlainText} from '../../../../plugins/ggrc-utils';
import {ddValidationValueToMap, getLCAPopupTitle} from '../../../../plugins/utils/ca-utils';

const ViewModel = canDefineMap.extend({seal: false}, {
  rowData: {
    value: () => ({}),
  },
  pubSub: {
    value: () => pubSub,
  },
  isFileRequired: {
    get() {
      const requiredFilesCount = this.getRequiredInfoCountByType('attachment');
      const currentFilesCount = this.getCurrentFilesCount();

      return requiredFilesCount > currentFilesCount;
    },
  },
  isUrlRequired: {
    get() {
      const requiredUrlsCount = this.getRequiredInfoCountByType('url');
      const currentUrlsCount = this.getCurrentUrlsCount();

      return requiredUrlsCount > currentUrlsCount;
    },
  },
  requiredInfoModal: {
    value: () => ({}),
  },
  getRequiredInfoCountByType(requiredInfoType) {
    return this.getApplicableDropdownAttributes().reduce((count, attribute) => {
      return this.getRequiredInfoStates(attribute)[requiredInfoType]
        ? count + 1
        : count;
    }, 0);
  },
  getCurrentFilesCount() {
    return this.getApplicableDropdownAttributes().reduce((count, attribute) =>
      count + attribute.attachments.files.length, this.rowData.filesCount);
  },
  getCurrentUrlsCount() {
    return this.getApplicableDropdownAttributes().reduce((count, attribute) =>
      count + attribute.attachments.urls.length, this.rowData.urlsCount);
  },
  getApplicableDropdownAttributes() {
    return this.rowData.attributes.filter(
      (attribute) => attribute.isApplicable && attribute.type === 'dropdown');
  },
  validateAllAttributes() {
    this.rowData.attributes.forEach((attribute) => {
      if (!attribute.isApplicable) {
        return;
      }

      if (attribute.type === 'dropdown') {
        this.performDropdownValidation(attribute);
      } else {
        this.performDefaultValidation(attribute);
      }
    });
  },
  performDropdownValidation(attribute) {
    const {comment, attachment, url} = this.getRequiredInfoStates(attribute);
    const requiresAttachment = comment || attachment || url;

    canBatch.start();

    const validation = attribute.validation;
    validation.requiresAttachment = requiresAttachment;

    const hasMissingFile = attachment && this.isFileRequired;
    const hasMissingUrl = url && this.isUrlRequired;
    const hasMissingComment = comment && attribute.errorsMap.comment;

    if (requiresAttachment) {
      const hasMissingInfo = hasMissingFile
        || hasMissingUrl
        || hasMissingComment;

      const {comment, urls, files} = attribute.attachments;
      const hasUnsavedAttachments = comment !== null
        || urls.length > 0
        || files.length > 0;

      validation.valid = !hasMissingInfo;
      validation.hasMissingInfo = hasMissingInfo;
      validation.hasUnsavedAttachments = hasUnsavedAttachments;
    } else {
      validation.valid = validation.mandatory ? attribute.value !== '' : true;
      validation.hasMissingInfo = false;
      validation.hasUnsavedAttachments = false;
    }

    attribute.errorsMap = {
      attachment: hasMissingFile,
      url: hasMissingUrl,
      comment: hasMissingComment,
    };

    canBatch.stop();
  },
  performDefaultValidation(attribute) {
    let {type, value, validation} = attribute;

    if (!validation.mandatory) {
      return;
    }

    switch (type) {
      case 'text':
        value = getPlainText(value);
        break;
      case 'person':
        value = value && value.length;
        break;
    }

    validation.valid = !!(value);
  },
  getRequiredInfoStates(attribute) {
    const optionBitmask = attribute.multiChoiceOptions.config
      .get(attribute.value);
    return ddValidationValueToMap(optionBitmask);
  },
  checkAssessmentReadinessToComplete() {
    const isReadyToComplete = this.rowData.attributes.every(({validation}) => {
      return validation.valid === true;
    });

    return isReadyToComplete;
  },
  attributeValueChanged(value, index) {
    const attribute = this.rowData.attributes[index];
    attribute.value = value;
    attribute.modified = true;

    attribute.attachments = {
      files: [],
      urls: [],
      comment: null,
    };

    if (attribute.type === 'dropdown'
      && this.getRequiredInfoStates(attribute).comment) {
      attribute.errorsMap.comment = true;
    }

    this.validateAllAttributes();

    if (attribute.validation.hasMissingInfo) {
      this.showRequiredInfo(attribute);
    }

    this.rowData.isReadyToComplete = this.checkAssessmentReadinessToComplete();

    pubSub.dispatch({
      type: 'attributeModified',
      assessmentData: this.rowData,
    });
  },
  showRequiredInfo(attribute) {
    const requiredInfoConfig = this.getRequiredInfoConfig(attribute);
    const modalTitle = `Required ${getLCAPopupTitle(requiredInfoConfig)}`;
    const attachments = attribute.attachments;

    canBatch.start();

    this.requiredInfoModal.title = modalTitle;
    this.requiredInfoModal.content = {
      attribute: {
        id: attribute.id,
        title: attribute.title,
        value: attribute.value,
      },
      requiredInfo: requiredInfoConfig,
      urls: attachments.urls,
      files: attachments.files,
      comment: attachments.comment,
    };
    this.requiredInfoModal.state.open = true;

    canBatch.stop();
  },
  updateRequiredInfo(attributeId, changes) {
    const attribute = loFind(this.rowData.attributes, (attribute) =>
      attribute.id === attributeId);
    const attachments = attribute.attachments;

    canBatch.start();

    attachments.comment = changes.comment;
    attachments.urls.replace(changes.urls);
    attachments.files.replace(changes.files);

    attribute.modified = true;
    attribute.errorsMap.comment = attachments.comment === null;

    canBatch.stop();

    this.validateAllAttributes();
    this.rowData.isReadyToComplete = this.checkAssessmentReadinessToComplete();

    pubSub.dispatch({
      type: 'attributeModified',
      assessmentData: this.rowData,
    });
  },
  getRequiredInfoConfig(attribute) {
    const {comment, attachment, url} = this.getRequiredInfoStates(attribute);

    const showFile = attachment
      ? this.isFileRequired || attribute.attachments.files.length !== 0
      : false;
    const showUrl = url
      ? this.isUrlRequired || attribute.attachments.urls.length !== 0
      : false;
    const showComment = comment
      ? attribute.errorsMap.comment || attribute.attachments.comment !== null
      : false;

    return {
      attachment: showFile,
      url: showUrl,
      comment: showComment,
    };
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-table-row',
  view: canStache(template),
  ViewModel,
  events: {
    init() {
      this.viewModel.validateAllAttributes();
      this.viewModel.rowData.isReadyToComplete =
        this.viewModel.checkAssessmentReadinessToComplete();

      if (this.viewModel.rowData.isReadyToComplete) {
        pubSub.dispatch({
          type: 'assessmentReadyToComplete',
          assessmentId: this.viewModel.rowData.asmtId,
        });
      }
    },
    '{pubSub} requiredInfoSave'(pubSub, {attributeId, changes}) {
      const isAttributeInRow = this.viewModel.rowData.attributes.serialize()
        .map((attribute) => attribute.id)
        .includes(attributeId);

      if (isAttributeInRow) {
        this.viewModel.updateRequiredInfo(attributeId, changes);
      }
    },
  },
});
