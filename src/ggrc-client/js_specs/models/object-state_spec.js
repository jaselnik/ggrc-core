/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loMap from 'lodash/map';
import Audit from '../../js/models/business-models/audit';
import Assessment from '../../js/models/business-models/assessment';
import Issue from '../../js/models/business-models/issue';
import * as businessModels from '../../js/models/business-models';

describe('Model states test', () => {
  let basicStateObjects = ['AccessGroup', 'AccountBalance', 'Contract',
    'Control', 'DataAsset', 'Facility', 'KeyReport', 'Market',
    'Objective', 'OrgGroup', 'Policy', 'Process', 'Product', 'Program',
    'Project', 'Regulation', 'Risk', 'Requirement', 'Standard', 'System',
    'Threat', 'Vendor'];

  basicStateObjects.forEach((object) => {
    let expectedStatuses = ['Draft', 'Deprecated', 'Active'];
    it('checks if ' + object + ' has expected statuses', () => {
      expect(businessModels[object].statuses).toEqual(
        expectedStatuses, 'for object ' + object);
    });
  });
  it('checks if Audit has expected statuses', () => {
    let expectedStatuses = ['Planned', 'In Progress', 'Manager Review',
      'Ready for External Review', 'Completed', 'Deprecated'];
    expect(Audit.statuses).toEqual(expectedStatuses);
  });
  it('checks if Assessment has correct statuses', () => {
    let expectedStatuses = ['Not Started', 'In Progress', 'In Review',
      'Verified', 'Completed', 'Deprecated', 'Rework Needed'];
    expect(Assessment.statuses).toEqual(expectedStatuses);
  });
  it('checks if Issue has correct statuses', () => {
    let expectedStatuses = ['Draft', 'Deprecated', 'Active', 'Fixed',
      'Fixed and Verified'];
    expect(Issue.statuses).toEqual(expectedStatuses);
  });
});

describe('Model "status" attr test', () => {
  const objectsWithState = ['Assessment', 'AssessmentTemplate', 'Audit',
    'Contract', 'Control', 'Cycle', 'Document', 'Evidence', 'Issue',
    'Objective', 'Policy', 'Program', 'Regulation', 'Risk',
    'Requirement', 'Standard', 'Threat', 'Workflow'];
  const objectsWithLaunchStatus = ['AccessGroup', 'AccountBalance',
    'DataAsset', 'Facility', 'KeyReport', 'Market', 'Metric', 'OrgGroup',
    'Process', 'Product', 'ProductGroup', 'Project', 'System',
    'TechnologyEnvironment', 'Vendor'];

  objectsWithState.forEach((object) => {
    it(`checks if ${object} has State in attr_list`, () => {
      const attrList = businessModels[object].tree_view_options.attr_list;

      expect(loMap(attrList, 'attr_title')).toContain('State');
      expect(loMap(attrList, 'attr_name')).toContain('status');
    });
  });

  objectsWithLaunchStatus.forEach((object) => {
    it(`checks if ${object} has Launch Status in attr_list`, () => {
      const attrList = businessModels[object].tree_view_options.attr_list;

      expect(loMap(attrList, 'attr_title')).toContain('Launch Status');
      expect(loMap(attrList, 'attr_name')).toContain('status');
    });
  });

  it('checks if CycleTaskGroupObjectTask has Task State in attr_list', () => {
    const attrList = businessModels['CycleTaskGroupObjectTask']
      .tree_view_options.attr_list;

    expect(loMap(attrList, 'attr_title')).toContain('Task State');
    expect(loMap(attrList, 'attr_name')).toContain('status');
  });
});

describe('Model review state test', () => {
  const reviewObjects = ['Program', 'Regulation', 'Standard'];
  const externalReviewObjects = ['Control', 'Risk'];
  const objectsWithoutReview = ['AccessGroup', 'AccountBalance', 'Assessment',
    'AssessmentTemplate', 'Audit', 'DataAsset', 'Facility', 'Issue',
    'KeyReport', 'Market', 'Metric', 'OrgGroup', 'Process', 'Product',
    'ProductGroup', 'Project', 'System', 'TechnologyEnvironment', 'Vendor',
    'Contract', 'Objective', 'Policy', 'Requirement', 'Threat'];

  reviewObjects.forEach((object) => {
    it('checks if ' + object + ' has review status in attr_list', () => {
      const attrList = businessModels[object].tree_view_options.attr_list;

      expect(loMap(attrList, 'attr_title'))
        .toContain('Review State', 'for object ' + object);
      expect(loMap(attrList, 'attr_name'))
        .toContain('review_status', 'for object ' + object);
    });
  });

  externalReviewObjects.forEach((object) => {
    it('checks if ' + object + ' has external review status in attr_list',
      () => {
        const attrList = businessModels[object].tree_view_options.attr_list;

        let attr = attrList.
          find((attr) => attr.attr_name === 'external_review_status');

        expect(attr).not.toBeNull();
        expect(attr.attr_title).toBe('Review Status');
        expect(attr.attr_sort_field).toBe('review_status_display_name');
      });
  });

  objectsWithoutReview.forEach((object) => {
    it('checks if ' + object + ' has not review status in attr_list', () => {
      const attrList = businessModels[object].tree_view_options.attr_list;

      expect(loMap(attrList, 'attr_name')).not.toContain('review_status');
    });
  });
});
