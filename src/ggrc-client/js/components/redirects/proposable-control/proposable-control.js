/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import template from './templates/proposable-control.stache';
import {
  getInfoUrl,
  getProposalAttrUrl,
} from '../../../plugins/utils/ggrcq-utils';

const viewModel = canMap.extend({
  define: {
    link: {
      get() {
        const attrName = this.attr('attrName');
        const instance = this.attr('instance');
        const isCustomAttribute = this.attr('isCustomAttribute');

        return attrName
          ? getProposalAttrUrl(instance, attrName, isCustomAttribute)
          : getInfoUrl(instance);
      },
    },
  },
  instance: null,
  attrName: '',
  isCustomAttribute: false,
});

export default canComponent.extend({
  tag: 'proposable-control',
  view: canStache(template),
  viewModel,
});
