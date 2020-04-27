/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loDifference from 'lodash/difference';
/**
 * Business objects collection without Workflow objects and specific Audit
 * objects (AssessmentTemplate and Evidence)
 */
export const businessObjects = [
  'Assessment', 'AccessGroup', 'AccountBalance', 'Audit', 'Contract', 'Control',
  'DataAsset', 'Document', 'Facility', 'Issue', 'KeyReport', 'Market', 'Metric',
  'Objective', 'OrgGroup', 'Policy', 'Process', 'Product', 'ProductGroup',
  'Program', 'Project', 'Regulation', 'Requirement', 'Risk', 'Standard',
  'System', 'TechnologyEnvironment', 'Threat', 'Vendor',
];

/**
 * Business objects without Assessment, Audit, Document and Program
 */
export const coreObjects = loDifference(businessObjects,
  ['Assessment', 'Audit', 'Document', 'Program']);

/**
 * Scoping objects
 */
export const scopingObjects = [
  'AccessGroup', 'AccountBalance', 'DataAsset', 'Facility', 'KeyReport',
  'Market', 'Metric', 'OrgGroup', 'Process', 'Product', 'ProductGroup',
  'Project', 'System', 'TechnologyEnvironment', 'Vendor',
];

/**
 * External Directives
 */
export const externalDirectiveObjects = [
  'Regulation', 'Standard',
];

/**
 * External business objects
 */
export const externalBusinessObjects = ['Control', 'Risk', 'Contract',
  'Objective', 'Policy', 'Requirement', 'Threat'];

/**
 * Snapshotable objects
 */
export const snapshotableObjects = GGRC.config.snapshotable_objects;
