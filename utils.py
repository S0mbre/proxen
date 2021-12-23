# -*- coding: utf-8 -*-
import os

# --------------------------------------------------------------- #

NL = '\n'
CODING = 'utf-8'

# --------------------------------------------------------------- #

def make_abspath(filename, root=''):
    if not root: root = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(root, filename) if filename else root)

# --------------------------------------------------------------- #

    