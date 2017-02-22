from pyfcm import FCMNotification as _FCMNotification
from flask_httpauth import HTTPBasicAuth


class FCMNotification(_FCMNotification):
    def set_api_key(self, key):
        self._FCM_API_KEY = key


auth = HTTPBasicAuth()
push_service = FCMNotification(api_key="<api-key>")
