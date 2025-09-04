# paypal_client.py
# PayPal REST helper - get token, create order, capture order
# Khong dung SDK, goi thang API bang requests

import time
import requests
import logging
from django.conf import settings

# Config logger
logger = logging.getLogger("paypal_client")
logger.setLevel(logging.DEBUG)

class PayPalClient:
    def __init__(self):
        # lay client id va secret tu settings
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.secret = settings.PAYPAL_SECRET
        self.mode = getattr(settings, "PAYPAL_MODE", "sandbox")  # sandbox hoac live

        # chon base url
        if self.mode == "live":
            self.base = "https://api.paypal.com"
        else:
            self.base = "https://api.sandbox.paypal.com"

        # cache token
        self._token = None
        self._token_expire = 0

    def _get_token(self):
        # neu token con hieu luc thi dung lai
        if self._token and time.time() < self._token_expire - 60:
            return self._token

        token_url = f"{self.base}/v1/oauth2/token"
        headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        data = {"grant_type": "client_credentials"}

        logger.debug(">>> [PayPal] requesting token from %s", token_url)
        r = requests.post(token_url, headers=headers, data=data, auth=(self.client_id, self.secret))
        r.raise_for_status()
        j = r.json()

        self._token = j.get("access_token")
        expires_in = int(j.get("expires_in", 3600))
        self._token_expire = time.time() + expires_in
        logger.debug(">>> [PayPal] got token, expires_in=%s", expires_in)
        return self._token

    def create_order(self, total, currency="USD", return_url=None, cancel_url=None):
        token = self._get_token()
        url = f"{self.base}/v2/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": f"{float(total):.2f}"
                    }
                }
            ]
        }

        if return_url or cancel_url:
            body["application_context"] = {}
            if return_url:
                body["application_context"]["return_url"] = return_url
            if cancel_url:
                body["application_context"]["cancel_url"] = cancel_url

        logger.debug(">>> [PayPal create_order] body=%s", body)
        r = requests.post(url, headers=headers, json=body)
        r.raise_for_status()
        resp = r.json()
        logger.debug(">>> [PayPal create_order] resp=%s", resp)
        return resp

    def capture_order(self, order_id):
        token = self._get_token()
        url = f"{self.base}/v2/checkout/orders/{order_id}/capture"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        logger.debug(">>> [PayPal capture_order] order_id=%s", order_id)
        r = requests.post(url, headers=headers)
        r.raise_for_status()
        resp = r.json()
        logger.debug(">>> [PayPal capture_order] resp=%s", resp)
        return resp
