/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loMap from 'lodash/map';
import {ggrcAjax} from '../ajax-extensions';
import {
  buildParam,
  batchRequests,
} from './query-api-utils';

const toBulkModel = (instances, targetProps) => {
  let state = targetProps.state;
  return loMap(instances, (item) => {
    return {
      id: item.id,
      state: state,
    };
  });
};

export default {
  update(model, instances, targetProps) {
    const url = '/api/' + model.table_plural;
    instances = toBulkModel(instances, targetProps);
    return new Promise((resolve, reject) => {
      ggrcAjax({
        url: url,
        method: 'PATCH',
        data: JSON.stringify(instances),
        contentType: 'application/json',
      }).done((res) => {
        resolve(res);
      }).fail((err) => {
        reject(err);
      });
    });
  },
};

const requestAssessmentsCount = (
  relevant = null,
  filters,
  permissions = null
) => {
  const param = buildParam('Assessment', {}, relevant, [], filters);
  param.type = 'count';

  if (permissions) {
    param.permissions = permissions;
  }

  return batchRequests(param).then(({Assessment: {count}}) => count);
};

export const getAsmtCountForCompletion = (relevant) => {
  const filters = {
    expression: {
      left: {
        left: 'assignees',
        op: {
          name: '~',
        },
        right: GGRC.current_user.email,
      },
      op: {
        name: 'AND',
      },
      right: {
        left: {
          left: 'status',
          op: {
            name: 'IN',
          },
          right: [
            'Not Started',
            'In Progress',
            'Rework Needed',
          ],
        },
        op: {
          name: 'AND',
        },
        right: {
          left: {
            left: 'sox_302_enabled',
            op: {
              name: '=',
            },
            right: 'yes',
          },
          op: {
            name: 'AND',
          },
          right: {
            left: 'archived',
            op: {
              name: '=',
            },
            right: 'No',
          },
        },
      },
    },
  };

  return requestAssessmentsCount(relevant, filters, 'update');
};

export const getAsmtCountForVerify = (relevant) => {
  const filters = {
    expression: {
      left: {
        object_name: 'Person',
        op: {
          name: 'relevant',
        },
        ids: [
          GGRC.current_user.id,
        ],
      },
      op: {
        name: 'AND',
      },
      right: {
        left: {
          left: 'status',
          op: {
            name: '=',
          },
          right: 'In Review',
        },
        op: {
          name: 'AND',
        },
        right: {
          left: {
            left: 'archived',
            op: {
              name: '=',
            },
            right: 'No',
          },
          op: {
            name: 'AND',
          },
          right: {
            left: 'verifiers',
            op: {
              name: '~',
            },
            right: GGRC.current_user.email,
          },
        },
      },
    },
  };

  return requestAssessmentsCount(relevant, filters);
};
