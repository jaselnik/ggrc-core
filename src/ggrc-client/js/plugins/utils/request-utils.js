/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

/**
 * Makes POST request to the proposed [url] with certain [body].
 * @param {String} url A string containing the URL to which the request is
 * sent.
 * @param {Object} body Data to be sent to the server.
 * @return {Promise<Object>} Result of the request.
 */
export const request = async (url, body) => {
  try {
    const response = await fetch(url, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: {
        'Content-type': 'application/json',
      },
      credentials: 'include',
    });

    const json = await response.json();

    if (!response.ok) {
      return Promise.reject({
        json,
        status: response.status,
        statusText: response.statusText,
      });
    }

    return json;
  } catch (err) {
    return Promise.reject({
      json: {message: err.message},
    });
  }
};
