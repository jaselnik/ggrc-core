/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import canComponent from 'can-component';

const POPOVER_HOVER_WAIT_TIME = 100;

export default canComponent.extend({
  tag: 'popover-component',
  leakScope: true,
  viewModel: canMap.extend({
    header: '',
    content: '',
    isInitialized: false,
    showPopover($el) {
      $el.popover('show');

      const left = $el.offset().left;
      $('.btstrp-popover__wrapper').offset({left});
    },
    hidePopover($el) {
      $el.popover('hide');
    },
    initializePopover($el) {
      $el.popover({
        trigger: 'manual',
        html: true,
        title: this.attr('header'),
        content: this.attr('content'),
        animation: true,
        container: 'body',
        placement(el) {
          $(el).addClass('btstrp-popover__wrapper');
          return 'bottom';
        },
      });
    },
  }),
  events: {
    '[data-popover-trigger] mouseenter'(el) {
      const $el = $(el);

      if (!this.viewModel.attr('isInitialized')) {
        this.viewModel.initializePopover($el);
        this.viewModel.attr('isInitialized', true);
      }

      this.viewModel.showPopover($el);

      $('.btstrp-popover__wrapper').one('mouseleave', () => {
        this.viewModel.hidePopover($el);
      });
    },
    '[data-popover-trigger] mouseleave'(el) {
      setTimeout(() => {
        if (!$('.btstrp-popover__wrapper:hover').length) {
          this.viewModel.hidePopover($(el));
        }
      }, POPOVER_HOVER_WAIT_TIME);
    },
  },
});
