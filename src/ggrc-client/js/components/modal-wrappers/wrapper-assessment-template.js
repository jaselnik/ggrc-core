/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canMap from 'can-map';
import canComponent from 'can-component';
import {
  isMultiLevelFlow,
  getAssessmentFlows,
} from '../../plugins/utils/verification-flow-utils';

const peopleTitlesList = [
  'Auditors', 'Principal Assignees', 'Secondary Assignees',
  'Primary Contacts', 'Secondary Contacts', 'Control Operators',
  'Control Owners', 'Risk Owners',
];
const VERIFICATION_LEVELS = [
  '2', '3', '4', '5', '6', '7', '8', '9', '10',
];

const DEFAULT_REVIEW_LEVEL = '2';

const PEOPLE_VALUES_OPTIONS = Object.freeze({
  Control: [
    {value: 'Admin', title: 'Object Admins'},
    {value: 'Audit Lead', title: 'Audit Captain'},
    {value: 'Auditors', title: 'Auditors'},
    {value: 'Principal Assignees', title: 'Principal Assignees'},
    {value: 'Secondary Assignees', title: 'Secondary Assignees'},
    {value: 'Control Operators', title: 'Control Operators'},
    {value: 'Control Owners', title: 'Control Owners'},
    {value: 'Other Contacts', title: 'Other Contacts'},
    {value: 'other', title: 'Others...'},
  ],
  Risk: [
    {value: 'Admin', title: 'Object Admins'},
    {value: 'Audit Lead', title: 'Audit Captain'},
    {value: 'Auditors', title: 'Auditors'},
    {value: 'Principal Assignees', title: 'Principal Assignees'},
    {value: 'Secondary Assignees', title: 'Secondary Assignees'},
    {value: 'Risk Owners', title: 'Risk Owners'},
    {value: 'Other Contacts', title: 'Other Contacts'},
    {value: 'other', title: 'Others...'},
  ],
  defaults: [
    {value: 'Admin', title: 'Object Admins'},
    {value: 'Audit Lead', title: 'Audit Captain'},
    {value: 'Auditors', title: 'Auditors'},
    {value: 'Principal Assignees', title: 'Principal Assignees'},
    {value: 'Secondary Assignees', title: 'Secondary Assignees'},
    {value: 'Primary Contacts', title: 'Primary Contacts'},
    {value: 'Secondary Contacts', title: 'Secondary Contacts'},
    {value: 'other', title: 'Others...'},
  ],
});

export default canComponent.extend({
  tag: 'wrapper-assessment-template',
  leakScope: true,
  viewModel: canMap.extend({
    instance: {},
    assessmentWorkflows: [],
    verificationLevels: [],
    define: {
      showCaptainAlert: {
        type: Boolean,
        value: false,
        get() {
          return peopleTitlesList
            .includes(this.attr('instance.default_people.assignees'));
        },
      },
      peopleValues: {
        get() {
          let options = PEOPLE_VALUES_OPTIONS[
            this.attr('instance.template_object_type')
          ];
          return options ? options : PEOPLE_VALUES_OPTIONS['defaults'];
        },
      },
      defaultAssigneeLabel: {
        type: String,
        get() {
          let labels = this.attr('instance.DEFAULT_PEOPLE_LABELS');
          let assignee = this.attr('instance.default_people.assignees');
          return labels[assignee];
        },
      },
      defaultVerifierLabel: {
        type: String,
        get() {
          let labels = this.attr('instance.DEFAULT_PEOPLE_LABELS');
          let verifiers = this.attr('instance.default_people.verifiers');
          return labels[verifiers];
        },
      },
      isMultiLevelVerification: {
        get() {
          const isMultiLevelVerification =
            isMultiLevelFlow(this.attr('instance'));

          if (!isMultiLevelVerification) {
            this.attr('instance.review_levels_count', null);
          } else {
            if (!this.attr('instance.review_levels_count')) {
              this.attr('instance.review_levels_count', DEFAULT_REVIEW_LEVEL);
            }
          }

          return isMultiLevelVerification;
        },
      },
    },
  }),
  events: {
    inserted() {
      this.viewModel.attr('assessmentWorkflows', getAssessmentFlows());
      this.viewModel.attr('verificationLevels', VERIFICATION_LEVELS);
    },
  },
});
