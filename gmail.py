#!/usr/bin/env python

import base64, email.message, email.mime, email.parser, email.utils, hashlib, hmac, optparse, os, sys, urllib


class MessageSendingFailure(Exception):
    pass


class Signer(object):
    def __init__(self, SECRET_KEYS=None):
        if not SECRET_KEYS:
            try:
               SECRET_KEYS = [os.environ['GMAIL_SECRET_KEY']]
            except KeyError:
                try:
                    SECRET_KEYS = [open('/etc/envdir/GMAIL_SECRET_KEY').readline().rstrip()]
                except OSError:
                    raise EnvironmentError("GMAIL_SECRET_KEY is not set.")
        self.SECRET_KEYS = SECRET_KEYS

    @staticmethod
    def sign(msg, key):
        return base64.encodestring(hmac.new(key, msg, hashlib.sha1).digest()).strip()

    def generate_signature(self, msg):
        return self.sign(msg, self.SECRET_KEYS[0])

    def verify_signature(self, msg, signature):
        for key in self.SECRET_KEYS:
            if self.sign(msg, key) == signature:
                return True
        return False


class Connection(object):
    def __init__(self, EMAIL_APPENGINE_PROXY_URL=None):
        if not EMAIL_APPENGINE_PROXY_URL:
            try:
                EMAIL_APPENGINE_PROXY_URL = os.environ['GMAIL_PROXY_URL']
            except KeyError:
                try:
                    EMAIL_APPENGINE_PROXY_URL = open('/etc/envdir/GMAIL_PROXY_URL').readline().rstrip()
                except OSError:
                    raise EnvironmentError("GMAIL_PROXY_URL is not set.")
        self.EMAIL_APPENGINE_PROXY_URL = EMAIL_APPENGINE_PROXY_URL

    def make_request(self, data):
        response = urllib.urlopen(self.EMAIL_APPENGINE_PROXY_URL, data=data)
        return response.getcode(), response.read()


class GmailProxy(object):
    def __init__(self, SECRET_KEY=None, EMAIL_APPENGINE_PROXY_URL=None, fix_sender=False, fail_silently=False):
        self.signer = Signer([SECRET_KEY])
        self.connection = Connection(EMAIL_APPENGINE_PROXY_URL)
        self.fix_sender = fix_sender
        self.fail_silently = fail_silently

    def send_mail(self, msg):
        values = {'msg':msg.as_string(),
                  'signature':self.signer.generate_signature(msg.as_string())}
        if self.fix_sender:
            values['fix_sender'] = 'true'
        data = urllib.urlencode([(k, v.encode('utf-8')) for k, v in values.items()])
        status, errmsg = self.connection.make_request(data)

        if status != 204:
            if not self.fail_silently:
                raise MessageSendingFailure(errmsg)
            else:
                return False
        return True


if __name__ == '__main__':
    """mail -s [space-separated to-addresses] to-address
       and the message on stdin"""
    parser = optparse.OptionParser()
    parser.add_option("-s", dest="subject", help="subject of message")
    parser.add_option("--fix-sender", action="store_true", dest="fix_sender",
                      help="If sender is not authorized, replace From with an authorized sender")
    options, to_addresses = parser.parse_args()
    if to_addresses:
        msg = email.message.Message()
        msg['From'] = os.environ['USER']
        msg['To'] = ",".join(to_addresses) # escaping necessary?
        msg['Subject'] = options.subject
        msg.set_payload(sys.stdin.read())
    else:
        # We're expecting a whole message on stdin:
        msg = email.parser.Parser().parse(sys.stdin)
        recipient = os.environ.get('RECIPIENT')
        if recipient:
            msg['To'] = recipient
    GmailProxy(fix_sender=options.fix_sender).send_mail(msg)
