/*
  Copyright (C) 2020 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import '../simple-modal/simple-modal';
import '../form/fields/dropdown-form-field';
import '../comment/comment-input';
import '../url-edit-control/url-edit-control';

import canComponent from 'can-component';
import canDefineMap from 'can-define/map/map';
import canStache from 'can-stache';
import template from './required-info-modal.stache';
import {uploadFiles} from '../../plugins/utils/gdrive-picker-utils';
import {connectionLostNotifier} from '../../plugins/utils/notifiers-utils';
import {isConnectionLost} from '../../plugins/utils/errors-utils';
import {getPlainText} from '../../plugins/ggrc-utils';
import pubSub from '../../pub-sub';

const ViewModel = canDefineMap.extend({seal: false}, {
  content: {
    set(content) {
      /**
       * In order to not modify "content" fields (affect parent component),
       *  need to prepare a copy of them
       */
      this.comment = content.comment;
      this.urlsList.replace(content.urls);
      this.filesList.replace(content.files);

      return content;
    },
  },
  dropdownOptions: {
    get() {
      return [this.content.attribute.value];
    },
  },
  title: {
    value: '',
  },
  state: {
    value: () => ({
      open: false,
    }),
  },
  urlsList: {
    value: () => [],
  },
  filesList: {
    value: () => [],
  },
  comment: {
    value: null,
  },
  urlsEditMode: {
    value: false,
  },
  noItemsText: {
    value: '',
  },
  setUrlEditMode(value) {
    this.urlsEditMode = value;
  },
  addUrl(url) {
    this.urlsList.push(url);
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

      this.filesList.push(...filesList);
    } catch (err) {
      if (isConnectionLost()) {
        connectionLostNotifier();
      }
    }
  },
  onSave() {
    const hasText = getPlainText(this.comment).length !== 0;

    pubSub.dispatch({
      type: 'requiredInfoSave',
      attributeId: this.content.attribute.id,
      changes: {
        comment: hasText ? this.comment : null,
        files: this.filesList,
        urls: this.urlsList,
      },
    });

    this.closeModal();
  },
  closeModal() {
    this.setUrlEditMode(false);
    this.state.open = false;
  },
  removeItemByIndex(collectionName, index) {
    this[collectionName].splice(index, 1);
  },
});

export default canComponent.extend({
  tag: 'required-info-modal',
  view: canStache(template),
  ViewModel,
});
