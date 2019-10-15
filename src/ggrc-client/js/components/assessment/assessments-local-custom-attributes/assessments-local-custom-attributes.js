/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/
import '../../form/form-validation-icon';
import '../../custom-attributes/custom-attributes-field';
import '../../popover-component/popover-component';
import '../assessments-lca-popover/assessments-lca-popover';
import '../../custom-attributes/custom-attributes-field-view';

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import template from './assessments-local-custom-attributes.stache';
import popoverRelObjectsHeader from './templates/popover-related-objects-header.stache';
import popoverRelObjectsContent from './templates/popover-related-objects-content.stache';
import popoverRelAnswersHeader from './templates/popover-related-answers-header.stache';
import popoverRelAnswersContent from './templates/popover-related-answers-content.stache';
import {
  buildParam,
  batchRequests,
} from '../../../plugins/utils/query-api-utils';
import QueryParser from '../../../generated/ggrc_filter_query_parser';

const viewModel = canMap.extend({
  fields: [],
  disabled: false,
  popovers: {
    relObjectsHeader: null,
    relObjectsContent: null,
    relAnswersHeader: null,
    relAnswersContent: null,
  },
  getFieldClass(type) {
    return type === 'checkbox' ? 'custom-attribute-checkbox' : '';
  },
  updateRequiredInfo(fieldIndex) {
    const field = this.attr('fields')[fieldIndex];
    this.dispatch({
      type: 'updateRequiredInfo',
      field,
    });
  },
  fieldValueChanged(value, fieldIndex) {
    const field = this.attr('fields')[fieldIndex];
    this.dispatch({
      type: 'fieldValueChanged',
      field,
      value,
    });
  },
  getRelatedAssessmentsFilter(relatedAssessments) {
    return {
      expression: {
        left: {
          left: 'child_type',
          op: {
            name: '=',
          },
          right: relatedAssessments.assessments_type,
        },
        op: {
          name: 'AND',
        },
        right: {
          object_name: 'Assessment',
          op: {
            name: 'relevant',
          },
          ids: relatedAssessments.assessments.map(({id}) => id),
        },
      },
    };
  },
  loadRelatedObjects(relatedAssessments) {
    const initialFilter =
      this.getRelatedAssessmentsFilter(relatedAssessments[0]);
    const filter = relatedAssessments.reduce(
      (filter, assessments) => QueryParser.joinQueries(
        filter,
        this.getRelatedAssessmentsFilter(assessments),
        'OR'
      ), initialFilter);
    const fields = ['id', 'revision'];
    const param = buildParam('Snapshot', {}, null, fields, filter);

    return batchRequests(param).then(({Snapshot: {values}}) => values);
  },
  initRelatedObjectsPopover() {
    const fields = this.attr('fields');
    /**
     * It's necessary to return a function that returns a function
     * because canJS considers that this construction () => ()() is computed function
     * and if template contains canJS components they starts to initialize.
     * We should initialize component after hovering over the popover.
     */
    this.attr('popovers.relObjectsHeader', (index) => () => {
      const count = fields[index].attr('relatedAssessments.count');
      const assessment = (count === 1) ? 'assessment' : 'assessments';
      return canStache(popoverRelObjectsHeader)({
        count,
        assessment,
      });
    });

    const cache = new Map();
    this.attr('popovers.relObjectsContent', (index) => () => {
      if (!cache.has(index)) {
        const relatedObjectsDfd = this.loadRelatedObjects(
          fields[index].attr('relatedAssessments.values').serialize()
        );

        cache.set(index, relatedObjectsDfd);
      }

      return canStache(popoverRelObjectsContent)({
        relatedObjectsDfd: cache.get(index),
      });
    });
  },
  initRelatedAnswersPopover() {
    const fields = this.attr('fields');

    this.attr('popovers.relAnswersHeader', () => () =>
      canStache(popoverRelAnswersHeader)());

    this.attr('popovers.relAnswersContent', (index) => () =>
      canStache(popoverRelAnswersContent)({
        relatedAnswers: fields[index].attr('relatedAnswers'),
        attributeType: fields[index].attr('type'),
        attributeOptions: fields[index].attr('multiChoiceOptions.values'),
      }));
  },
  initPopovers() {
    this.initRelatedObjectsPopover();
    this.initRelatedAnswersPopover();
  },
  init() {
    this.initPopovers();
  },
});

const events = {
  '{viewModel} fields'() {
    this.viewModel.initPopovers();
  },
};

export default canComponent.extend({
  tag: 'assessments-local-custom-attributes',
  view: canStache(template),
  viewModel,
  events,
});
