/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loForEach from 'lodash/forEach';
import canMap from 'can-map';
import SummaryWidgetController from '../controllers/summary-widget-controller';
import DashboardWidget from '../controllers/dashboard-widget-controller';
import InfoWidget from '../controllers/info-widget-controller';
import WidgetList from '../modules/widget-list';
import {isDashboardEnabled} from '../plugins/utils/dashboards-utils';
import {getWidgetConfig} from '../plugins/utils/widgets-utils';
import {widgetModules} from '../plugins/utils/widgets-utils';
import {
  getPageInstance,
  getPageModel,
  isAllObjects,
} from '../plugins/utils/current-page-utils';
import * as businessModels from '../models/business-models/index';
import TreeViewConfig from '../apps/base-widgets';

const summaryWidgetViews = Object.freeze({
  audits: '/audits/summary.stache',
});

const infoWidgetViews = Object.freeze({
  programs: '/programs/info.stache',
  audits: '/audits/info.stache',
  people: '/people/info.stache',
  policies: '/policies/info.stache',
  controls: '/controls/info.stache',
  systems: '/systems/info.stache',
  processes: '/processes/info.stache',
  products: '/products/info.stache',
  assessments: '/assessments/info.stache',
  assessment_templates:
    '/assessment_templates/info.stache',
  issues: '/issues/info.stache',
  evidence: '/evidence/info.stache',
  documents: '/documents/info.stache',
  risks: '/risks/info.stache',
  contracts: '/contracts/info.stache',
  objectives: '/objectives/info.stache',
  requirements: '/requirements/info.stache',
  threats: '/threats/info.stache',
});

let CoreExtension = {};

CoreExtension.name = 'core"';
widgetModules.push(CoreExtension);
Object.assign(CoreExtension, {
  init_widgets: function () {
    let baseWidgetsByType = TreeViewConfig.attr('base_widgets_by_type');
    let widgetList = new WidgetList('ggrc_core');
    let objectClass = getPageModel();
    let objectTable = objectClass && objectClass.table_plural;
    let object = getPageInstance();
    let modelNames;
    let possibleModelType;
    let farModels;
    let extraDescriptorOptions;

    // Info and summary widgets display the object information instead of listing
    // connected objects.
    if (summaryWidgetViews[objectTable]) {
      widgetList.addWidget(object.constructor.model_singular, 'summary', {
        content_controller: SummaryWidgetController,
        instance: object,
        widget_view: summaryWidgetViews[objectTable],
      });
    }
    if (isDashboardEnabled(object)) {
      widgetList.addWidget(object.constructor.model_singular, 'dashboard', {
        content_controller: DashboardWidget,
        instance: object,
        widget_view: '/base_objects/dashboard-widget.stache',
      });
    }
    widgetList.addWidget(object.constructor.model_singular, 'info', {
      content_controller: InfoWidget,
      instance: object,
      widget_view: infoWidgetViews[objectTable],
    });
    modelNames = canMap.keys(baseWidgetsByType);
    modelNames.sort();
    possibleModelType = modelNames.slice();
    modelNames.forEach(function (name) {
      let wList;
      let childModelList = [];
      let widgetConfig = getWidgetConfig(name);
      name = widgetConfig.name;
      TreeViewConfig.attr('basic_model_list').push({
        model_name: name,
        display_name: widgetConfig.widgetName,
      });

      // Initialize child_model_list, and child_display_list each model_type
      wList = baseWidgetsByType[name];

      loForEach(wList, function (item) {
        let childConfig;
        if (possibleModelType.indexOf(item) !== -1) {
          childConfig = getWidgetConfig(name);
          childModelList.push({
            model_name: childConfig.name,
            display_name: childConfig.widgetName,
          });
        }
      });
      TreeViewConfig.attr('sub_tree_for').attr(name, {
        model_list: childModelList,
        display_list: businessModels[name]
          .tree_view_options.child_tree_display_list || wList,
      });
    });

    // the assessments_view only needs the Assessments widget
    if (/^\/assessments_view/.test(window.location.pathname)) {
      farModels = ['Assessment'];
    } else {
      farModels = baseWidgetsByType[object.constructor.model_singular];
    }

    // here we are going to define extra descriptor options, meaning that
    //  these will be used as extra options to create widgets on top of

    extraDescriptorOptions = {
      all: (function () {
        let all = {
          Evidence: {
            treeViewDepth: 0,
          },
          AssessmentTemplate: {
            treeViewDepth: 0,
          },
          Workflow: {
            treeViewDepth: 0,
          },
          CycleTaskGroupObjectTask: {
            widget_id: 'task',
            widget_name: () => {
              if (object instanceof businessModels.Person) {
                return 'Tasks';
              }
              return 'Workflow Tasks';
            },
            treeViewDepth: 1,
            content_controller_options: {
              showBulkUpdate: !isAllObjects(),
            },
          },
        };

        let defOrder = TreeViewConfig.attr('defaultOrderTypes');
        Object.keys(defOrder).forEach(function (type) {
          if (!all[type]) {
            all[type] = {};
          }
          all[type].order = defOrder[type];
        });

        return all;
      })(),

      // An Audit has a different set of object that are more relevant to it,
      // thus these objects have a customized priority. On the other hand,
      // the object otherwise prioritized by default (e.g. Regulation) have
      // their priority lowered so that they fit nicely into the alphabetical
      // order among the non-prioritized object types.
      Audit: {
        Assessment: {
          order: 7,
        },
        Issue: {
          order: 8,
        },
        Evidence: {
          order: 9,
        },
      },

      Program: {
        Program_parent: {
          order: 8,
        },
        Program_child: {
          order: 9,
        },
      },
    };

    loForEach(farModels, function (modelName) {
      let widgetConfig = getWidgetConfig(modelName);
      modelName = widgetConfig.name;

      let farModel;
      let descriptor = {};
      let widgetId;

      farModel = businessModels[modelName];
      if (farModel) {
        widgetId = widgetConfig.widgetId;
        descriptor = {
          instance: object,
          far_model: farModel,
        };
      } else {
        widgetId = modelName;
      }

      // Custom overrides
      if (extraDescriptorOptions.all &&
          extraDescriptorOptions.all[modelName]) {
        $.extend(descriptor, extraDescriptorOptions.all[modelName]);
      }

      const customDescriptor =
        extraDescriptorOptions[object.constructor.model_singular] &&
        (extraDescriptorOptions[object.constructor.model_singular][widgetId] ||
          extraDescriptorOptions[object.constructor.model_singular][modelName]);
      if (customDescriptor) {
        $.extend(descriptor, customDescriptor);
      }

      descriptor.widgetType = 'treeview';
      widgetList.addWidget(
        object.constructor.model_singular, widgetId, descriptor);
    });
  },
});
