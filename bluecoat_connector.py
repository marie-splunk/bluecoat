# Phantom imports
import phantom.app as phantom
from phantom.app import BaseConnector
from phantom.app import ActionResult

from bluecoat_consts import *

from django.http import HttpResponse
import json
import os
import requests
from urllib.parse import urlparse


def handle_request(request, path_parts):
    """
    request contains the data posted to the rest endpoint,
    it is the django http request object path_parts is a
    list of the URL tokenized.
    """
    # Load the data
    list_data = _load_data()
    blacklist = list_data.get('blacklist', [])
    whitelist = list_data.get('whitelist', [])
    full_list = '''define category phantom_blacklist
    {}
    end
    define category phantom_whitelist
    {}
    end'''
    return HttpResponse(full_list.format('\n'.join(blacklist),
                                         '\n'.join(whitelist)))


def _load_data(list_mgr_connector=None):
    """Loads the data that was added to."""
    # Get the directory of the file
    dir_path = os.path.split(__file__)[0]
    list_data_file = '{0}/data/list_data.json'.format(dir_path)
    list_data = {'blacklist': [], 'whitelist': []}
    try:
        # If database file already exists, load it.
        if os.path.isfile(list_data_file):
            with open(list_data_file, 'r') as f:
                list_json = f.read()
                list_data = json.loads(list_json)
    except Exception as e:
        if list_mgr_connector:
            list_mgr_connector.debug_print('In _load_data: '
                                           'Exception: {0}'.format(str(e)))
        pass
    if list_mgr_connector:
        list_mgr_connector.debug_print('Loaded state: ', list_data)
    return list_data


def _save_data(list_data, list_mgr_connector):
    """Saves the list_data into the same file."""
    # Get the directory of the file
    dir_path = os.path.split(__file__)[0]
    list_data_file = '{0}/data/list_data.json'.format(dir_path)
    if list_mgr_connector:
        list_mgr_connector.debug_print('Saving state: ', list_data)
    try:
        with open(list_data_file, 'w+') as f:
            f.write(json.dumps(list_data))
            f.flush()
    except:
        return phantom.APP_ERROR
    return phantom.APP_SUCCESS


class BlueCoatConnector(BaseConnector):
    ACTION_ID_BLOCK_URL = 'block_url'
    ACTION_ID_UNBLOCK_URL = 'unblock_url'
    ACTION_ID_ALLOW_URL = 'allow_url'
    ACTION_ID_DISALLOW_URL = 'disallow_url'
    ACTION_ID_URL_REPUTATION = 'url_reputation'

    def __init__(self):
        # Call the BaseConnectors init first
        super(BlueCoatConnector, self).__init__()
        self._list_data = {}

    def initialize(self):
        """Automatically called by the BaseConnector at the
        start of the action handler."""
        # Load the data
        self._list_data = _load_data(self)
        return phantom.APP_SUCCESS

    def finalize(self):
        """Automatically called by the BaseConnector once
        the action calls are done."""
        # Save the data back into the file, if any of the
        # actions modified the data
        # it will get written to the file
        _save_data(self._list_data, self)
        return phantom.APP_SUCCESS

    def _test_connectivity(self, param):
        config = self.get_config()

        self.save_progress('Querying proxy server to check connectivity')
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES,
                           config['proxy_host'])
        try:
            r = requests.get(TEST_URL.format(config['proxy_host'],
                                             config['proxy_mgmt_port'],
                                             'http://www.google.com'),
                             auth=(config['username'], config['password']),
                             verify=config[phantom.APP_JSON_VERIFY])
            r.raise_for_status()
        except requests.HTTPError as e:
            self.set_status(phantom.APP_ERROR, ERR_SERVER_CONNECTION, e)
            self.append_to_message(ERR_CONNECTIVITY_TEST)
            return self.get_status()
        return self.set_status_save_progress(phantom.APP_SUCCESS,
                                             SUCC_CONNECTIVITY_TEST)

    def _handle_block_url(self, param):
        url = urlparse(param[BLUECOAT_JSON_URL]).netloc
        action_result = ActionResult(dict(param))
        self.add_action_result(action_result)
        # Check if URL is already blacklisted.
        if self._list_data['blacklist'].count(url) > 0:
            action_result.set_status(phantom.APP_ERROR, ERR_BLOCK_URL)
            return action_result.get_status()
        self._list_data['blacklist'].append(url)
        action_result.add_data(self._list_data)
        return action_result.set_status(phantom.APP_SUCCESS, SUCC_BLOCK_URL)

    def _handle_unblock_url(self, param):
        url = urlparse(param[BLUECOAT_JSON_URL]).netloc
        action_result = ActionResult(dict(param))
        self.add_action_result(action_result)
        try:
            self._list_data['blacklist'].remove(url)
            action_result.add_data(self._list_data)
        except ValueError:
            action_result.set_status(phantom.APP_ERROR, ERR_UNBLOCK_URL)
            return action_result.get_status()
        return action_result.set_status(phantom.APP_SUCCESS, SUCC_UNBLOCK_URL)

    def _handle_allow_url(self, param):
        url = urlparse(param[BLUECOAT_JSON_URL]).netloc
        action_result = ActionResult(dict(param))
        self.add_action_result(action_result)
        # Check if URL is already blacklisted.
        if self._list_data['whitelist'].count(url) > 0:
            action_result.set_status(phantom.APP_ERROR, ERR_ALLOW_URL)
            return action_result.get_status()
        self._list_data['whitelist'].append(url)
        action_result.add_data(self._list_data)
        return action_result.set_status(phantom.APP_SUCCESS, SUCC_ALLOW_URL)

    def _handle_disallow_url(self, param):
        url = urlparse(param[BLUECOAT_JSON_URL]).netloc
        action_result = ActionResult(dict(param))
        self.add_action_result(action_result)
        try:
            self._list_data['whitelist'].remove(url)
            action_result.add_data(self._list_data)
        except ValueError:
            action_result.set_status(phantom.APP_ERROR, ERR_DISALLOW_URL)
            return action_result.get_status()
        return action_result.set_status(phantom.APP_SUCCESS, SUCC_DISALLOW_URL)

    def _handle_url_reputation(self, param):
        config = self.get_config()
        action_result = ActionResult(dict(param))
        self.add_action_result(action_result)
        try:
            r = requests.get(TEST_URL.format(config['proxy_host'],
                                             config['proxy_mgmt_port'],
                                             param['url']),
                             auth=(config['username'], config['password']),
                             verify=config[phantom.APP_JSON_VERIFY])
            r.raise_for_status()
        except requests.HTTPError as e:
            action_result.set_status(phantom.APP_ERROR, ERR_URL_REPUTATION, e)
            return action_result.get_status()
        try:
            data = {k: v for k, v in [l.split(':') for l in ''.join(r.text.strip().split(' ')).split('\n')]}
            data['url'] = param['url']
            action_result.add_data(data)
            action_result.set_status(phantom.APP_SUCCESS, SUCC_URL_REPUTATION)
        except Exception as e:
            # self.debug_print("URL Reputation Debug Exception: {}".format(e))
            # self.debug_print("URL Reputation Debug Exception Text: {}".format(r.text))
            action_result.set_status(phantom.APP_ERROR, r.text.strip(), e)
        return action_result.get_status()

    def handle_action(self, param):
        ret_val = phantom.APP_SUCCESS
        action_id = self.get_action_identifier()
        self.debug_print("action_id", self.get_action_identifier())
        if action_id == self.ACTION_ID_BLOCK_URL:
            ret_val = self._handle_block_url(param)
        elif action_id == self.ACTION_ID_UNBLOCK_URL:
            ret_val = self._handle_unblock_url(param)
        elif action_id == self.ACTION_ID_ALLOW_URL:
            ret_val = self._handle_allow_url(param)
        elif action_id == self.ACTION_ID_DISALLOW_URL:
            ret_val = self._handle_disallow_url(param)
        elif action_id == self.ACTION_ID_URL_REPUTATION:
            ret_val = self._handle_url_reputation(param)
        elif action_id == phantom.ACTION_ID_TEST_ASSET_CONNECTIVITY:
            ret_val = self._test_connectivity(param)
        return ret_val


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('No test json specified as input')
        exit(0)
    with open(sys.argv[1]) as my_f:
        in_json = my_f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))
        connector = BlueCoatConnector()
        connector.print_progress_message = True
        my_ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(my_ret_val), indent=4))
    exit(0)
