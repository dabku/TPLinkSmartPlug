import requests
import json
import logging

logger = logging.getLogger('root')


class SmartPlug:
    def __init__(self, config=None):
        if config is None:
            raise InternalError('No config file selected')
        try:
            with open(config) as cnf_file:
                config = json.load(cnf_file)
        except FileNotFoundError:
            raise InternalError('Cannot open configuration file: {}'.format(config))
        try:
            self.login = config['TPLinkSmartPlug']['login']
            self.password = config['TPLinkSmartPlug']['password']
            self.tplink_url = config['TPLinkSmartPlug']['url']
        except KeyError:
            raise InternalError('Supplied configuration file has invalid format')
        self.app_url = ''
        self.devices = {}
        self.token = ''

        self.initialize_token()
        self.setup_devices()

    def _post_request(self, url, data=None, headers={'Content-type': 'application/json'}, retries=1):
        """
        Posts request and evaluates various errors that it might encounter with TLink server. 
        On each error, it will raise and exception, except of TokenError which will try to acquire (retries) times
        :param url: URL of the request
        :param data: JSON data to post
        :param headers: request of headers
        :param retries: numbers of retries enabled for token expiry only
        :return: returns the CONTENT of the request
        """
        try:
            r = requests.post(url, data, headers)
        except requests.ConnectionError:
            logger.error('Connection error: {}'.format(url))
            raise NotConnected
        content = json.loads(r.content)
        if content['error_code'] != 0:
            if content['error_code'] == -20651:
                if retries > 0:
                    logger.warning('Token expired, getting new token'.format(retries))
                    self.initialize_token()
                    content = self._post_request('{}?token={}'.format(self.tplink_url, self.token),
                                                 data, headers, retries-1)
                else:
                    logger.warning('Token expired, out of retries')
                    raise TokenError
            else:
                logger.error('TPLink Error: code {}, msg: {}'.format(content['error_code'], content['msg']))
            if content['error_code'] == -20571:
                raise DeviceNotConnected
            if content['error_code'] == -20601:
                raise LoginError
            if content['error_code'] == -20104:
                raise InvalidRequest
            if content['error_code'] == -20105:
                raise InvalidRequest('One or more parameter has wrong type')
            # handling retries
            if content['error_code'] != 0:
                raise InternalError
        return content

    def _get_id(self, name):
        """
        Gets id used by TP Link service based on alias.
        :param name: alias of the device
        :return: Device id
        """

        try:
            return self.devices[name]['device_id']
        except KeyError:
            raise UnknownDevices("Device with alias {} not found".format(name))
        except TypeError:
            raise InternalError("Device list is not initalized")


    def get_state(self, name):
        """
        Gets state of the requested device
        :param name: alias of the device 
        :return: current boolean state of the device
        """
        device_id = self._get_id(name)
        params = {"method": "passthrough", "params": {"deviceId": device_id,
                                                      "requestData": "{\"system\":{\"get_sysinfo\":null}}"}}
        response = self._post_request('{}?token={}'.format(self.tplink_url, self.token), data=json.dumps(params))
        try:
            sysinfo = json.loads(response['result']['responseData'])
            state = sysinfo['system']['get_sysinfo']['relay_state']
        except KeyError:
            raise UnexpectedResponse(response)
        return state == 1

    def set_state(self, name, turn_on=True):
        """
        Sets state of the specified device
        :param name: alias of the device 
        :param turn_on: desired boolean state of the device
        :return: None
        """
        device_id = self._get_id(name)
        value = int(turn_on)
        logger.debug('Setting plug state: {}'.format(value))
        params = {"method": "passthrough", "params": {"deviceId": device_id,
                                                      "requestData": "{\"system\":{\"set_relay_state\":{\"state\":" +
                                                                     str(value)+"}}}"}}
        response = self._post_request('{}?token={}'.format(self.tplink_url, self.token), data=json.dumps(params))

        try:
            return response['error_code'] == 0
        except KeyError:
            raise UnexpectedResponse(response)

    def initialize_token(self):
        """
        Gets token from TP Link service. Token is used to get and set device data instead of the credentials
        :return: None
        """
        logger.debug('Getting token')
        req_params = {"method": "login",
                      "params": {
                          "appType": "Kasa_Android",
                          "cloudUserName": self.login,
                          "cloudPassword": self.password,
                          "terminalUUID": ''
                      }}
        response = self._post_request(self.tplink_url, data=json.dumps(req_params))
        try:
            self.token = response['result']['token']
        except KeyError:
            raise UnexpectedResponse(response)

    def get_devices_details(self):
        """
        
        Creates and executes request for all Devicess assigned to currently sign in account
        :return: Array of dictionaries returned by TPLink service
        """
        req_params = {"method": "getDeviceList"}
        response = self._post_request('{}?token={}'.format(self.tplink_url, self.token), data=json.dumps(req_params))
        return response['result']['deviceList']

    def setup_devices(self):
        """
        Gets all devices from TPLink service. 
        It's essential to set up the devices in order to get their id's before calling get/set state methods.
        :return: None
        """
        response = self.get_devices_details()
        for device in response:
            try:
                new_device = {'device_id': device['deviceId'],
                              'app_url': device['appServerUrl'],
                              'model': device['deviceModel']}
                self.devices[device['alias']] = new_device
            except KeyError:
                raise InternalError('Failed to add the device: {}'.format(device))


class TokenError(Exception):
    pass


class NotConnected(Exception):
    pass


class DeviceNotConnected(Exception):
    pass


class UnexpectedResponse(Exception):
    pass


class InternalError(Exception):
    pass


class LoginError(Exception):
    pass


class InvalidRequest(Exception):
    pass


class UnknownDevices(Exception):
    pass