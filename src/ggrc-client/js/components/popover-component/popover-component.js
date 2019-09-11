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
    /**
     * Сontent is function because template may contain canJS components which are not yet initialized.
     * After calling of this function, all the components will be initialized (called needed lifecycle-related methods etc.).
     *
     * @type {function}
     */
    content: null,
    isInitialized: false,
    showPopover($el) {
      $el.popover('show');
      /**
       * We add "content" after showing of the popover because
       * "content" can be canStache's fragment. canStache's fragments are initialized
       * properly only in case, if we add them in the DOM. If we use Bootstrap's option "content" during
       * the initialization of popover, "content"'ll be added internally in some Bootstrap's
       * fragment which will be inserted into the DOM later - components
       * which are included into canStache won't call different methods like `inserted` and set up bindings
       * between viewModel and view.
       */
      $('.btstrp-popover__wrapper .popover-content')
        .html(this.attr('content')());
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
        content: null,
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
      setTimeout(() => {
        if ($el.is(':hover')) {
          this.viewModel.showPopover($el);

          $('.btstrp-popover__wrapper').one('mouseleave', () => {
            this.viewModel.hidePopover($el);
          });
        }
      }, POPOVER_HOVER_WAIT_TIME);
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
