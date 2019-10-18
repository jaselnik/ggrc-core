/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import {ggrcAjax} from '../../plugins/ajax_extensions';
import {handleAjaxError} from '../../plugins/utils/errors-utils';

const DEFAULT_TIMEOUT = 2000;
const MAX_TIMEOUT = 60000;

export const trackStatus = (
  url,
  onSuccessHandler,
  onFailureHandler,
  timeout = DEFAULT_TIMEOUT) => {
  timeout = timeout > MAX_TIMEOUT ? MAX_TIMEOUT : timeout;

  const timeoutId = setTimeout(() => {
    checkStatus(url, onSuccessHandler, onFailureHandler, timeout);
  }, timeout);

  return timeoutId;
};

const getStatus = (url) => {
  return ggrcAjax({
    method: 'GET',
    url,
    cache: false,
  });
};

const checkStatus = (url, onSuccessHandler, onFailureHandler, timeout) => {
  getStatus(url)
    .done(({background_task: {status}}) => {
      switch (status) {
        case 'Running':
        case 'Pending': {
          trackStatus(url, onSuccessHandler, onFailureHandler, timeout * 2);
          break;
        }
        case 'Success': {
          onSuccessHandler();
          break;
        }
        case 'Failure': {
          onFailureHandler();
          break;
        }
      }
    })
    .fail((jqxhr, textStatus, errorThrown) => {
      handleAjaxError(jqxhr, errorThrown);
    });
};
