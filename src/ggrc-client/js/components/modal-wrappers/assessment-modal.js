/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import '../assessment-template-attributes/assessment-template-attributes';
import '../assessment-templates/assessment-templates-dropdown/assessment-templates-dropdown';
import '../spinner-component/spinner-component';
import canComponent from 'can-component';
import MappingOperationsVM from '../view-models/mapping-operations-vm';
import {
  toObject,
  extendSnapshot,
} from '../../plugins/utils/snapshot-utils';
import {loadObjectsByStubs} from '../../plugins/utils/query-api-utils';
import {notifier} from '../../plugins/utils/notifiers-utils';
import {getAjaxErrorInfo} from '../../plugins/utils/errors-utils';

export default canComponent.extend({
  tag: 'assessment-modal',
  leakScope: true,
  viewModel: MappingOperationsVM.extend({
    define: {
      /**
       * Indicates the situation, when the user chooses some assessment
       * template and in the same time it did not have some another preselected
       * template before choosing.
       */
      isInitialTemplateLoading: {
        get() {
          return (
            true &&
            this.attr('isAttributesLoading') &&
            !this.attr('assessmentTemplate')
          );
        },
      },
    },
    instance: null,
    isNewInstance: false,
    mappingsList: [],
    assessmentTemplate: null,
    isAttributesLoading: false,
    fields: ['id', 'type', 'child_type', 'revision', 'title', 'name', 'email'],
    loadData() {
      return this.attr('instance').getRelatedObjects()
        .then((data) => {
          let snapshots = data.Snapshot.map((snapshot) => {
            let snapshotObject = toObject(snapshot);
            return extendSnapshot(snapshot, snapshotObject);
          });

          this.attr('mappingsList').replace(snapshots);
        });
    },
    async setAssessmentTemplate(templateId) {
      const instance = this.attr('instance');
      const templateStub = {
        id: templateId,
        type: 'AssessmentTemplate',
      };

      this.attr('isAttributesLoading', true);
      try {
        const [loadedTemplate] = await loadObjectsByStubs(
          [templateStub],
          [
            'custom_attribute_definitions',
            'verification_workflow',
          ]
        );

        instance.attr('template', templateStub);
        this.attr('assessmentTemplate', loadedTemplate);
      } catch (xhr) {
        notifier('error', getAjaxErrorInfo(xhr).details);
      } finally {
        this.attr('isAttributesLoading', false);
      }
    },
    onAssessmentTemplateChanged({template}) {
      if (!template) {
        this.attr('assessmentTemplate', null);
        this.attr('instance.template', null);
      } else {
        this.setAssessmentTemplate(template.id);
      }
    },
  }),
  events: {
    inserted() {
      let vm = this.viewModel;
      if (!vm.attr('isNewInstance')) {
        vm.loadData();
      }
    },
  },
});
