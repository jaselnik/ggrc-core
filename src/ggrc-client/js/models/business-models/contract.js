/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Cacheable from '../cacheable';
import ChangeableExternally from '../mixins/changeable-externally';
import Proposable from '../mixins/proposable';

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
  mixins: [
    ChangeableExternally,
    Proposable,
  ],
  is_custom_attributable: true,
  isRoleable: true,
  sub_tree_view_options: {
    default_filter: ['Requirement'],
  },
  statuses: ['Draft', 'Deprecated', 'Active'],
  tree_view_options: {
    attr_list: Cacheable.attr_list.concat([{
      attr_title: 'State',
      attr_name: 'status',
      order: 40,
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
    }, {
      attr_title: 'Created By',
      attr_name: 'created_by',
    }]),
  },
}, {});
