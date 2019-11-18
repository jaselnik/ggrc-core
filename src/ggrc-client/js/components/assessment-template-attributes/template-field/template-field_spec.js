/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import canStache from 'can-stache';
import canList from 'can-list';
import canMap from 'can-map';
import Component from './template-field';
import {getComponentVM, spyProp} from '../../../../js_specs/spec-helpers';

describe('template-field component', function () {
  let viewModel;

  beforeEach(function () {
    viewModel = getComponentVM(Component);
  });

  describe('denormalizeMandatory() method', function () {
    it('returns correct denormalized field', function () {
      let field = new canMap({
        multi_choice_options: 'foo,bar,baz,bam',
        multi_choice_mandatory: '0,1,2,3',
      });
      let result = viewModel.denormalizeMandatory(field);

      expect(result.length).toEqual(4);
      expect(result[0].attachment).toEqual(false);
      expect(result[0].comment).toEqual(false);
      expect(result[1].attachment).toEqual(false);
      expect(result[1].comment).toEqual(true);
      expect(result[2].attachment).toEqual(true);
      expect(result[2].comment).toEqual(false);
      expect(result[3].attachment).toEqual(true);
      expect(result[3].comment).toEqual(true);
    });

    it('returns false for attachment and comment for missing mandatory',
      function () {
        let field = new canMap({
          multi_choice_options: 'one,two,three,four,five',
          multi_choice_mandatory: '0,1,2',
        });
        let result = viewModel.denormalizeMandatory(field);

        expect(result.length).toEqual(5);
        expect(result[0].attachment).toEqual(false);
        expect(result[0].comment).toEqual(false);
        expect(result[1].attachment).toEqual(false);
        expect(result[1].comment).toEqual(true);
        expect(result[2].attachment).toEqual(true);
        expect(result[2].comment).toEqual(false);

        expect(result[3].attachment).toEqual(false);
        expect(result[3].comment).toEqual(false);
        expect(result[4].attachment).toEqual(false);
        expect(result[4].comment).toEqual(false);
      });

    it('returns values only for defined options', function () {
      let field = new canMap({
        multi_choice_options: 'one,two,three',
        multi_choice_mandatory: '0,1,2,2,0',
      });
      let result = viewModel.denormalizeMandatory(field);

      expect(result.length).toEqual(3);
      expect(result[0].attachment).toEqual(false);
      expect(result[0].comment).toEqual(false);
      expect(result[1].attachment).toEqual(false);
      expect(result[1].comment).toEqual(true);
      expect(result[2].attachment).toEqual(true);
      expect(result[2].comment).toEqual(false);
    });
  });

  describe('normalizeMandatory() method', function () {
    it('returns correct normalized attrs', function () {
      let attrs = new canList([
        {attachment: false, comment: false},
        {attachment: true, comment: false},
        {attachment: false, comment: true},
        {attachment: true, comment: true},
      ]);
      let result = viewModel.normalizeMandatory(attrs);

      expect(result).toEqual('0,2,1,3');
    });
  });

  describe('emitting events', function () {
    describe('"{viewModel.instance} verification_workflow" event', () => {
      let event;

      beforeEach(() => {
        const eventName = '{viewModel.instance} verification_workflow';
        event = Component.prototype.events[eventName].bind({viewModel});
      });

      it('should call "initTextFieldOptions" function when ' +
      'isTextFieldOptionsVisible is TRUE', () => {
        spyProp(viewModel, 'isTextFieldOptionsVisible').and.returnValue(true);
        spyOn(viewModel, 'initTextFieldOptions');
        spyOn(viewModel, 'denormalizeMandatory').and
          .returnValue([
            {value: 'Empty'},
            {value: 'Not empty'},
          ]);

        event();
        expect(viewModel.initTextFieldOptions).toHaveBeenCalled();
        expect(viewModel.attr('attrs').serialize()).toEqual([
          {value: 'Empty'},
          {value: 'Not empty'},
        ]);
      });

      it('should NOT call "initTextFieldOptions" function when ' +
      'isTextFieldOptionsVisible is FALSE', () => {
        spyProp(viewModel, 'isTextFieldOptionsVisible').and.returnValue(false);
        spyOn(viewModel, 'initTextFieldOptions');

        event();
        expect(viewModel.initTextFieldOptions).not.toHaveBeenCalled();
      });
    });

    describe('on-remove event', function () {
      let $root; // the component's root DOM element
      let onRemoveCallback;

      beforeEach(function () {
        let $body = $('body');
        let docFragment;
        let htmlSnippet;
        let renderer;
        let templateContext;

        onRemoveCallback = jasmine.createSpy('onRemoveCallback');

        htmlSnippet = [
          '<template-field',
          '  field:from="fieldDefinition"',
          '  types:from="types"',
          '  on:remove="fieldRemoved()">',
          '</template-field>',
        ].join('');

        templateContext = new canMap({
          types: new canList([
            {
              type: 'Text',
              name: 'Text',
              text: 'Enter description',
            },
          ]),
          fieldDefinition: {
            attribute_type: 'Text',
          },
          fieldRemoved: onRemoveCallback,
        });

        renderer = canStache(htmlSnippet);
        docFragment = renderer(templateContext);
        $body.append(docFragment);

        $root = $body.find('template-field');
      });

      afterEach(function () {
        $root.remove();
      });

      it('invokes the provided handler when element is removed', function () {
        let $btnDelete = $root.find('.fa-trash').closest('a');
        $btnDelete.click();
        expect(onRemoveCallback).toHaveBeenCalled();
      });
    });
  });
});
