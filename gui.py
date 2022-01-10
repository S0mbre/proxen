# -*- coding: utf-8 -*-
import os, json, struct
import traceback
from qtimports import *
import utils
import sysproxy

# ******************************************************************************** #

PROXY_OBJS = ['http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'noproxy']

# ******************************************************************************** #
# *****          QThreadStump
# ******************************************************************************** #

class QThreadStump(QtCore.QThread):

    ## Error signal (args are: instance of this thread and the error message)
    sig_error = Signal(QtCore.QThread, str)

    def __init__(self, default_priority=QtCore.QThread.NormalPriority,
                 on_start=None, on_finish=None, on_run=None, on_error=None,
                 start_signal=None, stop_signal=None,
                 free_on_finish=False, start_now=False, can_terminate=True):
        super().__init__()
        self.init(default_priority, on_start, on_finish, on_run, on_error,
                  start_signal, stop_signal, free_on_finish, can_terminate)
        if start_now: self.start()

    def __del__(self):
        try:
            self.wait()
        except:
            pass

    def init(self, default_priority=QtCore.QThread.NormalPriority,
             on_start=None, on_finish=None, on_run=None, on_error=None,
             start_signal=None, stop_signal=None,
             free_on_finish=False, can_terminate=True):
        try:
            self.started.disconnect()
            self.finished.disconnect()
            self.sig_error.disconnect()
        except:
            pass

        self.setTerminationEnabled(can_terminate)
        if on_start: self.started.connect(on_start)
        if on_finish: self.finished.connect(on_finish)
        if free_on_finish: self.finished.connect(self.deleteLater)
        if start_signal: start_signal.connect(self.start)
        if stop_signal: stop_signal.connect(self.terminate)
        if on_error: self.sig_error.connect(on_error)
        self.default_priority = default_priority if default_priority != QtCore.QThread.InheritPriority else QtCore.QThread.NormalPriority
        self.on_run = on_run
        self.mutex = QtCore.QMutex()

    def lock(self):
        self.mutex.lock()

    def unlock(self):
        self.mutex.unlock()

    ## Executes the worker function pointed to by QThreadStump::on_run.
    def run(self):
        self.setPriority(self.default_priority)
        if self.on_run and not self.isInterruptionRequested():
            try:
                self.on_run()
            except Exception as err:
                traceback.print_exc(limit=None)
                self.sig_error.emit(self, str(err))

# ******************************************************************************** #
# *****          BrowseEdit
# ******************************************************************************** #

class BrowseEdit(QtWidgets.QLineEdit):

    def __init__(self, text='', parent=None,
                dialogtype=None, btnicon=None, btnposition=None,
                opendialogtitle=None, filefilters=None, fullpath=True):
        super().__init__(text, parent)
        ## `str` path and dialog type ('file' or 'folder')
        self.dialogtype = dialogtype or 'fileopen'
        ## `str` icon file name in 'assets/icons'
        self.btnicon = btnicon or 'folder.png'
        ## `int` browse button position (0 or 1)
        self.btnposition = btnposition or QtWidgets.QLineEdit.TrailingPosition
        ## `str` dialog title
        self._opendialogtitle = opendialogtitle
        ## `str` file filters for file browse dialog
        self._filefilters = filefilters
        self.fullpath = fullpath
        self.delegate = None
        self._set_title_and_filters()
        self.reset_action()

    def _set_title_and_filters(self):
        self.opendialogtitle = getattr(self, 'opendialogtitle', None) or self._opendialogtitle or \
            ('Select file' if self.dialogtype.startswith('file') else 'Select folder')
        self.filefilters = getattr(self, 'filefilters', None) or self._filefilters or 'All files (*.*)'

    def _get_dir(self, text=None):
        if text is None: text = self.text()
        if text and not (os.path.isfile(text) or os.path.isdir(text)):
            text = os.path.join(os.getcwd(), text)
        if os.path.isfile(text) or os.path.isdir(text):
            return text #os.path.dirname(text)
        else:
            return os.getcwd()

    def _clear_actions(self):
        for act_ in self.actions():
            self.removeAction(act_)

    def reset_action(self):
        self._clear_actions()
        self.btnaction = QAction(QtGui.QIcon(f"resources/{self.btnicon}"), '')
        self.btnaction.setToolTip(self.opendialogtitle)
        self.btnaction.triggered.connect(self.on_btnaction)
        self.addAction(self.btnaction, self.btnposition)
        #self.show()

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

class BasicDialog(QtWidgets.QDialog):

    def __init__(self, geometry=None, title=None, icon=None, parent=None,
                 flags=QtCore.Qt.WindowFlags(),
                 sizepolicy=QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)):
        super().__init__(parent, flags)
        self.initUI(geometry, title, icon)
        self.setSizePolicy(sizepolicy)

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QFormLayout()

    def initUI(self, geometry=None, title=None, icon=None):
        self.addMainLayout()
        self.btn_OK = QtWidgets.QPushButton(QtGui.QIcon("resources/like.png"), 'OK', None)
        self.btn_OK.setMaximumWidth(150)
        self.btn_OK.setDefault(True)
        self.btn_OK.clicked.connect(self.on_btn_OK_clicked)
        self.btn_cancel = QtWidgets.QPushButton(QtGui.QIcon("resources/cancel.png"), 'Cancel', None)
        self.btn_cancel.setMaximumWidth(150)
        self.btn_cancel.clicked.connect(self.on_btn_cancel_clicked)
        self.layout_bottom = QtWidgets.QHBoxLayout()
        self.layout_bottom.setSpacing(10)
        self.layout_bottom.addStretch()
        self.layout_bottom.addWidget(self.btn_OK)
        self.layout_bottom.addWidget(self.btn_cancel)
        self.layout_bottom.addStretch()

        self.layout_main = QtWidgets.QVBoxLayout()
        self.layout_main.addLayout(self.layout_controls)
        # self.layout_main.addStretch()
        self.layout_main.addLayout(self.layout_bottom)

        self.setLayout(self.layout_main)
        if geometry:
            self.setGeometry(*geometry)
        else:
            self.adjustSize()
        if title:
            self.setWindowTitle(title)
        if icon:
            self.setWindowIcon(QtGui.QIcon(f"resources/{icon}"))

    def validate(self):
        return True

    @Slot()
    def on_btn_OK_clicked(self):
        if self.validate(): self.accept()

    @Slot()
    def on_btn_cancel_clicked(self):
        self.reject()

# ******************************************************************************** #
# *****          TestEnv
# ******************************************************************************** # 

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
        self.cb_type.currentIndexChanged.connect(self.on_cb_type)
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

    def validate(self):
        if not self.le_name.text().strip():
            QtWidgets.QMessageBox.critical(self, 'Error', 'Please indicate variable name!')
            return False
        if not (self.chb_user.isChecked() or self.chb_system.isChecked()):
            QtWidgets.QMessageBox.critical(self, 'Error', 'At least one domain must be selected!')
            return False
        return True

    @Slot(int)
    def on_cb_type(self, index):
        if index == 2:
            dlg = TestEnvEditorAsk()
            if dlg.exec():
                self.strdata_mode = dlg.btns.checkedId()
            else:
                self.strdata_mode = 0

class TestEnv(BasicDialog):

    def __init__(self):
        self.sysproxy = sysproxy.Sysproxy(False)
        self.thread_update = QThreadStump(on_run=self.sysproxy.update_vars, on_start=self.update_actions,
                                          on_finish=self.update_envlist, on_error=self.update_envlist)
        self.thread_action = QThreadStump(on_run=None, on_start=self.update_actions,
                                          on_finish=self.refresh_vars_gui, on_error=self.refresh_vars_gui)
        super().__init__(title='SysEnv', icon='settings.png')

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QHBoxLayout()

        self.tw_envs = QtWidgets.QTableWidget(0, 3)
        self.tw_envs.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tw_envs.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tw_envs.setSortingEnabled(True)
        self.tw_envs.itemSelectionChanged.connect(self.update_actions)
        self.tw_envs.itemChanged.connect(self.tw_itemChanged)
        self.tw_envs.setHorizontalHeaderLabels(['Variable', 'Domain', 'Value'])
        self.tw_envs.horizontalHeader().setStretchLastSection(True)
        self.layout_controls.addWidget(self.tw_envs)

        self.tbar = QtWidgets.QToolBar()
        self.tbar.setOrientation(QtCore.Qt.Vertical)
        self.tbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.tbar.setFixedWidth(100)

        self.act_refresh = QAction(QtGui.QIcon("resources/repeat.png"), 'Refresh')
        self.act_refresh.setShortcut(QtGui.QKeySequence.Refresh)
        self.act_refresh.setToolTip('Refresh system env variables')
        self.act_refresh.triggered.connect(self.on_act_refresh)
        self.tbar.addAction(self.act_refresh)
        
        self.act_add = QAction(QtGui.QIcon("resources/add.png"), 'Add')
        self.act_add.setShortcut(QtGui.QKeySequence.New)
        self.act_add.setToolTip('Add variable')
        self.act_add.triggered.connect(self.on_act_add)
        self.tbar.addAction(self.act_add)

        self.act_delete = QAction(QtGui.QIcon("resources/error.png"), 'Unset')
        self.act_delete.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete))
        self.act_delete.setToolTip('Delete variables')
        self.act_delete.triggered.connect(self.on_act_delete)
        self.tbar.addAction(self.act_delete)

        self.layout_controls.addWidget(self.tbar)

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

    def update_envlist(self):
        try:
            self.tw_envs.itemSelectionChanged.disconnect()
            self.tw_envs.itemChanged.disconnect()
        except:
            pass

        self.tw_envs.setSortingEnabled(False)
        self.tw_envs.clearContents()
        self.tw_envs.setRowCount(len(self.sysproxy.locals) + len(self.sysproxy.globals))
        self.tw_envs.setMinimumSize(300, 300)

        i = 0
        for k, lst_envs in enumerate((self.sysproxy.locals, self.sysproxy.globals)):
            for env_name in lst_envs:                
                item0 = QtWidgets.QTableWidgetItem(env_name)               
                item1 = QtWidgets.QTableWidgetItem('user' if k == 0 else 'system')
                val = lst_envs[env_name][0]
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

    def refresh_vars_gui(self):
        if self.thread_update.isRunning():
            return
        while self.thread_action.isRunning():
            self.thread_action.wait()
        self.thread_update.start()

    def unset_vars(self, varnames):
        # varnames: list of 2-tuples: [('env', 'user'), ('env', 'system'), ...]
        def do_unser_vars():
            for var in varnames:
                modes = ['user']
                if var[1] == 'system':
                    modes.append('system')
                self.sysproxy.unset_sys_env(var[0], modes, False)
        return do_unser_vars

    def set_var(self, varname, value, modes=('user',)):
        def do_set_var():
            self.sysproxy.set_sys_env(varname, value, modes, False)
        return do_set_var

    def create_var(self, varname, value, valtype, modes=('user',)):
        def do_create_var():
            self.sysproxy.set_sys_env(varname, value, True, valtype, modes, False)
        return do_create_var

    # ============================================= SLOTS ================================================================ #

    @Slot()
    def update_actions(self):
        cnt_sel = len(self.tw_envs.selectedItems())
        running = self.thread_update.isRunning() or self.thread_action.isRunning()
        self.act_delete.setEnabled(not running and cnt_sel > 2)
        self.act_refresh.setEnabled(not running)
        self.act_add.setEnabled(not running)

    @Slot(bool)
    def on_act_refresh(self, checked):
        self.refresh_vars_gui()

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

## The application's main GUI window
class MainWindow(BasicDialog):

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
        self.sysproxy = sysproxy.Proxy()
        self.localproxy = self.sysproxy.asdict()
        rec = QtGui.QGuiApplication.primaryScreen().geometry()
        super().__init__(title='Proxen!', icon='proxen.png', geometry=(rec.width() // 2 - 175, rec.height() // 2 - 125, 350, 550),
                         flags=QtCore.Qt.Dialog | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.settings_to_gui()

    def addMainLayout(self):
        self.layout_controls = QtWidgets.QVBoxLayout()

        self.tb = QtWidgets.QToolBox()
        self.tb.currentChanged.connect(self.tb_currentChanged)

        # 1) main page: enable and persist toggles
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
        self.btn_enable_proxy.setIconSize(QtCore.QSize(64, 64))
        self.btn_enable_proxy.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))
        self.btn_enable_proxy.setDefaultAction(self.act_enable_proxy)
        self.btn_enable_proxy.setStyleSheet('QToolButton { border: null; padding: 0px } ')
        self.l_enable_proxy = QtWidgets.QLabel('ENABLE')
        self.lo_enable_proxy = QtWidgets.QVBoxLayout()
        self.lo_enable_proxy.addWidget(self.l_enable_proxy, 0, QtCore.Qt.AlignHCenter)
        self.lo_enable_proxy.addWidget(self.btn_enable_proxy, 0, QtCore.Qt.AlignHCenter)

        # persist toggle
        act_persist_proxy_icon = QtGui.QIcon()
        act_persist_proxy_icon.addPixmap(QtGui.QPixmap(utils.make_abspath('resources/off-button.png')),  QtGui.QIcon.Normal, QtGui.QIcon.Off)
        act_persist_proxy_icon.addPixmap(QtGui.QPixmap(utils.make_abspath('resources/on-button.png')), QtGui.QIcon.Normal, QtGui.QIcon.On)
        self.act_persist_proxy = QAction(act_persist_proxy_icon, '')
        self.act_persist_proxy.setToolTip('Persist proxy settings in system')
        self.act_persist_proxy.setCheckable(True)
        self.act_persist_proxy.setChecked(True)
        self.act_persist_proxy.toggled.connect(self.on_act_persist_proxy)
        self.btn_persist_proxy = QtWidgets.QToolButton()
        self.btn_persist_proxy.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.btn_persist_proxy.setIconSize(QtCore.QSize(64, 64))
        self.btn_persist_proxy.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))
        self.btn_persist_proxy.setDefaultAction(self.act_persist_proxy)
        self.btn_persist_proxy.setStyleSheet('QToolButton { border: null; padding: 0px } ')
        self.l_persist_proxy = QtWidgets.QLabel('PERSIST')
        self.lo_persist_proxy = QtWidgets.QVBoxLayout()
        self.lo_persist_proxy.addWidget(self.l_persist_proxy, 0, QtCore.Qt.AlignHCenter)
        self.lo_persist_proxy.addWidget(self.btn_persist_proxy, 0, QtCore.Qt.AlignHCenter)

        self.lo_wmain.addLayout(self.lo_enable_proxy)
        self.lo_wmain.addLayout(self.lo_persist_proxy)
        self.lo_wmain1 = QtWidgets.QVBoxLayout()
        self.lo_wmain1.addLayout(self.lo_wmain)
        self.lo_wmain1.addStretch()
        self.wmain.setLayout(self.lo_wmain1)
        self.tb.addItem(self.wmain, 'Enable')

        # 2) config page
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
        self.btn_apply.setFixedWidth(70)
        self.btn_apply.setDefaultAction(self.act_apply)
        self.lo_loadsave.addWidget(self.btn_apply)

        self.act_restore = QAction(QtGui.QIcon("resources/undo.png"), 'Restore')
        self.act_restore.setToolTip('Restore proxy configuration from system')
        self.act_restore.triggered.connect(self.on_act_restore)
        self.btn_restore = QtWidgets.QToolButton()
        self.btn_restore.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_restore.setFixedWidth(70)
        self.btn_restore.setDefaultAction(self.act_restore)
        self.lo_loadsave.addWidget(self.btn_restore)

        self.act_saveconfig = QAction(QtGui.QIcon("resources/save.png"), 'Save')
        self.act_saveconfig.setToolTip('Save current configuration to disk')
        self.act_saveconfig.triggered.connect(self.on_act_saveconfig)        
        self.btn_saveconfig = QtWidgets.QToolButton()
        self.btn_saveconfig.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_saveconfig.setFixedWidth(70)
        self.btn_saveconfig.setDefaultAction(self.act_saveconfig)
        self.lo_loadsave.addWidget(self.btn_saveconfig)

        self.act_loadconfig = QAction(QtGui.QIcon("resources/folder-15.png"), 'Load')
        self.act_loadconfig.setToolTip('Load configuration from disk')
        self.act_loadconfig.triggered.connect(self.on_act_loadconfig)  
        self.btn_loadconfig = QtWidgets.QToolButton()
        self.btn_loadconfig.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_loadconfig.setFixedWidth(70)
        self.btn_loadconfig.setDefaultAction(self.act_loadconfig)        
        self.lo_loadsave.addWidget(self.btn_loadconfig)

        self.lo_wconfig.addLayout(self.lo_loadsave)

        self.wconfig.setLayout(self.lo_wconfig)
        self.tb.addItem(self.wconfig, 'Settings')

        # ----
        self.layout_controls.addWidget(self.tb)
        # self.layout_controls.addStretch()

    def apply_config(self):
        self.sysproxy.fromdict(self.localproxy)
        self.sysproxy.do_persist()
        self.settings_to_gui()

    def restore_config(self):
        self.localproxy = self.sysproxy.asdict()
        self.settings_to_gui()

    # ============================================= SLOTS ================================================================ #

    @Slot()
    def settings_to_gui(self):
        # disconnect signals
        try:
            self.act_enable_proxy.toggled.disconnect()
            self.act_persist_proxy.toggled.disconnect()            
            self.gb_noproxy.toggled.disconnect()
            self.te_noproxy.textChanged.disconnect()
        except:
            pass

        # main toggles
        self.act_enable_proxy.setChecked(self.localproxy['enabled'])
        self.act_persist_proxy.setChecked(sysproxy.OS == 'Windows' or (self.localproxy['http_proxy'] and self.localproxy['http_proxy']['persist']))
        self.act_persist_proxy.setEnabled(sysproxy.OS != 'Windows')

        # settings
        self.on_btns_protocol_selected(0, True)

        self.gb_noproxy.setChecked(not self.localproxy['noproxy'] is None)
        self.te_noproxy.setPlainText('\n'.join(self.localproxy['noproxy']['noproxies'].split(',')))
        self.update_actions_enabled()

        # reconnect signals
        self.act_enable_proxy.toggled.connect(self.on_act_enable_proxy)
        self.act_persist_proxy.toggled.connect(self.on_act_persist_proxy)
        self.gb_noproxy.toggled.connect(self.on_gb_noproxy_checked)
        self.te_noproxy.textChanged.connect(self.on_te_noproxy_changed)

    @Slot()
    def on_btn_OK_clicked(self):
        if self.validate(): 
            self.apply_config()
            self.accept()

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

    @Slot(bool)
    def on_act_enable_proxy(self, checked):
        self.localproxy['enabled'] = checked
        self.update_actions_enabled()

    @Slot(bool)
    def on_act_persist_proxy(self, checked):
        for proxy in PROXY_OBJS:
            if self.localproxy[proxy] is None: continue
            self.localproxy[proxy]['persist'] = checked
        self.update_actions_enabled()

    @Slot(int)
    def tb_currentChanged(self, index):
        self.setFixedHeight(250 if index == 0 else 550)

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
        proxy_obj = self.localproxy[PROXY_OBJS[self.btns_protocol.checkedId()]]
        self.gb_proxy.setChecked(not proxy_obj is None)
        self.le_proxyhost.setText(proxy_obj['host'] if proxy_obj else '')
        if proxy_obj:
            self.le_proxyport.setValue(proxy_obj['port'])
        self.gb_auth.setChecked(proxy_obj['auth'] if proxy_obj else False)
        self.le_user.setText(proxy_obj['uname'] if proxy_obj else '')
        self.le_pass.setText(proxy_obj['password'] if proxy_obj else '')
        # reconnect signals
        self.gb_proxy.toggled.connect(self.on_gb_proxy_checked)
        self.le_proxyhost.textEdited.connect(self.on_le_proxyhost_edit)
        self.le_proxyport.valueChanged.connect(self.on_le_proxyport_changed)
        self.gb_auth.toggled.connect(self.on_gb_auth_checked)
        self.le_user.textEdited.connect(self.on_le_user_edit)
        self.le_pass.textEdited.connect(self.on_le_pass_edit)

    @Slot(bool)
    def on_act_apply(self, checked):        
        self.update_actions_enabled()
        if not self.act_apply.isEnabled():
            return
        self.apply_config()
        self.update_actions_enabled()

    @Slot(bool)
    def on_act_restore(self, checked):        
        self.update_actions_enabled()
        if not self.act_restore.isEnabled():
            return
        self.restore_config()
        self.update_actions_enabled()

    @Slot(bool)
    def on_act_loadconfig(self, checked):
        selected_path = QtWidgets.QFileDialog.getOpenFileName(self, 'Select config file', 'proxy_config.json', 'JSON files (*.json)')
        selected_path = selected_path[0]
        if not selected_path: return
        with open(selected_path, 'r', encoding=utils.CODING) as f_:
            self.localproxy = json.load(f_)
            self.settings_to_gui()

    @Slot(bool)
    def on_act_saveconfig(self, checked):
        selected_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Select config file', 'proxy_config.json', 'JSON files (*.json)')
        selected_path = selected_path[0]
        if not selected_path: return
        with open(selected_path, 'w', encoding=utils.CODING) as f_:
            json.dump(self.localproxy, f_, indent=4)

    @Slot(str)
    def on_le_proxyhost_edit(self, text):
        proxy_obj = self.localproxy[PROXY_OBJS[self.btns_protocol.checkedId()]]
        proxy_obj['host'] = text
        self.update_actions_enabled()

    @Slot(int)
    def on_le_proxyport_changed(self, value):
        proxy_obj = self.localproxy[PROXY_OBJS[self.btns_protocol.checkedId()]]
        proxy_obj['port'] = value
        self.update_actions_enabled()

    @Slot(bool)
    def on_gb_proxy_checked(self, checked):
        proxy = PROXY_OBJS[self.btns_protocol.checkedId()]
        if not checked:
            self.localproxy[proxy] = None
        else:
            sysproxy_obj = getattr(self.sysproxy, proxy, None)
            self.localproxy[proxy] = sysproxy_obj.asdict().copy() if sysproxy_obj else sysproxy.Proxyconf().asdict().copy()
        self.settings_to_gui()

    @Slot(bool)
    def on_gb_auth_checked(self, checked):
        proxy = PROXY_OBJS[self.btns_protocol.checkedId()]
        self.localproxy[proxy]['auth'] = checked
        self.update_actions_enabled()

    @Slot(str)
    def on_le_user_edit(self, text):
        proxy_obj = self.localproxy[PROXY_OBJS[self.btns_protocol.checkedId()]]
        proxy_obj['uname'] = text
        self.update_actions_enabled()

    @Slot(str)
    def on_le_pass_edit(self, text):
        proxy_obj = self.localproxy[PROXY_OBJS[self.btns_protocol.checkedId()]]
        proxy_obj['password'] = text
        self.update_actions_enabled()

    @Slot(bool)
    def on_gb_noproxy_checked(self, checked):
        self.localproxy['noproxy'] = None if not checked else self.sysproxy.noproxy.asdict().copy()
        self.update_actions_enabled()

    @Slot()
    def on_te_noproxy_changed(self):
        txt = self.te_noproxy.toPlainText()
        if txt:
            self.localproxy['noproxy']['noproxies'] = ','.join(txt.split('\n'))
        else:
            self.localproxy['noproxy'] = None
        self.update_actions_enabled()        