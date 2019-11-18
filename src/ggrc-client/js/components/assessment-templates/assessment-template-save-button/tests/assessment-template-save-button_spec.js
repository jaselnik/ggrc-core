/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import Component from '../assessment-template-save-button';
import {getComponentVM} from '../../../../../js_specs/spec-helpers';

describe('assessment-template-save-button component', () => {
  let viewModel;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
  });

  describe('validateNegativeResponses() method', () => {
    let validateNegativeResponses;

    beforeEach(() => {
      validateNegativeResponses =
        viewModel.validateNegativeResponses.bind(viewModel);
    });

    it('should return NULL when "negativeResponseDefs" is empty', () => {
      expect(validateNegativeResponses([])).toBeNull();
    });

    it('should return NULL when "negativeResponseDefs" definition has ' +
    '1+ positive or 1+ negative answers', () => {
      const negativeResponseDefs = [
        // url / file + negative / negative response
        {title: 'LCA1', multi_choice_mandatory: '4,10,8'}, // 2 negative + 1 positive

        // none / negative response + url / none
        {title: 'LCA2', multi_choice_mandatory: '0,12,0'}, // 1 negative + 2 positive

        // negative response / none / none
        {title: 'LCA3', multi_choice_mandatory: '8,0,0'}, // 1 negative + 2 positive
      ];

      expect(validateNegativeResponses(negativeResponseDefs)).toBeNull();
    });

    it('should return list of definitions where all options are negative',
      () => {
        const negativeResponseDefs = [
          // url + negative / file + negative response / negative response
          {title: 'LCA1', multi_choice_mandatory: '12,10,8'}, // 3 negative

          // none / negative response + url / none
          {title: 'LCA2', multi_choice_mandatory: '0,12,0'}, // 1 negative + 2 positive

          // negative response // negative response // negative response + comment
          {title: 'LCA3', multi_choice_mandatory: '8,8,9'}, // 3 negative
        ];

        expect(validateNegativeResponses(negativeResponseDefs)).toEqual({
          noPositiveAnswers: ['LCA1', 'LCA3'],
          allPositiveAnswers: [],
        });
      }
    );

    it('should return list of definitions where all options are positive',
      () => {
        const negativeResponseDefs = [
          // url / file / comment
          {title: 'LCA1', multi_choice_mandatory: '4,2,1'}, // 3 positive

          // none / none / none
          {title: 'LCA2', multi_choice_mandatory: '0,0,0'}, // 3 positive

          // negative response / negative response / negative response + comment
          {title: 'LCA3', multi_choice_mandatory: '8,8,1'}, // 2 negative + 1 positive
        ];

        expect(validateNegativeResponses(negativeResponseDefs)).toEqual({
          noPositiveAnswers: [],
          allPositiveAnswers: ['LCA1', 'LCA2'],
        });
      }
    );

    it('should return list of definitions where all options are positive or ' +
    'negative', () => {
      const negativeResponseDefs = [
        // url / file / comment
        {title: 'LCA1', multi_choice_mandatory: '4,2,1'}, // 3 positive

        // none / none / none
        {title: 'LCA2', multi_choice_mandatory: '0,0,0'}, // 3 positive

        // negative response / negative response / negative response + comment
        {title: 'LCA3', multi_choice_mandatory: '8,8,1'}, // 2 negative + 1 positive

        // negative response / negative response / negative response
        {title: 'LCA4', multi_choice_mandatory: '8,8,8'}, // 3 negative
      ];

      expect(validateNegativeResponses(negativeResponseDefs)).toEqual({
        noPositiveAnswers: ['LCA4'],
        allPositiveAnswers: ['LCA1', 'LCA2'],
      });
    });
  });

  describe('getNegativeResponseDefinitions() method', () => {
    const instance = {
      custom_attribute_definitions: [
        {
          title: 'LCA1',
          attribute_type: 'Text',
          multi_choice_mandatory: '0,0',
        }, {
          title: 'LCA2',
          attribute_type: 'Rich Text',
          multi_choice_mandatory: '0,0',
        }, {
          title: 'LCA3',
          attribute_type: 'Date',
          multi_choice_mandatory: null,
        }, {
          title: 'LCA4',
          attribute_type: 'Checkbox',
          multi_choice_mandatory: null,
        }, {
          title: 'LCA5',
          attribute_type: 'Multiselect',
          multi_choice_mandatory: null,
        }, {
          title: 'LCA6',
          attribute_type: 'Dropdown',
          multi_choice_mandatory: '0,1,2,4,8',
        }, {
          title: 'LCA7',
          attribute_type: 'Map:Person',
          multi_choice_mandatory: null,
        },
      ],
    };

    it('should return definitions only for ' +
    '"Dropdown", "Text" and "Rich Text" types', () => {
      viewModel.attr('instance', instance);

      const definitions = viewModel.getNegativeResponseDefinitions();
      expect(definitions).toEqual([
        {
          title: 'LCA1',
          attribute_type: 'Text',
          multi_choice_mandatory: '0,0',
        }, {
          title: 'LCA2',
          attribute_type: 'Rich Text',
          multi_choice_mandatory: '0,0',
        }, {
          title: 'LCA6',
          attribute_type: 'Dropdown',
          multi_choice_mandatory: '0,1,2,4,8',
        },
      ]);
    });
  });

  describe('save() method', () => {
    const saveButtonElement = {};
    let save;
    let eventSpy;

    beforeEach(() => {
      save = viewModel.save.bind(viewModel);
    });

    beforeEach(() => {
      spyOn(viewModel, 'saveInstance');
      spyOn(viewModel, 'getNegativeResponseDefinitions');
      spyOn(viewModel, 'showConfirm');

      eventSpy = {
        stopPropagation: jasmine.createSpy(),
      };
    });

    it('should call "showConfirm" function when definitions have ' +
    'all negative or positive responses', () => {
      const instance = {verification_workflow: 'SOX302'};
      viewModel.attr('instance', instance);

      spyOn(viewModel, 'validateNegativeResponses').and.returnValue({
        noPositiveAnswers: ['LCA1'],
        allPositiveAnswers: ['LCA2', 'LCA3'],
      });

      save(saveButtonElement, eventSpy);
      expect(viewModel.showConfirm).toHaveBeenCalled();
      expect(eventSpy.stopPropagation)
        .toHaveBeenCalledBefore(viewModel.showConfirm);

      expect(viewModel.saveInstance).not.toHaveBeenCalled();
    });

    it('should call "saveInstance" function when definitions do NOT have ' +
    'all negative or positive responses', () => {
      const instance = {verification_workflow: 'SOX302'};
      viewModel.attr('instance', instance);

      spyOn(viewModel, 'validateNegativeResponses').and.returnValue(null);

      save(saveButtonElement, eventSpy);
      expect(viewModel.showConfirm).not.toHaveBeenCalled();
      expect(viewModel.saveInstance).toHaveBeenCalled();
      expect(eventSpy.stopPropagation)
        .toHaveBeenCalledBefore(viewModel.saveInstance);
    });

    it('should call "saveInstance" function when verification_workflow is ' +
    'NOT SOX302', () => {
      const instance = {verification_workflow: 'STANDARD'};
      viewModel.attr('instance', instance);

      save(saveButtonElement, eventSpy);

      expect(viewModel.showConfirm).not.toHaveBeenCalled();
      expect(viewModel.saveInstance).toHaveBeenCalled();
      expect(eventSpy.stopPropagation)
        .toHaveBeenCalledBefore(viewModel.saveInstance);
    });
  });
});
