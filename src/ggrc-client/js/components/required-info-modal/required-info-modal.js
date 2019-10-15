/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import '../simple-modal/simple-modal';
import '../form/fields/dropdown-form-field';
import '../comment/comment-input';
import '../url-edit-control/url-edit-control';

import canComponent from 'can-component';
import canStache from 'can-stache';
import canMap from 'can-map';
import template from './required-info-modal.stache';
import {uploadFiles} from '../../plugins/utils/gdrive-picker-utils';
import {notifier} from '../../plugins/utils/notifiers-utils';
import {isConnectionLost} from '../../plugins/utils/errors-utils';
import {getPlainText} from '../../plugins/ggrc_utils';

const viewModel = canMap.extend({
  define: {
    content: {
      set(content) {
        this.attr('commentValue', content.attr('commentValue'));
        this.attr('urlsList').replace(content.attr('urls'));
        this.attr('filesList').replace(content.attr('files'));

        return content;
      },
    },
    dropdownOptions: {
      get() {
        return [this.attr('content.field.value')];
      },
    },
  },
  title: '',
  state: {
    open: false,
  },
  // in order to not modify "content" fields (affect parent component),
  // need to prepare a copy of them
  urlsList: [],
  filesList: [],
  commentValue: null,
  urlsEditMode: false,
  noItemsText: '',
  setUrlEditMode(value) {
    this.attr('urlsEditMode', value);
  },
  addUrl(url) {
    this.attr('urlsList').push({url});
    this.setUrlEditMode(false);
  },
  async addFiles() {
    try {
      const rawFiles = await uploadFiles();
      const filesList = rawFiles.map(({id, title, alternateLink}) => ({
        id,
        title,
        link: alternateLink,
      }));

      this.attr('filesList').push(...filesList);
    } catch (err) {
      if (isConnectionLost()) {
        notifier('error', 'Internet connection was lost.');
      }
    }
  },
  onSave() {
    const commentValue = this.attr('commentValue');
    const hasText = getPlainText(commentValue).trim().length !== 0;

    this.dispatch({
      type: 'submit',
      fieldId: this.attr('content.field.id'),
      changes: {
        commentValue: hasText ? commentValue : null,
        files: this.attr('filesList'),
        urls: this.attr('urlsList'),
      },
    });

    this.closeModal();
  },
  closeModal() {
    this.setUrlEditMode(false);
    this.attr('state.open', false);
  },
  removeItemByIndex(collectionName, index) {
    this.attr(collectionName).splice(index, 1);
  },
});

export default canComponent.extend({
  tag: 'required-info-modal',
  view: canStache(template),
  viewModel,
});
