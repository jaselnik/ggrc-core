/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canComponent from 'can-component';
import canDefineMap from 'can-define/map/map';
import canStache from 'can-stache';
import '../../../popover-component/popover-component';
import template from './templates/assessments-bulk-complete-popover.stache';
import {
  buildParam,
  batchRequests,
} from '../../../../plugins/utils/query-api-utils';
import popoverRelObjectsHeader from './templates/popover-related-objects-header.stache';
import popoverRelObjectsContent from './templates/popover-related-objects-content.stache';

const ViewModel = canDefineMap.extend({seal: false}, {
  rowData: {
    value: () => [],
  },
  popovers: {
    value: {
      relObjectsHeader: null,
      relObjectsContent: null,
    },
  },
  initRelatedObjectsPopover() {
    const assessmentType = this.rowData.asmtType.toLowerCase();

    this.popovers.relObjectsHeader = () => () => {
      return canStache(popoverRelObjectsHeader)({
        assessmentType,
      });
    };

    let cache = null;
    this.popovers.relObjectsContent = () => () => {
      if (!cache) {
        const relatedObjectsPromise = this.loadMappedObjects();
        cache = relatedObjectsPromise;
      }

      return canStache(popoverRelObjectsContent)({
        relatedObjectsPromise: cache,
        assessmentType,
      });
    };
  },

  async loadMappedObjects() {
    const filters = {
      expression: {
        left: {
          left: 'child_type',
          op: {
            name: '=',
          },
          right: this.rowData.asmtType,
        },
        op: {
          name: 'AND',
        },
        right: {
          object_name: 'Assessment',
          op: {
            name: 'relevant',
          },
          ids: [this.rowData.asmtId],
        },
      },
    };

    const fields = ['id', 'revision'];
    const param = buildParam('Snapshot', {}, null, fields, filters);
    const objects = await batchRequests(param)
      .then(({Snapshot: {values}}) => values);

    const mappedObjects = objects.map(({revision, id}) => ({
      id,
      title: revision.content.title,
      type: revision.resource_type.toLowerCase(),
      description: revision.content.description,
    }));
    return mappedObjects;
  },
});

export default canComponent.extend({
  tag: 'assessments-bulk-complete-popover',
  view: canStache(template),
  ViewModel,
  events: {
    inserted() {
      this.viewModel.initRelatedObjectsPopover();
    },
  },
});
