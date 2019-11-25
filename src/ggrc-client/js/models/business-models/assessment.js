/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loThrottle from 'lodash/throttle';
import loIsFunction from 'lodash/isFunction';
import loAssign from 'lodash/assign';
import {ggrcAjax, ggrcGet} from '../../plugins/ajax-extensions';
import Cacheable from '../cacheable';
import {prepareCustomAttributes} from '../../plugins/utils/ca-utils';
import {getRole} from '../../plugins/utils/acl-utils';
import {sortByName} from '../../plugins/utils/label-utils';
import tracker from '../../tracker';
import CaUpdate from '../mixins/ca-update';
import AutoStatusChangeable from '../mixins/auto-status-changeable';
import AccessControlList from '../mixins/access-control-list';
import RefetchHash from '../mixins/refetch-hash';
import AssessmentIssueTracker from '../mixins/assessment-issue-tracker';
import RelatedAssessmentsLoader from '../mixins/related-assessments-loader';
import {REFRESH_MAPPING, REFRESHED} from '../../events/event-types';

export default Cacheable.extend({
  root_object: 'assessment',
  root_collection: 'assessments',
  category: 'governance',
  findOne: 'GET /api/assessments/{id}',
  findAll: 'GET /api/assessments',
  update: 'PUT /api/assessments/{id}',
  destroy: 'DELETE /api/assessments/{id}',
  create: 'POST /api/assessments',
  mixins: [
    CaUpdate, AutoStatusChangeable,
    AccessControlList, RefetchHash,
    AssessmentIssueTracker, RelatedAssessmentsLoader,
  ],
  is_custom_attributable: true,
  isRoleable: true,
  defaults: {
    test_plan_procedure: true,
    assessment_type: 'Control',
    status: 'Not Started',
    send_by_default: true, // notifications when a comment is added
    recipients: 'Assignees,Creators,Verifiers', // user roles to be notified
    _is_sox_restricted: false, // restrict assignee's permissions if enabled sox302
    _readonly_fields: [], // readOnly attributes names to restrict permissions
    verification_workflow: 'STANDARD',
    review_levels_count: null,
  },
  statuses: ['Not Started', 'In Progress', 'In Review',
    'Verified', 'Completed', 'Deprecated', 'Rework Needed'],
  unchangeableIssueTrackerIdStatuses: ['In Review', 'Verified', 'Completed',
    'Deprecated'],
  assigneeHierarchy: {
    Verifiers: 1,
    Assignees: 2,
    Creators: 3,
    'Primary Contacts': 4,
    'Secondary Contacts': 5,
  },
  tree_view_options: {
    add_item_view: 'assessments/tree-add-item',
    attr_list: [{
      attr_title: 'Title',
      attr_name: 'title',
      order: 1,
    }, {
      attr_title: 'State',
      attr_name: 'status',
      order: 2,
    }, {
      attr_title: 'Label',
      attr_name: 'label',
      order: 3,
    }, {
      attr_title: 'Verified',
      attr_name: 'verified',
      order: 4,
    }, {
      attr_title: 'Code',
      attr_name: 'slug',
      order: 5,
    }, {
      attr_title: 'Due Date',
      attr_name: 'start_date',
      order: 6,
    }, {
      attr_title: 'Created Date',
      attr_name: 'created_at',
      order: 7,
    }, {
      attr_title: 'Last Updated Date',
      attr_name: 'updated_at',
      order: 8,
    }, {
      attr_title: 'Last Updated By',
      attr_name: 'modified_by',
      order: 9,
    }, {
      attr_title: 'Verified Date',
      attr_name: 'verified_date',
      order: 10,
    }, {
      attr_title: 'Finished Date',
      attr_name: 'finished_date',
      order: 11,
    }, {
      attr_title: 'Last Deprecated Date',
      attr_name: 'end_date',
      order: 12,
    }, {
      attr_title: 'Conclusion: Design',
      attr_name: 'design',
      order: 13,
    }, {
      attr_title: 'Conclusion: Operation',
      attr_name: 'operationally',
      order: 14,
    }, {
      attr_title: 'Archived',
      attr_name: 'archived',
      order: 15,
    }, {
      attr_title: 'Ticket Tracker',
      attr_name: 'issue_url',
      order: 16,
      deny: !GGRC.ISSUE_TRACKER_ENABLED,
    }, {
      attr_title: 'Last Comment',
      attr_name: 'last_comment',
      order: 17,
    }, {
      attr_title: 'Description',
      attr_name: 'description',
      order: 18,
    }, {
      attr_title: 'Notes',
      attr_name: 'notes',
      order: 19,
    }, {
      attr_title: 'Assessment Procedure',
      attr_name: 'test_plan',
      order: 20,
    }, {
      attr_title: 'Assessment Workflow',
      attr_name: 'verification_workflow',
      order: 21,
    }],
    display_attr_names: ['title', 'status', 'label', 'Assignees', 'Verifiers',
      'start_date', 'updated_at'],
  },
  sub_tree_view_options: {
    default_filter: ['Control'],
  },
  confirmEditModal: {
    title: 'Confirm moving Assessment to "In Progress"',
    description: 'You are about to move Assessment from ' +
    '"{{status}}" to "In Progress" - are you sure about that?',
    button: 'Confirm',
  },
  conclusions: ['Effective', 'Ineffective', 'Needs improvement',
    'Not Applicable'],
  editModeStatuses: ['In Progress', 'Rework Needed', 'Not Started'],
  doneStatuses: ['Completed', 'Verified', 'In Review'],
  prepareAttributes: function (attrs) {
    return attrs[this.root_object] ? attrs[this.root_object] : attrs;
  },
  /**
   * Assessment specific AJAX data parsing logic
   * @param {Object} attributes - hash of Model key->values
   * @return {Object} - parsed object with normalized data
   */
  parseModel: function (attributes) {
    let values;
    let definitions;
    attributes = this.prepareAttributes(attributes);
    values = attributes.custom_attribute_values || [];
    definitions = attributes.custom_attribute_definitions || [];

    if (!definitions.length) {
      return attributes;
    }

    if (attributes.labels && attributes.labels.length) {
      attributes.labels = sortByName(attributes.labels);
    }

    attributes.custom_attribute_values =
      prepareCustomAttributes(definitions, values);
    return attributes;
  },
  model: function (attributes, oldModel) {
    if (!attributes) {
      return;
    }

    if (typeof attributes.serialize === 'function') {
      attributes = attributes.serialize();
    } else {
      attributes = this.parseModel(attributes);
    }

    if (!oldModel) {
      let id = attributes[this.id];
      oldModel = this.findInCacheById(id);
    }

    let model = oldModel && loIsFunction(oldModel.attr) ?
      oldModel.attr(attributes) :
      new this(attributes);

    // Sometimes we are updating model partially and asynchronous
    // for example when we load relationships.
    // In this case we have to update backup to solve isDirty issues.
    let backup = model._backupStore();
    if (backup) {
      loAssign(backup, attributes);
    }

    // This is a temporary solution
    if (attributes.documents) {
      model.attr('documents', attributes.documents, true);
    }

    return model;
  },
}, {
  define: {
    title: {
      value: '',
      validate: {
        required: true,
      },
    },
    audit: {
      value: null,
      validate: {
        required: true,
      },
    },
    issue_tracker: {
      value: {},
      validate: {
        validateIssueTrackerEnabled() {
          return 'Assessment';
        },
        validateIssueTrackerComponentId: true,
        validateIssueTrackerTitle: true,
        validateIssueTrackerIssueId() {
          return this.constructor.unchangeableIssueTrackerIdStatuses;
        },
      },
    },
  },
  init: function () {
    if (this._super) {
      this._super(...arguments);
    }
    this.bind('refreshInstance', this.refresh.bind(this));
    this.bind(REFRESH_MAPPING.type, () => {
      if (this.constructor.doneStatuses.includes(this.status)) {
        this.refresh();
      }
    });
  },
  beforeCreate: function () {
    if (!this.audit) {
      throw new Error('Cannot save assessment, audit not set.');
    } else if (!this.audit.context) {
      throw new Error(
        'Cannot save assessment, audit context not set.');
    }
    this.attr('context', this.attr('audit.context'));
    this.attr('design', '');
    this.attr('operationally', '');
  },
  _transformBackupProperty: function (badProperties) {
    let backupInstance = this._backupStore();
    if (!backupInstance) {
      return;
    }
    badProperties.forEach(function (property) {
      if (!this[property] && !backupInstance[property] &&
      (this[property] !== backupInstance[property])) {
        backupInstance[property] = this[property];
      }
    }.bind(this));

    if (this.validate_assessor !== undefined) {
      backupInstance.validate_assessor = this.validate_assessor;
    }
    if (this.validate_creator !== undefined) {
      backupInstance.validate_creator = this.validate_creator;
    }
  },
  isDirty: function (checkAssociations) {
    this._transformBackupProperty(['design', 'operationally']);
    return this._super(checkAssociations);
  },
  formPreload: function (newObjectForm, params, pageInstance) {
    let currentUser = GGRC.current_user;

    if (!this.audit || !this.audit.id || !this.audit.type) {
      if (pageInstance.type === 'Audit') {
        this.attr('audit', pageInstance);
      }
    }

    if (!newObjectForm) {
      return;
    }

    // Make sure before create is called before save
    this.beforeCreate();

    if (this.audit) {
      const auditors = this.audit.findRoles('Auditors');
      const auditCaptains = this.audit.findRoles('Audit Captains');

      markForAddition(this, currentUser, 'Creators');
      if (!auditCaptains.length) {
        markForAddition(this, currentUser, 'Assignees');
      }
      auditCaptains.forEach((item) => {
        markForAddition(this, item.person, 'Assignees');
      });
      auditors.forEach((item) => {
        markForAddition(this, item.person, 'Verifiers');
      });
    }

    function markForAddition(instance, user, type) {
      let rolesNames = type.split(',');
      let acl = instance.attr('access_control_list');

      rolesNames.forEach((roleName) => {
        let role = getRole('Assessment', roleName);

        if (role) {
          acl.push({
            ac_role_id: role.id,
            person: {
              id: user.id,
            },
            person_id: user.id,
          });
        }
      });
    }
  },
  refresh: function () {
    let href = this.selfLink || this.href;

    if (!href) {
      return $.Deferred().reject();
    }
    if (!this._pending_refresh) {
      this._pending_refresh = {
        dfd: $.Deferred(),
        fn: loThrottle(() => {
          let dfd = this._pending_refresh.dfd;
          ggrcAjax({
            url: href,
            type: 'get',
            dataType: 'json',
          })
            .then((model) => {
              model = this.cleanupAcl(model);
              delete this._pending_refresh;
              if (model) {
                model = this.constructor.model(model, this);
                this.afterRefresh && this.afterRefresh();
                model.backup();
                return model;
              }
            })
            .done((...args) => {
              dfd.resolve(...args);
              this.dispatch(REFRESHED);
            })
            .fail((...args) => {
              dfd.reject(...args);
            });
        }, 300, {trailing: false}),
      };
    }

    this._pending_refresh.fn();
    return this._pending_refresh.dfd;
  },
  getRelatedObjects() {
    const stopFn = tracker.start(
      this.type,
      tracker.USER_JOURNEY_KEYS.API,
      tracker.USER_ACTIONS.ASSESSMENT.RELATED_OBJECTS);

    return ggrcGet(`/api/assessments/${this.attr('id')}/related_objects`)
      .then((response) => {
        let auditTitle = response.Audit.title;

        stopFn();

        if (this.attr('audit')) {
          this.attr('audit.title', auditTitle);
        }

        return response;
      }, stopFn.bind(null, true));
  },
});
