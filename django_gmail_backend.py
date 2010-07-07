from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

from gmail import GmailProxy, MessageSendingFailure


class GmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False):
        self.gmail_proxy = GmailProxy(settings.SECRET_KEY, settings.EMAIL_APPENGINE_PROXY_URL, fail_silently)
        super(GmailBackend, self).__init__(fail_silently)

    def send_messages(self, messages):
        n = 0
        for message in messages:
            try:
                self.gmail_proxy.send_mail(message.message())
                n += 1
            except MessageSendingFailure:
                pass
        return n
