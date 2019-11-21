/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loCapitalize from 'lodash/capitalize';
import canList from 'can-list';
import canMap from 'can-map';
import Component from '../assessment-info-pane';
import {getComponentVM, makeFakeInstance} from '../../../../../js_specs/spec-helpers';
import tracker from '../../../../tracker';
import {
  RELATED_ITEMS_LOADED,
  REFRESH_MAPPING,
  REFRESH_RELATED,
} from '../../../../events/event-types';
import * as queryApiUtils from '../../../../plugins/utils/query-api-utils';
import * as commentsUtils from '../../../../plugins/utils/comments-utils';
import * as aclUtils from '../../../../plugins/utils/acl-utils';
import * as caUtils from '../../../../plugins/utils/ca-utils';
import * as DeferredTransactionUtil from '../../../../plugins/utils/deferred-transaction-utils';
import * as Permission from '../../../../permission';
import {CUSTOM_ATTRIBUTE_TYPE} from '../../../../plugins/utils/custom-attribute/custom-attribute-config';
import * as NotifiersUtils from '../../../../plugins/utils/notifiers-utils';
import * as businessModels from '../../../../models/business-models';
import Evidence from '../../../../models/business-models/evidence';

describe('assessment-info-pane component', () => {
  let vm;

  beforeEach(function () {
    vm = getComponentVM(Component);
  });

  describe('verifiers get() method', () => {
    beforeEach(function () {
      vm.attr('instance', {});
    });

    describe('if there is no verifier role id', () => {
      beforeEach(function () {
        vm.attr('_verifierRoleId', null);
      });

      it('returns an empty array', function () {
        expect(vm.attr('verifiers')).toEqual([]);
      });
    });

    it('returns verifiers', function () {
      const verifierRoleId = 1;
      const acl = [
        {ac_role_id: verifierRoleId, person: {id: 301}},
        {ac_role_id: 2, person: {id: 100}},
        {ac_role_id: verifierRoleId, person: {id: 432}},
      ];
      const expected = [
        acl[0],
        acl[2],
      ].map((item) => item.person);
      vm.attr('_verifierRoleId', verifierRoleId);
      vm.attr('instance.access_control_list', acl);
      expect(vm.attr('verifiers').serialize()).toEqual(expected);
    });
  });

  describe('showProcedureSection get() method', () => {
    beforeEach(function () {
      vm.attr('instance', {});
    });

    it('returns test_plan value if it exists', function () {
      const testPlan = 'Some value';
      vm.attr('instance.test_plan', testPlan);
      expect(vm.attr('showProcedureSection')).toBe(testPlan);
    });

    it('returns issue_tracker.issue_url value if there is no test_plan',
      function () {
        const issueUrl = 'Some value';
        vm.attr('instance.issue_tracker', {issue_url: issueUrl});
        expect(vm.attr('showProcedureSection')).toBe(issueUrl);
      });
  });

  describe('assessmentTypeNameSingular get() method', () => {
    let fakeType;

    beforeEach(function () {
      fakeType = 'FakeType';
      businessModels[fakeType] = {};
      vm.attr('instance', {
        assessment_type: fakeType,
      });
    });

    afterAll(function () {
      businessModels[fakeType] = undefined;
    });

    it('returns singular title for object which has type equals to ' +
    'assessment object type', function () {
      const title = 'Fake Title';
      businessModels[fakeType].title_singular = title;
      expect(vm.attr('assessmentTypeNameSingular')).toBe(title);
    });
  });

  describe('assessmentTypeNamePlural get() method', () => {
    let fakeType;

    beforeEach(function () {
      fakeType = 'FakeType';
      businessModels[fakeType] = {};
      vm.attr('instance', {
        assessment_type: fakeType,
      });
    });

    afterAll(function () {
      businessModels[fakeType] = undefined;
    });

    it('returns plural title for object which has type equals to ' +
    'assessment object type', function () {
      const title = 'Fake Title';
      businessModels[fakeType].title_plural = title;
      expect(vm.attr('assessmentTypeNamePlural')).toBe(title);
    });
  });

  describe('assessmentTypeObjects get() method', () => {
    beforeEach(function () {
      vm.attr({
        instance: {},
        mappedSnapshots: [],
      });
    });

    it('returns mapped snapshots, which has a child type equals to ' +
    'assessment type', function () {
      const asmtType = 'SomeType';
      const mappedSnapshots = [
        {child_type: asmtType, data: 'Data 1'},
        {child_type: 'Type1', data: 'Data 2'},
        {child_type: asmtType, data: 'Data 3'},
      ];
      const expected = [mappedSnapshots[0], mappedSnapshots[2]];
      vm.attr('instance.assessment_type', asmtType);
      vm.attr('mappedSnapshots', mappedSnapshots);
      expect(vm.attr('assessmentTypeObjects').serialize()).toEqual(expected);
    });
  });

  describe('relatedInformation get() method', () => {
    beforeEach(function () {
      vm.attr({
        instance: {},
        mappedSnapshots: [],
      });
    });

    it('returns related information from mapped snapshots list', function () {
      const asmtType = 'SomeType';
      const mappedSnapshots = [
        {child_type: asmtType, data: 'Data 1'},
        {child_type: 'Type1', data: 'Data 2'},
        {child_type: asmtType, data: 'Data 3'},
      ];
      const expected = [mappedSnapshots[1]];
      vm.attr('instance.assessment_type', asmtType);
      vm.attr('mappedSnapshots', mappedSnapshots);
      expect(vm.attr('relatedInformation').serialize()).toEqual(expected);
    });
  });

  describe('editMode attribute', () => {
    const editableStatuses = ['Not Started', 'In Progress', 'Rework Needed'];
    const nonEditableStates = ['In Review', 'Completed', 'Deprecated'];
    const allStatuses = editableStatuses.concat(nonEditableStates);

    describe('get() method', () => {
      beforeEach(function () {
        vm.attr('instance', makeFakeInstance({
          model: businessModels.Assessment,
        })());
      });

      it('returns false if instance is archived', function () {
        vm.attr('instance.archived', true);

        allStatuses.forEach((status) => {
          vm.attr('instance.status', status);
          expect(vm.attr('editMode')).toBe(false);
        });
      });

      describe('if instance is not archived', () => {
        it('returns true if instance status and currentState' +
        'have equal editable otherwise false',
        function () {
          allStatuses.forEach((status) => {
            vm.attr('instance.status', status);
            vm.attr('currentState', status);
            expect(vm.attr('editMode'))
              .toBe(editableStatuses.includes(status));
          });
        });

        it('returns false if instance status is editable and currentState' +
        'is NOT editable',
        () => {
          vm.attr('instance.status', editableStatuses[0]);
          vm.attr('currentState', nonEditableStates[0]);
          expect(vm.attr('editMode')).toBeFalsy();
        });

        it('returns false if instance status is NOT editable and currentState' +
        'is editable',
        () => {
          vm.attr('instance.status', nonEditableStates[0]);
          vm.attr('currentState', editableStatuses[0]);
          expect(vm.attr('editMode')).toBeFalsy();
        });

        it('returns false if instance status and currentState' +
        'have different EDITABLE statuses',
        () => {
          vm.attr('instance.status', editableStatuses[1]);
          vm.attr('currentState', editableStatuses[0]);
          expect(vm.attr('editMode')).toBeFalsy();
        });
      });
    });

    describe('set() method', () => {
      it('calls onStateChange handler for "In Progress" status without undo',
        function () {
          spyOn(vm, 'onStateChange');
          vm.attr('editMode', true);
          expect(vm.onStateChange).toHaveBeenCalledWith({
            state: 'In Progress',
            undo: false,
          });
        });
    });
  });

  describe('isEditDenied get() method', () => {
    beforeEach(function () {
      spyOn(Permission, 'isAllowedFor');
      vm.attr('instance', {});
    });

    it('returns true if there are no update permissions for the ' +
    'current instance', function () {
      let result;
      Permission.isAllowedFor.and.returnValue(false);
      result = vm.attr('isEditDenied');
      expect(result).toBe(true);
      expect(Permission.isAllowedFor).toHaveBeenCalledWith(
        'update',
        vm.attr('instance')
      );
    });

    describe('when there are update permissions for the current instance',
      () => {
        beforeEach(function () {
          Permission.isAllowedFor.and.returnValue(true);
        });

        it('returns true if the current instance is archived', function () {
          vm.attr('instance.archived', true);
          expect(vm.attr('isEditDenied')).toBe(true);
        });

        it('returns false if the current instance is not archived',
          function () {
            vm.attr('instance.archived', false);
            expect(vm.attr('isEditDenied')).toBe(false);
          });
      });
  });

  describe('isRestricted get() method', () => {
    beforeEach(() => {
      spyOn(Permission, 'isAllowedFor');
      vm.attr('instance', {});
    });

    it('returns true if isEditDenied is set to true', () => {
      Permission.isAllowedFor.and.returnValue(false);
      const result = vm.attr('isRestricted');
      expect(result).toBe(true);
    });

    it('returns true if isEditDenied and ' +
      '_is_sox_restricted are set to true', () => {
      vm.attr('instance', {_is_sox_restricted: true});
      Permission.isAllowedFor.and.returnValue(true);
      const result = vm.attr('isRestricted');
      expect(result).toBe(true);
    });

    it('returns false if isEditDenied and ' +
    'instance._is_sox_restricted are set to false', () => {
      vm.attr('instance', {_is_sox_restricted: false});
      Permission.isAllowedFor.and.returnValue(true);
      const result = vm.attr('isRestricted');
      expect(result).toBe(false);
    });

    it('returns true if instance._is_sox_restricted is set to true ' +
    ' isEditDenied is set to false ', () => {
      vm.attr('instance', {_is_sox_restricted: true});
      Permission.isAllowedFor.and.returnValue(true);
      const result = vm.attr('isRestricted');
      expect(result).toBe(true);
    });
  });

  describe('isSemiRestrictedOnStatus get() method', () => {
    beforeEach(() => {
      spyOn(Permission, 'isAllowedFor');
      vm.attr('instance', {});
    });

    it('returns true if isEditDenied is set to true', () => {
      Permission.isAllowedFor.and.returnValue(false);
      vm.attr('instance', {_is_sox_restricted: false, status: 'In Progress'});
      const result = vm.attr('isSemiRestrictedOnStatus');
      expect(result).toBe(true);
    });

    it('returns true if instance._is_sox_restricted is set to true ' +
    'and status is "Completed"', () => {
      Permission.isAllowedFor.and.returnValue(true);
      vm.attr('instance', {_is_sox_restricted: true, status: 'Completed'});
      const result = vm.attr('isSemiRestrictedOnStatus');
      expect(result).toBe(true);
    });

    it('returns false if instance._is_sox_restricted is set to true ' +
    'and status is "In Progress"', () => {
      Permission.isAllowedFor.and.returnValue(true);
      vm.attr('instance', {_is_sox_restricted: true, status: 'In Progress'});
      const result = vm.attr('isSemiRestrictedOnStatus');
      expect(result).toBe(false);
    });
  });

  describe('isInfoPaneSaving get() method', () => {
    it('returns false if related items are updating', function () {
      vm.attr('isUpdatingRelatedItems', true);
      expect(vm.attr('isInfoPaneSaving')).toBe(false);
    });

    describe('returns true', () => {
      beforeEach(function () {
        vm.attr('isUpdatingRelatedItems', false);
      });

      it('if urls are updating', function () {
        vm.attr('isUpdatingUrls', true);
        expect(vm.attr('isInfoPaneSaving')).toBe(true);
      });

      it('if comments are updating', function () {
        vm.attr('isUpdatingComments', true);
        expect(vm.attr('isInfoPaneSaving')).toBe(true);
      });

      it('if files are updating', function () {
        vm.attr('isUpdatingFiles', true);
        expect(vm.attr('isInfoPaneSaving')).toBe(true);
      });

      it('if the assessment is saving', function () {
        vm.attr('isAssessmentSaving', true);
        expect(vm.attr('isInfoPaneSaving')).toBe(true);
      });
    });
  });

  describe('setUrlEditMode() method', () => {
    it('sets value for \'urlsEditMode\' attribute', function () {
      const value = false;
      const expectedProp = 'urlsEditMode';
      vm.setUrlEditMode(value);
      expect(vm.attr(expectedProp)).toBe(value);
    });
  });

  describe('setInProgressState() method', () => {
    beforeEach(function () {
      spyOn(vm, 'onStateChange');
    });

    it('calls onStateChange with appropriate object', function () {
      const obj = {state: 'In Progress', undo: false};
      vm.setInProgressState();
      expect(vm.onStateChange).toHaveBeenCalledWith(obj);
    });
  });

  describe('isReadOnlyAttribute() method', () => {
    beforeEach(() => {
      spyOn(Permission, 'isAllowedFor');
      vm.attr('instance', {archived: false});
      vm.attr('instance._readonly_fields', []);
    });

    it('returns true if isEditDenied is set to true', () => {
      Permission.isAllowedFor.and.returnValue(false);
      const result = vm.isReadOnlyAttribute();
      expect(result).toBe(true);
    });

    it('returns true if propName is included ' +
    'to readOnlyAttributes list', () => {
      Permission.isAllowedFor.and.returnValue(true);
      const propName = 'title';
      vm.attr('instance._readonly_fields', [propName]);
      const result = vm.isReadOnlyAttribute(propName);
      expect(result).toBe(true);
    });

    it('returns false if propName is not included ' +
    'to readOnlyAttributes list', () => {
      Permission.isAllowedFor.and.returnValue(true);
      const propName = 'title';
      vm.attr('instance._readonly_fields', ['description']);
      const result = vm.isReadOnlyAttribute(propName);
      expect(result).toBe(false);
    });
  });

  describe('getQuery() method', () => {
    beforeEach(function () {
      spyOn(queryApiUtils, 'buildParam');
    });

    it('returns the built query', function () {
      const expected = {};
      queryApiUtils.buildParam.and.returnValue(expected);
      const result = vm.getQuery();
      expect(result).toBe(expected);
    });

    describe('builds query with help', () => {
      let ARGS;

      beforeAll(function () {
        ARGS = {
          TYPE: 0,
          SORT_OBJ: 1,
          REL_FILTER: 2,
          FIELDS: 3,
          ADT_FILTER: 4,
        };
      });

      beforeEach(function () {
        vm.attr('instance', {
          type: 'instanceType',
          id: 1,
        });
      });

      it('passed type', function () {
        const type = 'Type';
        vm.getQuery(type, {}, []);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.TYPE]).toBe(type);
      });

      it('passed sortObj', function () {
        const sortObj = {};
        vm.getQuery('Type', sortObj, []);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.SORT_OBJ]).toBe(sortObj);
      });

      it('empty obj if sortObj is empty', function () {
        const sortObj = null;
        vm.getQuery('Type', sortObj, []);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.SORT_OBJ]).toEqual({});
      });

      it('relevant filter made from instance type and id', function () {
        const relevantFilters = [{
          type: vm.attr('instance.type'),
          id: vm.attr('instance.id'),
          operation: 'relevant',
        }];
        vm.getQuery('Type', {}, []);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.REL_FILTER]).toEqual(relevantFilters);
      });

      it('empty array of fields', function () {
        vm.getQuery('Type', {}, []);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.FIELDS]).toEqual([]);
      });

      it('passed additional filter', function () {
        const adtFilter = [];
        vm.getQuery('Type', {}, adtFilter);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.ADT_FILTER]).toBe(adtFilter);
      });

      it('empty array if additional filter is empty', function () {
        const adtFilter = null;
        vm.getQuery('Type', {}, adtFilter);
        const args = queryApiUtils.buildParam.calls.argsFor(0);
        expect(args[ARGS.ADT_FILTER]).toEqual([]);
      });
    });
  });

  describe('getSnapshotQuery() method', () => {
    beforeEach(function () {
      spyOn(vm, 'getQuery');
    });

    it('returns result of getQuery method', function () {
      const fakeQuery = {};
      vm.getQuery.and.returnValue(fakeQuery);
      const result = vm.getSnapshotQuery();
      expect(result).toBe(fakeQuery);
    });

    it('sets "Snapshot" type for getQuery method', function () {
      const type = 'Snapshot';
      vm.getSnapshotQuery();
      expect(vm.getQuery).toHaveBeenCalledWith(type);
    });
  });

  describe('requestQuery() method', () => {
    let dfd;

    beforeEach(function () {
      dfd = $.Deferred();
      spyOn(queryApiUtils, 'batchRequests').and.returnValue(dfd);
    });

    it('sets "isUpdating{<passed capitalized type>}" property to true before ' +
    'resolving a request', function () {
      const type = 'type';
      const expectedProp = `isUpdating${loCapitalize(type)}`;
      vm.attr(expectedProp, false);
      vm.requestQuery({}, type);
      expect(vm.attr(expectedProp)).toBe(true);
    });

    it('makes request with help passed query', function () {
      const query = {
        param1: '',
        param2: '',
      };
      vm.requestQuery(query);
      expect(queryApiUtils.batchRequests).toHaveBeenCalledWith(query);
    });

    describe('when request was resolved', () => {
      let response;

      beforeEach(function () {
        response = {
          type1: {
            values: [],
          },
          type2: {
            values: [],
          },
        };

        dfd.resolve(response);
      });

      it('returns values from first response object', async function (done) {
        const resp = await vm.requestQuery({});
        expect(resp).toBe(response.type1.values);
        done();
      });

      it('sets "isUpdating{<passed capitalized type>}" property to false ',
        async function (done) {
          const type = 'type';
          const expectedProp = `isUpdating${loCapitalize(type)}`;
          await vm.requestQuery({}, type);
          expect(vm.attr(expectedProp)).toBe(false);
          done();
        });
    });

    describe('when request was rejected', () => {
      beforeEach(function () {
        dfd.reject();
      });

      it('returns empty array', async function (done) {
        const resp = await vm.requestQuery({});
        expect(resp).toEqual([]);
        done();
      });

      it('sets "isUpdating{<passed capitalized type>}" property to false ',
        async function (done) {
          const type = 'type';
          const expectedProp = `isUpdating${loCapitalize(type)}`;
          await vm.requestQuery({}, type);
          expect(vm.attr(expectedProp)).toBe(false);
          done();
        });
    });
  });

  describe('loadSnapshots() method', () => {
    beforeEach(function () {
      spyOn(vm, 'requestQuery');
      spyOn(vm, 'getSnapshotQuery');
    });

    it('returns result of the snapshots query', function () {
      const expectedResult = Promise.resolve();
      vm.requestQuery.and.returnValue(expectedResult);
      const result = vm.loadSnapshots();
      expect(result).toBe(expectedResult);
    });

    it('uses query for Snapshots', function () {
      const query = {field: 'f1'};
      vm.getSnapshotQuery.and.returnValue(query);
      vm.loadSnapshots();
      expect(vm.requestQuery).toHaveBeenCalledWith(query);
    });
  });

  describe('loadFiles() method', () => {
    beforeEach(function () {
      spyOn(vm, 'requestQuery');
      spyOn(vm, 'getEvidenceQuery');
    });

    it('forms query from "FILE" evidence query', function () {
      vm.loadFiles();
      expect(vm.getEvidenceQuery).toHaveBeenCalledWith('FILE');
    });

    it('returns result of the files query', function () {
      const expectedResult = Promise.resolve();
      vm.requestQuery.and.returnValue(expectedResult);
      const result = vm.loadFiles();
      expect(result).toBe(expectedResult);
    });

    it('uses Evidence query and "files" type', function () {
      const query = {field: 'f1'};
      const type = 'files';
      vm.getEvidenceQuery.and.returnValue(query);
      vm.loadFiles();
      expect(vm.requestQuery).toHaveBeenCalledWith(query, type);
    });
  });

  describe('loadUrls() method', () => {
    beforeEach(function () {
      spyOn(vm, 'requestQuery');
      spyOn(vm, 'getEvidenceQuery');
    });

    it('forms query from "URL" evidence query', function () {
      vm.loadUrls();
      expect(vm.getEvidenceQuery).toHaveBeenCalledWith('URL');
    });

    it('returns result of the urls query', function () {
      const expectedResult = Promise.resolve();
      vm.requestQuery.and.returnValue(expectedResult);
      const result = vm.loadUrls();
      expect(result).toBe(expectedResult);
    });

    it('uses Evidence query and "urls" type', function () {
      const query = {field: 'f1'};
      const type = 'urls';
      vm.getEvidenceQuery.and.returnValue(query);
      vm.loadUrls();
      expect(vm.requestQuery).toHaveBeenCalledWith(query, type);
    });
  });

  describe('updateItems() method', () => {
    beforeEach(function () {
      spyOn(vm, 'refreshCounts');
    });

    describe('for certain types', () => {
      let types;

      beforeEach(function () {
        types = ['urls', 'files'];
        types.forEach((type, i) => {
          const methodName = `load${loCapitalize(type)}`;
          vm.attr(type.toLowerCase(), []);
          spyOn(vm, methodName);
        });
      });

      it('calls appropriate methods with the passed capitalized types',
        function () {
          vm.updateItems(...types);
          types.forEach((type) => {
            const methodName = `load${loCapitalize(type)}`;
            expect(vm[methodName]).toHaveBeenCalled();
          });
        });

      it('replaces values of passed fields in VM with the results of ' +
      'appropriate methods', function () {
        const loadedData = types.map((type, i) => [type, i]);
        types.forEach((type, i) => {
          const methodName = `load${loCapitalize(type)}`;
          vm[methodName].and.returnValue(loadedData[i]);
        });
        vm.updateItems(...types);
        types.forEach((type, i) => {
          expect(vm.attr(type).serialize()).toEqual(loadedData[i]);
        });
      });
    });

    it('not throws an exception if types is not passed', function () {
      const closure = function () {
        vm.updateItems();
      };
      expect(closure).not.toThrow();
    });
  });

  describe('isAllowedToMap attribute', () => {
    describe('get() method', () => {
      beforeEach(function () {
        vm.attr('instance', {});
      });

      it('returns true if there is audit and it is allowed to read ' +
      'instance.audit', () => {
        vm.attr('instance.audit', {});
        spyOn(Permission, 'isAllowedFor').and.returnValue(true);

        let result = vm.attr('isAllowedToMap');

        expect(result).toBe(true);
      });
      it('returns false if there is no audit', () => {
        vm.attr('instance.audit', null);

        let result = vm.attr('isAllowedToMap');

        expect(result).toBe(false);
      });

      it('returns false if there is audit but it is not allowed ' +
      'to read instance.audit', () => {
        vm.attr('instance.audit', {});
        spyOn(Permission, 'isAllowedFor').and.returnValue(false);

        let result = vm.attr('isAllowedToMap');

        expect(result).toBe(false);
      });
    });
  });

  describe('removeItems() method', () => {
    const itemsType = 'comments';

    let items = new canList([...Array(3).keys()]).map((item, index) => {
      return {
        id: index,
        type: itemsType,
      };
    });

    it('should remove all unsaved items from list', () => {
      vm.attr(itemsType, items);

      let event = {
        items: [items[0], items[2]],
      };

      vm.removeItems(event, itemsType);
      let actualItems = vm.attr(itemsType);
      expect(actualItems.length).toBe(1);
      expect(actualItems[0].attr('id')).toEqual(1);
    });
  });

  describe('addItems() method', () => {
    let type;
    let event;

    beforeEach(function () {
      type = 'Type';
      event = {
        items: [1, 2, 3],
      };
      vm.attr(type, [4, 5, 6]);
    });

    it('pushes items from event into beginning of the list with name from ' +
    'type param', function () {
      const beforeInvoke = vm.attr(type).serialize();
      const expectedResult = event.items.concat(beforeInvoke);
      vm.addItems(event, type);
      expect(vm.attr(type).serialize()).toEqual(expectedResult);
    });

    it('sets "isUpdating{<passed capitalized type>}" property to true',
      function () {
        const expectedProp = `isUpdating${loCapitalize(type)}`;
        vm.attr(expectedProp, false);

        vm.addItems(event, type);
        expect(vm.attr(expectedProp)).toBe(true);
      });

    it('works fine, when event.items prop is array-like object', function () {
      const beforeInvoke = vm.attr(type).serialize();
      const expectedResult = event.items.concat(beforeInvoke);

      event.items = new canList(event.items);
      vm.addItems(event, type);

      expect(vm
        .attr(type)
        .serialize()
      ).toEqual(expectedResult);
    });
  });

  describe('addAction() method', () => {
    beforeEach(function () {
      vm.attr('instance', {});
    });

    it('sets instance.actions to empty object if there are no actions',
      function () {
        vm.attr('instance.actions', null);
        vm.addAction('actionType', {});
        expect(vm.attr('instance.actions')).toBeDefined();
      });

    it('pushes into actions.{<passed actionType>} passed related item if ' +
    'there is actions.{<passed actionType>}', function () {
      const actionType = 'actionType';
      const related = {
        data: 'Important data',
      };

      vm.attr('instance.actions', {[actionType]: []});
      vm.addAction(actionType, related);

      const last = vm
        .attr('instance.actions')
        .attr(actionType).pop();
      expect(last.serialize()).toEqual(related);
    });

    it('creates actions.{<passed actionType>} list for instance with passed ' +
    'related item if there are no actions.{<passed actionType>}', function () {
      const actionType = 'actionType';
      const related = {
        data: 'Important data',
      };
      const expected = [related];
      vm.addAction(actionType, related);
      expect(vm
        .attr('instance.actions')
        .attr(actionType)
        .serialize()
      ).toEqual(expected);
    });
  });

  describe('addRelatedItem() method', () => {
    let assessment;
    let event;
    let type;
    let related;
    let dfd;

    beforeEach(function () {
      dfd = $.Deferred();
      type = 'type';
      event = {
        item: new canMap({
          id: 1,
          type: 'Type',
        }),
      };
      related = {
        id: event.item.attr('id'),
        type: event.item.attr('type'),
      };
      assessment = new canMap({
        actions: [],
      });

      vm.attr('instance', {});
      vm.attr('instance').dispatch = jasmine.createSpy('dispatch');
      vm.attr('deferredSave', {
        execute: jasmine.createSpy('execute').and.returnValue(dfd),
      });

      spyOn(vm, 'addAction');
      spyOn(vm, 'removeItems');
    });

    describe('within executed deferred function into deferredSave', () => {
      let executedFunc;

      beforeEach(function () {
        vm.addRelatedItem(event, type);
        executedFunc = vm.attr('deferredSave').execute.calls.argsFor(0)[0];
      });

      it('adds add_related action with related object', function () {
        executedFunc();
        expect(vm.addAction).toHaveBeenCalledWith(
          'add_related',
          related
        );
      });
    });

    describe('if deferredSave was resolved', () => {
      beforeEach(function () {
        dfd.resolve(assessment);
      });

      it('sets "isUpdating{<passed capitalized type>}" property to false',
        function (done) {
          const expectedProp = `isUpdating${loCapitalize(type)}`;

          vm.addRelatedItem(event, type);

          dfd.always(() => {
            expect(vm.attr(expectedProp)).toBe(false);
            done();
          });
        });

      it('removes actions for assessment', function (done) {
        vm.addRelatedItem(event, type);
        dfd.always(() => {
          expect(assessment.attr('actions')).toBeUndefined();
          done();
        });
      });

      it('dispatches RELATED_ITEMS_LOADED for instance', function (done) {
        vm.addRelatedItem(event, type);
        dfd.always(() => {
          expect(vm.attr('instance').dispatch).toHaveBeenCalledWith(
            RELATED_ITEMS_LOADED
          );
          done();
        });
      });

      it('refreshes counts for "Evidence" if related items type is "Evidence"',
        function (done) {
          spyOn(vm, 'refreshCounts');
          event.item.attr('type', 'Evidence');
          vm.addRelatedItem(event, type);
          dfd.always(() => {
            expect(vm.refreshCounts).toHaveBeenCalledWith(
              [event.item.type]
            );
            done();
          });
        });

      it('increases comment related counts when comment is added', (done) => {
        vm.attr('commentsTotalCount', 0);
        vm.attr('newCommentsCount', 0);

        event.item.attr('type', 'Comment');
        vm.addRelatedItem(event, 'comments');
        dfd.always(() => {
          expect(vm.attr('commentsTotalCount')).toBe(1);
          expect(vm.attr('newCommentsCount')).toBe(1);
          done();
        });
      });
    });

    describe('if deferredSave was rejected', () => {
      beforeEach(function () {
        dfd.reject(assessment);
        spyOn(NotifiersUtils, 'notifierXHR');
      });

      it('sets "isUpdating{<passed capitalized type>}" property to false',
        function (done) {
          const expectedProp = `isUpdating${loCapitalize(type)}`;

          vm.addRelatedItem(event, type);

          dfd.always(() => {
            expect(vm.attr(expectedProp)).toBe(false);
            done();
          });
        });

      it('calls removeItems with appropriate params', (done) => {
        dfd.reject(assessment);
        vm.addRelatedItem(event, type);
        dfd.fail(() => {
          expect(vm.removeItems.calls.count()).toBe(1);
          expect(vm.removeItems).toHaveBeenCalledWith({
            items: [event.item],
          }, type);
          done();
        });
      });

      it('removes actions for assessment', function (done) {
        vm.addRelatedItem(event, type);
        dfd.always(() => {
          expect(assessment.attr('actions')).toBeUndefined();
          done();
        });
      });

      it('dispatches RELATED_ITEMS_LOADED for instance', function (done) {
        vm.addRelatedItem(event, type);
        dfd.always(() => {
          expect(vm.attr('instance').dispatch).toHaveBeenCalledWith(
            RELATED_ITEMS_LOADED
          );
          done();
        });
      });

      it('refreshes counts for "Evidence" if related items type is "Evidence"',
        function (done) {
          spyOn(vm, 'refreshCounts');
          event.item.attr('type', 'Evidence');
          vm.addRelatedItem(event, type);
          dfd.always(() => {
            expect(vm.refreshCounts).toHaveBeenCalledWith(
              [event.item.type]
            );
            done();
          });
        });
    });
  });

  describe('removeRelatedItem() method', () => {
    let dfd;
    let type;
    let item;
    let items;
    let related;
    let assessment;

    beforeEach(function () {
      const countOfItems = 3;
      dfd = $.Deferred();
      type = 'type';
      items = new canList(
        Array(...Array(countOfItems).keys())
      ).map((item, index) => {
        return {
          id: index,
          type: 'Awesome type',
        };
      });
      item = items.attr(countOfItems - 1);
      related = {
        id: item.attr('id'),
        type: item.attr('type'),
      };
      assessment = new canMap({
        actions: [],
      });
      vm.attr(type, items);
      vm.attr('deferredSave', {
        push: jasmine.createSpy('push').and.returnValue(dfd),
      });

      spyOn(vm, 'addAction');
      spyOn(NotifiersUtils, 'notifier');
      spyOn(vm, 'refreshCounts');
    });

    it('sets "isUpdating{<passed capitalized type>}" property to true ' +
    'before deferredSave\'s resolve', function () {
      const expectedProp = `isUpdating${loCapitalize(type)}`;
      vm.attr(expectedProp, false);
      vm.removeRelatedItem(item, type);
      expect(vm.attr(expectedProp)).toBe(true);
    });

    it('removes passed item from {<passed type>} list', function () {
      vm.removeRelatedItem(item, type);
      expect(items.indexOf(item)).toBe(-1);
    });

    describe('pushed function into deferredSave', () => {
      let pushedFunc;

      beforeEach(function () {
        vm.removeRelatedItem(item, type);
        pushedFunc = vm.attr('deferredSave').push.calls.argsFor(0)[0];
      });

      it('adds remove_related action with related object', function () {
        pushedFunc();
        expect(vm.addAction).toHaveBeenCalledWith(
          'remove_related',
          related
        );
      });
    });

    describe('if deferredSave was resolved', () => {
      beforeEach(function () {
        dfd.resolve(assessment);
      });

      it('sets "isUpdating{<passed capitalized type>}" property to false',
        function (done) {
          const expectedProp = `isUpdating${loCapitalize(type)}`;

          vm.removeRelatedItem(item, type);

          dfd.always(() => {
            expect(vm.attr(expectedProp)).toBe(false);
            done();
          });
        });

      it('removes actions for assessment from response', function (done) {
        vm.removeRelatedItem(item, type);

        dfd.always(() => {
          expect(assessment.attr('actions')).toBeUndefined();
          done();
        });
      });
    });

    describe('if deferredSave was rejected ', () => {
      beforeEach(function () {
        dfd.reject(assessment);
      });

      it('shows error', function (done) {
        vm.removeRelatedItem(item, type);
        dfd.fail(() => {
          expect(NotifiersUtils.notifier).toHaveBeenCalledWith(
            'error',
            'Unable to remove URL.'
          );
          done();
        });
      });

      it('inserts removed item from {<passed type>} list at previous place',
        function (done) {
          vm.removeRelatedItem(item, type);
          dfd.fail(() => {
            expect(items.indexOf(item)).not.toBe(-1);
            done();
          });
        });

      it('sets "isUpdating{<passed capitalized type>}" property to false',
        function (done) {
          const expectedProp = `isUpdating${loCapitalize(type)}`;

          vm.removeRelatedItem(item, type);

          dfd.always(() => {
            expect(vm.attr(expectedProp)).toBe(false);
            done();
          });
        });

      it('removes actions for assessment from response', function (done) {
        vm.removeRelatedItem(item, type);

        dfd.always(() => {
          expect(assessment.attr('actions')).toBeUndefined();
          done();
        });
      });
    });
  });

  describe('updateRelatedItems() method', () => {
    let dfd;

    beforeEach(function () {
      dfd = $.Deferred();
      vm.attr('instance', {});
      vm.attr('instance').getRelatedObjects =
        jasmine.createSpy('getRelatedObjects').and.returnValue(dfd);
    });

    it('sets isUpdatingRelatedItems property to true', function () {
      const prop = 'isUpdatingRelatedItems';
      vm.attr(prop, false);
      vm.updateRelatedItems();
      expect(vm.attr(prop)).toBe(true);
    });

    describe('when related objects were received successfully', () => {
      let data;

      beforeEach(() => {
        data = {
          'Evidence:FILE': [],
          'Evidence:URL': [],
        };
        dfd.resolve(data);
      });

      it('replaces mappedSnapshots list with loaded mapped snapshots',
        function (done) {
          data.Snapshot = {data: '1'};
          vm.updateRelatedItems().then(() => {
            expect(vm.attr('mappedSnapshots').serialize()).toEqual([
              data.Snapshot,
            ]);
            done();
          });
        });

      it('creates Evidence model for each loaded file', function (done) {
        data['Evidence:FILE'] = [{data: '1'}, {data: '2'}];
        vm.updateRelatedItems().then(() => {
          vm.attr('files').forEach((file) => {
            expect(file).toEqual(jasmine.any(Evidence));
          });
          done();
        });
      });

      it('replaces urls list with loaded urls', function (done) {
        let evidenceData = {data: '1'};
        data['Evidence:URL'] = [evidenceData];

        vm.updateRelatedItems().then(() => {
          expect(vm.attr('urls')[0].serialize()).toEqual(
            (new Evidence(evidenceData)).serialize()
          );
          done();
        });
      });

      it('creates Evidence model for each loaded url', function (done) {
        data['Evidence:URL'] = [{data: '1'}, {data: '2'}];
        vm.updateRelatedItems().then(() => {
          vm.attr('urls').forEach((url) => {
            expect(url).toEqual(jasmine.any(Evidence));
          });
          done();
        });
      });

      it('sets isUpdatingRelatedItems to false', function (done) {
        vm.updateRelatedItems().then(() => {
          expect(vm.attr('isUpdatingRelatedItems')).toBe(false);
          done();
        });
      });

      it('dispatches RELATED_ITEMS_LOADED for the instance', function (done) {
        const dispatchSpy = jasmine.createSpy('dispatch');
        vm.attr('instance').dispatch = dispatchSpy;
        vm.updateRelatedItems().then(() => {
          expect(dispatchSpy).toHaveBeenCalledWith(RELATED_ITEMS_LOADED);
          done();
        });
      });
    });
  });

  describe('loadFirstComments() method', () => {
    beforeEach(() => {
      spyOn(commentsUtils, 'loadComments');
    });

    it('loads default comments count if not defined', () => {
      commentsUtils.loadComments
        .and.returnValue(Promise.resolve({Comment: {values: []}}));
      vm.attr('commentsPerPage', 20);

      let instance = vm.attr('instance');

      vm.loadFirstComments();

      expect(commentsUtils.loadComments)
        .toHaveBeenCalledWith(instance, 'Comment', 0, 20);
    });

    it('loads needed comments count', () => {
      commentsUtils.loadComments
        .and.returnValue(Promise.resolve({Comment: {values: []}}));
      let instance = vm.attr('instance');

      vm.loadFirstComments(15);

      expect(commentsUtils.loadComments)
        .toHaveBeenCalledWith(instance, 'Comment', 0, 15);
    });

    it('loads more comments if they are added by current user', () => {
      commentsUtils.loadComments
        .and.returnValue(Promise.resolve({Comment: {values: []}}));
      vm.attr('newCommentsCount', 20);

      let instance = vm.attr('instance');

      vm.loadFirstComments(5);

      expect(commentsUtils.loadComments)
        .toHaveBeenCalledWith(instance, 'Comment', 0, 25);
    });

    it('sets comments if loaded', async () => {
      vm.attr('comments', []);
      commentsUtils.loadComments.and.returnValue(Promise.resolve({
        Comment: {
          total: 3,
          values: [{}, {}, {}],
        },
      }));

      await vm.loadFirstComments();

      expect(vm.attr('comments').length).toBe(3);
    });

    it('replaces new comments with loaded', async () => {
      vm.attr('comments', [{id: 3}, {id: 1}]);
      vm.attr('newCommentsCount', 1);

      let instance = vm.attr('instance');

      commentsUtils.loadComments.and.returnValue(Promise.resolve({
        Comment: {
          total: 3,
          values: [{id: 4}, {id: 3}, {id: 2}],
        },
      }));

      await vm.loadFirstComments(2);

      expect(commentsUtils.loadComments)
        .toHaveBeenCalledWith(instance, 'Comment', 0, 3);

      expect(vm.attr('comments').length).toBe(4);

      vm.attr('comments').forEach((comment, index) => {
        expect(comment.id).toBe(4 - index);
      });
    });

    it('sets commentsTotalCount if comments are loaded', async () => {
      vm.attr('commentsTotalCount', 0);
      commentsUtils.loadComments.and.returnValue(Promise.resolve({
        Comment: {
          total: 3,
          values: [{}, {}, {}],
        },
      }));

      await vm.loadFirstComments();

      expect(vm.attr('commentsTotalCount')).toBe(3);
    });

    it('resets newCommentsCount', async () => {
      commentsUtils.loadComments.and.returnValue(Promise.resolve({
        Comment: {
          total: 3,
          values: [{}, {}, {}],
        },
      }));

      vm.attr('newCommentsCount', 20);

      await vm.loadFirstComments(5);

      expect(vm.attr('newCommentsCount')).toBe(0);
    });
  });

  describe('loadMoreComments() method', () => {
    beforeEach(() => {
      spyOn(commentsUtils, 'loadComments');
    });

    it('loads next comments', () => {
      vm.attr('comments', [{}, {}]);
      vm.attr('commentsPerPage', 20);

      commentsUtils.loadComments.and.returnValue(Promise.resolve({
        Comment: {
          total: 0,
          values: [],
        },
      }));

      let instance = vm.attr('instance');

      vm.loadMoreComments();

      expect(commentsUtils.loadComments)
        .toHaveBeenCalledWith(instance, 'Comment', 2, 20);
    });

    it('loads comments from defined index', () => {
      vm.attr('comments', [{}, {}]);
      vm.attr('commentsPerPage', 20);

      commentsUtils.loadComments.and.returnValue(Promise.resolve({
        Comment: {
          total: 0,
          values: [],
        },
      }));

      let instance = vm.attr('instance');

      vm.loadMoreComments(5);

      expect(commentsUtils.loadComments)
        .toHaveBeenCalledWith(instance, 'Comment', 5, 20);
    });

    it('adds loaded comments to collection if there are no new comments',
      async () => {
        vm.attr('commentsTotalCount', 2);
        vm.attr('comments', []);

        commentsUtils.loadComments.and.returnValue(Promise.resolve({
          Comment: {
            total: 2,
            values: [{}, {}],
          },
        }));

        await vm.loadMoreComments();

        expect(vm.attr('comments').length).toBe(2);
      });

    it('loads new and next comments if new comments are added by another users',
      async () => {
        vm.attr('commentsTotalCount', 20);
        vm.attr('comments', [{}, {}]);

        spyOn(vm, 'loadFirstComments');
        spyOn(vm, 'loadMoreComments');
        vm.loadMoreComments.withArgs().and.callThrough();
        vm.loadMoreComments.withArgs(jasmine.any(Number));

        commentsUtils.loadComments.and.returnValue(Promise.resolve({
          Comment: {
            total: 25,
            values: [{}, {}, {}],
          },
        }));

        await vm.loadMoreComments();

        expect(vm.attr('comments').length).toBe(2);
        expect(vm.loadFirstComments).toHaveBeenCalledWith(5);
        expect(vm.loadMoreComments).toHaveBeenCalledWith(7);
      });

    it('turns on/off isLoadingComments flag if loaded successfully', (done) => {
      vm.attr('isLoading', false);

      commentsUtils.loadComments
        .and.returnValue(Promise.resolve({
          Comment: {
            total: 0,
            values: [],
          },
        }));

      vm.loadMoreComments()
        .finally(() => {
          expect(vm.attr('isLoadingComments')).toBe(false);
          done();
        });

      expect(vm.attr('isLoadingComments')).toBe(true);
    });

    it('turns on/off isLoadingComments flag if loading failed', (done) => {
      vm.attr('isLoading', false);

      commentsUtils.loadComments.and.returnValue(Promise.reject());

      vm.loadMoreComments()
        .catch(() => {
          expect(vm.attr('isLoadingComments')).toBe(false);
          done();
        });

      expect(vm.attr('isLoadingComments')).toBe(true);
    });
  });

  describe('initializeFormFields() method', () => {
    let results;

    beforeEach(function () {
      vm.attr({
        formFields: [],
        instance: {},
      });
      results = [1, 2, 3];
      spyOn(caUtils, 'getCustomAttributes');
      spyOn(caUtils, 'convertValuesToFormFields');
    });

    it('gets CA with help getCustomAttributes', function () {
      vm.initializeFormFields();
      expect(caUtils.getCustomAttributes).toHaveBeenCalledWith(
        vm.attr('instance'), caUtils.CUSTOM_ATTRIBUTE_TYPE.LOCAL
      );
    });

    it('assigns converted CA values to form fields', function () {
      caUtils.getCustomAttributes.and.returnValue(results);
      caUtils.convertValuesToFormFields.and.returnValue(results);
      vm.initializeFormFields();
      expect(
        vm.attr('formFields').serialize()
      ).toEqual(results);
      expect(caUtils.convertValuesToFormFields).toHaveBeenCalledWith(results);
    });
  });

  describe('initGlobalAttributes() method', () => {
    beforeEach(function () {
      vm.attr('instance', {
        customAttr: jasmine.createSpy('customAttr'),
      });
    });

    it('sets global custom attributes', function () {
      const expectedResult = new canList([]);
      const customAttr = vm.attr('instance').customAttr;
      customAttr.and.returnValue(expectedResult);

      vm.initGlobalAttributes();

      expect(customAttr).toHaveBeenCalledWith({
        type: CUSTOM_ATTRIBUTE_TYPE.GLOBAL,
      });
      expect(vm.attr('globalAttributes')).toBe(expectedResult);
    });
  });

  describe('initializeDeferredSave() method', () => {
    beforeEach(function () {
      vm.attr('deferredSave', {});
    });

    describe('calls a DeferredTransaction constructor for deferredSave with' +
    'specified params, where', () => {
      let args;
      let ARGS_ORDER;

      beforeAll(function () {
        ARGS_ORDER = {
          CALLBACK: 0,
          TIMEOUT: 1,
        };
      });

      beforeEach(function () {
        const dfdT = spyOn(DeferredTransactionUtil, 'default');
        vm.initializeDeferredSave();
        args = dfdT.calls.argsFor(0);
      });

      it('completeTransaction param is a function', function () {
        expect(
          args[ARGS_ORDER.CALLBACK]
        ).toEqual(jasmine.any(Function));
      });

      it('timeout param is 1000ms', function () {
        expect(
          args[ARGS_ORDER.TIMEOUT]
        ).toBe(1000);
      });

      describe('completeTransaction function', () => {
        let completeTransaction;
        let resolveFunc;
        let rejectFunc;
        let dfd;

        beforeEach(() => {
          dfd = $.Deferred();
          completeTransaction = args[ARGS_ORDER.CALLBACK];
          vm.attr('instance', {
            save: jasmine.createSpy('save').and.returnValue(dfd),
          });
          resolveFunc = jasmine.createSpy('resolveFunc');
          rejectFunc = jasmine.createSpy('rejectFunc');
        });

        it('saves instance', function () {
          completeTransaction();
          expect(vm.attr('instance').save).toHaveBeenCalled();
        });

        it('calls passed resolve function if the saving was resolved',
          function (done) {
            dfd.resolve();
            completeTransaction(resolveFunc, rejectFunc);
            dfd.done(() => {
              expect(resolveFunc).toHaveBeenCalled();
              expect(rejectFunc).not.toHaveBeenCalled();
              done();
            });
          });

        it('calls passed reject function if the saving was rejected',
          function (done) {
            dfd.reject();
            completeTransaction(resolveFunc, rejectFunc);
            dfd.fail(function () {
              expect(rejectFunc).toHaveBeenCalled();
              expect(resolveFunc).not.toHaveBeenCalled();
              done();
            });
          });
      });
    });
  });

  describe('beforeStatusSave() method', () => {
    const defaultAssessmentStatus = 'DefaultStatus';
    beforeEach(() => {
      vm.attr('instance', {
        status: defaultAssessmentStatus,
      });

      vm.attr('previousStatus', undefined);
    });

    it('should set new status', () => {
      const newStatus = 'NewAssessmnetStatus';
      vm.beforeStatusSave.call(vm, newStatus, false);

      expect(vm.attr('instance.status')).toEqual(newStatus);
      expect(vm.attr('previousStatus')).toEqual(defaultAssessmentStatus);
    });

    it('should set previous status. Undo is TRUE', () => {
      const newStatus = 'NewAssessmnetStatus';
      vm.attr('previousStatus', defaultAssessmentStatus);

      vm.beforeStatusSave.call(vm, newStatus, true);

      expect(vm.attr('instance.status')).toEqual(defaultAssessmentStatus);
      expect(vm.attr('previousStatus')).toBe(undefined);
    });
  });

  describe('onStateChange() method', () => {
    let method;
    let instanceSave;

    beforeEach(() => {
      const {'default': DeferredTransaction} = DeferredTransactionUtil;
      instanceSave = $.Deferred();
      method = vm.onStateChange.bind(vm);
      spyOn(tracker, 'start').and.returnValue(() => {});
      vm.attr('instance', makeFakeInstance({
        model: businessModels.Assessment,
        instanceProps: {
          save() {
            return instanceSave;
          },
          validateGCAs: jasmine.createSpy('validateGCAs'),
        },
      })());
      vm.attr('deferredSave', new DeferredTransaction((resolve, reject) => {
        vm.attr('instance').save().done(resolve).fail(reject);
      }, 0, true));
      spyOn(vm, 'initializeFormFields').and.returnValue(() => {});
      spyOn(NotifiersUtils, 'notifier');
    });

    it('prevents state change to deprecated for archived instance', (done) => {
      vm.attr('instance.archived', true);
      vm.attr('instance.status', 'Completed');

      method({
        state: vm.attr('deprecatedState'),
      }).then(() => {
        expect(vm.attr('instance.status')).toBe('Completed');
        done();
      });
    });

    it('prevents state change to initial for archived instance', (done) => {
      vm.attr('instance.archived', true);
      vm.attr('instance.status', 'Completed');

      method({
        state: vm.attr('initialState'),
      }).then(() => {
        expect(vm.attr('instance.status')).toBe('Completed');
        done();
      });
    });

    it('prevents completing assessment when mandatory GCAs are not filled in',
      () => {
        let instance = vm.attr('instance');
        instance.attr('status', 'In Progress');

        method({state: 'In Review'});

        expect(NotifiersUtils.notifier)
          .toHaveBeenCalledWith('error', jasmine.any(String));
      });

    it('should set status from response', (done) => {
      const newStatus = 'new status';
      const newStatusFromResponse = 'status from response';
      const currentStatus = 'current status';

      vm.attr('currentState', currentStatus);
      instanceSave.resolve();

      spyOn(vm.attr('deferredSave'), 'execute').and.
        returnValue($.Deferred().resolve(
          {status: newStatusFromResponse}
        ));

      method({
        undo: false,
        status: newStatus,
      }).then(() => {
        expect(vm.attr('currentState')).toBe(newStatusFromResponse);
        done();
      });
    });

    it('resets status after conflict', (done) => {
      vm.attr('instance.status', 'Baz');
      instanceSave.reject({}, {
        status: 409,
        remoteObject: {
          status: 'Foo',
        },
      });

      method({
        status: 'Bar',
      }).fail(() => {
        expect(vm.attr('instance.status')).toBe('Foo');
        done();
      });
    });
  });

  describe('saveGlobalAttributes() method', () => {
    let event;

    beforeEach(function () {
      event = {
        globalAttributes: [],
      };
      vm.attr('instance', {});
    });

    it('adds deferred transaction', function () {
      const push = jasmine.createSpy('push');
      vm.attr('deferredSave', {push});
      vm.saveGlobalAttributes(event);
      expect(push).toHaveBeenCalledWith(jasmine.any(Function));
    });

    describe('added deferred transaction', function () {
      let action;
      let customAttr;

      beforeEach(function () {
        const push = jasmine.createSpy('push');
        customAttr = jasmine.createSpy('customAttr');
        vm.attr('instance', {customAttr});
        vm.attr('deferredSave', {push});
        vm.saveGlobalAttributes(event);
        action = push.calls.argsFor(0)[0];
      });

      it('sets global custom attributes from passed event object', function () {
        event.globalAttributes = new canMap({
          '123': 'Value',
          '2': 'Value2',
        });
        action();
        expect(customAttr).toHaveBeenCalledWith('123', 'Value');
        expect(customAttr).toHaveBeenCalledWith('2', 'Value2');
      });
    });
  });

  describe('showRequiredInfoModal() method', () => {
    let event;

    beforeEach(function () {
      const field = new canMap({
        title: 'Perfect Title',
        type: 'Perfect Type',
        options: [],
        value: {},
        errorsMap: {
          error1: true,
          error2: false,
          error3: false,
        },
        saveDfd: {},
      });
      event = {field};
    });

    describe('sets for modal.content', () => {
      let field;

      beforeEach(function () {
        field = event.field;
      });

      it('"options" field', function () {
        const expectedResult = field.attr('options');
        vm.showRequiredInfoModal(event);
        expect(vm.attr('modal.content.options')).toBe(expectedResult);
      });

      it('"contextScope" field', function () {
        const expectedResult = field;
        vm.showRequiredInfoModal(event);
        expect(vm.attr('modal.content.contextScope')).toBe(expectedResult);
      });

      it('"fields" field', function () {
        const errors = field.errorsMap;
        const expectedResult = canMap.keys(errors)
          .map((error) => errors[error] ? error : null)
          .filter((errorCode) => !!errorCode);
        vm.showRequiredInfoModal(event);
        expect(vm.attr('modal.content.fields').serialize())
          .toEqual(expectedResult);
      });

      it('"value" field', function () {
        const expectedResult = field.attr('value');
        vm.showRequiredInfoModal(event);
        expect(vm.attr('modal.content.value')).toBe(expectedResult);
      });

      it('"title" field', function () {
        const expectedResult = field.attr('title');
        vm.showRequiredInfoModal(event);
        expect(vm.attr('modal.content.title')).toBe(expectedResult);
      });

      it('"type" field', function () {
        const expectedResult = field.attr('type');
        vm.showRequiredInfoModal(event);
        expect(vm.attr('modal.content.type')).toBe(expectedResult);
      });

      describe('"saveDfd" field with', () => {
        it('deferred object from event.saveDfd field', function () {
          const expectedResult = $.Deferred();
          event.saveDfd = expectedResult;
          vm.showRequiredInfoModal(event);
          expect(vm.attr('modal.content.saveDfd').serialize())
            .toEqual(expectedResult);
        });

        it('resolved deferred object, if there is no event.saveDfd',
          function (done) {
            event.saveDfd = null;
            vm.showRequiredInfoModal(event);
            vm.attr('modal.content.saveDfd').then(done);
          });
      });
    });

    it('sets modal.modalTitle through getLCAPopupTitle', () => {
      const title = 'something';
      const expectedResult = `Required ${title}`;
      spyOn(caUtils, 'getLCAPopupTitle').and.returnValue(title);
      vm.showRequiredInfoModal(event);
      expect(vm.attr('modal.modalTitle')).toBe(expectedResult);
      expect(caUtils.getLCAPopupTitle).toHaveBeenCalledWith(
        event.field.attr('errorsMap'));
    });

    it('sets modal.state.open field to true', () => {
      vm.showRequiredInfoModal(event);
      expect(vm.attr('modal.state.open')).toBe(true);
    });
  });

  describe('setVerifierRoleId() method', () => {
    beforeEach(function () {
      spyOn(aclUtils, 'getRole');
    });

    it('assigns null to vm._verifierRoleId if there is no role for ' +
    'Assessment.Verifiers', function () {
      aclUtils.getRole.and.returnValue(undefined);
      vm.setVerifierRoleId();
      expect(vm.attr('_verifierRoleId')).toBeNull();
    });

    it('assigns role id (for "Assessment" type and "Verifiers" role name) ' +
    'to vm._verifierRoleId if it exists', function () {
      const verifierRole = {id: 1};
      aclUtils.getRole.and.returnValue(verifierRole);
      vm.setVerifierRoleId();
      expect(vm.attr('_verifierRoleId')).toBe(verifierRole.id);
    });
  });

  describe('component scope', () => {
    let fakeComponent;

    beforeEach(function () {
      fakeComponent = {viewModel: vm};
    });

    describe('init() method', () => {
      let init;

      beforeEach(function () {
        init = Component.prototype.init.bind(fakeComponent);
        spyOn(vm, 'initializeFormFields');
        spyOn(vm, 'initGlobalAttributes');
        spyOn(vm, 'updateRelatedItems');
        spyOn(vm, 'initializeDeferredSave');
        spyOn(vm, 'setVerifierRoleId');
        spyOn(vm, 'loadFirstComments');
      });

      it('calls vm.initializeFormFields method', function () {
        init();
        expect(vm.initializeFormFields).toHaveBeenCalled();
      });

      it('calls vm.initGlobalAttributes method', function () {
        init();
        expect(vm.initGlobalAttributes).toHaveBeenCalled();
      });

      it('calls vm.updateRelatedItems method', function () {
        init();
        expect(vm.updateRelatedItems).toHaveBeenCalled();
      });

      it('calls initializeDeferredSave method', function () {
        init();
        expect(vm.initializeDeferredSave).toHaveBeenCalled();
      });

      it('calls setVerifierRoleId method', function () {
        init();
        expect(vm.setVerifierRoleId).toHaveBeenCalled();
      });

      it('calls loadFirstComments method', function () {
        init();
        expect(vm.loadFirstComments).toHaveBeenCalled();
      });
    });

    describe('"{vm.instance} ${REFRESH_MAPPING.type}"() event handler',
      () => {
        let event;
        let snapshots;
        let evObject;

        beforeEach(function () {
          const eventName = `{viewModel.instance} ${REFRESH_MAPPING.type}`;
          event = Component.prototype.events[eventName].bind(fakeComponent);
          snapshots = {
            data: 'Important data',
          };
          spyOn(vm, 'loadSnapshots').and.returnValue(snapshots);
          vm.attr('instance', {});
          evObject = {};
        });

        it('assigns loaded snapshots to vm.mappedSnapshots field',
          function () {
            event([{}], evObject);
            const result = vm.attr('mappedSnapshots').serialize();
            expect(vm.loadSnapshots).toHaveBeenCalled();
            expect(result).toEqual([snapshots]);
          });

        it('dispatches REFRESH_RELATED event with appropriate model name',
          function () {
            const dispatch = spyOn(vm.attr('instance'), 'dispatch');
            evObject.destinationType = 'Type';
            event([{}], evObject);
            expect(dispatch).toHaveBeenCalledWith({
              ...REFRESH_RELATED,
              model: evObject.destinationType,
            });
          });
      });

    describe('"{vm.instance} modelBeforeSave"() event handler',
      () => {
        let event;

        beforeEach(function () {
          const eventName = '{viewModel.instance} modelBeforeSave';
          event = Component.prototype.events[eventName].bind(fakeComponent);
        });

        it('sets vm.isAssessmentSaving to true', function () {
          event();
          const result = vm.attr('isAssessmentSaving');
          expect(result).toBe(true);
        });
      });

    describe('"{vm.instance} modelAfterSave"() event handler',
      () => {
        let event;

        beforeEach(function () {
          spyOn(vm, 'getStateDisplayName');
          const eventName = '{viewModel.instance} modelAfterSave';
          event = Component.prototype.events[eventName].bind(fakeComponent);
        });

        it('sets vm.isAssessmentSaving to false', function () {
          event();
          const result = vm.attr('isAssessmentSaving');
          expect(result).toBe(false);
        });
      });

    describe('{vm.instance} assessment_type', () => {
      let event;

      beforeEach(function () {
        const eventName = '{viewModel.instance} assessment_type';
        event = Component.prototype.events[eventName].bind(fakeComponent);
        vm.attr('instance', {});
      });

      it('binds "updated" handler', function () {
        spyOn(vm.instance, 'bind');
        event();
        expect(vm.instance.bind).toHaveBeenCalledWith(
          'updated',
          jasmine.any(Function)
        );
      });

      describe('when "updated" event was triggered on the instance', () => {
        beforeEach(function () {
          event();
        });

        it('dispatches refresh related event with appropriate data',
          function (done) {
            const instance = vm.attr('instance');
            instance.bind(REFRESH_RELATED.type, (event) => {
              expect(event.model).toBe('Related Assessments');
              done();
            });
            instance.dispatch('updated');
          });

        it('unbinds "updated" event from the instance', function () {
          const instance = vm.attr('instance');
          spyOn(instance, 'unbind');
          instance.dispatch('updated');
          expect(instance.unbind).toHaveBeenCalledWith(
            'updated',
            jasmine.any(Function)
          );
        });
      });
    });

    describe('"{viewModel} instance"() event handler', () => {
      let event;

      beforeEach(function () {
        const eventName = '{viewModel} instance';
        event = Component.prototype.events[eventName].bind(fakeComponent);
        spyOn(vm, 'initializeFormFields');
        spyOn(vm, 'initGlobalAttributes');
        spyOn(vm, 'updateRelatedItems');
        spyOn(vm, 'loadFirstComments');
        spyOn(vm, 'getStateDisplayName');
      });

      it('calls vm.initializeFormFields method', function () {
        event();
        expect(vm.initializeFormFields).toHaveBeenCalled();
      });

      it('calls vm.initGlobalAttributes method', function () {
        event();
        expect(vm.initGlobalAttributes).toHaveBeenCalled();
      });

      it('calls vm.updateRelatedItems method', function () {
        event();
        expect(vm.updateRelatedItems).toHaveBeenCalled();
      });

      it('calls vm.loadFirstComments method', function () {
        event();
        expect(vm.loadFirstComments).toHaveBeenCalled();
      });

      it('resets comments props', () => {
        vm.attr('comments', [{}, {}]);
        vm.attr('commentsTotalCount', 2);

        event();

        expect(vm.attr('comments').length).toBe(0);
        expect(vm.attr('commentsTotalCount')).toBe(0);
      });
    });
  });

  describe('saveGlobalAttributes() method', () => {
    let method;
    let event;

    beforeEach(() => {
      method = vm.saveGlobalAttributes.bind(vm);
      vm.attr('deferredSave', {
        push: jasmine.createSpy(),
      });
      vm.attr('instance', {
        customAttr: jasmine.createSpy(),
      });
    });

    it('pushes callback into deferredSave which calls customAttr method',
      () => {
        event = {
          globalAttributes: new canMap({'1': true}),
        };

        method(event);

        let callback = vm.attr('deferredSave').push.calls.allArgs()[0][0];
        callback();
        expect(vm.attr('instance').customAttr).toHaveBeenCalledWith('1', true);
      });
  });

  describe('"instance updated" event', () => {
    let handler;
    let viewModel;
    let instance;

    beforeEach(() => {
      const {'default': DeferredTransaction} = DeferredTransactionUtil;

      viewModel = getComponentVM(Component);
      viewModel.attr('deferredSave', new DeferredTransaction());
      spyOn(viewModel, 'reinitFormFields');

      let eventContext = {
        viewModel,
      };

      instance = jasmine.createSpyObj(['backup']);

      let events = Component.prototype.events;
      handler = events['{viewModel.instance} updated'].bind(eventContext);
    });

    it('should NOT call "reinitFormFields" method' +
    'if "deferredSave" queue is NOT empty', () => {
      spyOn(viewModel.attr('deferredSave'), 'isPending')
        .and.returnValue(true);

      handler([instance]);
      expect(viewModel.reinitFormFields.calls.count()).toBe(0);
    });

    it('should call "reinitFormFields" method' +
    'if "deferredSave" queue is empty', () => {
      spyOn(viewModel.attr('deferredSave'), 'isPending')
        .and.returnValue(false);

      handler([instance]);
      expect(viewModel.reinitFormFields.calls.count()).toBe(1);
    });

    it('should make a backup of instance', () => {
      handler([instance]);

      expect(instance.backup).toHaveBeenCalled();
    });
  });

  describe('reinitFormFields() method', () => {
    beforeEach(() => {
      vm.attr({
        formFields: [],
      });
      spyOn(caUtils, 'getCustomAttributes');
    });

    it('should update all values. Equal ids', () => {
      let currentFormFields = [
        {id: 1, value: 'text_val #1'},
        {id: 2, value: 'text_val #2'},
        {id: 3, value: 'text_val #3'},
      ];

      let updatedFormFields = new canList([
        {id: 1, value: 'text_val #1'},
        {id: 2, value: 'text_val #_2'},
        {id: 3, value: 'text_val #3'},
      ]);

      vm.attr('formFields', currentFormFields);
      spyOn(caUtils, 'convertValuesToFormFields')
        .and.returnValue(updatedFormFields);

      vm.reinitFormFields();

      let formFields = vm.attr('formFields');
      formFields.forEach((formField, index) => {
        expect(formField.attr('value'))
          .toEqual(updatedFormFields[index].attr('value'));
      });
    });

    it('should update values of form fields with equal ids', () => {
      let currentFormFields = [
        {id: 1, value: 'text_val #1'},
        {id: 2, value: 'text_val #2'},
        {id: 3, value: 'text_val #3'},
      ];

      let updatedFormFields = new canList([
        {id: 11, value: 'text_val #11'},
        {id: 2, value: 'text_val #_2'},
        {id: 33, value: 'text_val #33'},
        {id: 44, value: 'text_val #33'},
      ]);

      vm.attr('formFields', currentFormFields);
      spyOn(caUtils, 'convertValuesToFormFields')
        .and.returnValue(updatedFormFields);

      vm.reinitFormFields();

      let formFields = vm.attr('formFields');
      expect(formFields[0].attr('value'))
        .toEqual(currentFormFields[0].value);
      expect(formFields[1].attr('value'))
        .toEqual(updatedFormFields[1].attr('value'));
      expect(formFields[2].attr('value'))
        .toEqual(currentFormFields[2].value);
    });

    it('should NOT update count of form fields', () => {
      let currentFormFields = [
        {id: 1, value: 'text_val #1'},
        {id: 2, value: 'text_val #2'},
        {id: 3, value: 'text_val #3'},
      ];

      let updatedFormFields = new canList([
        {id: 1, value: 'text_val #1'},
        {id: 2, value: 'text_val #22'},
        {id: 3, value: 'text_val #3'},
        {id: 4, value: 'text_val #4'},
      ]);

      vm.attr('formFields', currentFormFields);
      spyOn(caUtils, 'convertValuesToFormFields')
        .and.returnValue(updatedFormFields);

      vm.reinitFormFields();

      let formFields = vm.attr('formFields');
      expect(formFields.length).toBe(currentFormFields.length);
    });
  });
});
