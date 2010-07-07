import email.parser, logging, os

from google.appengine.api.mail import EmailMessage, InvalidSenderError
from google.appengine.ext.webapp import RequestHandler

from gmail import Signer


suffixes = dict(line.strip().split()[:2] for line in open('google.mime.types'))


class BadRequestError(ValueError):
    pass


class BadMessageError(ValueError):
    pass


def get_filename(part):
    filename = part.get_filename()
    if not filename:
        content_type = part.get_content_type()
        try:
            filename = "file.%s" % suffixes[content_type]
        except KeyError:
            raise BadMessageError("Google won't let us send content of type '%s'" % content_type)
    return filename

def send_message(msg):
    sender = msg.get_unixfrom() or msg['From']
    if not sender:
        raise BadMessageError("No sender specified")
    to = msg['To']
    if not to:
        raise BadMessageError("No destination addresses specified")
    message = EmailMessage(sender=sender or msg['From'], to=to)

    # Go through all the headers which Google will let us use
    cc = msg['Cc']
    if cc:
        message.cc = cc
    bcc = msg['Bcc']
    if bcc:
        message.bcc = cc
    reply_to = msg['Reply-To']
    if reply_to:
        message.reply_to = reply_to
    subject = msg['Subject']
    if subject:
        message.subject = subject

    # If there's just a plain text body, use that, otherwise
    # iterate over all the attachments
    payload = msg.get_payload()
    if isinstance(payload, basestring):
        message.body = payload
    else:
        # GAW demands we specify the body explicitly - we use the first textual attachment.
        payload = msg.walk()
        while True:
            try:
                firstpart = payload.next()
            except StopIteration:
                raise BadMessageError("Message consists only of multipart attachments")
            if not firstpart.get_content_type().startswith('multipart'):
                break
        if not firstpart.get_content_type() == 'text/plain':
            raise BadMessageError("No text body found for message")
        message.body = firstpart.get_payload()
        message.attachments = [(get_filename(part), part.as_string()) for part in payload
                               if not part.get_content_type().startswith('multipart')]
    try:
        message.send()
    except InvalidSenderError:
        raise BadMessageError("Unauthorized message sender '%s'" % sender)

def check_signature(msg, signature):
    os.environ['GMAIL_SECRET_KEY'] = open('GMAIL_SECRET_KEY').read().strip()
    return Signer().generate_signature(msg) == signature

def parse_args(request):
    msg = request.get('msg')
    if not msg:
        raise BadRequestError("No message found")
    signature = request.get('signature')
    if not signature:
        raise BadRequestError("No signature found")
    if not check_signature(msg, signature):
        raise BadRequestError("Signature doesn't match")
    return str(msg) # email.parser barfs on unicode


class SendMail(RequestHandler):
    def post(self):
        try:
            msg = parse_args(self.request)
            send_message(email.parser.Parser().parsestr(msg))
            logging.info("Sent message ok\n%s" % msg)
            self.error(204)
        except BadRequestError, e:
            logging.error("Malformed request")
            self.error(400)
            self.response.out.write(e.args[0])
        except BadMessageError, e:
            logging.error("Failed to send message\n%s" % msg)
            self.error(400)
            self.response.out.write(e.args[0])
        except Exception, e:
            logging.exception("Failed to process request\n%s" % self.request)
            self.error(500)
