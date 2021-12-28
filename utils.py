# -*- coding: utf-8 -*-
import os, logging

# --------------------------------------------------------------- #

NL = '\n'
CODING = 'utf-8'

logging.basicConfig(encoding='utf-8', level=logging.DEBUG, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# --------------------------------------------------------------- #

def make_abspath(filename, root=''):
    if not root: root = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(root, filename) if filename else root)

# --------------------------------------------------------------- #

def log(what, how='info', *args, **kwargs):
    if how == 'info':
        logging.info(what, *args, **kwargs)
    elif how == 'warn':
        logging.warning(what, *args, **kwargs)
    elif how == 'error':
        logging.error(what, *args, **kwargs)
    elif how == 'debug':
        logging.debug(what, *args, **kwargs)
    elif how == 'critical':
        logging.critical(what, *args, **kwargs)
    elif how == 'exception':
        logging.exception(what, *args, **kwargs)

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