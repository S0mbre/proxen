# -*- coding: utf-8 -*-
import os, json

from qtimports import *
import utils
from sysproxy import Sysproxy, Proxy, OS, Proxyconf, Noproxy

# ******************************************************************************** #

PROXY_OBJS = ['http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'noproxy']

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
        self.sysproxy = Proxy()
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
        self.act_persist_proxy.setChecked(OS == 'Windows' or (self.localproxy['http_proxy'] and self.localproxy['http_proxy']['persist']))
        self.act_persist_proxy.setEnabled(OS != 'Windows')

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
            self.localproxy[proxy] = sysproxy_obj.asdict().copy() if sysproxy_obj else Proxyconf().asdict().copy()
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
