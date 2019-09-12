/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/


import '../../collapsible-panel/collapsible-panel';
import '../../advanced-search/advanced-search-container/advanced-search-container';

import canComponent from 'can-component';
import canStache from 'can-stache';
import canBatch from 'can-event/batch/batch';
import template from './assessments-bulk-complete.stache';
import ObjectOperationsBaseVM from '../../view-models/object-operations-base-vm';
import {STATES_KEYS} from '../../../plugins/utils/state-utils';
import loFindIndex from 'lodash/findIndex';
import {request} from '../../../plugins/utils/request-utils';
import {confirm} from '../../../plugins/utils/modals';
import {getFetchErrorInfo} from '../../../plugins/utils/errors-utils';
import {notifier} from '../../../plugins/utils/notifiers-utils';

const viewModel = ObjectOperationsBaseVM.extend({
  define: {
    isSelectButtonDisabled: {
      get() {
        return (
          this.attr('isAttributesGenerating') ||
          !this.attr('hasChangedSelection')
        );
      },
    },
    hasChangedSelection: {
      get() {
        return (
          this.attr('selectedAfterLastSelection.length') > 0 ||
          this.attr('deselectedAfterLastSelection.length') > 0
        );
      },
    },
  },
  showSearch: false,
  showFields: false,
  isMyAssessmentsView: false,
  mappedToItems: [],
  filterItems: [],
  mappingItems: [],
  statesCollectionKey: STATES_KEYS.BULK_COMPLETE,
  type: 'Assessment',
  isAttributesGenerating: false,
  attributes: [],
  /**
   * Contains selected objects (which have id and type properties)
   */
  selectedAfterLastSelection: [],
  deselectedAfterLastSelection: [],
  /**
   * Util which removes `newItems`'s items from `collectionForRemove` collection
   * and add them to `collectionForAdd` collection if they were removed from
   * `collectionForRemove`.
   * @param {Array} items - Items for processing
   * @param {canList} collectionForRemove - Collection in which `items` should be
   * removed if they are included in `collectionForRemove`
   * @param {canList} collectionForAdd - Collection which should be filled by the
   * `items` which weren't added to `collectionForRemove`
   */
  updateSelectionCollections(items, collectionForRemove, collectionForAdd) {
    canBatch.start();

    items.forEach((item) => {
      const removeItemIndex = loFindIndex(collectionForRemove,
        (removedItem) => item.attr('id') === removedItem.attr('id'));

      if (removeItemIndex !== -1) {
        collectionForRemove.splice(removeItemIndex, 1);
      } else {
        collectionForAdd.push(item);
      }
    });

    canBatch.stop();
  },
  onSelectClick() {
    if (this.attr('hasChangedSelection')) {
      confirm({
        modal_title: 'Warning',
        modal_description: 'Custom attributes list will be updated ' +
          'accordingly. All already added answers will be lost.',
        button_view:
          `${GGRC.templates_path}/modals/confirm_cancel_buttons.stache`,
        modal_confirm: 'Proceed',
      }, () => this.generateAttributes());
    } else {
      this.generateAttributes();
    }
  },
  async generateAttributes() {
    this.attr('isAttributesGenerating', true);

    try {
      const attributesList = await this.loadGeneratedAttributes();
      this.attr('attributes', attributesList);
      this.attr('showResults', false);
      this.attr('showFields', true);
      this.attr('selectedAfterLastSelection', []);
      this.attr('deselectedAfterLastSelection', []);
    } catch (err) {
      notifier('error', getFetchErrorInfo(err).details);
    } finally {
      this.attr('isAttributesGenerating', false);
    }
  },
  loadGeneratedAttributes() {
    return request('/api/bulk_operations/cavs/search', {
      ids: this.attr('selected').serialize()
        .map((selected) => selected.id),
    });
  },
});

const events = {
  inserted() {
    this.viewModel.onSubmit();
  },
  // catch selection of objects by inner components
  '{viewModel.selected} add'(el, ev, selected) {
    this.viewModel.updateSelectionCollections(
      selected,
      this.viewModel.attr('deselectedAfterLastSelection'),
      this.viewModel.attr('selectedAfterLastSelection')
    );
  },
  // catch deselection of objects by inner components
  '{viewModel.selected} remove'(el, ev, deselected) {
    this.viewModel.updateSelectionCollections(
      deselected,
      this.viewModel.attr('selectedAfterLastSelection'),
      this.viewModel.attr('deselectedAfterLastSelection')
    );
  },
};

export default canComponent.extend({
  tag: 'assessments-bulk-complete',
  view: canStache(template),
  viewModel,
  events,
});
