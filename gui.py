# -*- coding: utf-8 -*-
## @package proxen.gui
# @brief The GUI app main window implementation -- see MainWindow class.
import os, json, struct
import traceback

from qtimports import *
import utils
import sysproxy

# ******************************************************************************** #

## `list` proxy variable names
PROXY_OBJS = ['http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'noproxy']

# ******************************************************************************** #
# *****          QThreadStump
# ******************************************************************************** #

## Customized thread class (based on QThread) that adds
# progress, error etc. signals and mutex locking to avoid thread racing.
class QThreadStump(QtCore.QThread):

    ## Error signal (args are: instance of this thread and the error message)
    sig_error = Signal(QtCore.QThread, str)

    ## @param priority `int` thread default priority (default = normal)
    # @param on_start `callable` callback function called before the main
    # operation is executed (callback has no args or returned result)
    # @param on_finish `callable` callback function called after the main
    # operation completes (callback has no args or returned result)
    # @param on_run `callable` callback function for the main
    # operation (callback has no args or returned result)
    # @param on_error `callable` callback function to handle exceptions
    # raised during the thread operation (see QThreadStump::sig_error)
    # @param start_signal `Signal` signal that can be connected to
    # the `start` slot (if not `None`)
    # @param stop_signal `Signal` signal that can be connected to
    # the `terminate` slot (if not `None`)
    # @param free_on_finish `bool` whether the thread instance will be deleted
    # from memory after it completes its operation (default = `False`)    
    # @param can_terminate `bool` whether the thread can be terminated (default = `True`)
    # @param start_now `bool` whether to start the thread upon creation (default = `False`)
    def __init__(self, priority=QtCore.QThread.NormalPriority,
                 on_start=None, on_finish=None, on_run=None, on_error=None,
                 start_signal=None, stop_signal=None,
                 free_on_finish=False, can_terminate=True, start_now=False):
        super().__init__()
        ## `int` thread default priority (default = normal)
        self.priority = priority
        ## `callable` callback function executed before the thread runs
        self.on_start = on_start
        ## `callable` callback function executed after the thread finishes
        self.on_finish = on_finish
        ## `callable` callback function for the main operation
        self.on_run = on_run
        ## `callable` callback function executed when an exception occurs
        self.on_error = on_error
        ## `bool` whether the thread instance will be deleted from memory after it completes
        self.free_on_finish = free_on_finish
        ## `bool` whether the thread can be terminated
        self.can_terminate = can_terminate
        ## `Signal` signal that can be connected to the `start` slot (if not `None`)
        self.start_signal = start_signal
        ## `Signal` signal that can be connected to the `terminate` slot (if not `None`)
        self.stop_signal = stop_signal
        ## `QtCore.QMutex` mutex lock used by QThreadStump::lock() and QThreadStump::unlock()
        self.mutex = QtCore.QMutex()
        if start_now: self.start()

    ## Destructor: waits for the thread to complete.
    def __del__(self):
        try:
            self.wait()
        except:
            pass

    ## `int` getter for `QtCore.QThread.default_priority` (thread priority)
    @property
    def priority(self):
        return self.default_priority

    ## sets `QtCore.QThread.default_priority` (thread priority)
    @priority.setter
    def priority(self, _priority):
        try:
            self.default_priority = _priority if _priority != QtCore.QThread.InheritPriority else QtCore.QThread.NormalPriority
        except:
            pass

    ## `callable` getter for QThreadStump::_on_start
    @property
    def on_start(self):
        return self._on_start

    ## setter for QThreadStump::_on_start
    @on_start.setter
    def on_start(self, _on_start):
        try:
            self.started.disconnect()
        except:
            pass
        ## `callable` callback function executed before the thread runs
        self._on_start = _on_start
        if self._on_start:
            self.started.connect(self._on_start)

    ## `callable` getter for QThreadStump::_on_finish
    @property
    def on_finish(self):
        return self._on_finish

    ## setter for QThreadStump::_on_finish
    @on_finish.setter
    def on_finish(self, _on_finish):
        try:
            self.finished.disconnect()
        except:
            pass
        ## `callable` callback function executed after the thread finishes
        self._on_finish = _on_finish
        if self._on_finish:
            self.finished.connect(self._on_finish)
        if getattr(self, '_free_on_finish', False):
            self.finished.connect(self.deleteLater)

    ## `bool` getter for QThreadStump::_free_on_finish
    @property
    def free_on_finish(self):
        return self._free_on_finish

    ## setter for QThreadStump::_free_on_finish
    @free_on_finish.setter
    def free_on_finish(self, _free_on_finish):
        try:
            self.finished.disconnect()
        except:
            pass
        ## `bool` whether the thread instance will be deleted from memory after it completes
        self._free_on_finish = _free_on_finish
        if getattr(self, '_on_finish', None):
            self.finished.connect(self._on_finish)
        if self._free_on_finish:
            self.finished.connect(self.deleteLater)

    ## `callable` getter for QThreadStump::_on_error
    @property
    def on_error(self):
        return self._on_error

    ## setter for QThreadStump::_on_error
    @on_error.setter
    def on_error(self, _on_error):
        try:
            self.sig_error.disconnect()
        except:
            pass
        ## `callable` callback function executed when an exception occurs
        self._on_error = _on_error
        if self._on_error:
            self.sig_error.connect(self._on_error)

    ## `bool` getter for QThreadStump::_can_terminate
    @property
    def can_terminate(self):
        return self._can_terminate

    ## setter for QThreadStump::_can_terminate
    @can_terminate.setter
    def can_terminate(self, _can_terminate):
        self.setTerminationEnabled(_can_terminate)
        ## `bool` whether the thread can be terminated
        self._can_terminate = _can_terminate

    ## `Signal` getter for QThreadStump::_start_signal
    @property
    def start_signal(self):
        return self._start_signal

    ## setter for QThreadStump::_start_signal
    @start_signal.setter
    def start_signal(self, _start_signal):
        ## `Signal` signal that can be connected to the `start` slot
        self._start_signal = _start_signal
        if self._start_signal:
            self._start_signal.connect(self.start)

    ## `Signal` getter for QThreadStump::_stop_signal
    @property
    def stop_signal(self):
        return self._stop_signal

    ## setter for QThreadStump::_stop_signal
    @stop_signal.setter
    def stop_signal(self, _stop_signal):
        ## `Signal` signal that can be connected to the `terminate` slot
        self._stop_signal = _stop_signal
        if self._stop_signal:
            self._stop_signal.connect(self.terminate)

    ## Locks the internal mutex to preclude data racing.
    def lock(self):
        self.mutex.lock()

    ## Releases the mutex lock.
    def unlock(self):
        self.mutex.unlock()

    ## Executes the worker function pointed to by QThreadStump::on_run.
    def run(self):
        try:
            self.setPriority(self.priority)
        except:
            pass
        if self.on_run and not self.isInterruptionRequested():
            try:
                self.on_run()
            except Exception as err:
                traceback.print_exc(limit=None)
                self.sig_error.emit(self, str(err))

# ******************************************************************************** #
# *****          BrowseEdit
# ******************************************************************************** #

## @brief Edit field with internal 'Browse' button to file or folder browsing.
# Inherited from `QtWidgets.QLineEdit`
class BrowseEdit(QtWidgets.QLineEdit):

    ## @param text `str` initial text in edit field (default = empty)
    # @param parent `QtWidgets.QWidget` parent widget (default = `None`, i.e. no parent)
    # @param dialogtype `str` path and dialog type:
    #   * 'fileopen' = open file browse dialog
    #   * 'filesave' = save file browse dialog
    #   * 'folder' = folder browse dialog
    # `None` = 'fileopen' (default)
    # @param btnicon `str` icon file name in 'resources' directory
    # `None` = 'resources/folder.png' (default)
    # @param btnposition `int` browse button position:
    #   * 0 (`QtWidgets.QLineEdit.LeadingPosition`) = left-aligned
    #   * 1 (`QtWidgets.QLineEdit.TrailingPosition`) = right-aligned
    # `None` = `QtWidgets.QLineEdit.TrailingPosition` (default)
    # @param opendialogtitle `str` dialog title (`None` will use a default title)
    # @param filefilters `str` file filters for file browse dialog, e.g.
    # `"Images (*.png *.xpm *.jpg);;Text files (*.txt);;XML files (*.xml)"`\n
    # `None` sets the default filter: `"All files (*.*)"`
    # @param fullpath `bool` whether the full file / folder path will be returned
    def __init__(self, text='', parent=None,
                dialogtype=None, btnicon=None, btnposition=None,
                opendialogtitle=None, filefilters=None, fullpath=True):
        super().__init__(text, parent)
        ## `str` path and dialog type ('file' or 'folder')
        self.dialogtype = dialogtype or 'fileopen'
        ## `str` icon file name in 'resources' directory
        self.btnicon = btnicon or 'folder.png'
        ## `int` browse button position (0 or 1)
        self.btnposition = btnposition or QtWidgets.QLineEdit.TrailingPosition
        ## `str` dialog title
        self._opendialogtitle = opendialogtitle
        ## `str` file filters for file browse dialog
        self._filefilters = filefilters
        ## `bool` whether the full file / folder path will be returned
        self.fullpath = fullpath
        ##  `QtWidgets.QWidget` the component edit delegate
        self.delegate = None
        self._set_title_and_filters()
        self.reset_action()

    ## Updates the dialog's title and file filters.
    def _set_title_and_filters(self):
        self.opendialogtitle = getattr(self, 'opendialogtitle', None) or self._opendialogtitle or \
            ('Select file' if self.dialogtype.startswith('file') else 'Select folder')
        self.filefilters = getattr(self, 'filefilters', None) or self._filefilters or 'All files (*.*)'

    ## Gets the start directory for the browse dialog.
    def _get_dir(self, text=None):
        if text is None: text = self.text()
        if text and not (os.path.isfile(text) or os.path.isdir(text)):
            text = os.path.join(os.getcwd(), text)
        if os.path.isfile(text) or os.path.isdir(text):
            return text #os.path.dirname(text)
        else:
            return os.getcwd()

    ## Clears previous actions from the underlying object.
    def _clear_actions(self):
        for act_ in self.actions():
            self.removeAction(act_)

    ## Resets the browse action (after setting options).
    def reset_action(self):
        self._clear_actions()
        self.btnaction = QAction(QtGui.QIcon(f"resources/{self.btnicon}"), '')
        self.btnaction.setToolTip(self.opendialogtitle)
        self.btnaction.triggered.connect(self.on_btnaction)
        self.addAction(self.btnaction, self.btnposition)

    ## Triggered slot for the browse action: opens dialog and sets the edit text.
    @Slot()
    def on_btnaction(self):
        if self.delegate: self.delegate.blockSignals(True)
        opendialogdir = self._get_dir()
        if self.dialogtype == 'fileopen':
            selected_path = QtWidgets.QFileDialog.getOpenFileName(self.window(), self.opendialogtitle, opendialogdir, self.filefilters)
            selected_path = selected_path[0]
        elif self.dialogtype == 'filesave':
            selected_path = QtWidgets.QFileDialog.getSaveFileName(self.window(), self.opendialogtitle, opendialogdir, self.filefilters)
            selected_path = selected_path[0]
        elif self.dialogtype == 'folder':
            selected_path = QtWidgets.QFileDialog.getExistingDirectory(self.window(), self.opendialogtitle, opendialogdir)
        else:
            if self.delegate: self.delegate.blockSignals(False)
            return
        if not selected_path:
            if self.delegate: self.delegate.blockSignals(False)
            return
        selected_path = selected_path.replace('/', os.sep)
        if not self.fullpath:
            selected_path = os.path.basename(selected_path)
        self.setText(selected_path)
        if self.delegate: self.delegate.blockSignals(False)

# ******************************************************************************** #
# *****          BasicDialog
# ******************************************************************************** #

## @brief Base class for simple dialog windows.
# Creates the basic layout for controls (leaving the central area free to add controls),
# and declares the validate() method to validate correctness of user input before accepting.
class BasicDialog(QtWidgets.QDialog):

    ## @param geometry `4-tuple` window geometry data: `(left, top, width, height)`.
    # If set to `None` (default), the position will be centered on the parent widget or screen
    # and the size will be automatically adjusted to fit the internal controls.
    # @param title `str` window title (`None` for no title)
    # @param icon `str` window icon file path (relative to project dir).
    # `None` means no icon.
    # @param parent `QtWidgets.QWidget` parent widget (default = `None`, i.e. no parent)
    # @param flags `QtCore.Qt.WindowFlags` [Qt window flags](https://doc.qt.io/qt-5/qt.html#WindowType-enum)
    # @param btn_ok `str`|`dict` 'OK' button caption or extended properties.
    # If it is passed as a `str`, it is the caption (text) of an 'OK' button which
    # triggers `accept()` when clicked. If passed as a `dict`, it may contain a number of
    # button properties:
    #   * `text` the button caption (text)
    #   * `tooltip` the button tooltip (shown on mouse hover)
    #   * `icon` the button's icon file (relative to project dir)
    # If `None` is passed, no 'OK' button will be added.
    # @param btn_cancel `str`|`dict` 'Cancel' button caption or extended properties.
    # See `btn_ok` description above. This button will trigger `reject()` to cancel the dialog.
    # @param sizepolicy `QtWidgets.QSizePolicy` [QWidget size policy](https://doc.qt.io/qt-5/qsizepolicy.html).
    # Default is fixed size in both directions (non-resizable dialog).
    def __init__(self, geometry=None, title=None, icon=None, parent=None,
                 flags=QtCore.Qt.WindowFlags(), btn_ok='OK', btn_cancel='Cancel',
                 sizepolicy=QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)):
        super().__init__(parent, flags)
        self.initUI(geometry, title, icon, btn_ok, btn_cancel)
        self.setSizePolicy(sizepolicy)

    ## @brief Creates the main (central) layout for controls.
    # Must be overridden by child classes to change the layout type
    # (default = `QtWidgets.QFormLayout`) and add controls.
    def addMainLayout(self):
        ## `QtWidgets.QFormLayout` central layout for controls
        self.layout_controls = QtWidgets.QFormLayout()

    ## Creates the core controls: OK and Cancel buttons and layouts.
    # @param geometry `4-tuple` window geometry data: `(left, top, width, height)`.
    # If set to `None` (default), the position will be centered on the parent widget or screen
    # and the size will be automatically adjusted to fit the internal controls.
    # @param title `str` window title (`None` for no title)
    # @param icon `str` window icon file name (relative to project dir). `None` means no icon.
    # @param btn_ok `str`|`dict` 'OK' button caption or extended properties.
    # If it is passed as a `str`, it is the caption (text) of an 'OK' button which
    # triggers `accept()` when clicked. If passed as a `dict`, it may contain a number of
    # button properties:
    #   * `text` the button caption (text)
    #   * `tooltip` the button tooltip (shown on mouse hover)
    #   * `icon` the button's icon file (relative to project dir)
    # If `None` is passed, no 'OK' button will be added.
    # @param btn_cancel `str`|`dict` 'Cancel' button caption or extended properties.
    # See `btn_ok` description above. This button will trigger `reject()` to cancel the dialog.
    def initUI(self, geometry=None, title=None, icon=None, btn_ok='OK', btn_cancel='Cancel'):
        self.addMainLayout()

        if btn_ok or btn_cancel:
            ## `QtWidgets.QVBoxLayout` window layout
            self.layout_main = QtWidgets.QVBoxLayout()
            ## `QtWidgets.QHBoxLayout` bottom layout for OK and Cancel buttons
            self.layout_bottom = QtWidgets.QHBoxLayout()
            self.layout_bottom.setSpacing(10)
            self.layout_bottom.addStretch()
            if btn_ok:
                if not isinstance(btn_ok, dict):
                    iconfile = utils.make_abspath('resources/like.png')
                    ttip = 'Apply and quit'
                    caption = btn_ok
                else:
                    iconfile = utils.make_abspath(btn_ok.get('icon', 'resources/like.png'))
                    ttip = btn_ok.get('tooltip', 'Apply and quit')
                    caption = btn_ok.get('text', 'OK')
                ## `QtWidgets.QPushButton` OK button
                self.btn_OK = QtWidgets.QPushButton(QtGui.QIcon(iconfile), caption, None)
                if ttip:
                    self.btn_OK.setToolTip(ttip)
                self.btn_OK.setMaximumWidth(150)
                self.btn_OK.setDefault(True)
                self.btn_OK.clicked.connect(self.on_btn_OK_clicked)
                self.layout_bottom.addWidget(self.btn_OK)
            if btn_cancel:
                if not isinstance(btn_cancel, dict):
                    iconfile = utils.make_abspath('resources/cancel.png')
                    ttip = 'Apply and quit'
                    caption = btn_cancel
                else:
                    iconfile = utils.make_abspath(btn_cancel.get('icon', 'resources/cancel.png'))
                    ttip = btn_cancel.get('tooltip', 'Cancel and quit')
                    caption = btn_cancel.get('text', 'Cancel')
                ## `QtWidgets.QPushButton` Cancel button
                self.btn_cancel = QtWidgets.QPushButton(QtGui.QIcon(iconfile), caption, None)
                if ttip:
                    self.btn_cancel.setToolTip(ttip)
                self.btn_cancel.setMaximumWidth(150)
                self.btn_cancel.clicked.connect(self.on_btn_cancel_clicked)
                self.layout_bottom.addWidget(self.btn_cancel)          
            self.layout_bottom.addStretch()
            self.layout_main.addLayout(self.layout_controls)
            # self.layout_main.addStretch()
            self.layout_main.addLayout(self.layout_bottom)
        else:
            self.layout_main = self.layout_controls

        self.setLayout(self.layout_main)

        if geometry:
            self.setGeometry(*geometry)
        else:
            self.adjustSize()
        if title:
            self.setWindowTitle(title)
        if icon:
            self.setWindowIcon(QtGui.QIcon(f"resources/{icon}"))

    ## Validates user input (reimplemented in child classes).
    # @returns `bool` `True` if user input is valid, `False` otherwise
    # @see on_btn_OK_clicked()
    def validate(self):
        return True

    ## @brief Fires when the OK button is clicked.
    # Calls validate() to check correctness of input and, if correct,
    # accepts and closes window.
    @Slot()
    def on_btn_OK_clicked(self):
        if self.validate(): self.accept()

    ## Fires when the Cancel button is clicked: rejects input and closes window.
    @Slot()
    def on_btn_cancel_clicked(self):
        self.reject()

# ******************************************************************************** #
# *****          TestEnv
# ******************************************************************************** #

## String to binary data optiona dialog used by gui::TestEnv.
class TestEnvEditorAsk(BasicDialog):
    def __init__(self):
        super().__init__(title='Interpret value as...', icon='info.png')

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QVBoxLayout()

        self.btns = QtWidgets.QButtonGroup()
        self.lo_btns = QtWidgets.QHBoxLayout()
        for i, t in enumerate(['Hex data', 'UTF-8 string', 'ASCII string']):
            rb = QtWidgets.QRadioButton(t) # e.g. de ad be ef 00 | DEADBEEF00
            if i == 0:
                rb.setChecked(True)
            self.btns.addButton(rb, i)
            self.lo_btns.addWidget(rb)
        self.btns.idToggled.connect(self.on_btns_selected)
        self.layout_controls.addLayout(self.lo_btns)

        self.te_notes = QtWidgets.QPlainTextEdit()
        palette = QtGui.QPalette()
        palette.setBrush(QtGui.QPalette.Base, QtGui.QBrush(QtGui.QColor(255, 0, 0, 0)))
        self.te_notes.setPalette(palette)
        self.te_notes.setReadOnly(True)
        self.layout_controls.addWidget(self.te_notes)

        self.on_btns_selected(0, True)

    @Slot(int, bool)
    def on_btns_selected(self, index, checked):
        if not checked: return
        txt = ''
        if index == 0:
            txt = 'Hex bytes, e.g. "de ad be ef 00" or "DEADBEEF00"'
        elif index == 1:
            txt = 'Unicode (UTF-8) string (will be converted to bytes)'
        elif index == 2:
            txt = 'ASCII string (will be converted to bytes)'
        self.te_notes.setPlainText(txt)

## New variable editor dialog used by gui::TestEnv.
class TestEnvEditor(BasicDialog):
    def __init__(self):
        super().__init__(title='New', icon='add.png')
        self.strdata_mode = None

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QFormLayout()

        self.le_name = QtWidgets.QLineEdit('')
        self.le_value = QtWidgets.QLineEdit('')
        self.cb_type = QtWidgets.QComboBox()
        self.cb_type.setEditable(False)
        cb_data = [('String', 'string'), ('Number', 'number'), ('Blob', 'binary'), ('String with macros', 'macro')]
        for d in cb_data:
            self.cb_type.addItem(d[0], d[1])
        self.cb_type.setCurrentIndex(0)
        self.cb_type.activated.connect(self.on_cb_type)
        self.chb_user = QtWidgets.QCheckBox('User (local)')
        self.chb_user.setChecked(True)
        self.chb_system = QtWidgets.QCheckBox('System')
        self.chb_system.setChecked(False)
        self.chb_system.setEnabled(sysproxy.CURRENT_USER[1])
        self.lo_chb = QtWidgets.QHBoxLayout()
        self.lo_chb.addWidget(self.chb_user)
        self.lo_chb.addWidget(self.chb_system)

        self.layout_controls.addRow('Name', self.le_name)
        self.layout_controls.addRow('Value', self.le_value)
        self.layout_controls.addRow('Type', self.cb_type)
        self.layout_controls.addRow('Namespaces', self.lo_chb)

    ## Accepts input closing the dialog only if a valid variable name and value are present.
    def validate(self):
        if not self.le_name.text().strip():
            QtWidgets.QMessageBox.critical(self, 'Error', 'Please indicate variable name!')
            return False
        if not (self.chb_user.isChecked() or self.chb_system.isChecked()):
            QtWidgets.QMessageBox.critical(self, 'Error', 'At least one domain must be selected!')
            return False
        return True

    ## Triggered when a combobox item is activated to selected the data type.
    @Slot(int)
    def on_cb_type(self, index):
        if index == 2:
            dlg = TestEnvEditorAsk()
            if dlg.exec():
                self.strdata_mode = dlg.btns.checkedId()
            else:
                try:
                    self.cb_type.currentIndexChanged.disconnect()
                    self.cb_type.setCurrentIndex(0)
                finally:
                    self.cb_type.currentIndexChanged.connect(self.on_cb_type)

## System environment variable viewer and editor interface.
class TestEnv(BasicDialog):

    def __init__(self):
        ## `sysproxy::Sysenv` env variable manipulator object
        self.sysenv = sysproxy.Sysenv(False)
        ## `gui::QThreadStump` variable update thread
        self.thread_update = QThreadStump(on_run=self.sysenv.update_vars, on_start=self.update_actions,
                                          on_finish=self.update_envlist, on_error=self.update_envlist)
        ## `gui::QThreadStump` variable edit thread
        self.thread_action = QThreadStump(on_run=None, on_start=self.update_actions,
                                          on_finish=self.refresh_vars_gui, on_error=self.refresh_vars_gui)
        ## `bool` marker showing that there have been changes to the variables
        self.has_changed = False
        super().__init__(title='System Environment Variable Editor', icon='settings.png', 
                         btn_ok={'text': 'Close', 'icon': 'resources/cancel.png', 
                         'tooltip': 'Close dialog'}, btn_cancel=None)

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QVBoxLayout()
        self.layout_controls.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)

        self.lo_controls = QtWidgets.QHBoxLayout()

        ## `QtWidgets.QTableWidget` table showing the env variables
        self.tw_envs = QtWidgets.QTableWidget(0, 3)
        self.tw_envs.setMinimumSize(200, 400)
        self.tw_envs.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tw_envs.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tw_envs.setSortingEnabled(True)
        self.tw_envs.itemSelectionChanged.connect(self.update_actions)
        self.tw_envs.itemChanged.connect(self.tw_itemChanged)
        self.tw_envs.setHorizontalHeaderLabels(['Variable', 'Domain', 'Value'])
        self.tw_envs.horizontalHeader().setStretchLastSection(True)
        self.lo_controls.addWidget(self.tw_envs)
        ## `QtWidgets.QToolBar` toolbar with action buttons
        self.tbar = QtWidgets.QToolBar()
        self.tbar.setOrientation(QtCore.Qt.Vertical)
        self.tbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.tbar.setFixedWidth(100)
        ## `QAction` refresh variables action
        self.act_refresh = QAction(QtGui.QIcon("resources/repeat.png"), 'Refresh')
        self.act_refresh.setShortcut(QtGui.QKeySequence.Refresh)
        self.act_refresh.setToolTip('Refresh system env variables')
        self.act_refresh.triggered.connect(self.on_act_refresh)
        self.tbar.addAction(self.act_refresh)
        ## `QAction` create variable action
        self.act_add = QAction(QtGui.QIcon("resources/add.png"), 'Add')
        self.act_add.setShortcut(QtGui.QKeySequence.New)
        self.act_add.setToolTip('Add variable')
        self.act_add.triggered.connect(self.on_act_add)
        self.tbar.addAction(self.act_add)
        ## `QAction` delete variable action
        self.act_delete = QAction(QtGui.QIcon("resources/error.png"), 'Unset')
        self.act_delete.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete))
        self.act_delete.setToolTip('Delete variables')
        self.act_delete.triggered.connect(self.on_act_delete)
        self.tbar.addAction(self.act_delete)

        self.lo_controls.addWidget(self.tbar)
        self.layout_controls.addLayout(self.lo_controls)
        ## `QtWidgets.QLabel` warning notification at bottom
        self.l_warning = QtWidgets.QLabel()
        # self.l_warning.setWordWrap(True)
        self.l_warning.setMinimumHeight(50)
        self.l_warning.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.l_warning.setAlignment(QtCore.Qt.AlignHCenter)
        self.l_warning.hide()

        self.layout_controls.addWidget(self.l_warning, alignment=QtCore.Qt.AlignCenter)

    def showEvent(self, event):
        # show
        event.accept()
        # fill vars
        self.on_act_refresh(False)

    def closeEvent(self, event):
        if self.thread_action.isRunning():
            self.thread_action.terminate()
            self.thread_action.wait()
        if self.thread_update.isRunning():
            self.thread_update.terminate()
            self.thread_update.wait()
        event.accept()

    ## Worker method TestEnv::thread_update to populate the main table from TestEnv::sysenv.
    def update_envlist(self):
        try:
            self.tw_envs.itemSelectionChanged.disconnect()
            self.tw_envs.itemChanged.disconnect()
        except:
            pass

        self.tw_envs.setSortingEnabled(False)
        self.tw_envs.clearContents()
        self.tw_envs.setRowCount(len(self.sysenv.locals) + len(self.sysenv.globals))
        self.tw_envs.setMinimumSize(300, 300)

        i = 0
        for k, lst_envs in enumerate((self.sysenv.locals, self.sysenv.globals)):
            for env_name in lst_envs:
                item0 = QtWidgets.QTableWidgetItem(env_name)
                item1 = QtWidgets.QTableWidgetItem('user' if k == 0 else 'system')
                val = lst_envs[env_name]
                if isinstance(val, str):
                    sval = val
                elif isinstance(val, bytes):
                    sval = " ".join(["{:02x}".format(x) for x in bytearray(val)])
                else:
                    sval = str(val)
                item2 = QtWidgets.QTableWidgetItem(sval)

                flags = QtCore.Qt.ItemIsEnabled
                if k == 0 or sysproxy.CURRENT_USER[1]:
                    flags1 = flags | QtCore.Qt.ItemIsSelectable
                    flags2 = flags1 | QtCore.Qt.ItemIsEditable
                else:
                    flags1 = flags
                    flags2 = flags
                    item2.setForeground(QtGui.QBrush(QtCore.Qt.gray))

                item0.setFlags(flags1)
                item1.setFlags(flags1)
                item2.setFlags(flags2)

                self.tw_envs.setItem(i, 0, item0)
                self.tw_envs.setItem(i, 1, item1)
                self.tw_envs.setItem(i, 2, item2)
                i += 1

        self.tw_envs.setSortingEnabled(True)
        self.tw_envs.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

        self.tw_envs.itemSelectionChanged.connect(self.update_actions)
        self.tw_envs.itemChanged.connect(self.tw_itemChanged)

        self.update_actions()

    ## Repopulates the main table in a separate thread (TestEnv::thread_update).
    def refresh_vars_gui(self):
        if self.thread_update.isRunning():
            return
        while self.thread_action.isRunning():
            self.thread_action.wait()
        self.update_warning()
        self.thread_update.start()

    ## Worker method TestEnv::thread_action to unset (delete) the selected variables.
    # @param varnames `iterable` an iterable of 2-tuples indicating the variable name
    # and domain:
    # ```
    # [ (env_name, 'user' or 'system'), ... ]
    # ```
    # @see sysproxy::Sysenv::unset_sys_env()
    def unset_vars(self, varnames):
        # varnames: list of 2-tuples: [('env', 'user'), ('env', 'system'), ...]
        def do_unser_vars():
            for var in varnames:
                modes = ['user']
                if var[1] == 'system':
                    modes.append('system')
                self.sysenv.unset_sys_env(var[0], modes, False)
        self.has_changed = True
        return do_unser_vars

    ## Worker method TestEnv::thread_action to change a variable.
    # @param varname `str` the env variable name
    # @param value `Any` the variable value
    # @param modes `iterable` an iterable of either or both of 'user' and 'system',
    # to indicate the domain(s) where the variable must be persisted
    # @see sysproxy::Sysenv::set_sys_env()
    def set_var(self, varname, value, modes=('user',)):
        def do_set_var():
            self.sysenv.set_sys_env(varname, value, modes, False)
        self.has_changed = True
        return do_set_var

    ## Worker method TestEnv::thread_action to create a new variable.
    # @param varname `str` the env variable name
    # @param value `Any` the variable value
    # @param valtype `str`|`int` the type of the value to create (see sysproxy::Sysenv::win_create_reg())
    # @param modes `iterable` an iterable of either or both of 'user' and 'system',
    # to indicate the domain(s) where the variable must be persisted
    # @see sysproxy::Sysenv::set_sys_env()
    def create_var(self, varname, value, valtype, modes=('user',)):
        def do_create_var():
            self.sysenv.set_sys_env(varname, value, True, valtype, modes, False)
        self.has_changed = True
        return do_create_var

    # ============================================= SLOTS ================================================================ #

    ## Updates the Enabled property of the 3 actions based on running threads and 
    # selected variables.
    @Slot()
    def update_actions(self):
        cnt_sel = len(self.tw_envs.selectedItems())
        running = self.thread_update.isRunning() or self.thread_action.isRunning()
        self.act_delete.setEnabled(not running and cnt_sel > 2)
        self.act_refresh.setEnabled(not running)
        self.act_add.setEnabled(not running)

    ## Updates the visibility and text of TestEnv::l_warning
    # if Super User privileges are detected or a variable change on Unix.
    @Slot()
    def update_warning(self):
        if (not self.has_changed and not sysproxy.CURRENT_USER[1]):
            return
        txt = ''
        if sysproxy.CURRENT_USER[1]:
            txt = 'SuperUser privileges active!<br>'
        if self.has_changed and sysproxy.OS != 'Windows':
            txt += 'Relogin to apply changes to OS!'
        self.l_warning.setText(f'<span style="font-size:11pt; font-weight:600; color:red;">{txt}</span>')
        self.l_warning.show()

    ## TestEnv::act_refresh handler: calls TestEnv::refresh_vars_gui().
    @Slot(bool)
    def on_act_refresh(self, checked):
        self.refresh_vars_gui()

    ## TestEnv::act_add handler: shows gui::TestEnvEditor dialog to
    # create a new env variable.
    @Slot(bool)
    def on_act_add(self, checked):
        while self.thread_update.isRunning() or self.thread_action.isRunning():
            self.thread_update.wait()
            self.thread_action.wait()

        new_var_dlg = TestEnvEditor()
        if not new_var_dlg.exec():
            return
        env = new_var_dlg.le_name.text().strip()
        val = new_var_dlg.le_value.text()
        valtype =  new_var_dlg.cb_type.currentData()

        if valtype == 'binary':
            if new_var_dlg.strdata_mode == 1:
                val = val.encode(utils.CODING)
            elif new_var_dlg.strdata_mode == 2:
                val = val.encode('ascii')
            else:
                val = bytes.fromhex(val)
        elif valtype == 'number':
            try:
                val = int(val)
            except:
                try:
                    val = bytes(struct.unpack('!I', struct.pack('!f', val))[0])
                    valtype = 'binary'
                except:
                    val = 0

        modes = []
        if new_var_dlg.chb_user.isChecked():
            modes.append('user')
        if new_var_dlg.chb_system.isChecked():
            modes.append('system')

        if not modes: return

        self.thread_action.on_run = self.create_var(env, val, valtype, modes)
        self.thread_action.start()

    ## TestEnv::act_delete handler: runs TestEnv::thread_action thread with the
    # TestEnv::unset_vars() method to delete the variables currently selected in 
    # TestEnv::tw_envs.
    @Slot(bool)
    def on_act_delete(self, checked):
        selitems = self.tw_envs.selectedItems()
        if len(selitems) < 2 or self.thread_update.isRunning():
            return

        while self.thread_action.isRunning():
            self.thread_action.wait()

        warned = False
        envs_to_unset = []
        for item in selitems:
            if item.column() != 0: continue
            envmode = self.tw_envs.item(item.row(), 1).text()
            if envmode == 'system' and not sysproxy.CURRENT_USER[1]:
                if not warned:
                    QtWidgets.QMessageBox.warning(self, 'Warning', 'Cannot unset variable without SU privilege!')
                continue
            envs_to_unset.append((item.text(), envmode))

        if not envs_to_unset: return

        self.thread_action.on_run = self.unset_vars(envs_to_unset)
        self.thread_action.start()

    ## Triggers when a variable has been changed / added in TestEnv::tw_envs.
    @Slot(QtWidgets.QTableWidgetItem)
    def tw_itemChanged(self, item: QtWidgets.QTableWidgetItem):
        if item.column() != 2 or self.thread_update.isRunning():
            return

        while self.thread_action.isRunning():
            self.thread_action.wait()

        env = self.tw_envs.item(item.row(), 0).text()
        val = item.text()
        envmode = self.tw_envs.item(item.row(), 1).text()

        self.thread_action.on_run = self.set_var(env, val, (envmode,))
        self.thread_action.start()

# ******************************************************************************** #
# *****          MainWindow
# ******************************************************************************** #

## The application's main GUI interface to control the system proxy settings.
class MainWindow(BasicDialog):

    ## Gets the application instance.
    # @returns `QtWidgets.QApplication` the application instance
    @staticmethod
    def get_app(args):
        try:
            app = QtWidgets.QApplication.instance()
            if app is None:
                app = QtWidgets.QApplication(args)
            return app
        except:
            return QtWidgets.QApplication(args)

    def __init__(self):
        ## `sysproxy::Proxy` the proxy manipulation object
        self.sysproxy = sysproxy.Proxy()
        ## `dict` local proxy settings bound to the GUI controls
        self.localproxy = self.sysproxy.asdict()
        rec = QtGui.QGuiApplication.primaryScreen().geometry()
        ## `gui::QThreadStump` thread to apply proxy changes to system
        self.thread_apply = QThreadStump(on_run=None, on_start=self._on_apply_start,
                                         on_finish=self._on_apply_finish, on_error=self._on_apply_finish)
        super().__init__(title='Proxen!', icon='proxen.png', geometry=(rec.width() // 2 - 225, rec.height() // 2 - 100, 450, 600),
                         flags=QtCore.Qt.Dialog | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.btn_OK.setToolTip('Apply changes and quit')
        self.btn_cancel.setToolTip('Cancel changes and quit')
        self.settings_to_gui()

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QVBoxLayout()

        ## `QSvgWidget` loading animation widget overlaying main window during operations
        self.loading_widget = QSvgWidget(utils.make_abspath('resources/loading.svg'))
        self.loading_widget.renderer().setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        self.loading_widget.setWindowFlags(QtCore.Qt.SplashScreen | QtCore.Qt.FramelessWindowHint)
        ## `QtWidgets.QToolBox` toolbox grouping the GUI controls
        self.tb = QtWidgets.QToolBox()
        self.tb.currentChanged.connect(self.tb_currentChanged)

        ## `QtWidgets.QWidget` main page: enable and persist toggles
        self.wmain = QtWidgets.QWidget()
        self.lo_wmain = QtWidgets.QHBoxLayout()

        # enable toggle
        act_enable_proxy_icon = QtGui.QIcon()
        act_enable_proxy_icon.addPixmap(QtGui.QPixmap(utils.make_abspath('resources/off-button.png')),  QtGui.QIcon.Normal, QtGui.QIcon.Off)
        act_enable_proxy_icon.addPixmap(QtGui.QPixmap(utils.make_abspath('resources/on-button.png')), QtGui.QIcon.Normal, QtGui.QIcon.On)
        self.act_enable_proxy = QAction(act_enable_proxy_icon, '')
        self.act_enable_proxy.setToolTip('Toggle proxy on/off')
        self.act_enable_proxy.setCheckable(True)
        self.act_enable_proxy.setChecked(False)
        self.act_enable_proxy.toggled.connect(self.on_act_enable_proxy)
        self.btn_enable_proxy = QtWidgets.QToolButton()
        self.btn_enable_proxy.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        # self.btn_enable_proxy.setFixedSize(64, 64)
        self.btn_enable_proxy.setIconSize(QtCore.QSize(54, 54))
        self.btn_enable_proxy.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))
        self.btn_enable_proxy.setDefaultAction(self.act_enable_proxy)
        self.btn_enable_proxy.setStyleSheet('QToolButton { border: null; padding: 0px } ')
        self.l_enable_proxy = QtWidgets.QLabel('ENABLE')
        self.lo_enable_proxy = QtWidgets.QVBoxLayout()
        self.lo_enable_proxy.addWidget(self.l_enable_proxy, 0, QtCore.Qt.AlignHCenter)
        self.lo_enable_proxy.addWidget(self.btn_enable_proxy, 0, QtCore.Qt.AlignHCenter)

        self.lo_wmain.addLayout(self.lo_enable_proxy)
        self.lo_wmain1 = QtWidgets.QVBoxLayout()
        self.lo_wmain1.addLayout(self.lo_wmain)
        self.lo_wmain1.addStretch()
        self.wmain.setLayout(self.lo_wmain1)
        self.tb.addItem(self.wmain, 'Enable')

        ## `QtWidgets.QWidget` config page
        self.wconfig = QtWidgets.QWidget()
        self.lo_wconfig = QtWidgets.QVBoxLayout()

        # protocol selector
        self.lo_btns_protocol = QtWidgets.QHBoxLayout()
        self.btns_protocol = QtWidgets.QButtonGroup()
        for i, s in enumerate(('HTTP', 'HTTPS', 'FTP', 'RSYNC')):
            rb = QtWidgets.QRadioButton(s)
            self.btns_protocol.addButton(rb, i)
            self.lo_btns_protocol.addWidget(rb)
        self.btns_protocol.button(0).setChecked(True)
        self.btns_protocol.idToggled.connect(self.on_btns_protocol_selected)
        self.lo_wconfig.addLayout(self.lo_btns_protocol)

        # proxy group box
        self.gb_proxy = QtWidgets.QGroupBox('Enable proxy')
        self.gb_proxy.setCheckable(True)
        self.gb_proxy.toggled.connect(self.on_gb_proxy_checked)
        self.lo_gb_proxy = QtWidgets.QVBoxLayout()
        self.lo_proxyhost = QtWidgets.QVBoxLayout()
        self.l_proxyhost = QtWidgets.QLabel('Proxy host')
        self.le_proxyhost = QtWidgets.QLineEdit()
        self.le_proxyhost.setPlaceholderText('Proxy host')
        self.le_proxyhost.textEdited.connect(self.on_le_proxyhost_edit)
        self.lo_proxyhost.addWidget(self.l_proxyhost)
        self.lo_proxyhost.addWidget(self.le_proxyhost)
        self.lo_proxyport = QtWidgets.QVBoxLayout()
        self.l_proxyport = QtWidgets.QLabel('Port')
        self.le_proxyport = QtWidgets.QSpinBox()
        self.le_proxyport.setRange(1, 65536)
        self.le_proxyport.setFixedWidth(80)
        self.le_proxyport.valueChanged.connect(self.on_le_proxyport_changed)
        self.lo_proxyport.addWidget(self.l_proxyport)
        self.lo_proxyport.addWidget(self.le_proxyport)
        self.lo_proxy_and_port = QtWidgets.QHBoxLayout()
        self.lo_proxy_and_port.setSpacing(10)
        self.lo_proxy_and_port.addLayout(self.lo_proxyhost)
        self.lo_proxy_and_port.addLayout(self.lo_proxyport)
        self.lo_gb_proxy.addLayout(self.lo_proxy_and_port)
        self.gb_auth = QtWidgets.QGroupBox('Authorization')
        self.gb_auth.setCheckable(True)
        self.gb_auth.toggled.connect(self.on_gb_auth_checked)
        self.lo_gb_auth = QtWidgets.QHBoxLayout()
        self.lo_gb_auth.setSpacing(10)
        self.l_user = QtWidgets.QLabel('User name')
        self.le_user = QtWidgets.QLineEdit()
        self.le_user.setPlaceholderText('User name')
        self.le_user.textEdited.connect(self.on_le_user_edit)
        self.lo_user = QtWidgets.QVBoxLayout()
        self.lo_user.addWidget(self.l_user)
        self.lo_user.addWidget(self.le_user)
        self.lo_gb_auth.addLayout(self.lo_user)
        self.l_pass = QtWidgets.QLabel('Password')
        self.le_pass = QtWidgets.QLineEdit()
        self.le_pass.setPlaceholderText('Password')
        self.le_pass.textEdited.connect(self.on_le_pass_edit)
        self.le_pass.setEchoMode(QtWidgets.QLineEdit.PasswordEchoOnEdit)
        self.lo_pass = QtWidgets.QVBoxLayout()
        self.lo_pass.addWidget(self.l_pass)
        self.lo_pass.addWidget(self.le_pass)
        self.lo_gb_auth.addLayout(self.lo_pass)
        self.gb_auth.setLayout(self.lo_gb_auth)
        self.lo_gb_proxy.addWidget(self.gb_auth)
        self.btn_copyto = QtWidgets.QPushButton('Copy to others')
        self.btn_copyto.setFixedWidth(120)
        self.btn_copyto.clicked.connect(self.on_btn_copyto)
        self.lo_gb_proxy.addWidget(self.btn_copyto)

        self.lo_gb_proxy.addStretch()
        self.gb_proxy.setLayout(self.lo_gb_proxy)
        self.lo_wconfig.addWidget(self.gb_proxy)

        # no proxy
        self.gb_noproxy = QtWidgets.QGroupBox('No proxy')
        self.gb_noproxy.setCheckable(True)
        self.gb_noproxy.toggled.connect(self.on_gb_noproxy_checked)
        self.lo_gb_noproxy = QtWidgets.QVBoxLayout()

        self.te_noproxy = QtWidgets.QTextEdit()
        self.te_noproxy.setPlaceholderText('Excluded hosts (separate with new lines and/or spaces)')
        self.te_noproxy.setAcceptRichText(False)
        self.te_noproxy.setUndoRedoEnabled(True)
        self.te_noproxy.textChanged.connect(self.on_te_noproxy_changed)
        self.lo_gb_noproxy.addWidget(self.te_noproxy)
        self.gb_noproxy.setLayout(self.lo_gb_noproxy)
        self.lo_wconfig.addWidget(self.gb_noproxy)

        # load / save settings
        self.lo_loadsave = QtWidgets.QHBoxLayout()
        self.lo_loadsave.setSpacing(10)

        self.act_apply = QAction(QtGui.QIcon("resources/success.png"), 'Apply')
        self.act_apply.setToolTip('Apply proxy configuration to system')
        self.act_apply.triggered.connect(self.on_act_apply)
        self.btn_apply = QtWidgets.QToolButton()
        self.btn_apply.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_apply.setFixedWidth(90)
        self.btn_apply.setDefaultAction(self.act_apply)
        self.lo_loadsave.addWidget(self.btn_apply)

        self.act_restore = QAction(QtGui.QIcon("resources/undo.png"), 'Restore')
        self.act_restore.setToolTip('Restore proxy configuration from system')
        self.act_restore.triggered.connect(self.on_act_restore)
        self.btn_restore = QtWidgets.QToolButton()
        self.btn_restore.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_restore.setFixedWidth(90)
        self.btn_restore.setDefaultAction(self.act_restore)
        self.lo_loadsave.addWidget(self.btn_restore)

        self.act_saveconfig = QAction(QtGui.QIcon("resources/save.png"), 'Save')
        self.act_saveconfig.setToolTip('Save current configuration to disk')
        self.act_saveconfig.triggered.connect(self.on_act_saveconfig)
        self.btn_saveconfig = QtWidgets.QToolButton()
        self.btn_saveconfig.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_saveconfig.setFixedWidth(90)
        self.btn_saveconfig.setDefaultAction(self.act_saveconfig)
        self.lo_loadsave.addWidget(self.btn_saveconfig)

        self.act_loadconfig = QAction(QtGui.QIcon("resources/folder-15.png"), 'Load')
        self.act_loadconfig.setToolTip('Load configuration from disk')
        self.act_loadconfig.triggered.connect(self.on_act_loadconfig)
        self.btn_loadconfig = QtWidgets.QToolButton()
        self.btn_loadconfig.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_loadconfig.setFixedWidth(90)
        self.btn_loadconfig.setDefaultAction(self.act_loadconfig)
        self.lo_loadsave.addWidget(self.btn_loadconfig)

        self.lo_wconfig.addLayout(self.lo_loadsave)

        self.wconfig.setLayout(self.lo_wconfig)
        self.tb.addItem(self.wconfig, 'Proxies')

        ## `QtWidgets.QWidget` app settings page
        self.wappconfig = QtWidgets.QWidget()
        self.lo_wappconfig = QtWidgets.QVBoxLayout()

        self.chb_debug = QtWidgets.QCheckBox('Debug messages to console')
        self.chb_debug.setToolTip('Setting will apply after app restart')
        self.chb_debug.setChecked(utils.DEBUG)
        self.lo_wappconfig.addWidget(self.chb_debug)
        self.chb_log = QtWidgets.QCheckBox('Write log to log.txt')
        self.chb_log.setToolTip(self.chb_debug.toolTip())
        self.chb_log.setChecked(not utils.LOGFILE is None)
        self.lo_wappconfig.addWidget(self.chb_log)

        self.act_envedit = QAction(QtGui.QIcon("resources/edit.png"), 'Env variables...')
        self.act_envedit.setToolTip('View and edit all environment variables')
        self.act_envedit.triggered.connect(self.on_act_envedit)
        self.btn_envedit = QtWidgets.QToolButton()
        self.btn_envedit.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_envedit.setFixedWidth(150)
        self.btn_envedit.setDefaultAction(self.act_envedit)
        self.lo_wappconfig.addWidget(self.btn_envedit)

        self.lo_wappconfig.addStretch()

        self.wappconfig.setLayout(self.lo_wappconfig)
        self.tb.addItem(self.wappconfig, 'Settings')

        self.layout_controls.addWidget(self.tb)
        # self.layout_controls.addStretch()

    ## Applies the local settings to the system.
    # @see sysproxy::Proxy::fromdict()
    def _do_apply_config(self):
        self.sysproxy.fromdict(self.localproxy)
        # time.sleep(5)        

    ## Restores the previous proxy settings.
    # @see sysproxy::Proxy::restore()
    def _do_restore_config(self):
        self.sysproxy.restore()

    ## Callback triggered after the apply thread (MainWindow::thread_apply) completes its job.
    def _on_apply_finish(self):
        self.localproxy = self.sysproxy.asdict()
        self.loading_widget.hide()
        self.setVisible(True)
        self.settings_to_gui()

    ## Callback triggered before the apply thread (MainWindow::thread_apply) starts its job.
    def _on_apply_start(self):
        self.setVisible(False)
        self.loading_widget.setGeometry(self.x(), self.y(), self.width(), self.height())
        self.loading_widget.show()

    ## Starts the apply thread (MainWindow::thread_apply) to apply changes.
    def apply_config(self):
        if self.thread_apply.isRunning():
            return
        self.thread_apply.on_run = self._do_apply_config
        # self.thread_apply.on_finish = self._on_apply_finish
        self.thread_apply.start()

    ## Starts the apply thread (MainWindow::thread_apply) to restore the previous state.
    def restore_config(self):
        if self.thread_apply.isRunning():
            return
        self.thread_apply.on_run = self._do_restore_config
        # self.thread_apply.on_finish = self._on_apply_finish
        self.thread_apply.start()

    ## Saves the app settings to `config.ini`.
    def save_app_settings(self):
        utils.CONFIG['app']['debug'] = str(self.chb_debug.isChecked()).lower()
        utils.CONFIG['app']['logfile'] = 'log.txt' if self.chb_log.isChecked() else None
        utils.config_save()

    # ============================================= SLOTS ================================================================ #

    def showEvent(self, event):
        # show
        event.accept()
        # fill vars
        self.settings_to_gui()

    def closeEvent(self, event):
        # apply app config
        self.save_app_settings()

        # apply proxy config
        if self.thread_apply.isRunning():
            self.thread_apply.wait()
        if self.sysproxy.asdict() != self.localproxy:
            # unsaved changes
            btn = QtWidgets.QMessageBox.question(self, 'Apply proxy settings',
                                                'APPLY system proxy configuration before quit?',
                                                defaultButton=QtWidgets.QMessageBox.Yes)
            self.thread_apply.on_run = self._do_apply_config if btn == QtWidgets.QMessageBox.Yes else self._do_restore_config
            self.thread_apply.on_start = None
            self.thread_apply.on_finish = None
            self.thread_apply.on_error = None
            self.thread_apply.start()
            self.thread_apply.wait()
        event.accept()

    ## Updates the GUI controls from the data in MainWindow::localproxy.
    @Slot()
    def settings_to_gui(self):
        # disconnect signals
        try:
            self.act_enable_proxy.toggled.disconnect()
            self.gb_noproxy.toggled.disconnect()
            self.te_noproxy.textChanged.disconnect()
        except:
            pass

        # main toggle
        self.act_enable_proxy.setChecked(self.localproxy['enabled'])

        # settings
        self.on_btns_protocol_selected(0, True)

        noproxy_ = not self.localproxy['noproxy'] is None
        self.gb_noproxy.setChecked(noproxy_)
        self.te_noproxy.setPlainText('\n'.join(self.localproxy['noproxy'].split(',')) if noproxy_ else '')
        self.update_actions_enabled()

        # reconnect signals
        self.act_enable_proxy.toggled.connect(self.on_act_enable_proxy)
        self.gb_noproxy.toggled.connect(self.on_gb_noproxy_checked)
        self.te_noproxy.textChanged.connect(self.on_te_noproxy_changed)

    ## Asks the user to apply unsaved changes before quitting.
    @Slot()
    def on_btn_OK_clicked(self):
        if not self.validate(): return
        self.save_app_settings()
        if self.sysproxy.asdict() != self.localproxy:
            btn = QtWidgets.QMessageBox.question(self, 'Apply proxy settings',
                                                 'APPLY proxy configuration and quit?',
                                                 defaultButton=QtWidgets.QMessageBox.Yes)
            if btn != QtWidgets.QMessageBox.Yes:
                return

            if self.thread_apply.isRunning():
                self.thread_apply.wait()

            self.thread_apply.on_run = self._do_apply_config
            self.thread_apply.on_finish = None
            self.thread_apply.on_error = None
            self.thread_apply.start()
            self.thread_apply.wait()
        self.accept()

    ## Asks the user to cancel unsaved changes before quitting.
    @Slot()
    def on_btn_cancel_clicked(self):
        self.save_app_settings()
        if self.sysproxy.asdict() != self.localproxy:
            btn = QtWidgets.QMessageBox.question(self, 'Cancel proxy settings',
                                                 'RESTORE system proxy configuration and quit?',
                                                 defaultButton=QtWidgets.QMessageBox.Yes)
            if btn != QtWidgets.QMessageBox.Yes:
                return
            if self.thread_apply.isRunning():
                self.thread_apply.wait()
            self.thread_apply.on_run = self._do_restore_config
            self.thread_apply.on_finish = None
            self.thread_apply.on_error = None
            self.thread_apply.start()
            self.thread_apply.wait()
        self.reject()

    ## Updates the app actions based on unsaved changes and active threads.
    @Slot()
    def update_actions_enabled(self):
        sysdict = self.sysproxy.asdict()
        has_changed = (self.localproxy != sysdict)

        self.act_apply.setEnabled(has_changed)
        self.act_restore.setEnabled(has_changed)

        # update control styles to highlight unsaved properties
        # proxy = PROXY_OBJS[self.btns_protocol.checkedId()]
        # if (self.localproxy[proxy] and not sysdict[proxy]) or (not self.localproxy[proxy] and sysdict[proxy]):
        #     self.gb_proxy.setStyleSheet('QGroupBox::indicator { background-color: yellow; }')
        # else:
        #     self.gb_proxy.setStyleSheet('QGroupBox::indicator { background-color: white; }')

        # if self.localproxy[proxy]:
        #     self.le_proxyhost.setStyleSheet('QLineEdit {{ background: {}; }} '.format(
        #         'white' if self.localproxy[proxy]['host'] == sysdict[proxy]['host'] else 'yellow'))

    ## Triggers when the Enable toggle is switched.
    @Slot(bool)
    def on_act_enable_proxy(self, checked):
        self.localproxy['enabled'] = checked
        # apply immediately to system
        self.apply_config()

    ## Triggers when the `MainWindow::tb` toolbox is changed by selecting a group.
    @Slot(int)
    def tb_currentChanged(self, index):
        self.setFixedHeight(250 if index != 1 else 600)

    ## Triggers when a proxy radio button is checked to show the settings
    # for the corresponding proxy.
    @Slot(int, bool)
    def on_btns_protocol_selected(self, index, checked):
        # disconnect signals
        try:
            self.gb_proxy.toggled.disconnect()
            self.le_proxyhost.textEdited.disconnect()
            self.le_proxyport.valueChanged.disconnect()
            self.gb_auth.toggled.disconnect()
            self.le_user.textEdited.disconnect()
            self.le_pass.textEdited.disconnect()
        except:
            pass
        proxy_obj = self.localproxy.get(PROXY_OBJS[self.btns_protocol.checkedId()], None)
        self.gb_proxy.setChecked(not proxy_obj is None)
        self.le_proxyhost.setText(proxy_obj['host'] if proxy_obj else '')
        if proxy_obj:
            self.le_proxyport.setValue(proxy_obj['port'])
        self.gb_auth.setChecked(proxy_obj['auth'] if proxy_obj else False)
        self.le_user.setText(proxy_obj['uname'] if proxy_obj and proxy_obj['auth'] else '')
        self.le_pass.setText(proxy_obj['password'] if proxy_obj and proxy_obj['auth'] else '')
        # reconnect signals
        self.gb_proxy.toggled.connect(self.on_gb_proxy_checked)
        self.le_proxyhost.textEdited.connect(self.on_le_proxyhost_edit)
        self.le_proxyport.valueChanged.connect(self.on_le_proxyport_changed)
        self.gb_auth.toggled.connect(self.on_gb_auth_checked)
        self.le_user.textEdited.connect(self.on_le_user_edit)
        self.le_pass.textEdited.connect(self.on_le_pass_edit)

    ## `MainWindow::act_apply` handler: applies changes to system.
    @Slot(bool)
    def on_act_apply(self, checked):
        self.update_actions_enabled()
        if not self.act_apply.isEnabled():
            return
        self.apply_config()

    ## `MainWindow::act_restore` handler: restores the current proxy settings.
    @Slot(bool)
    def on_act_restore(self, checked):
        self.update_actions_enabled()
        if not self.act_restore.isEnabled():
            return
        self.restore_config()

    ## `MainWindow::act_loadconfig` handler: loads proxy settings from a JSON file.
    @Slot(bool)
    def on_act_loadconfig(self, checked):
        selected_path = QtWidgets.QFileDialog.getOpenFileName(self, 'Select config file', 'proxy_config.json', 'JSON files (*.json)')
        selected_path = selected_path[0]
        if not selected_path: return
        with open(selected_path, 'r', encoding=utils.CODING) as f_:
            self.localproxy = json.load(f_) # TODO: check keys in dict import
            self.settings_to_gui()

    ## `MainWindow::act_saveconfig` handler: saves proxy settings to a JSON file.
    @Slot(bool)
    def on_act_saveconfig(self, checked):
        selected_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Select config file', 'proxy_config.json', 'JSON files (*.json)')
        selected_path = selected_path[0]
        if not selected_path: return
        with open(selected_path, 'w', encoding=utils.CODING) as f_:
            json.dump(self.localproxy, f_, indent=4)

    ## Triggers when the proxy host is edited.
    @Slot(str)
    def on_le_proxyhost_edit(self, text):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        proxy_obj = self.localproxy.get(prot, None)
        if not proxy_obj is None:
            proxy_obj['host'] = text
        else:
            prot_ = prot.split('_')[0]
            host_ = text
            port_ = self.le_proxyport.value()
            self.localproxy[prot] = sysproxy.Proxyconf(None, prot_, host_,
                                                       port_, self.gb_auth.isChecked(),
                                                       self.le_user.text(), self.le_pass.text()).asdict()
        self.update_actions_enabled()

    ## Triggers when the proxy port is changed.
    @Slot(int)
    def on_le_proxyport_changed(self, value):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        proxy_obj: sysproxy.Proxyconf = self.localproxy.get(prot, None)
        if not proxy_obj is None:
            proxy_obj['port'] = value
        else:
            prot_ = prot.split('_')[0]
            host_ = self.le_proxyhost.text()
            port_ = value
            self.localproxy[prot] = sysproxy.Proxyconf(None, prot_, host_,
                                                       port_, self.gb_auth.isChecked(),
                                                       self.le_user.text(), self.le_pass.text()).asdict()
        self.update_actions_enabled()

    ## Triggers when the proxy group box is checked or unchecked.
    @Slot(bool)
    def on_gb_proxy_checked(self, checked):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        if not checked:
            self.localproxy[prot] = None
            self.settings_to_gui()
        else:
            prot_ = prot.split('_')[0]
            host_ = self.le_proxyhost.text()
            port_ = self.le_proxyport.value()
            self.localproxy[prot] = sysproxy.Proxyconf(None, prot_, host_,
                                                       port_, self.gb_auth.isChecked(),
                                                       self.le_user.text(), self.le_pass.text()).asdict()
            self.update_actions_enabled()

    ## Triggers when the proxy auth group box is checked or unchecked.
    @Slot(bool)
    def on_gb_auth_checked(self, checked):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        if self.localproxy.get(prot, None):
            self.localproxy[prot]['auth'] = checked
            self.update_actions_enabled()

    ## Triggers when the proxy user name is edited.
    @Slot(str)
    def on_le_user_edit(self, text):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        if self.localproxy.get(prot, None):
            self.localproxy[prot]['uname'] = text
            self.update_actions_enabled()

    ## Triggers when the proxy password is edited.
    @Slot(str)
    def on_le_pass_edit(self, text):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        if self.localproxy.get(prot, None):
            self.localproxy[prot]['password'] = text
            self.update_actions_enabled()

    ## Triggers when the no-proxy group box is checked or unchecked.
    @Slot(bool)
    def on_gb_noproxy_checked(self, checked):
        if not checked:
            self.localproxy['noproxy'] = None
        else:
            self.localproxy['noproxy'] = str(self.sysproxy.noproxy) if not self.sysproxy.noproxy is None else None
        self.update_actions_enabled()

    ## Triggers when the no-proxy text is changed.
    @Slot()
    def on_te_noproxy_changed(self):
        if self.localproxy.get('noproxy', None) is None:
            return
        txt = self.te_noproxy.toPlainText()
        if txt:
            self.localproxy['noproxy'] = ','.join(txt.split('\n'))
        else:
            self.localproxy['noproxy'] = None
        self.update_actions_enabled()

    ## The 'Copy To' button handler: copies settings to the other proxies.
    @Slot()
    def on_btn_copyto(self):
        prot = PROXY_OBJS[self.btns_protocol.checkedId()]
        for prot_other in PROXY_OBJS[:-1]:
            if prot_other == prot: continue
            self.localproxy[prot_other] = self.localproxy[prot].copy()
        self.settings_to_gui()

    ## `MainWindow::act_envedit` handler: shows the gui::TestEnv dialog to 
    # edit variables manually.
    @Slot(bool)
    def on_act_envedit(self, checked):
        TestEnv().exec()