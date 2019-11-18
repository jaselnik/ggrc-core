/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canList from 'can-list';
import Cacheable from '../cacheable';
import RefetchHash from '../mixins/refetch-hash';
import AssessmentIssueTracker from '../mixins/assessment-issue-tracker';
import Stub from '../stub';

/**
 * A model describing a template for the newly created Assessment objects.
 *
 * This is useful when creating multiple similar Assessment objects. Using an
 * AssessmentTemplate helps avoiding repeatedly defining the same set of
 * Assessment object properties for each new instance.
 */
export default Cacheable.extend({
  root_object: 'assessment_template',
  root_collection: 'assessment_templates',
  model_singular: 'AssessmentTemplate',
  model_plural: 'AssessmentTemplates',
  title_singular: 'Assessment Template',
  title_plural: 'Assessment Templates',
  table_singular: 'assessment_template',
  table_plural: 'assessment_templates',
  mixins: [
    RefetchHash,
    AssessmentIssueTracker,
  ],
  findOne: 'GET /api/assessment_templates/{id}',
  findAll: 'GET /api/assessment_templates',
  update: 'PUT /api/assessment_templates/{id}',
  destroy: 'DELETE /api/assessment_templates/{id}',
  create: 'POST /api/assessment_templates',
  is_custom_attributable: false,
  attributes: {
    context: Stub,
  },
  defaults: {
    test_plan_procedure: true,
    sox_302_enabled: false,
    template_object_type: 'Control',
    default_people: {
      assignees: 'Principal Assignees',
      verifiers: 'Auditors',
    },
    status: 'Draft',
    verification_workflow: 'STANDARD',
    review_levels_count: null,
  },
  statuses: ['Draft', 'Deprecated', 'Active'],
  tree_view_options: {
    attr_list: [{
      attr_title: 'Title',
      attr_name: 'title',
      order: 10,
    }, {
      attr_title: 'State',
      attr_name: 'status',
      order: 20,
    }, {
      attr_title: 'Code',
      attr_name: 'slug',
      order: 30,
    }, {
      attr_title: 'Last Updated Date',
      attr_name: 'updated_at',
      order: 70,
    }, {
      attr_title: 'Last Updated By',
      attr_name: 'modified_by',
      order: 71,
    }, {
      attr_title: 'SOX 302 assessment workflow',
      attr_name: 'sox_302_enabled',
      order: 72,
    }],
    add_item_view: 'assessment_templates/tree-add-item',
  },
}, {
  define: {
    title: {
      value: '',
      validate: {
        required: true,
      },
    },
    default_people: {
      validate: {
        validateDefaultAssignees: true,
        validateDefaultVerifiers: true,
      },
    },
    issue_tracker: {
      value: {},
      validate: {
        validateIssueTrackerComponentId: true,
      },
    },
    can_use_issue_tracker: {
      value: false,
    },
  },
  /**
   * An event handler when the add/edit form is about to be displayed.
   *
   * It builds a list of all object types used to populate the corresponding
   * dropdown menu on the form.
   * It also deserializes the default people settings so that those form
   * fields are correctly populated.
   *
   * @param {Boolean} isNew - whether instance is new
   * @param {*} params - additional params
   * @param {*} pageInstance - current page instance
   */
  formPreload: function (isNew, params, pageInstance) {
    if (!this.audit || !this.audit.id || !this.audit.type) {
      if (pageInstance.type === 'Audit') {
        this.attr('audit', pageInstance);
      }
    }

    if (!this.custom_attribute_definitions) {
      this.attr('custom_attribute_definitions', new canList());
    }
  },
});
