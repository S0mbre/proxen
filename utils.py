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
    