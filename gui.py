# -*- coding: utf-8 -*-
import os
from urllib.request import getproxies

from qtimports import *
import utils
from sysproxy import Sysproxy

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
        self.btnaction = QAction(QtGui.QIcon(utils.make_abspath(f"resources/{self.btnicon}")), '')
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
        self.proxy_settings = {'enabled': False, 'persist': True,
                               'http': {'host': '', 'port': -1, 'auth': False, 'user': '', 'pass': ''},
                               'https': {'host': '', 'port': -1, 'auth': False, 'user': '', 'pass': ''},
                               'ftp': {'host': '', 'port': -1, 'auth': False, 'user': '', 'pass': ''},
                               'rsync': {'host': '', 'port': -1, 'auth': False, 'user': '', 'pass': ''},
                               'noproxy': {'enabled': True, 'hosts': []}
                              }
        self.sysproxy = Sysproxy()
        rec = QtGui.QGuiApplication.primaryScreen().geometry()
        super().__init__(title='Proxen!', icon='proxen.png', geometry=(rec.width() // 2 - 175, rec.height() // 2 - 125, 350, 500),
                         flags=QtCore.Qt.Dialog | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.settings_from_system()
        self.settings_to_gui()

    def settings_from_system(self):
        print(self.sysproxy.enabled)
        print(self.sysproxy.noproxy)

    def settings_to_gui(self):
        pass

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
        self.lo_gb_proxy = QtWidgets.QVBoxLayout()
        self.lo_proxyhost = QtWidgets.QVBoxLayout()
        self.l_proxyhost = QtWidgets.QLabel('Proxy host')
        self.le_proxyhost = QtWidgets.QLineEdit()
        self.le_proxyhost.setPlaceholderText('Proxy host')
        self.lo_proxyhost.addWidget(self.l_proxyhost)
        self.lo_proxyhost.addWidget(self.le_proxyhost)
        self.lo_proxyport = QtWidgets.QVBoxLayout()
        self.l_proxyport = QtWidgets.QLabel('Port')
        self.le_proxyport = QtWidgets.QSpinBox()
        self.le_proxyport.setRange(1, 65536)
        self.le_proxyport.setFixedWidth(80)
        self.lo_proxyport.addWidget(self.l_proxyport)
        self.lo_proxyport.addWidget(self.le_proxyport)
        self.lo_proxy_and_port = QtWidgets.QHBoxLayout()
        self.lo_proxy_and_port.setSpacing(10)
        self.lo_proxy_and_port.addLayout(self.lo_proxyhost)
        self.lo_proxy_and_port.addLayout(self.lo_proxyport)
        self.lo_gb_proxy.addLayout(self.lo_proxy_and_port)
        self.gb_auth = QtWidgets.QGroupBox('Authorization')
        self.gb_auth.setCheckable(True)
        self.lo_gb_auth = QtWidgets.QHBoxLayout()
        self.lo_gb_auth.setSpacing(10)
        self.l_user = QtWidgets.QLabel('User name')
        self.le_user = QtWidgets.QLineEdit()
        self.le_user.setPlaceholderText('User name')
        self.lo_user = QtWidgets.QVBoxLayout()
        self.lo_user.addWidget(self.l_user)
        self.lo_user.addWidget(self.le_user)
        self.lo_gb_auth.addLayout(self.lo_user)
        self.l_pass = QtWidgets.QLabel('Password')
        self.le_pass = QtWidgets.QLineEdit()
        self.le_pass.setPlaceholderText('Password')
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
        self.lo_gb_noproxy = QtWidgets.QVBoxLayout()

        self.te_noproxy = QtWidgets.QTextEdit()
        self.te_noproxy.setPlaceholderText('Excluded hosts (separate with new lines and/or spaces)')
        self.te_noproxy.setAcceptRichText(False)
        self.te_noproxy.setUndoRedoEnabled(True)
        self.lo_gb_noproxy.addWidget(self.te_noproxy)
        self.gb_noproxy.setLayout(self.lo_gb_noproxy)
        self.lo_wconfig.addWidget(self.gb_noproxy)

        self.wconfig.setLayout(self.lo_wconfig)
        self.tb.addItem(self.wconfig, 'Settings')

        # ----
        self.layout_controls.addWidget(self.tb)
        # self.layout_controls.addStretch()

    # ============================================= SLOTS ================================================================ #

    @Slot(bool)
    def on_act_enable_proxy(self, checked):
        pass

    @Slot(bool)
    def on_act_persist_proxy(self, checked):
        pass

    @Slot(int)
    def tb_currentChanged(self, index):
        self.setFixedHeight(250 if index == 0 else 500)

    @Slot(int, bool)
    def on_btns_protocol_selected(self, index, checked):
        pass
