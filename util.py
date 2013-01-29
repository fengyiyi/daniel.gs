def get_file_ext(path):
    ext = ''
    extidx = path.rfind('.')
    if extidx != -1:
        ext = path[extidx:]
    return ext

def get_file_name(path):
    import os
    return os.path.basename(path)

def get_file_log_handler(debug=False):
    import os, logging
    from logging.handlers import TimedRotatingFileHandler

    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_handler = TimedRotatingFileHandler('logs/app.log', when='H', interval=12)
    if debug:
        log_handler.setLevel(logging.DEBUG)
    else:
        log_handler.setLevel(logging.WARNING)
    log_handler.setFormatter(logging.Formatter('%(asctime)s|%(levelname)s|%(filename)s|%(lineno)d|%(funcName)s|%(message)s'))
    return log_handler

import logging
import logging.handlers

class TlsSMTPHandler(logging.handlers.SMTPHandler):
    def emit(self, record):
        try:
            import smtplib
            import string # for tls add this line
            try:
                from email.utils import formatdate
            except ImportError:
                formatdate = self.date_time
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port)
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s" % (
                            self.fromaddr,
                            string.join(self.toaddrs, ","),
                            self.getSubject(record),
                            formatdate(), self.format(record))
            if self.username:
                smtp.ehlo() # for tls add this line
                smtp.starttls() # for tls add this line
                smtp.ehlo() # for tls add this line
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg)
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

def get_email_log_handler():
    mail_handler = TlsSMTPHandler(('smtp.gmail.com', 587),
                               'app@daniel.gs',
                               ['me@daniel.gs'], '[ERROR] There was a critical error in daniel.gs app.',
                               ('app@daniel.gs', 'wltn1004'))
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(logging.Formatter('Timestamp: %(asctime)s\nLevel: %(levelname)s\nLocation: %(filename)s (%(lineno)d)\nFunction: %(funcName)s\n\n%(message)s'))
    return mail_handler

# convert string to datetime (UTC/GMT)
def datetime_from_dropbox(source):
    from datetime import datetime, timedelta
    return datetime.strptime(source[:-6], "%a, %d %b %Y %H:%M:%S") - timedelta(hours=(int(source[-5:])/100))

def dict_to_obj(**source):
    obj = object()
    obj.__dict__.update(source)
    return obj

class cached_property(object):
    def __init__(self, func, name=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, None)
        if value is None:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value

def time_metric(func):  
    from datetime import datetime
    from functools import wraps
    from flask import g

    if g.app.config.get('timemetric', False):
        @wraps(func)
        def _func(*args, **kwargs):
            ts = datetime.now()
            try:
                return func(*args, **kwargs)
            finally:
                print '['+func.__module__+'] '+func.__name__+': '+str(datetime.now()-ts)

        return _func
    else:
        return func