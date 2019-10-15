/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/


import '../../collapsible-panel/collapsible-panel';
import '../../advanced-search/advanced-search-container/advanced-search-container';
import '../../assessment/assessments-local-custom-attributes/assessments-local-custom-attributes';
import '../../required-info-modal/required-info-modal';

import canComponent from 'can-component';
import canStache from 'can-stache';
import canBatch from 'can-event/batch/batch';
import canMap from 'can-map';
import template from './assessments-bulk-complete.stache';
import ObjectOperationsBaseVM from '../../view-models/object-operations-base-vm';
import {STATES_KEYS} from '../../../plugins/utils/state-utils';
import loFindIndex from 'lodash/findIndex';
import {request} from '../../../plugins/utils/request-utils';
import {confirm} from '../../../plugins/utils/modals';
import {getFetchErrorInfo} from '../../../plugins/utils/errors-utils';
import {notifier} from '../../../plugins/utils/notifiers-utils';
import {
  getCustomAttributeType,
  ddValidationValueToMap,
  getLCAPopupTitle,
} from '../../../plugins/utils/ca-utils';
import loSome from 'lodash/some';
import loFind from 'lodash/find';
import {getPlainText} from '../../../plugins/ggrc_utils';
import {
  create,
  setDefaultStatusConfig,
} from '../../../plugins/utils/advanced-search-utils';

const viewModel = ObjectOperationsBaseVM.extend({
  define: {
    isSelectButtonDisabled: {
      get() {
        return (
          this.attr('selected.length') === 0 ||
          this.attr('isAttributesGenerating') ||
          !this.attr('hasChangedSelection')
        );
      },
    },
    hasChangedSelection: {
      get() {
        return (
          this.attr('selectedAfterLastSelection.length') > 0 ||
          this.attr('deselectedAfterLastSelection.length') > 0
        );
      },
    },
  },
  showSearch: false,
  showFields: false,
  isMyAssessmentsView: false,
  mappedToItems: [],
  filterItems: [],
  defaultFilterItems: [],
  mappingItems: [],
  statesCollectionKey: STATES_KEYS.BULK_COMPLETE,
  type: 'Assessment',
  isAttributesGenerating: false,
  attributeFields: [],
  isAttributesGenerated: false,
  requiredInfoModal: {
    title: '',
    state: {open: false},
    content: {
      field: null,
      requiredInfo: null,
      commentValue: null,
      urls: [],
      files: [],
    },
  },
  /**
   * Contains selected objects (which have id and type properties)
   */
  selectedAfterLastSelection: [],
  deselectedAfterLastSelection: [],
  /**
   * Util which removes `newItems`'s items from `collectionForRemove` collection
   * and add them to `collectionForAdd` collection if they were removed from
   * `collectionForRemove`.
   * @param {Array} items - Items for processing
   * @param {canList} collectionForRemove - Collection in which `items` should be
   * removed if they are included in `collectionForRemove`
   * @param {canList} collectionForAdd - Collection which should be filled by the
   * `items` which weren't added to `collectionForRemove`
   */
  updateSelectionCollections(items, collectionForRemove, collectionForAdd) {
    canBatch.start();

    items.forEach((item) => {
      const removeItemIndex = loFindIndex(collectionForRemove,
        (removedItem) => item.attr('id') === removedItem.attr('id'));

      if (removeItemIndex !== -1) {
        collectionForRemove.splice(removeItemIndex, 1);
      } else {
        collectionForAdd.push(item);
      }
    });

    canBatch.stop();
  },
  onSelectClick() {
    const hasUpdatedAttributes = loSome(this.attr('attributeFields'),
      (field) => field.attr('value') !== field.attr('defaultValue'));

    if (hasUpdatedAttributes) {
      confirm({
        modal_title: 'Warning',
        modal_description: 'Custom attributes list will be updated ' +
          'accordingly. All already added answers will be lost.',
        button_view:
          `${GGRC.templates_path}/modals/confirm_cancel_buttons.stache`,
        modal_confirm: 'Proceed',
      }, () => this.generateAttributes());
    } else {
      this.generateAttributes();
    }
  },
  convertToArray(value) {
    return typeof value === 'string' ? value.split(',') : [];
  },
  convertToAttributeField({
    attribute,
    related_assessments: relatedAssessments,
    assessments_with_values: relatedAnswers,
  }, fieldIndex) {
    const attributeType = getCustomAttributeType(attribute.attribute_type);
    const optionsList = this.convertToArray(attribute.multi_choice_options);
    const optionsStates = this.convertToArray(attribute.multi_choice_mandatory);
    const optionsConfig = optionsStates.reduce((config, state, index) => {
      const optionValue = optionsList[index];
      return config.set(optionValue, Number(state));
    }, new Map());
    const defaultValue = attribute.default_value;
    const value = attributeType === 'checkbox'
      ? defaultValue === '1'
      : defaultValue;

    return {
      value,
      id: fieldIndex,
      attachments: null,
      title: attribute.title,
      type: attributeType,
      defaultValue: attribute.default_value,
      placeholder: attribute.placeholder,
      multiChoiceOptions: {
        values: optionsList,
        config: optionsConfig,
      },
      validation: {
        mandatory: attribute.mandatory,
        valid: !attribute.mandatory,
        requiresAttachment: false,
        hasMissingInfo: false,
      },
      relatedAssessments,
      relatedAnswers: relatedAnswers.map((answer) => ({
        title: answer.title,
        attributeValue: answer.attribute_person_id === null
          ? answer.attribute_value
          : answer.attribute_person_id,
      })),
    };
  },
  async generateAttributes() {
    this.attr('isAttributesGenerating', true);

    try {
      const rawAttributesList = await this.loadGeneratedAttributes();
      const attributeFields = rawAttributesList.map((rawAttribute, index) =>
        this.convertToAttributeField(rawAttribute, index));

      this.attr('isAttributesGenerated', true);
      this.attr('attributeFields', attributeFields);
      this.attr('showResults', false);
      this.attr('showFields', true);
      this.attr('selectedAfterLastSelection', []);
      this.attr('deselectedAfterLastSelection', []);
    } catch (err) {
      notifier('error', getFetchErrorInfo(err).details);
    } finally {
      this.attr('isAttributesGenerating', false);
    }
  },
  loadGeneratedAttributes() {
    return request('/api/bulk_operations/cavs/search', {
      ids: this.attr('selected').serialize()
        .map((selected) => selected.id),
    });
  },
  updateAttributeField({field, value}) {
    field.attr('value', value);
    this.validateField(field);
  },
  validateDropdown(field) {
    const {
      comment,
      attachment,
      url,
    } = this.getRequiredInfoStates(field);
    const requiresAttachment = comment || attachment || url;

    canBatch.start();

    const validation = field.attr('validation');
    validation.attr('requiresAttachment', requiresAttachment);

    if (requiresAttachment) {
      field.attr('attachments', {
        commentValue: null,
        files: [],
        urls: [],
      });
      validation.attr({
        valid: false,
        hasMissingInfo: true,
      });
      this.showRequiredInfoModal(field);
    } else {
      field.attr('attachments', null);
      validation.attr({
        valid: validation.attr('mandatory')
          ? field.attr('value') !== ''
          : true,
        hasMissingInfo: false,
      });
    }

    canBatch.stop();
  },
  validateRequiredInfo(field) {
    const attachments = field.attr('attachments');
    const {
      comment,
      attachment,
      url,
    } = this.getRequiredInfoStates(field);

    const hasValidFiles = attachment
      ? attachments.attr('files.length') > 0
      : true;
    const hasValidUrls = url
      ? attachments.attr('urls.length') > 0
      : true;
    const hasValidComment = comment
      ? attachments.attr('commentValue') !== null
      : true;

    const hasValidAttachments = (
      hasValidFiles &&
      hasValidUrls &&
      hasValidComment
    );

    field.attr('validation').attr({
      valid: hasValidAttachments,
      hasMissingInfo: !hasValidAttachments,
    });
  },
  performDefaultValidation(field) {
    const validation = field.attr('validation');

    if (!validation.attr('mandatory')) {
      return;
    }

    const value = field.attr('type') === 'text'
      ? getPlainText(field.attr('value')).trim()
      : field.attr('value');

    // explicitly check empty values in order to see which real cases exist
    const isEmptyValue = (
      value === '' || // for Text, Rich Text, Multiselect cases
      value === null || // for Person, Date cases
      value === false // for Checkbox case
    );

    validation.attr('valid', !isEmptyValue);
  },
  validateField(field) {
    if (field.attr('type') === 'dropdown') {
      this.validateDropdown(field);
    } else {
      this.performDefaultValidation(field);
    }
  },
  getRequiredInfoStates(field) {
    const optionBitmask = field.attr('multiChoiceOptions.config')
      .get(field.attr('value'));
    return ddValidationValueToMap(optionBitmask);
  },
  updateRequiredInfo({fieldId, changes}) {
    const field = loFind(this.attr('attributeFields'), (field) =>
      field.attr('id') === fieldId);
    const attachments = field.attr('attachments');

    canBatch.start();
    attachments.attr('commentValue', changes.commentValue);
    attachments.attr('urls').replace(changes.urls);
    attachments.attr('files').replace(changes.files);
    canBatch.stop();

    this.validateRequiredInfo(field);
  },
  showRequiredInfoModal(field) {
    const requiredInfo = this.getRequiredInfoStates(field);
    const attachments = field.attr('attachments');
    const requiredInfoModal = this.attr('requiredInfoModal');
    const modalTitle = `Required ${getLCAPopupTitle(requiredInfo)}`;

    canBatch.start();
    requiredInfoModal.attr('title', modalTitle);
    requiredInfoModal.attr('content', {
      field: {
        id: field.attr('id'),
        title: field.attr('title'),
        value: field.attr('value'),
      },
      requiredInfo,
      urls: attachments.attr('urls'),
      files: attachments.attr('files'),
      commentValue: attachments.attr('commentValue'),
    });
    requiredInfoModal.attr('state.open', true);
    canBatch.stop();
  },
  initDefaultFilter() {
    const stateConfig = setDefaultStatusConfig(
      new canMap,
      this.attr('type'),
      this.attr('statesCollectionKey')
    );
    const items = [
      create.state(stateConfig),
      create.operator('AND'),
      create.attribute({
        field: 'Assignees',
        operator: '~',
        value: GGRC.current_user.email,
      }),
    ];

    this.attr('filterItems', items);
    this.attr('defaultFilterItems', items);
  },
  init() {
    this.initDefaultFilter();
  },
});

const events = {
  inserted() {
    this.viewModel.onSubmit();
  },
  // catch selection of objects by inner components
  '{viewModel.selected} add'(el, ev, selected) {
    this.viewModel.updateSelectionCollections(
      selected,
      this.viewModel.attr('deselectedAfterLastSelection'),
      this.viewModel.attr('selectedAfterLastSelection')
    );
  },
  // catch deselection of objects by inner components
  '{viewModel.selected} remove'(el, ev, deselected) {
    this.viewModel.updateSelectionCollections(
      deselected,
      this.viewModel.attr('selectedAfterLastSelection'),
      this.viewModel.attr('deselectedAfterLastSelection')
    );
  },
};

export default canComponent.extend({
  tag: 'assessments-bulk-complete',
  view: canStache(template),
  viewModel,
  events,
});
