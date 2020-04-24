/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import template from './templates/external-control.stache';
import {getQuestionsAttrUrl} from '../../../plugins/utils/ggrcq-utils';

const viewModel = canMap.extend({
  define: {
    link: {
      get() {
        return getQuestionsAttrUrl(this.attr('instance'));
      },
    },
  },
  instance: null,
});

export default canComponent.extend({
  tag: 'external-control',
  view: canStache(template),
  viewModel,
});
