/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canControl from 'can-control';
import '../../components/assessment-template-clone/assessment-template-clone';
import '../../components/assessment/assessments-bulk-complete/assessments-bulk-complete';
import '../../components/object-bulk-update/object-bulk-update';
import '../../components/object-mapper/object-mapper';
import '../../components/object-generator/object-generator';
import '../../components/object-search/object-search';
import {
  isAuditScopeModel,
} from '../../plugins/utils/snapshot-utils';
import asmtTemplateCloneTemplate from './assessment-template-clone-modal.stache';
import objectGeneratorTemplate from './object-generator-modal.stache';
import objectMapperTemplate from './object-mapper-modal.stache';
import objectSearchTemplate from './object-search-modal.stache';
import objectBulkUpdateTemplate from './object-bulk-update-modal.stache';
import asmtBulkCompleteTemplate from './assessments-bulk-complete-modal.stache';
import {notifier} from '../../plugins/utils/notifiers-utils';
import * as businessModels from '../../models/business-models';
import {changeUrl} from '../../router';
import {getMegaObjectRelation} from '../../plugins/utils/mega-object-utils';

const DATA_CORRUPTION_MESSAGE = 'Some Data is corrupted! ' +
            'Missing Scope Object';
const OBJECT_REQUIRED_MESSAGE = 'Required Data for In Scope Object is missing' +
  ' - Original Object is mandatory';

const ObjectMapper = canControl.extend({
  defaults: {
    component: objectMapperTemplate,
  },
  launch: function ($trigger, options) {
    let href = $trigger ?
      $trigger.attr('data-href') || $trigger.attr('href') :
      '';
    let modalId = 'ajax-modal-' + (href || '')
      .replace(/[/?=&#%]/g, '-')
      .replace(/^-/, '');
    let $target =
      $('<div id="' + modalId +
      '" class="modal modal-selector object-modal hide"></div>');

    $target.modal_form({}, $trigger);
    this.newInstance($target[0], Object.assign({
      $trigger,
    }, options));

    $target.on('modal:dismiss', function () {
      $(this).remove();
    });

    $target.on('hideModal', function (e) {
      $target.modal_form('silentHide');
    });

    $target.on('showModal', function () {
      $target.modal_form('show');
    });

    return $target;
  },
  openMapper: function (data, disableMapper, btn) {
    let self = this;
    let isSearch = /unified-search/ig.test(data.toggle);

    if (disableMapper) {
      return;
    }

    if (data.join_object_type === undefined || data.join_object_type === null) {
      throw new Error(OBJECT_REQUIRED_MESSAGE);
    }

    if (isAuditScopeModel(data.join_object_type) && !isSearch) {
      openForSnapshots(data);
    } else if (data.mega_object) {
      openForMegaObject(data);
    } else {
      openForCommonObjects(data, isSearch);
    }

    // each object type will be perceived as a snapshot, except types with
    // special config
    function openForSnapshots(data) {
      let config = getBaseConfig();
      let special = [{
        types: ['Issue'],
        // set config like for common objects
        config: getConfigForCommonObjects(data).general,
      }];

      Object.assign(config.general, {useSnapshots: true});
      Object.assign(config.special, special);

      if (data.is_new) {
        Object.assign(config.general, {
          object: data.join_object_type,
          type: data.join_option_type,
          isNew: true,
          relevantTo: [{
            readOnly: true,
            type: data.snapshot_scope_type,
            id: data.snapshot_scope_id,
          }],
        });
        self.launch(btn, Object.assign(config, data));
        return;
      }

      if (data.join_object_id === undefined || data.join_object_id === null) {
        throw new Error(OBJECT_REQUIRED_MESSAGE);
      }

      let model = businessModels[data.join_object_type];
      let auditScopeObject =
        model.findInCacheById(data.join_object_id);
      let audit = auditScopeObject.attr('audit');

      if (!audit.id) {
        notifier('error', DATA_CORRUPTION_MESSAGE);
        setTimeout(function () {
          changeUrl('/dashboard');
        }, 3000);
        return;
      }

      Object.assign(config.general, {
        object: data.join_object_type,
        'join-object-id': data.join_object_id,
        type: data.join_option_type,
        relevantTo: [{
          readOnly: true,
          type: audit.type,
          id: audit.id,
          title: audit.title,
        }],
      });
      self.launch(btn, Object.assign(config, data));
    }

    function openForCommonObjects(data, isSearch) {
      let config = getConfigForCommonObjects(data);

      if (isSearch) {
        ObjectSearch.launch(btn, Object.assign(config, data));
      } else {
        self.launch(btn, Object.assign(config, data));
      }
    }

    function openForMegaObject(data) {
      const config = getConfigForCommonObjects(data);

      const {relation} = getMegaObjectRelation(data.mega_object_widget);

      Object.assign(config.general, {
        isMegaObject: data.mega_object,
        megaRelation: relation,
      });

      self.launch(btn, Object.assign(config, data));
    }

    function getBaseConfig() {
      return {
        general: {
          useSnapshots: false,
          object: '',
          type: '',
          'join-object-id': null,
          // if set then each mapped object will be relevant to
          // relevantTo object (for example, snapshots relevant to Audit (at 08/2017))
          relevantTo: null,
        },
        special: [],
      };
    }

    function getConfigForCommonObjects(data) {
      let base = getBaseConfig();

      Object.assign(base.general, {
        object: data.join_object_type,
        type: data.join_option_type,
        'join-object-id': data.join_object_id,
      });

      return base;
    }
  },
}, {
  init: function () {
    let frag = canStache(this.options.component)(this.options);
    this.element.html(frag);
  },
});

const ObjectSearch = ObjectMapper.extend({
  defaults: {
    component: objectSearchTemplate,
  },
}, {});

const ObjectGenerator = ObjectMapper.extend({
  defaults: {
    component: objectGeneratorTemplate,
  },
}, {});

const ObjectBulkUpdate = ObjectMapper.extend({
  defaults: {
    component: objectBulkUpdateTemplate,
  },
}, {});

const AssessmentTemplateClone = ObjectMapper.extend({
  defaults: {
    component: asmtTemplateCloneTemplate,
  },
}, {});

const AssessmentsBulkComplete = ObjectMapper.extend({
  defaults: {
    component: asmtBulkCompleteTemplate,
  },
}, {});

export {
  ObjectMapper,
  ObjectGenerator,
  ObjectSearch,
  ObjectBulkUpdate,
  AssessmentTemplateClone,
  AssessmentsBulkComplete,
};
