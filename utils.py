# -*- coding: utf-8 -*-
## @package proxen.utils
# @brief Globals and utility functions used across the app.
import os, logging
from config import *

# --------------------------------------------------------------- #

## `bool` debug mode switcher (`True` = print debug messages to console)
DEBUG = CONFIG['app'].getboolean('debug', fallback=False) if 'app' in CONFIG else False
## `str` newline symbol
NL = '\n'
## `str` default coding (for file IO)
CODING = 'utf-8'
## `str` log message mask
LOGMSGFORMAT = '[{asctime}] {message}'
## `str` log file name (relative to project dir); empty = no log output
LOGFILE = CONFIG['app'].get('logfile', None) if 'app' in CONFIG else None
## `logging.Logger` the global logger object
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
## `logging.Formatter` logging formatter object
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

## Creates an absolute path given the root directory.
# @param root `str` the root directory to form the abs path (empty = project directory)
# @returns `str` the absolute file / folder path
def make_abspath(filename, root=''):
    if not root: root = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(root, filename) if filename else root)

# --------------------------------------------------------------- #

## Makes a log message using the global logger instance.
# @param what `str` the message text
# @param how `str` determines the log message type:
# - `info`: information message (default)
# - `warn`: warning message
# - `error`: error message
# - `debug`: debug message
# - `critical`: critical message 
# - `exception`: exception message
# @param args `positional args` passed to the logger
# @param kwargs `keyword args` passed to the logger
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

## Checks if the current user has admin / root / SU privileges.
# @returns `tuple` a 2-tuple of the following elements:
# -# `str` current user name
# -# `bool` whether the user has admin / root / SU privileges (`True`) or not (`False`)
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
        if os.geteuid() == 0:
            return (os.environ['USER'], True)
        else:
            return (os.environ['USER'], False)    