/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Cacheable from '../cacheable';
import AccessControlList from '../mixins/access-control-list';
import Reviewable from '../mixins/reviewable';
import UniqueTitle from '../mixins/unique-title';
import CaUpdate from '../mixins/ca-update';
import BaseNotifications from '../mixins/notifications/base-notifications';
import ChangeableExternally from '../mixins/changeable-externally';
import Stub from '../stub';

export default Cacheable.extend({
  root_object: 'contract',
  root_collection: 'contracts',
  model_plural: 'Contracts',
  table_plural: 'contracts',
  title_plural: 'Contracts',
  model_singular: 'Contract',
  title_singular: 'Contract',
  table_singular: 'contract',
  category: 'governance',
  findAll: 'GET /api/contracts',
  findOne: 'GET /api/contracts/{id}',
  create: 'POST /api/contracts',
  update: 'PUT /api/contracts/{id}',
  destroy: 'DELETE /api/contracts/{id}',
  mixins: [
    AccessControlList,
    Reviewable,
    UniqueTitle,
    CaUpdate,
    BaseNotifications,
    ChangeableExternally,
  ],
  is_custom_attributable: true,
  isRoleable: true,
  sub_tree_view_options: {
    default_filter: ['Requirement'],
  },
  defaults: {
    status: 'Draft',
    kind: 'Contract',
  },
  statuses: ['Draft', 'Deprecated', 'Active'],
  attributes: {
    context: Stub,
    modified_by: Stub,
  },
  tree_view_options: {
    attr_list: Cacheable.attr_list.concat([
      {
        attr_title: 'State',
        attr_name: 'status',
        order: 40,
      }, {
        attr_title: 'Review State',
        attr_name: 'review_status',
        order: 80,
      }, {
        attr_title: 'Effective Date',
        attr_name: 'start_date',
        order: 85,
      }, {
        attr_title: 'Reference URL',
        attr_name: 'reference_url',
        order: 90,
      }, {
        attr_title: 'Description',
        attr_name: 'description',
        order: 95,
      }, {
        attr_title: 'Notes',
        attr_name: 'notes',
        order: 100,
      }, {
        attr_title: 'Assessment Procedure',
        attr_name: 'test_plan',
        order: 105,
      }, {
        attr_title: 'Last Deprecated Date',
        attr_name: 'end_date',
        order: 110,
      }]),
  },
}, {});
