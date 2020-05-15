/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../assessments-bulk-complete-popover-content';
import {getComponentVM} from '../../../../../../js_specs/spec-helpers';

describe('assessments-bulk-complete-popover-content component', () => {
  let viewModel;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
    viewModel.isLoading = false;
  });

  describe('initRelatedObjects() method', () => {
    it('sets "isLoading" to true before call "relatedObjectsPromise"',
      () => {
        viewModel.initRelatedObjects();
        expect(viewModel.isLoading).toBeTruthy();
      });

    it('sets "relatedObjects" values', async () => {
      const relatedObjects = [{id: 1}];
      viewModel.relatedObjectsPromise = Promise.resolve(relatedObjects);
      await viewModel.initRelatedObjects();
      expect(viewModel.relatedObjects.serialize()).toEqual(relatedObjects);
    });

    it('sets "isLoading" to false after call "relatedObjectsPromise"',
      async () => {
        viewModel.relatedObjectsPromise = Promise.resolve();
        await viewModel.initRelatedObjects();
        expect(viewModel.isLoading).toBeFalsy();
      });
  });
});
