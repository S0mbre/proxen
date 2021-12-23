# -*- coding: utf-8 -*-
# universal imports supporting PyQt5, PyQt6, PySide2, PySide6
try:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets, QtSvg
        from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
        from PyQt6.QtGui import QAction
    except ImportError:
        from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
        from PySide6.QtCore import Signal, Slot
        from PySide6.QtGui import QAction
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg
        from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
        from PyQt5.QtWidgets import QAction
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets, QtSvg
        from PySide2.QtCore import Signal, Slot
        from PySide2.QtWidgets import QAction