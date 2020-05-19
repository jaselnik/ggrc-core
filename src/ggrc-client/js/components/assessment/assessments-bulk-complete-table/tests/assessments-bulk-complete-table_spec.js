/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../assessments-bulk-complete-table';
import {getComponentVM} from '../../../../../js_specs/spec-helpers';
import * as CaUtils from '../../../../plugins/utils/ca-utils';

describe('assessments-bulk-complete-table component', () => {
  let viewModel;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
  });

  describe('buildHeadersData() method', () => {
    it('returns formed array for headers data', () => {
      viewModel.attributesList = [{
        title: 'Title1',
        mandatory: true,
        default_value: 1,
      }, {
        title: 'Title2',
        mandatory: false,
        default_value: '',
      }];

      expect(viewModel.buildHeadersData().serialize()).toEqual([{
        title: 'Title1',
        mandatory: true,
      }, {
        title: 'Title2',
        mandatory: false,
      }]);
    });
  });

  describe('buildRowsData() method', () => {
    it('returns formed array for rows data', () => {
      viewModel.assessmentsList = [{
        id: 1,
        title: 'Asmt1',
        status: 'In Progress',
        assessment_type: 'Control',
        urls_count: 1,
        files_count: 0,
      }, {
        id: 2,
        title: 'Asmt2',
        status: 'Not Started',
        assessment_type: 'Vendor',
        urls_count: 0,
        files_count: 2,
      }];

      viewModel.attributesList = [{
        attribute_type: 'Text',
        title: 'LCA Text',
        mandatory: false,
        default_value: '',
        values: {
          '1': {
            attribute_person_id: null,
            attribute_definition_id: 4483,
            value: 'Some text',
            multi_choice_options: '',
            multi_choice_mandatory: null,
            definition_id: 1,
            preconditions_failed: null,
          },
        },
      }];

      spyOn(CaUtils, 'getCustomAttributeType').and.returnValue('input');

      spyOn(viewModel, 'prepareAttributeValue')
        .withArgs('input', '')
        .and.returnValue('')
        .withArgs('input', 'Some text', null)
        .and.returnValue('Some text');

      spyOn(viewModel, 'prepareMultiChoiceOptions')
        .withArgs('', null)
        .and.returnValue({
          optionsList: [],
          optionsConfig: new Map(),
        });

      expect(viewModel.buildRowsData()).toEqual([{
        asmtId: 1,
        asmtTitle: 'Asmt1',
        asmtStatus: 'In Progress',
        asmtType: 'Control',
        urlsCount: 1,
        filesCount: 0,
        isReadyToComplete: false,
        attributes: [{
          id: 4483,
          type: 'input',
          value: 'Some text',
          defaultValue: '',
          isApplicable: true,
          title: 'LCA Text',
          mandatory: false,
          multiChoiceOptions: {
            values: [],
            config: new Map(),
          },
          attachments: {
            files: [],
            urls: [],
            comment: null,
          },
          modified: false,
          validation: {
            mandatory: false,
            valid: true,
            requiresAttachment: false,
            hasMissingInfo: false,
            hasUnsavedAttachments: false,
          },
          errorsMap: {
            attachment: false,
            url: false,
            comment: false,
          },
        }],
      }, {
        asmtId: 2,
        asmtTitle: 'Asmt2',
        asmtStatus: 'Not Started',
        asmtType: 'Vendor',
        urlsCount: 0,
        filesCount: 2,
        isReadyToComplete: false,
        attributes: [{
          id: null,
          type: 'input',
          value: null,
          defaultValue: '',
          isApplicable: false,
          title: 'LCA Text',
          mandatory: false,
          multiChoiceOptions: {
            values: [],
            config: new Map(),
          },
          attachments: {
            files: [],
            urls: [],
            comment: null,
          },
          modified: false,
          validation: {
            mandatory: false,
            valid: true,
            requiresAttachment: false,
            hasMissingInfo: false,
            hasUnsavedAttachments: false,
          },
          errorsMap: {
            attachment: false,
            url: false,
            comment: false,
          },
        }],
      }]);
    });
  });

  describe('prepareAttributeValue() method', () => {
    describe('if type is "checkbox"', () => {
      it('should return "true"', () => {
        expect(viewModel.prepareAttributeValue('checkbox', '1')).toBe(true);
      });

      it('should return "false"', () => {
        expect(viewModel.prepareAttributeValue('checkbox', '0')).toBe(false);
      });
    });

    describe('if type is "date"', () => {
      it('should return value', () => {
        expect(viewModel.prepareAttributeValue('date', '2020/04/15'))
          .toBe('2020/04/15');
      });

      it('should return "null"', () => {
        expect(viewModel.prepareAttributeValue('date', '')).toBeNull();
      });
    });

    describe('if type is "dropdown"', () => {
      it('should return value', () => {
        expect(viewModel.prepareAttributeValue('dropdown', '1,2,3'))
          .toBe('1,2,3');
      });

      it('should return ""', () => {
        expect(viewModel.prepareAttributeValue('dropdown', '')).toBe('');
      });
    });

    describe('if type is "multiselect"', () => {
      it('should return value', () => {
        expect(viewModel.prepareAttributeValue('multiselect', '1,2,3'))
          .toBe('1,2,3');
      });

      it('should return ""', () => {
        expect(viewModel.prepareAttributeValue('multiselect', '')).toBe('');
      });
    });

    describe('if type is "person"', () => {
      it('should return formed array with needed data about person', () => {
        expect(viewModel.prepareAttributeValue('person', null, 384))
          .toEqual([{
            id: 384,
            type: 'Person',
            href: '/api/people/384',
            context_id: null,
          }]);
      });

      it('should return "null"', () => {
        expect(viewModel.prepareAttributeValue('person', null, null))
          .toBeNull();
      });
    });

    describe('for default block', () => {
      it('should return value', () => {
        expect(viewModel.prepareAttributeValue('input', 'Some text'))
          .toBe('Some text');
      });
    });
  });

  describe('prepareMultiChoiceOptions() method', () => {
    beforeEach(() => {
      spyOn(viewModel, 'convertToArray')
        .and.returnValues(['1', '2', '3'], ['2', '4', '1']);
    });

    it('calls convertToArray()', () => {
      viewModel.prepareMultiChoiceOptions('1,2,3', '2,4,1');

      expect(viewModel.convertToArray).toHaveBeenCalledTimes(2);
      expect(viewModel.convertToArray.calls.argsFor(0)).toEqual(['1,2,3']);
      expect(viewModel.convertToArray.calls.argsFor(1)).toEqual(['2,4,1']);
    });

    it('returns formed optionsList and optionsConfig', () => {
      expect(viewModel.prepareMultiChoiceOptions('1,2,3', '2,4,1'))
        .toEqual({
          optionsList: ['1', '2', '3'],
          optionsConfig: new Map([['1', 2], ['2', 4], ['3', 1]]),
        });
    });
  });

  describe('convertToArray() method', () => {
    it('returns array of values if parameter is "string" type', () => {
      expect(viewModel.convertToArray('1,2,3')).toEqual(['1', '2', '3']);
    });

    it('returns empty array if parameter is not "string" type', () => {
      expect(viewModel.convertToArray(123)).toEqual([]);
    });
  });

  describe('init() method', () => {
    let rowsData;

    beforeEach(() => {
      viewModel.headersData = [];
      viewModel.rowsData = [];
      spyOn(viewModel, 'buildHeadersData').and.returnValue(['LCA1, LCA2']);
      rowsData = [{
        attributes: [{
          id: 1,
          type: 'input',
        }, {
          id: 2,
          type: 'text',
        }],
      }];
      spyOn(viewModel, 'buildRowsData').and.returnValue(rowsData);
    });

    it('sets result of buildHeadersData() to headersData attribute', () => {
      viewModel.init();

      expect(viewModel.headersData.serialize()).toEqual(['LCA1, LCA2']);
    });

    it('sets result of buildRowsData() to rowsData attribute', () => {
      viewModel.init();

      expect(viewModel.rowsData.serialize()).toEqual(rowsData);
    });
  });
});
