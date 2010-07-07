#!/usr/bin/env python

import base64, email.message, email.mime, email.parser, email.utils, hashlib, hmac, optparse, os, sys, urllib


class MessageSendingFailure(Exception):
    pass


class Signer(object):
    def __init__(self, SECRET_KEY=None):
        if not SECRET_KEY:
            try:
               SECRET_KEY = os.environ['GMAIL_SECRET_KEY']
            except KeyError:
                try:
                    SECRET_KEY = open('/etc/envdir/GMAIL_SECRET_KEY').readline().rstrip()
                except OSError:
                    raise EnvironmentError("GMAIL_SECRET_KEY is not set.")
        self.SECRET_KEY = SECRET_KEY

    def generate_signature(self, msg):
        return base64.encodestring(hmac.new(self.SECRET_KEY, msg, hashlib.sha1).digest()).strip()


class Connection(object):
    def __init__(self, EMAIL_APPENGINE_PROXY_URL=None):
        import httplib2
        self.h = httplib2.Http()
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
        return self.h.request(self.EMAIL_APPENGINE_PROXY_URL, "POST", body=data)


class GmailProxy(object):
    def __init__(self, SECRET_KEY=None, EMAIL_APPENGINE_PROXY_URL=None):
        self.signer = Signer(SECRET_KEY)
        self.connection = Connection(EMAIL_APPENGINE_PROXY_URL)

    def send_mail(self, msg):
        values = {'msg':msg.as_string(),
                  'signature':self.signer.generate_signature(msg.as_string())}
        data = urllib.urlencode([(k, v.encode('utf-8')) for k, v in values.items()])
        r, c = self.connection.make_request(data)

        if r.status != 204:
            raise MessageSendingFailure(c)


if __name__ == '__main__':
    """mail -s [space-separated to-addresses] to-address
       and the message on stdin"""
    parser = optparse.OptionParser()
    parser.add_option("-s", dest="subject", help="subject of message")
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
    GmailProxy().send_mail(msg)
