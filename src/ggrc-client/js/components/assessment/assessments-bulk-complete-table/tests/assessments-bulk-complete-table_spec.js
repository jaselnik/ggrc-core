/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../assessments-bulk-complete-table';
import {getComponentVM} from '../../../../../js_specs/spec-helpers';
import * as CAUtils from '../../../../plugins/utils/ca-utils';

describe('assessments-bulk-complete-table component', () => {
  let viewModel;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
  });

  describe('headersData getter', () => {
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

      expect(viewModel.headersData.serialize()).toEqual([{
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
      }, {
        id: 2,
        title: 'Asmt2',
        status: 'Not Started',
        assessment_type: 'Vendor',
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
          },
        },
      }];

      spyOn(CAUtils, 'getCustomAttributeType').and.returnValue('input');

      spyOn(viewModel, 'prepareAttributeValue')
        .withArgs('input', '')
        .and.returnValue('')
        .withArgs('input', 'Some text')
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
          modified: false,
          validation: {
            mandatory: false,
            valid: true,
            requiresAttachment: false,
            hasMissingInfo: false,
          },
        }],
      }, {
        asmtId: 2,
        asmtTitle: 'Asmt2',
        asmtStatus: 'Not Started',
        asmtType: 'Vendor',
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
          modified: false,
          validation: {
            mandatory: false,
            valid: true,
            requiresAttachment: false,
            hasMissingInfo: false,
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

    describe('if type is not "checkbox" or "date"', () => {
      it('should return value', () => {
        expect(viewModel.prepareAttributeValue('person', 123)).toBe(123);
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
});
