/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canMap from 'can-map';
import loDifference from 'lodash/difference';
import moment from 'moment';
import {getComponentVM, makeFakeInstance} from '../../../../js_specs/spec-helpers';
import Component from '../tree-item-extra-info';
import CycleTaskGroupObjectTask from '../../../models/business-models/cycle-task-group-object-task';
import * as businessModels from '../../../models/business-models';
import TreeViewConfig from '../../../apps/base-widgets';

describe('tree-item-extra-info component', () => {
  let viewModel;
  let activeModel = [
    'Regulation',
    'Contract',
    'Policy',
    'Standard',
    'Requirement',
  ];

  beforeEach(() => {
    viewModel = getComponentVM(Component);
  });

  describe('is active if', () => {
    it('workflow_state is defined', () => {
      viewModel.instance = new canMap({workflow_state: 'far'});
      expect(viewModel.isActive).toBeTruthy();
    });

    activeModel.forEach((model) => {
      it('instance is ' + model, () => {
        viewModel.instance = makeFakeInstance({
          model: businessModels[model],
          instanceProps: {type: model},
        })();
        expect(viewModel.isActive).toBeTruthy();
      });
    });
  });

  describe('is not active if', function () {
    let allModels = Object.keys(TreeViewConfig.attr('base_widgets_by_type'));
    let notActiveModels = loDifference(allModels, activeModel);

    it('workflow_state is not defined', function () {
      viewModel.instance = new canMap({title: 'FooBar'});
      expect(viewModel.isActive).toBeFalsy();
    });

    notActiveModels.forEach(function (model) {
      if (businessModels[model]) {
        it('instance is ' + model, function () {
          viewModel.instance = makeFakeInstance(
            {model: businessModels[model]}
          )();
          expect(viewModel.isActive).toBeFalsy();
        });
      }
    });
  });

  describe('isOverdue property', function () {
    it('returns true if workflow_status is "Overdue"', function () {
      let result;
      viewModel.instance = new canMap({
        workflow_state: 'Overdue',
      });

      result = viewModel.isOverdue;

      expect(result).toBe(true);
    });

    it('returns false if workflow_status is not "Overdue"', function () {
      let result;
      viewModel.instance = new canMap({
        workflow_state: 'AnyState',
      });

      result = viewModel.isOverdue;

      expect(result).toBe(false);
    });

    it('returns true if instance is "CycleTasks" and overdue', function () {
      let result;
      let instance = makeFakeInstance({
        model: CycleTaskGroupObjectTask,
      })();
      instance.attr('end_date', moment().subtract(5, 'd'));
      viewModel.instance = instance;

      result = viewModel.isOverdue;

      expect(result).toBe(true);
    });

    it('returns false if instance is "CycleTasks" and not overdue',
      function () {
        let result;
        let instance = makeFakeInstance({
          model: CycleTaskGroupObjectTask,
        })();
        instance.attr('end_date', moment().add(5, 'd'));
        viewModel.instance = instance;

        result = viewModel.isOverdue;

        expect(result).toBe(false);
      });
  });

  describe('endDate property', () => {
    let result;

    it('returns "Today" for today', () => {
      viewModel.instance = new canMap({
        end_date: new Date(),
      });
      result = viewModel.endDate;
      expect(result).toEqual('Today');
    });

    it('returns date for tomorrow', () => {
      let tomorrow = new Date(new Date().getTime() + 24 * 60 * 60 * 1000);
      let expected = moment(tomorrow).format('MM/DD/YYYY');

      viewModel.instance = new canMap({
        end_date: tomorrow,
      });
      result = viewModel.endDate;
      expect(result).toEqual(expected);
    });

    it('returns date for yesterday', () => {
      let yesterday = new Date(new Date().getTime() - 24 * 60 * 60 * 1000);
      let expected = moment(yesterday).format('MM/DD/YYYY');

      viewModel.instance = new canMap({
        end_date: yesterday,
      });
      result = viewModel.endDate;
      expect(result).toEqual(expected);
    });

    it('returns date string when date is passed in', () => {
      viewModel.instance = new canMap({
        end_date: new Date(2000, 2, 2),
      });
      result = viewModel.endDate;
      expect(result).toEqual('03/02/2000');
    });

    it('returns "Today" for falsey', () => {
      viewModel.instance = new canMap({
        end_date: null,
      });
      result = viewModel.endDate;
      expect(result).toEqual('Today');
    });
  });

  describe('processPendingContent() method', () => {
    beforeEach(() => {
      spyOn(viewModel, 'addContent');
    });

    it('extracts pending content from pendingContent field', () => {
      const pendingContent = [
        () => Promise.resolve(),
        () => Promise.resolve(),
      ];
      viewModel.pendingContent.push(...pendingContent);

      viewModel.processPendingContent();

      expect(viewModel.pendingContent.length).toBe(0);
    });

    it('calls addContent() with resolved pending content', () => {
      const expected = [
        Promise.resolve('Content 1'),
        Promise.resolve('Content 2'),
      ];
      const pendingContent = expected.map((promise) => () => promise);
      viewModel.pendingContent.push(...pendingContent);

      viewModel.processPendingContent();

      expect(viewModel.addContent).toHaveBeenCalledWith(...expected);
    });
  });

  describe('addPromiseContent() method', () => {
    it('pushes passed callback from event to pendingContent', () => {
      const event = {
        callback: () => Promise.resolve(),
      };
      viewModel.pendingContent = [];

      viewModel.addPromiseContent(event);

      expect(viewModel.pendingContent.serialize()).toEqual([
        event.callback,
      ]);
    });
  });

  describe('addContent() method', () => {
    beforeEach(() => {
      spyOn($, 'when').and.returnValue(new Promise(() => {}));
    });

    it('sets spin field to true', () => {
      viewModel.addContent();
      expect(viewModel.spin).toBe(true);
    });

    it('pushes passed deferred objects to contentPromises', () => {
      const promises = [
        Promise.resolve(),
        Promise.resolve(),
      ];

      viewModel.addContent(...promises);

      expect(viewModel.contentPromises.serialize()).toEqual(promises);
    });

    it('updates dfdReady field with updated contentPromises', () => {
      const promises = [
        Promise.resolve(),
        Promise.resolve(),
      ];

      viewModel.addContent(promises);

      expect(viewModel.dfdReady).toEqual(jasmine.any(Promise));
    });

    describe('after resolving of contentPromises', () => {
      beforeEach(() => {
        $.when.and.returnValue(Promise.resolve());
      });

      it('sets spin field to false', async (done) => {
        viewModel.addContent();

        await viewModel.dfdReady;

        expect(viewModel.spin).toBe(false);
        done();
      });
    });
  });
});
