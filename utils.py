# -*- coding: utf-8 -*-
import os, logging
from config import *

# --------------------------------------------------------------- #

DEBUG = CONFIG['app'].getboolean('debug', fallback=False) if 'app' in CONFIG else False
NL = '\n'
CODING = 'utf-8'
LOGMSGFORMAT = '[{asctime}] {message}'
LOGFILE = CONFIG['app'].get('logfile', None) if 'app' in CONFIG else None

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt=LOGMSGFORMAT, datefmt='%Y-%m-%d %H:%M:%S', style='{')

if DEBUG:
    ch_debug = logging.StreamHandler()
    ch_debug.setLevel(logging.DEBUG)
    ch_debug.setFormatter(formatter)
    logger.addHandler(ch_debug)

if LOGFILE:
    ch_logfile = logging.FileHandler(os.path.abspath(LOGFILE), mode='w', encoding=CODING, delay=True)
    ch_logfile.setLevel(logging.DEBUG)
    ch_logfile.setFormatter(formatter)
    logger.addHandler(ch_logfile)

# --------------------------------------------------------------- #

def make_abspath(filename, root=''):
    if not root: root = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(root, filename) if filename else root)

# --------------------------------------------------------------- #

def log(what, how='info', *args, **kwargs):
    logger = logging.getLogger()
    if how == 'info':
        logger.info(what, *args, **kwargs)
    elif how == 'warn':
        logger.warning(what, *args, **kwargs)
    elif how == 'error':
        logger.error(what, *args, **kwargs)
    elif how == 'debug':
        logger.debug(what, *args, **kwargs)
    elif how == 'critical':
        logger.critical(what, *args, **kwargs)
    elif how == 'exception':
        logger.exception(what, *args, **kwargs)

# --------------------------------------------------------------- #    

def has_admin():
    if os.name == 'nt':
        try:
            # only windows users with admin privileges can read the C:\windows\temp
            temp = os.listdir(os.sep.join([os.environ.get('SystemRoot','C:\\windows'),'temp']))
        except:
            return (os.environ['USERNAME'], False)
        else:
            return (os.environ['USERNAME'], True)
    else:
        if 'SUDO_USER' in os.environ and os.geteuid() == 0:
            return (os.environ['SUDO_USER'], True)
        else:
            return (os.environ['USERNAME'], False)    