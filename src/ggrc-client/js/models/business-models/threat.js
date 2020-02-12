/*
 * Copyright (C) 2020 Google Inc.
 * Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import Cacheable from '../cacheable';
import ChangeableExternally from '../mixins/changeable-externally';

export default Cacheable.extend({
  root_object: 'threat',
  root_collection: 'threats',
  category: 'risk',
  findAll: 'GET /api/threats',
  findOne: 'GET /api/threats/{id}',
  mixins: [
    ChangeableExternally,
  ],
  is_custom_attributable: true,
  isRoleable: true,
  tree_view_options: {
    attr_list: Cacheable.attr_list.concat([
      {attr_title: 'Reference URL', attr_name: 'reference_url'},
      {attr_title: 'Effective Date', attr_name: 'start_date'},
      {attr_title: 'Last Deprecated Date', attr_name: 'end_date'},
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
    default_filter: ['Risk'],
  },
  statuses: ['Draft', 'Deprecated', 'Active'],
}, {});
