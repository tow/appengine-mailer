from google.appengine.ext.webapp import WSGIApplication
from google.appengine.ext.webapp.util import run_wsgi_app

from mail import SendMail

application = WSGIApplication([('/', SendMail),
                              ],
                              debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
