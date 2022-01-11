# -*- coding: utf-8 -*-
import configparser, ast

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

CONFIG = configparser.ConfigParser(allow_no_value=True, comment_prefixes=('#',), 
                                   converters={'list': conv_list, 'tuple': conv_tuple, 'literal': conv_literal})
CONFIG.read('config.ini')

# ======================================================================================= # 

def config_save():
    with open('config.ini', 'w', encoding='utf-8') as configfile:
        CONFIG.write(configfile)