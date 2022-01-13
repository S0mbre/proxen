# -*- coding: utf-8 -*-
import configparser, ast, os

# ======================================================================================= # 

def conv_list(s):
    if s.startswith('[') and s.endswith(']'):
        return ast.literal_eval(s)
    elif '\n' in s:
        return [ss.strip() for ss in s.split('\n')]
    return [s]

def conv_tuple(s):
    if s.startswith('(') and s.endswith(')'):
        return ast.literal_eval(s)
    elif '\n' in s:
        return tuple(ss.strip() for ss in s.split('\n'))
    return (s,)

def conv_literal(s):
    return ast.literal_eval(s)

# ======================================================================================= #     

CONFIG_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config.ini')
CONFIG = configparser.ConfigParser(allow_no_value=True, comment_prefixes=('#',), 
                                   converters={'list': conv_list, 'tuple': conv_tuple, 'literal': conv_literal})
if os.path.isfile(CONFIG_FILE): CONFIG.read(CONFIG_FILE)

# ======================================================================================= # 

def config_save():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
        CONFIG.write(configfile)