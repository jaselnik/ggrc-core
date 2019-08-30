/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import canComponent from 'can-component';
import {isMyAssessments} from '../../../plugins/utils/current-page-utils';
import {requestAssessmentsCount} from '../../../plugins/utils/bulk-update-service';

export default canComponent.extend({
  tag: 'assessment-tree-actions',
  viewModel: canMap.extend({
    define: {
      showBulkComplete: {
        value: false,
        get(lastSetValue, setAttrValue) {
          setAttrValue(lastSetValue); // set default value before request

          if (isMyAssessments()) {
            requestAssessmentsCount()
              .then(({Assessment: {count}}) => {
                setAttrValue(count > 0);
              });
          }
        },
      },
    },
    parentInstance: null,
    model: null,
  }),
});
