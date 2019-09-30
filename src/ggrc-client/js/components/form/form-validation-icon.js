/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canStache from 'can-stache';
import canMap from 'can-map';
import canComponent from 'can-component';
/**
 * State object to present possible icons for validation
 */
const icons = {
  noValidation: 'fa-check-circle',
  empty: '',
  valid: 'fa-check form-validation-icon__color-valid',
  invalid: 'fa-times form-validation-icon__color-invalid',
};

/**
 * Form validation icon component
 */
export default canComponent.extend({
  tag: 'form-validation-icon',
  view: canStache(
    '<i class="fa form-validation-icon__body {{iconCls}}"></i>'
  ),
  leakScope: true,
  viewModel: canMap.extend({
    define: {
      validation: {},
      iconCls: {
        get: function () {
          let icon = icons.empty;

          if (this.attr('validation.mandatory')) {
            icon = this.attr('validation.valid')
              ? icons.valid
              : icons.invalid;
          } else if (this.attr('validation.requiresAttachment')) {
            /* This validation is required for DropDowns with required attachments */

            icon = (
              this.attr('validation.valid') &&
              !this.attr('validation.hasMissingInfo')
            ) ? icons.valid : icons.invalid;
          }
          return icon;
        },
      },
    },
  }),
});
