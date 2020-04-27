/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loDifference from 'lodash/difference';
import {
  businessObjects,
  coreObjects,
  scopingObjects,
  snapshotableObjects,
  externalDirectiveObjects,
  externalBusinessObjects,
} from '../../plugins/models-types-collections';
import {getRoleableModels} from '../../plugins/utils/models-utils';

/*
  To configure a new mapping, use the following format :
  { <source object type> : {
      create: [ <object name>, ...],
      map : [ <object name>, ...],
      externalMap: [ <object name>, ...],
      unmap : [ <object name>, ...],
      indirectMappings: [ <object name>, ...],
    }
  }

  <create> - models that cannot be mapped but can be created in scope of source
    object
  <map> - models that can be mapped to source object directly
    using object mapper
  <externalMap> - models that can be mapped only through external system
    not locally
  <unmap> - models that can be unmapped from source
  <externalUnmap> - models that can be unmapped only through external system
    not locally
  <indirectMappings> - models which cannot be directly mapped to object
    through Relationship but linked by another way. Currently used for Mapping
    Filter in Object mapper and Global Search
*/

const roleableObjects = getRoleableModels()
  .map((model) => model.model_singular);

const createRule = {
  create: ['CycleTaskGroupObjectTask'],
};

const externalObjectConfig = {
  ...createRule,
  map: loDifference(businessObjects, [
    'Assessment',
    ...externalBusinessObjects,
    ...externalDirectiveObjects,
    ...scopingObjects,
  ]),
  unmap: loDifference(businessObjects, [
    'Assessment',
    'Audit',
    ...externalBusinessObjects,
    ...externalDirectiveObjects,
    ...scopingObjects,
  ]),
  externalMap: [
    ...externalBusinessObjects,
    ...externalDirectiveObjects,
    ...scopingObjects,
  ],
  externalUnmap: [
    ...externalBusinessObjects,
    ...externalDirectiveObjects,
    ...scopingObjects,
  ],
  indirectMappings: ['Assessment', 'Person', 'TaskGroup', 'Workflow'],
};

export default {
  Person: {
    indirectMappings: ['CycleTaskGroupObjectTask', 'TaskGroupTask', 'Workflow',
      ...roleableObjects],
  },

  Program: {
    create: ['Audit', 'CycleTaskGroupObjectTask'],
    map: [...coreObjects, 'Program', 'Document'],
    unmap: [...coreObjects, 'Program', 'Document'],
    indirectMappings: ['Person', 'TaskGroup', 'Workflow'],
  },

  Document: {
    map: [...coreObjects, 'Program'],
    unmap: [...coreObjects, 'Program'],
    indirectMappings: ['Person'],
  },

  // Core objects
  Issue: {
    ...createRule,
    map: [...coreObjects, 'Document', 'Program'],
    // mapping audit and assessment to issue is not allowed,
    // but unmapping possible
    unmap: [...coreObjects, 'Assessment', 'Audit', 'Document', 'Program'],
    indirectMappings: ['Assessment', 'Audit', 'Person', 'TaskGroup',
      'Workflow'],
  },
  Control: {
    ...createRule,
    map: ['Control', ...externalObjectConfig.map],
    unmap: ['Control', ...externalObjectConfig.unmap],
    externalMap: loDifference(externalObjectConfig.externalMap, ['Control']),
    externalUnmap: loDifference(externalObjectConfig.externalUnmap,
      ['Control']),
    indirectMappings: externalObjectConfig.indirectMappings,
  },
  Risk: {
    ...createRule,
    map: ['Risk', ...externalObjectConfig.map],
    unmap: ['Risk', ...externalObjectConfig.unmap],
    externalMap: loDifference(externalObjectConfig.externalMap, ['Risk']),
    externalUnmap: loDifference(externalObjectConfig.externalUnmap, ['Risk']),
    indirectMappings: externalObjectConfig.indirectMappings,
  },
  Contract: {
    ...createRule,
    map: externalObjectConfig.map,
    unmap: externalObjectConfig.unmap,
    externalMap: loDifference(externalObjectConfig.externalMap, ['Contract']),
    externalUnmap: loDifference(externalObjectConfig.externalUnmap,
      ['Contract']),
    indirectMappings: externalObjectConfig.indirectMappings,
  },
  Policy: {
    ...createRule,
    map: externalObjectConfig.map,
    unmap: externalObjectConfig.unmap,
    externalMap: loDifference(externalObjectConfig.externalMap, ['Policy']),
    externalUnmap: loDifference(externalObjectConfig.externalUnmap, ['Policy']),
    indirectMappings: externalObjectConfig.indirectMappings,
  },
  Objective: {
    ...externalObjectConfig,
  },
  Requirement: {
    ...externalObjectConfig,
  },
  Threat: {
    ...externalObjectConfig,
  },

  // Directives
  Regulation: {
    ...createRule,
    map: ['Standard', ...externalObjectConfig.map],
    unmap: ['Standard', ...externalObjectConfig.unmap],
    externalMap: [...scopingObjects, ...externalBusinessObjects],
    externalUnmap: [...scopingObjects, ...externalBusinessObjects],
    indirectMappings: externalObjectConfig.indirectMappings,
  },
  Standard: {
    ...createRule,
    map: ['Regulation', ...externalObjectConfig.map],
    unmap: ['Regulation', ...externalObjectConfig.unmap],
    externalMap: [...scopingObjects, ...externalBusinessObjects],
    externalUnmap: [...scopingObjects, ...externalBusinessObjects],
    indirectMappings: externalObjectConfig.indirectMappings,
  },

  // Scoping objects
  AccessGroup: {
    ...externalObjectConfig,
  },
  AccountBalance: {
    ...externalObjectConfig,
  },
  DataAsset: {
    ...externalObjectConfig,
  },
  Facility: {
    ...externalObjectConfig,
  },
  KeyReport: {
    ...externalObjectConfig,
  },
  Market: {
    ...externalObjectConfig,
  },
  Metric: {
    ...externalObjectConfig,
  },
  OrgGroup: {
    ...externalObjectConfig,
  },
  Process: {
    ...externalObjectConfig,
  },
  Product: {
    ...externalObjectConfig,
  },
  ProductGroup: {
    ...externalObjectConfig,
  },
  Project: {
    ...externalObjectConfig,
  },
  System: {
    ...externalObjectConfig,
  },
  TechnologyEnvironment: {
    ...externalObjectConfig,
  },
  Vendor: {
    ...externalObjectConfig,
  },

  // Audit
  Audit: {
    create: ['Assessment', 'AssessmentTemplate', 'CycleTaskGroupObjectTask'],
    map: [...snapshotableObjects, 'Issue'],
    unmap: ['Issue'],
    indirectMappings: ['Evidence', 'Person', 'Program'],
  },
  Assessment: {
    map: [...snapshotableObjects, 'Issue'],
    unmap: [...snapshotableObjects, 'Issue', 'Evidence'],
    indirectMappings: ['Audit', 'Evidence', 'Person'],
  },
  Evidence: {
    indirectMappings: ['Assessment', 'Audit', 'Person'],
  },
  AssessmentTemplate: {
    indirectMappings: ['Audit'],
  },

  // Workflow
  TaskGroup: {
    map: [...coreObjects, 'Program'],
    unmap: [...coreObjects, 'Program'],
    indirectMappings: ['Workflow'],
  },
  TaskGroupTask: {
    indirectMappings: ['Person', 'Workflow'],
  },
  Workflow: {
    indirectMappings: ['Person', 'TaskGroup', 'TaskGroupTask'],
  },
  CycleTaskGroupObjectTask: {
    map: [...coreObjects, 'Audit', 'Program'],
    unmap: [...coreObjects, 'Audit', 'Program'],
    indirectMappings: ['Person', 'Workflow'],
  },

  // Other
  MultitypeSearch: {
    map: [
      'AccessGroup', 'AccountBalance', 'Assessment', 'AssessmentTemplate',
      'Audit', 'Contract', 'Control', 'CycleTaskGroupObjectTask', 'DataAsset',
      'Document', 'Evidence', 'Facility', 'Issue', 'KeyReport', 'Market',
      'Metric', 'Objective', 'OrgGroup', 'Person', 'Process', 'Product',
      'ProductGroup', 'Project', 'Policy', 'Program', 'Regulation',
      'Requirement', 'Risk', 'Standard', 'System', 'TaskGroup',
      'TaskGroupTask', 'TechnologyEnvironment', 'Threat',
      'Vendor', 'Workflow',
    ],
  },
};

