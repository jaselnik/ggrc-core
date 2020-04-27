/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import loKeys from 'lodash/keys';
import loDifference from 'lodash/difference';
import canMap from 'can-map';
import * as Mappings from '../mappings';
import * as Permission from '../../../permission';

describe('Mappings', () => {
  let allTypes = [];
  let notMappableModels = [];
  const modules = {
    core: {
      models: [
        'AccessGroup',
        'AccountBalance',
        'Assessment',
        'AssessmentTemplate',
        'Audit',
        'Contract',
        'Control',
        'DataAsset',
        'Document',
        'Evidence',
        'Facility',
        'Issue',
        'KeyReport',
        'Market',
        'Metric',
        'Objective',
        'OrgGroup',
        'Person',
        'Policy',
        'Process',
        'Product',
        'ProductGroup',
        'Program',
        'Project',
        'Regulation',
        'Requirement',
        'Standard',
        'System',
        'Vendor',
        'Risk',
        'TechnologyEnvironment',
        'Threat',
      ],
      notMappable: ['Assessment', 'AssessmentTemplate', 'Evidence', 'Person'],
    },
    workflows: {
      models: [
        'Workflow',
        'TaskGroup',
        'TaskGroupTask',
        'CycleTaskGroupObjectTask',
        'CycleTaskGroup',
      ],
      notMappable: [
        'Workflow',
        'TaskGroup',
        'TaskGroupTask',
        'CycleTaskGroupObjectTask',
        'CycleTaskGroup',
      ],
    },
  };

  const externalModels = {
    scope: [
      'AccessGroup',
      'AccountBalance',
      'DataAsset',
      'Facility',
      'KeyReport',
      'Market',
      'Metric',
      'OrgGroup',
      'Process',
      'Product',
      'ProductGroup',
      'Project',
      'System',
      'TechnologyEnvironment',
      'Vendor',
    ],
    directives: [
      'Regulation',
      'Standard',
    ],
    business: [
      'Control',
      'Risk',
      'Contract',
      'Objective',
      'Policy',
      'Requirement',
      'Threat',
    ],
  };

  Object.keys(modules).forEach((module) => {
    allTypes = allTypes.concat(modules[module].models);
    notMappableModels = notMappableModels.concat(modules[module].notMappable);
  });

  const filtered = loDifference(allTypes, notMappableModels);

  const basicObjectsUnmappingRule = loDifference(filtered, ['Audit'],
    externalModels.scope, externalModels.directives, externalModels.business);

  const scopingObjectsUnmappingRules = {}; // eslint-disable-line id-length
  externalModels.scope.forEach((model) => {
    scopingObjectsUnmappingRules[model] = basicObjectsUnmappingRule;
  });

  const directivesObjectsUnmappingRules = { // eslint-disable-line id-length
    Standard: ['Regulation', ...basicObjectsUnmappingRule],
    Regulation: ['Standard', ...basicObjectsUnmappingRule],
  };

  const businessObjectsUnmappingRules = { // eslint-disable-line id-length
    Control: ['Control', ...basicObjectsUnmappingRule],
    Risk: ['Risk', ...basicObjectsUnmappingRule],
    Contract: basicObjectsUnmappingRule,
    Objective: basicObjectsUnmappingRule,
    Policy: basicObjectsUnmappingRule,
    Requirement: basicObjectsUnmappingRule,
    Threat: basicObjectsUnmappingRule,
  };

  const unmappingRules = Object.freeze({
    ...scopingObjectsUnmappingRules,
    ...directivesObjectsUnmappingRules,
    ...businessObjectsUnmappingRules,
    Assessment: loDifference(filtered, ['Audit', 'Person', 'Program', 'Project',
      'Workflow', 'Assessment', 'Document']).concat(['Evidence']),
    AssessmentTemplate: [],
    Audit: ['Issue'],
    CycleTaskGroupObjectTask: loDifference(filtered, ['Person',
      'Workflow', 'Assessment', 'Document']),
    Evidence: [],
    Document: loDifference(filtered,
      ['Audit', 'Assessment', 'Document', 'Person', 'Workflow']),
    Issue: loDifference(allTypes, ['Person', 'AssessmentTemplate', 'Evidence'],
      modules.workflows.notMappable),
    Person: [],
    Program: loDifference(allTypes, ['Audit'], modules.core.notMappable,
      modules.workflows.notMappable),
    TaskGroup: loDifference(filtered, ['Audit', 'Person',
      'Workflow', 'Assessment', 'Document']),
  });

  describe('allowedToUnmap() method', () => {
    beforeEach(() => {
      spyOn(Permission, 'isAllowedFor').and.returnValue(true);
    });

    it('checks that types are mappable', () => {
      let result = Mappings.allowedToUnmap('SourceType', 'TargetType');

      expect(result).toBeFalsy();
      expect(Permission.isAllowedFor).not.toHaveBeenCalled();
    });

    it('checks permissions to update source', () => {
      let result = Mappings.allowedToUnmap('DataAsset', 'Program');

      expect(result).toBeTruthy();
      expect(Permission.isAllowedFor)
        .toHaveBeenCalledWith('update', 'DataAsset');
      expect(Permission.isAllowedFor.calls.count()).toEqual(1);
    });

    it('checks permissions to update target', () => {
      let source = new canMap({type: 'DataAsset'});
      let target = new canMap({type: 'Program'});
      let result = Mappings.allowedToUnmap(source, target);

      expect(result).toBeTruthy();
      expect(Permission.isAllowedFor.calls.count()).toEqual(2);
      expect(Permission.isAllowedFor.calls.argsFor(0))
        .toEqual(['update', source]);
      expect(Permission.isAllowedFor.calls.argsFor(1))
        .toEqual(['update', target]);
    });
  });

  describe('getAllowedToUnmapModels() method', () => {
    let modelsForTests = loDifference(allTypes, [
      'TaskGroupTask',
      'CycleTaskGroup',
      'Workflow',
    ]);

    modelsForTests.forEach((type) => {
      it('returns mappable types for ' + type, () => {
        let expectedModels = unmappingRules[type];
        let result = Mappings.getAllowedToUnmapModels(type);
        let resultModels = loKeys(result);

        expect(expectedModels.sort()).toEqual(resultModels.sort());
      });
    });
  });
});
