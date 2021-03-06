# -*- coding: utf-8 -*-
## @package proxen.proxen
# @brief Main application entry-point module that creates and launches the GUI app -- see main() function.
import os, sys, traceback
from qtimports import QtCore, QtWidgets

# ======================================================================================= #

## Main function that creates and launches the application.
def main():

    from gui import MainWindow
    
    try:        
        # change working dir to current for correct calls to git
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        # initialize Qt Core App settings
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        # disable Qt debug messages
        QtCore.qInstallMessageHandler(lambda msg_type, msg_log_context, msg_string: None)
        # create QApplication instance
        app = QtWidgets.QApplication(sys.argv)
        # create main window
        mw = MainWindow()
        # show window
        mw.show()
        # run app's event loop
        sys.exit(app.exec())

    except SystemExit as err:
        if str(err) != '0':
            traceback.print_exc(limit=None)

    except Exception as err:
        traceback.print_exc(limit=None)
        sys.exit(1)

    except:
        traceback.print_exc(limit=None)
        sys.exit(1)

# ======================================================================================= #    

## Program entry point.
if __name__ == '__main__':
    main()
