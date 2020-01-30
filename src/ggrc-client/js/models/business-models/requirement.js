/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Cacheable from '../cacheable';
import UniqueTitle from '../mixins/unique-title';
import CaUpdate from '../mixins/ca-update';
import AccessControlList from '../mixins/access-control-list';
import BaseNotifications from '../mixins/notifications/base-notifications';
import Relationship from '../service-models/relationship';
import Reviewable from '../mixins/reviewable';
import ChangeableExternally from '../mixins/changeable-externally';
import Stub from '../stub';

export default Cacheable.extend({
  root_object: 'requirement',
  root_collection: 'requirements',
  model_plural: 'Requirements',
  table_plural: 'requirements',
  title_plural: 'Requirements',
  model_singular: 'Requirement',
  title_singular: 'Requirement',
  table_singular: 'requirement',
  category: 'governance',
  root_model: 'Requirement',
  findAll: 'GET /api/requirements',
  findOne: 'GET /api/requirements/{id}',
  create: 'POST /api/requirements',
  update: 'PUT /api/requirements/{id}',
  destroy: 'DELETE /api/requirements/{id}',
  is_custom_attributable: true,
  isRoleable: true,
  mixins: [
    UniqueTitle,
    CaUpdate,
    AccessControlList,
    BaseNotifications,
    Reviewable,
    ChangeableExternally,
  ],
  attributes: {
    context: Stub,
    modified_by: Stub,
  },
  tree_view_options: {
    attr_list: Cacheable.attr_list.concat([
      {attr_title: 'Reference URL', attr_name: 'reference_url'},
      {attr_title: 'Effective Date', attr_name: 'start_date'},
      {attr_title: 'Last Deprecated Date', attr_name: 'last_deprecated_date'},
      {
        attr_title: 'State',
        attr_name: 'status',
        order: 40,
      }, {
        attr_title: 'Description',
        attr_name: 'description',
      }, {
        attr_title: 'Notes',
        attr_name: 'notes',
      }, {
        attr_title: 'Assessment Procedure',
        attr_name: 'test_plan',
      }, {
        attr_title: 'Review State',
        attr_name: 'review_status',
        order: 80,
      }]),
  },
  sub_tree_view_options: {
    default_filter: ['Objective'],
  },
  defaults: {
    status: 'Draft',
  },
  statuses: ['Draft', 'Deprecated', 'Active'],
}, {
  define: {
    title: {
      value: '',
      validate: {
        required: true,
        validateUniqueTitle: true,
      },
    },
    _transient_title: {
      value: '',
      validate: {
        validateUniqueTitle: true,
      },
    },
    _directive: {
      value: null,
    },
  },
  created() {
    this._super(...arguments);

    if (!this._directive || !this._directive.id) {
      return;
    }

    let directiveDfd = new Relationship({
      source: this,
      destination: this._directive,
      context: this.context,
    }).save();

    this.delay_resolving_save_until($.when(directiveDfd));
  },
});
