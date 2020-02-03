/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Cacheable from '../cacheable';
import RelatedAssessmentsLoader from '../mixins/related-assessments-loader';
import ChangeableExternally from '../mixins/changeable-externally';
import Proposable from '../mixins/proposable';

export default Cacheable.extend({
  root_object: 'objective',
  root_collection: 'objectives',
  category: 'objectives',
  title_singular: 'Objective',
  title_plural: 'Objectives',
  findAll: 'GET /api/objectives',
  findOne: 'GET /api/objectives/{id}',
  mixins: [
    RelatedAssessmentsLoader,
    ChangeableExternally,
    Proposable,
  ],
  is_custom_attributable: true,
  isRoleable: true,
  tree_view_options: {
    attr_list: Cacheable.attr_list.concat([{
      attr_title: 'Last Assessment Date',
      attr_name: 'last_assessment_date',
      order: 45, // between State and Primary Contact
    }, {
      attr_title: 'Effective Date',
      attr_name: 'start_date',
    }, {
      attr_title: 'Last Deprecated Date',
      attr_name: 'last_deprecated_date',
    }, {
      attr_title: 'Created By',
      attr_name: 'created_by',
    }, {
      attr_title: 'Reference URL',
      attr_name: 'reference_url',
    }, {
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
    display_attr_names: ['title', 'status', 'last_assessment_date',
      'updated_at'],
    show_related_assessments: true,
  },
  sub_tree_view_options: {
    default_filter: ['Control'],
  },
  statuses: ['Draft', 'Deprecated', 'Active'],
}, {});
