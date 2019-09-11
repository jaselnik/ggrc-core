/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
import '../form/fields/dropdown-form-field';
import '../person/person-data';
import template from './readonly-inline-content.stache';

export default canComponent.extend({
  tag: 'readonly-inline-content',
  view: canStache(template),
  leakScope: true,
  viewModel: canMap.extend({
    withReadMore: false,
    options: [],
    value: '',
    define: {
      items: {
        get() {
          const options = this.attr('options');
          const value = this.attr('value');

          if (options.length && value && typeof(value) === 'string') {
            return value.split(',')
              .map((item) => `<p><i class="fa fa-circle"></i>${item}</p>`)
              .join('');
          }
          return '';
        },
      },
    },
  }),
});
