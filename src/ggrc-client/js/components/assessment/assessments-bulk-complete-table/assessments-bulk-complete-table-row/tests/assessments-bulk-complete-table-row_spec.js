/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../assessments-bulk-complete-table-row';
import {getComponentVM} from '../../../../../../js_specs/spec-helpers';
import pubSub from '../../../../../pub-sub';
import * as CaUtils from '../../../../../plugins/utils/ca-utils';
import * as GgrcUtils from '../../../../../plugins/ggrc-utils';

describe('assessments-bulk-complete-table-row component', () => {
  let viewModel;

  beforeEach(() => {
    viewModel = getComponentVM(Component);
  });

  describe('isFileRequired getter', () => {
    it('returns true if required files count is more than current files count',
      () => {
        spyOn(viewModel, 'getRequiredInfoCountByType')
          .withArgs('attachment')
          .and.returnValue(2);
        spyOn(viewModel, 'getCurrentFilesCount').and.returnValue(0);

        expect(viewModel.isFileRequired).toBe(true);
      });

    it('returns false if required files count is less than current files count',
      () => {
        spyOn(viewModel, 'getRequiredInfoCountByType')
          .withArgs('attachment')
          .and.returnValue(1);
        spyOn(viewModel, 'getCurrentFilesCount').and.returnValue(2);

        expect(viewModel.isFileRequired).toBe(false);
      });
  });

  describe('isUrlRequired getter', () => {
    it('returns true if required urls count is more than current urls count',
      () => {
        spyOn(viewModel, 'getRequiredInfoCountByType')
          .withArgs('url')
          .and.returnValue(2);
        spyOn(viewModel, 'getCurrentUrlsCount').and.returnValue(0);

        expect(viewModel.isUrlRequired).toBe(true);
      });

    it('returns false if required urls count is less than current urls count',
      () => {
        spyOn(viewModel, 'getRequiredInfoCountByType')
          .withArgs('url')
          .and.returnValue(1);
        spyOn(viewModel, 'getCurrentUrlsCount').and.returnValue(2);

        expect(viewModel.isUrlRequired).toBe(false);
      });
  });

  describe('getRequiredInfoCountByType() method', () => {
    it('returns count of dropdown attributes with "url" required info type',
      () => {
        const dropdownAttributes = [{
          isApplicable: true,
          type: 'dropdown',
          value: '2',
          multiChoiceOptions: {
            config: new Map([['1', 2], ['2', 4], ['3', 1]]),
          },
        }];
        spyOn(viewModel, 'getApplicableDropdownAttributes')
          .and.returnValue(dropdownAttributes);
        spyOn(viewModel, 'getRequiredInfoStates')
          .withArgs(dropdownAttributes[0])
          .and.returnValue({
            file: true,
            url: true,
            comment: false,
          });

        expect(viewModel.getRequiredInfoCountByType('url')).toBe(1);
      });
  });


  describe('getCurrentFilesCount() method', () => {
    it('returns current files count',
      () => {
        viewModel.rowData.filesCount = 2;
        const dropdownAttributes = [{
          attachments: {
            files: ['file1.png'],
          },
        }];
        spyOn(viewModel, 'getApplicableDropdownAttributes')
          .and.returnValue(dropdownAttributes);

        expect(viewModel.getCurrentFilesCount()).toBe(3);
      });
  });

  describe('getCurrentUrlsCount() method', () => {
    it('returns current urls count',
      () => {
        viewModel.rowData.urlsCount = 0;
        const dropdownAttributes = [{
          attachments: {
            urls: ['url1', 'url2'],
          },
        }];
        spyOn(viewModel, 'getApplicableDropdownAttributes')
          .and.returnValue(dropdownAttributes);

        expect(viewModel.getCurrentUrlsCount()).toBe(2);
      });
  });

  describe('getApplicableDropdownAttributes() method', () => {
    it('returns applicable dropdown attributes',
      () => {
        viewModel.rowData = {
          attributes: [{
            id: 1,
            type: 'dropdown',
            isApplicable: true,
          }, {
            id: 2,
            type: 'dropdown',
            isApplicable: false,
          }, {
            id: 3,
            type: 'input',
            isApplicable: true,
          }],
        };

        expect(viewModel.getApplicableDropdownAttributes().serialize())
          .toEqual([{
            id: 1,
            type: 'dropdown',
            isApplicable: true,
          }]);
      });
  });

  describe('validateAllAttributes() method', () => {
    beforeEach(() => {
      viewModel.rowData = {
        attributes: [{
          type: 'input',
          isApplicable: false,
        }, {
          type: 'input',
          isApplicable: true,
        }, {
          type: 'dropdown',
          isApplicable: true,
        }],
      };
      spyOn(viewModel, 'performDropdownValidation');
      spyOn(viewModel, 'performDefaultValidation');
    });

    it('calls performDropdownValidation() if attribute type is "dropdown" ' +
    'and it is applicable', () => {
      viewModel.validateAllAttributes();

      expect(viewModel.performDropdownValidation).toHaveBeenCalledTimes(1);
      expect(viewModel.performDropdownValidation)
        .toHaveBeenCalledWith(viewModel.rowData.attributes[2]);
    });

    it('calls performDefaultValidation() if attribute type is not "dropdown" ' +
    'and it is applicable', () => {
      viewModel.validateAllAttributes();

      expect(viewModel.performDefaultValidation).toHaveBeenCalledTimes(1);
      expect(viewModel.performDefaultValidation)
        .toHaveBeenCalledWith(viewModel.rowData.attributes[1]);
    });
  });

  describe('performDropdownValidation() method', () => {
    let getRequiredInfoStatesSpy;

    beforeEach(() => {
      getRequiredInfoStatesSpy = spyOn(viewModel, 'getRequiredInfoStates');
    });

    describe('if dropdown requires attachments', () => {
      let attribute;

      beforeEach(() => {
        attribute = {
          attachments: {
            comment: 'Some comment',
            urls: [],
            files: [],
          },
          validation: {
            requiresAttachment: false,
            valid: true,
            hasMissingInfo: false,
            hasUnsavedAttachments: false,
          },
          errorsMap: {
            file: false,
            url: false,
            comment: true,
          },
        };

        getRequiredInfoStatesSpy.and.returnValue({
          comment: true,
          attachment: false,
          url: false,
        });
      });

      it('should set true to requiresAttachment attribute', () => {
        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.requiresAttachment).toBe(true);
      });

      it('should set valid attribute to false', () => {
        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.valid).toBe(false);
      });

      it('should set hasMissingInfo attribute to true', () => {
        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.hasMissingInfo).toBe(true);
      });

      it('should set hasUnsavedAttachments attribute to true', () => {
        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.hasUnsavedAttachments).toBe(true);
      });
    });

    describe('if dropdown does not require attachments', () => {
      beforeEach(() => {
        getRequiredInfoStatesSpy.and.returnValue({
          comment: false,
          attachment: false,
          url: false,
        });
      });

      it('should set false to requiresAttachment attribute', () => {
        const attribute = {
          validation: {
            requiresAttachment: true,
          },
        };

        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.requiresAttachment).toBe(false);
      });

      it('should set false to has missing info', () => {
        const attribute = {
          validation: {
            hasMissingInfo: true,
          },
        };

        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.hasMissingInfo).toBe(false);
      });

      it('should set valid to true if attribute is not mandatory', () => {
        const attribute = {
          validation: {
            valid: false,
            mandatory: false,
          },
        };

        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.valid).toBe(true);
      });

      it('should set valid to true if it is mandatory attribute ' +
      'and value is not empty', () => {
        const attribute = {
          value: 'Some text',
          validation: {
            valid: false,
            mandatory: true,
          },
        };

        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.valid).toBe(true);
      });

      it('should set valid to false if it is mandatory attribute ' +
      'and value is empty', () => {
        const attribute = {
          value: '',
          validation: {
            valid: true,
            mandatory: true,
          },
        };

        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.valid).toBe(false);
      });

      it('should set false to hasUnsavedAttachments attribute', () => {
        const attribute = {
          validation: {
            hasUnsavedAttachments: true,
          },
        };

        viewModel.performDropdownValidation(attribute);

        expect(attribute.validation.hasUnsavedAttachments).toBe(false);
      });
    });

    it('should update errorsMap attribute', () => {
      getRequiredInfoStatesSpy.and.returnValue({
        attachment: false,
        url: false,
        comment: false,
      });

      const attribute = {
        validation: {
          requiresAttachment: false,
          valid: false,
          mandatory: false,
          hasMissingInfo: false,
          hasUnsavedAttachments: false,
        },
        errorsMap: {
          attachment: true,
          url: true,
          comment: true,
        },
      };

      viewModel.performDropdownValidation(attribute);

      expect(attribute.errorsMap).toEqual({
        attachment: false,
        url: false,
        comment: false,
      });
    });
  });

  describe('performDefaultValidation() method', () => {
    describe('if type is "text" and attribute is mandatory', () => {
      let getPlainTextSpy;

      beforeEach(() => {
        getPlainTextSpy = spyOn(GgrcUtils, 'getPlainText');
      });

      it('should set valid to true if value is not empty', () => {
        const attribute = {
          type: 'text',
          value: 'Some text',
          validation: {
            mandatory: true,
            valid: false,
          },
        };
        getPlainTextSpy.withArgs('Some text').and.returnValue('Some text');

        viewModel.performDefaultValidation(attribute);

        expect(attribute.validation.valid).toBe(true);
      });

      it('should set valid to false if value is empty', () => {
        const attribute = {
          type: 'text',
          value: '  ',
          validation: {
            mandatory: true,
            valid: false,
          },
        };
        getPlainTextSpy.withArgs('  ').and.returnValue('');

        viewModel.performDefaultValidation(attribute);

        expect(attribute.validation.valid).toBe(false);
      });
    });

    describe('if type is "person" and attribute is mandatory', () => {
      it('should set valid to true if value is not empty', () => {
        const attribute = {
          type: 'person',
          value: [{
            id: 384,
          }],
          validation: {
            mandatory: true,
            valid: false,
          },
        };

        viewModel.performDefaultValidation(attribute);

        expect(attribute.validation.valid).toBe(true);
      });

      it('should set valid to false if value is empty', () => {
        const attribute = {
          type: 'person',
          value: [],
          validation: {
            mandatory: true,
            valid: true,
          },
        };

        viewModel.performDefaultValidation(attribute);

        expect(attribute.validation.valid).toBe(false);
      });
    });

    describe('if type is not "text" or "person" and attribute is mandatory',
      () => {
        it('should set valid to true if value is not empty', () => {
          const attribute = {
            type: 'input',
            value: 'Some text',
            validation: {
              mandatory: true,
              valid: false,
            },
          };

          viewModel.performDefaultValidation(attribute);

          expect(attribute.validation.valid).toBe(true);
        });

        it('should set valid to false if value is empty', () => {
          const attribute = {
            type: 'input',
            value: '',
            validation: {
              mandatory: true,
              valid: true,
            },
          };

          viewModel.performDefaultValidation(attribute);

          expect(attribute.validation.valid).toBe(false);
        });
      });
  });

  describe('getRequiredInfoStates() method', () => {
    let attribute;

    beforeEach(() => {
      attribute = {
        value: '1',
        multiChoiceOptions: {
          config: new Map([['1', 2], ['2', 4], ['3', 1]]),
        },
      };
      spyOn(CaUtils, 'ddValidationValueToMap').and.returnValue({
        comment: false,
        attachment: false,
        url: true,
      });
    });

    it('calls ddValidationValueToMap()', () => {
      viewModel.getRequiredInfoStates(attribute);

      expect(CaUtils.ddValidationValueToMap).toHaveBeenCalledWith(2);
    });

    it('returns config with required info', () => {
      expect(viewModel.getRequiredInfoStates(attribute)).toEqual({
        comment: false,
        attachment: false,
        url: true,
      });
    });
  });

  describe('checkAssessmentReadinessToComplete() method', () => {
    it('returns true if all attributes are valid', () => {
      viewModel.rowData = {
        attributes: [{
          id: 1,
          validation: {
            valid: true,
          },
        }, {
          id: 2,
          validation: {
            valid: true,
          },
        }],
      };

      expect(viewModel.checkAssessmentReadinessToComplete()).toBe(true);
    });

    it('returns false if at least one attribute is invalid', () => {
      viewModel.rowData = {
        attributes: [{
          id: 1,
          validation: {
            valid: true,
          },
        }, {
          id: 2,
          validation: {
            valid: false,
          },
        }],
      };

      expect(viewModel.checkAssessmentReadinessToComplete()).toBe(false);
    });
  });

  describe('attributeValueChanged() method', () => {
    beforeEach(() => {
      viewModel.rowData = {
        attributes: [{
          id: 1,
          type: 'dropdown',
          value: 'Some value',
          modified: false,
          attachments: {
            files: [],
            urls: [],
            comment: null,
          },
          validation: {
            hasMissingInfo: true,
          },
          errorsMap: {
            comment: false,
          },
        }],
      };
      spyOn(viewModel, 'getRequiredInfoStates').and.returnValue({
        comment: true,
      });
      spyOn(viewModel, 'validateAllAttributes');
      spyOn(viewModel, 'showRequiredInfo');
      spyOn(viewModel, 'checkAssessmentReadinessToComplete');
      spyOn(pubSub, 'dispatch');
    });

    it('sets new value to attribute', () => {
      viewModel.attributeValueChanged('New value', 0);

      expect(viewModel.rowData.attributes[0].value).toBe('New value');
    });

    it('sets modified attribute to true', () => {
      viewModel.attributeValueChanged('New value', 0);

      expect(viewModel.rowData.attributes[0].modified).toBe(true);
    });

    it('refreshes attachments attribute', () => {
      viewModel.attributeValueChanged('New value', 0);

      expect(viewModel.rowData.attributes[0].attachments.serialize()).toEqual({
        files: [],
        urls: [],
        comment: null,
      });
    });

    it('sets errorsMap.comment to true if attribute type is dropdown and ' +
    'getRequiredInfoStates().comment returns true', () => {
      viewModel.attributeValueChanged('New value', 0);

      expect(viewModel.rowData.attributes[0].errorsMap.comment).toBe(true);
    });

    it('calls validateAllAttributes()', () => {
      viewModel.attributeValueChanged('New value', 0);

      expect(viewModel.validateAllAttributes).toHaveBeenCalled();
    });

    it('calls showRequiredInfo() if attribute has missing info', () => {
      viewModel.attributeValueChanged('New value', 0);

      expect(viewModel.showRequiredInfo)
        .toHaveBeenCalledWith(viewModel.rowData.attributes[0]);
    });

    it('does not call showRequiredInfo() if attribute has not missing info',
      () => {
        viewModel.rowData.attributes[0].validation.hasMissingInfo = false;

        viewModel.attributeValueChanged('New value', 0);

        expect(viewModel.showRequiredInfo).not.toHaveBeenCalled();
      });
  });

  describe('showRequiredInfo() method', () => {
    let attribute;

    beforeEach(() => {
      viewModel.requiredInfoModal = {
        title: '',
        state: {
          open: false,
        },
        content: {
          attribute: null,
          requiredInfo: null,
          comment: null,
          urls: [],
          files: [],
        },
      };

      attribute = {
        id: 1,
        title: 'LCA dp',
        value: 'Yes',
        attachments: {
          files: [],
          urls: ['url1'],
          comment: null,
        },
      };

      spyOn(viewModel, 'getRequiredInfoConfig').and.returnValue({
        attachment: false,
        url: true,
        comment: false,
      });
      spyOn(CaUtils, 'getLCAPopupTitle').and.returnValue('URL');
    });

    it('calls getRequiredInfoConfig()', () => {
      viewModel.showRequiredInfo(attribute);

      expect(viewModel.getRequiredInfoConfig).toHaveBeenCalledWith(attribute);
    });

    it('calls getRequiredInfoConfig()', () => {
      viewModel.showRequiredInfo(attribute);

      expect(CaUtils.getLCAPopupTitle).toHaveBeenCalledWith({
        attachment: false,
        url: true,
        comment: false,
      });
    });

    it('sets title to requiredInfoModal attribute', () => {
      viewModel.showRequiredInfo(attribute);

      expect(viewModel.requiredInfoModal.title).toBe('Required URL');
    });

    it('sets content to requiredInfoModal attribute', () => {
      viewModel.showRequiredInfo(attribute);

      expect(viewModel.requiredInfoModal.content.serialize()).toEqual({
        attribute: {
          id: 1,
          title: 'LCA dp',
          value: 'Yes',
        },
        requiredInfo: {
          attachment: false,
          url: true,
          comment: false,
        },
        urls: ['url1'],
        files: [],
        comment: null,
      });
    });

    it('sets requiredInfoModal state to open', () => {
      viewModel.showRequiredInfo(attribute);

      expect(viewModel.requiredInfoModal.state.open).toBe(true);
    });
  });

  describe('updateRequiredInfo() method', () => {
    beforeEach(() => {
      viewModel.rowData = {
        isReadyToComplete: false,
        attributes: [{
          id: 1,
          value: 'Some value 1',
          modified: false,
          attachments: {
            files: [],
            urls: [],
            comment: null,
          },
          errorsMap: {
            comment: false,
          },
        }],
      };
      spyOn(viewModel, 'validateAllAttributes');
      spyOn(viewModel, 'checkAssessmentReadinessToComplete')
        .and.returnValue(true);
      spyOn(pubSub, 'dispatch');
    });

    it('replaces attachments with new comment, files and urls', () => {
      viewModel.updateRequiredInfo(1, {
        comment: 'Some comment',
        urls: ['url1'],
        files: ['file1.png'],
      });

      expect(viewModel.rowData.attributes[0].attachments.serialize()).toEqual({
        comment: 'Some comment',
        urls: ['url1'],
        files: ['file1.png'],
      });
    });

    it('sets modified attributes to true', () => {
      viewModel.updateRequiredInfo(1, {
        comment: null,
        urls: ['url1'],
        files: [],
      });

      expect(viewModel.rowData.attributes[0].modified).toBe(true);
    });

    it('sets errorsMap.comment to false if comment was added', () => {
      viewModel.rowData.attributes[0].errorsMap.comment = true;
      viewModel.updateRequiredInfo(1, {
        comment: 'Some comment',
        urls: [],
        files: [],
      });

      expect(viewModel.rowData.attributes[0].errorsMap.comment).toBe(false);
    });

    it('sets errorsMap.comment to true if comment was not added', () => {
      viewModel.updateRequiredInfo(1, {
        comment: null,
        urls: [],
        files: [],
      });

      expect(viewModel.rowData.attributes[0].errorsMap.comment).toBe(true);
    });

    it('calls validateAllAttributes()', () => {
      viewModel.updateRequiredInfo(1, {
        comment: null,
        urls: ['url1'],
        files: [],
      });

      expect(viewModel.validateAllAttributes).toHaveBeenCalled();
    });

    it('sets result of checkAssessmentReadinessToComplete() ' +
    'to isReadyToComplete attribute', () => {
      viewModel.updateRequiredInfo(1, {
        comment: null,
        urls: ['url1'],
        files: [],
      });

      expect(viewModel.rowData.isReadyToComplete).toBe(true);
    });

    it('dispatches "attributeModified" event', () => {
      viewModel.updateRequiredInfo(1, {
        comment: null,
        urls: ['url1'],
        files: [],
      });

      expect(pubSub.dispatch).toHaveBeenCalledWith({
        type: 'attributeModified',
        assessmentData: viewModel.rowData,
      });
    });
  });

  describe('getRequiredInfoConfig() method', () => {
    describe('returns config with required information needed to show ' +
    'in Required Info modal', () => {
      describe('if getRequiredInfoStates().attachment is true', () => {
        let isFileRequiredGetSpy;

        beforeEach(() => {
          spyOn(viewModel, 'getRequiredInfoStates').and.returnValue({
            attachment: true,
            url: false,
            comment: false,
          });
          isFileRequiredGetSpy =
            spyOnProperty(viewModel, 'isFileRequired', 'get');
        });

        it('and file is required', () => {
          const attribute = {
            id: 1,
            attachments: {
              files: [],
            },
          };

          isFileRequiredGetSpy.and.returnValue(true);

          expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
            attachment: true,
            url: false,
            comment: false,
          });
        });

        it('and file is not required and attachments.files is not empty',
          () => {
            const attribute = {
              id: 1,
              attachments: {
                files: ['file1.png'],
              },
            };

            isFileRequiredGetSpy.and.returnValue(false);

            expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
              attachment: true,
              url: false,
              comment: false,
            });
          });

        it('and file is not required and attachments.files is empty', () => {
          const attribute = {
            id: 1,
            attachments: {
              files: [],
            },
          };

          isFileRequiredGetSpy.and.returnValue(false);

          expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
            attachment: false,
            url: false,
            comment: false,
          });
        });
      });

      describe('if getRequiredInfoStates().url is true', () => {
        let isUrlRequiredGetSpy;

        beforeEach(() => {
          spyOn(viewModel, 'getRequiredInfoStates').and.returnValue({
            attachment: false,
            url: true,
            comment: false,
          });
          isUrlRequiredGetSpy =
            spyOnProperty(viewModel, 'isUrlRequired', 'get');
        });

        it('and url is required', () => {
          const attribute = {
            id: 1,
            attachments: {
              urls: [],
            },
          };

          isUrlRequiredGetSpy.and.returnValue(true);

          expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
            attachment: false,
            url: true,
            comment: false,
          });
        });

        it('and url is not required and attachments.urls is not empty',
          () => {
            const attribute = {
              id: 1,
              attachments: {
                urls: ['url1'],
              },
            };

            isUrlRequiredGetSpy.and.returnValue(false);

            expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
              attachment: false,
              url: true,
              comment: false,
            });
          });

        it('and url is not required and attachments.urls is empty', () => {
          const attribute = {
            id: 1,
            attachments: {
              urls: [],
            },
          };

          isUrlRequiredGetSpy.and.returnValue(false);

          expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
            attachment: false,
            url: false,
            comment: false,
          });
        });
      });

      describe('if getRequiredInfoStates().comment is true', () => {
        beforeEach(() => {
          spyOn(viewModel, 'getRequiredInfoStates').and.returnValue({
            attachment: false,
            url: false,
            comment: true,
          });
        });

        it('and comment is required', () => {
          const attribute = {
            id: 1,
            attachments: {
              comment: null,
            },
            errorsMap: {
              comment: true,
            },
          };

          expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
            attachment: false,
            url: false,
            comment: true,
          });
        });

        it('and comment is not required and attachments.comment is not empty',
          () => {
            const attribute = {
              id: 1,
              attachments: {
                comment: 'Some comment',
              },
              errorsMap: {
                comment: false,
              },
            };

            expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
              attachment: false,
              url: false,
              comment: true,
            });
          });

        it('and comment is not required and attachments.comment is empty',
          () => {
            const attribute = {
              id: 1,
              attachments: {
                comment: null,
              },
              errorsMap: {
                comment: false,
              },
            };

            expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
              attachment: false,
              url: false,
              comment: false,
            });
          });
      });

      it('if getRequiredInfoStates() returns false ' +
      'for each required info type', () => {
        spyOn(viewModel, 'getRequiredInfoStates').and.returnValue({
          attachment: false,
          url: false,
          comment: false,
        });

        const attribute = {
          id: 1,
          attachments: {
            files: ['file1.png'],
            urls: ['url1'],
            comment: 'Some comment',
          },
        };

        expect(viewModel.getRequiredInfoConfig(attribute)).toEqual({
          attachment: false,
          url: false,
          comment: false,
        });
      });
    });
  });

  describe('events', () => {
    let events;

    beforeAll(() => {
      events = Component.prototype.events;
    });

    describe('init() handler', () => {
      let checkAsmtReadinessSpy;

      beforeEach(() => {
        viewModel.rowData = {
          asmtId: 1,
          isReadyToComplete: false,
          attributes: [{
            id: 1,
            type: 'input',
          }, {
            id: 2,
            type: 'text',
          }],
        };
        spyOn(viewModel, 'validateAllAttributes');
        checkAsmtReadinessSpy =
          spyOn(viewModel, 'checkAssessmentReadinessToComplete');
        spyOn(pubSub, 'dispatch');
      });

      it('calls validateAllAttributes()', () => {
        events.init.apply({viewModel});

        expect(viewModel.validateAllAttributes).toHaveBeenCalled();
      });

      it('sets result of checkAssessmentReadinessToComplete() ' +
      'to isReadyToComplete attribute', () => {
        checkAsmtReadinessSpy.and.returnValue(true);

        events.init.apply({viewModel});

        expect(viewModel.rowData.isReadyToComplete).toBe(true);
      });

      it('dispatches "assessmentReadyToComplete" event ' +
      'if assessment is ready to complete', () => {
        checkAsmtReadinessSpy.and.returnValue(true);

        events.init.apply({viewModel});

        expect(pubSub.dispatch).toHaveBeenCalledWith({
          type: 'assessmentReadyToComplete',
          assessmentId: 1,
        });
      });

      it('does not dispatch "assessmentReadyToComplete" event ' +
      'if assessment is not ready to complete', () => {
        checkAsmtReadinessSpy.and.returnValue(false);

        events.init.apply({viewModel});

        expect(pubSub.dispatch).not.toHaveBeenCalled();
      });
    });

    describe('{pubSub} requiredInfoSave handler', () => {
      beforeEach(() => {
        viewModel.rowData = {
          asmtId: 1,
          isReadyToComplete: false,
          attributes: [{
            id: 1,
            type: 'input',
          }, {
            id: 2,
            type: 'text',
          }],
        };
        spyOn(viewModel, 'updateRequiredInfo');
      });

      it('calls updateRequiredInfo() if attribute present in the row', () => {
        events['{pubSub} requiredInfoSave'].call({viewModel}, {}, {
          attributeId: 1,
          changes: 'Changes',
        });

        expect(viewModel.updateRequiredInfo).toHaveBeenCalledWith(1, 'Changes');
      });

      it('does not call updateRequiredInfo() ' +
      'if attribute is not present in the row', () => {
        events['{pubSub} requiredInfoSave'].call({viewModel}, {}, {
          attributeId: 3,
          changes: 'Changes',
        });

        expect(viewModel.updateRequiredInfo).not.toHaveBeenCalled();
      });
    });
  });
});
