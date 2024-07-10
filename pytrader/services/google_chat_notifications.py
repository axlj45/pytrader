import requests
import logging


class GoogleChatNotification:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.log = logging.getLogger("pytrader.notifications.googlechat")

    def send_text(self, message_text):
        message = {"text": message_text}
        self.send_object(message)

    def send_object(self, chat_object):
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        try:
            response = requests.post(self.webhook_url, headers=headers, json=chat_object)
            response.raise_for_status()
            self.log.debug(f"Google chat sent successfully with response code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.log.warn(f"Error sending message: {e}")
