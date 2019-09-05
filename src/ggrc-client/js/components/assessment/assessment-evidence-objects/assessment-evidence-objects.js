/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canMap from 'can-map';
import canComponent from 'can-component';
import canStache from 'can-stache';
import {
  buildParam,
  batchRequests,
} from '../../../plugins/utils/query-api-utils';
import {CUSTOM_ATTRIBUTE_TYPE} from '../../../plugins/utils/custom-attribute/custom-attribute-config';
import template from './assessment-evidence-objects.stache';

export default canComponent.extend({
  tag: 'assessment-evidence-objects',
  view: canStache(template),
  viewModel: canMap.extend({
    instance: {},
    evidenceFiles: [],
    evidenceUrls: [],
    localCustomAttributes: [],
    isInitialized: false,
    isLoading: false,
    expanded: false,
    loadEvidences() {
      const assessmentId = this.attr('instance').id;

      const filters = {
        expression: {
          left: {
            left: 'kind',
            op: {
              name: 'IN',
            },
            right: ['URL', 'FILE'],
          },
          op: {
            name: 'AND',
          },
          right: {
            object_name: 'Assessment',
            op: {
              name: 'relevant',
            },
            ids: [assessmentId],
          },
        },
      };

      const param = buildParam('Evidence', {}, null, [], filters);

      return batchRequests(param).then(({Evidence: {values}}) => values);
    },
    initLocalCustomAttributes() {
      const lcaObjects = this.attr('instance')
        .customAttr({type: CUSTOM_ATTRIBUTE_TYPE.LOCAL});
      this.attr('localCustomAttributes', lcaObjects);
    },
    async initEvidences() {
      try {
        this.attr('isLoading', true);
        const evidences = await this.loadEvidences();

        let urls = [];
        let files = [];

        evidences.forEach((item) => {
          if (item.kind === 'URL') {
            urls.push(item);
          } else {
            files.push(item);
          }
        });
        this.attr('evidenceUrls', urls);
        this.attr('evidenceFiles', files);

        this.attr('isInitialized', true);
      } finally {
        this.attr('isLoading', false);
      }
    },
  }),
  events: {
    '{viewModel} expanded'() {
      const viewModel = this.viewModel;

      const needToMakeRequest = viewModel.attr('expanded') &&
        !viewModel.attr('isInitialized');
      if (needToMakeRequest) {
        viewModel.initLocalCustomAttributes();
        viewModel.initEvidences();
      }
    },
  },
});
