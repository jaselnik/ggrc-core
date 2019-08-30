/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loMap from 'lodash/map';
import {ggrcAjax} from '../ajax_extensions';
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
  update: function (model, instances, targetProps) {
    const url = '/api/' + model.table_plural;
    const dfd = $.Deferred();
    instances = toBulkModel(instances, targetProps);

    ggrcAjax({
      url: url,
      method: 'PATCH',
      data: JSON.stringify(instances),
      contentType: 'application/json',
    }).done(function (res) {
      dfd.resolve(res);
    }).fail(function (err) {
      dfd.reject(err);
    });
    return dfd;
  },
};

export const requestAssessmentsCount = (relevant = null) => {
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
          left: 'archived',
          op: {
            name: '=',
          },
          right: 'false',
        },
      },
    },
  };

  const param = buildParam('Assessment', {}, relevant, [], filters);
  param.type = 'count';
  param.permissions = 'update';

  return batchRequests(param).then(({Assessment: {count}}) => count);
};
