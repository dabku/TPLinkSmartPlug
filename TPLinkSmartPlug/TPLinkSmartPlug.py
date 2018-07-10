import requests
import json
import logging

logger = logging.getLogger('root')


class SmartPlug:
    def __init__(self, login=None, password=None):
        if login is not None:
            self.login = login
        if password is not None:
            self.password = password
        self.state = None
        self.tplink_url = "https://wap.tplinkcloud.com"
        self.app_url = ''
        self.device_id = None
        self.token = ''
        self.get_token()

    def _post_request(self, url, data=None, headers={'Content-type': 'application/json'}, retries=1):
        try:
            r = requests.post(url, data, headers)
        except requests.ConnectionError:
            logger.error('Connection error: {}'.format(url))
            raise NotConnected
        content = json.loads(r.content)
        if content['error_code'] != 0:
            logger.error('TPLink Error: code {}, msg: {}'.format(content['error_code'], content['msg']))
            if content['error_code'] == -20651:
                if retries > 0:
                    logger.warning('Token expired, getting new token'.format(retries))
                    self.get_token()
                    content = self._post_request('{}?token={}'.format(self.tplink_url, self.token),
                                                 data, headers, retries-1)
                else:
                    logger.warning('Token expired, out of retries')
                    raise TokenError
            if content['error_code'] == -20571:
                raise DeviceNotConnected
            if content['error_code'] == -20601:
                raise LoginError
            if content['error_code'] == -20104:
                raise InvalidRequest
            # handling retries
            if content['error_code'] != 0:
                raise InternalError
        return content

    def get_state(self):
        logger.debug('Getting plug state')
        params = {"method": "passthrough", "params": {"deviceId": self.device_id,
                                                      "requestData": "{\"system\":{\"get_sysinfo\":null}}"}}
        response = self._post_request('{}?token={}'.format(self.tplink_url, self.token), data=json.dumps(params))
        try:
            sysinfo = json.loads(response['result']['responseData'])
            state = sysinfo['system']['get_sysinfo']['relay_state']
        except KeyError:
            raise UnexpectedResponse(response)
        return state == 1

    def set_state(self, turn_on=True):
        value = int(turn_on)
        logger.debug('Setting plug state: {}'.format(value))
        params = {"method": "passthrough", "params": {"deviceId": self.device_id,
                                                      "requestData": "{\"system\":{\"set_relay_state\":{\"state\":" +
                                                                     str(value)+"}}}"}}
        response = self._post_request('{}?token={}'.format(self.tplink_url, self.token), data=json.dumps(params))

        try:
            return response['error_code'] == 0
        except KeyError:
            raise UnexpectedResponse(response)

    def get_token(self):
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
        except TypeError:
            raise NotConnected
        except KeyError:
            raise UnexpectedResponse(response)

    def get_device_details(self):
        req_params = {"method": "getDeviceList"}
        response = self._post_request('{}?token={}'.format(self.tplink_url, self.token), data=json.dumps(req_params))
        return response['result']['deviceList']

    # todo: multiple devices
    def setup_device(self, device_no=0):
        response = self.get_device_details()
        try:
            self.device_id = response[device_no]['deviceId']
            self.app_url = response[device_no]['appServerUrl']
        except IndexError:
            raise InternalError('Wrong device number')


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