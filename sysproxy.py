# -*- coding: utf-8 -*-
import os, platform, traceback, re, json, subprocess
import dataclasses
from collections.abc import Callable

OS = platform.system()

if OS == 'Windows':
    import winreg
    WIN_REG_BRANCHES = {'HKEY_CLASSES_ROOT': winreg.HKEY_CLASSES_ROOT,
                        'HKCR': winreg.HKEY_CLASSES_ROOT,
                        'HKEY_CURRENT_USER': winreg.HKEY_CURRENT_USER,
                        'HKCU': winreg.HKEY_CURRENT_USER,
                        'HKEY_LOCAL_MACHINE': winreg.HKEY_LOCAL_MACHINE,
                        'HKLM': winreg.HKEY_LOCAL_MACHINE,
                        'HKEY_USERS': winreg.HKEY_USERS,
                        'HKU': winreg.HKEY_USERS,
                        'HKEY_CURRENT_CONFIG': winreg.HKEY_CURRENT_CONFIG,
                        'HKCC': winreg.HKEY_CURRENT_CONFIG
                        }

import utils

# --------------------------------------------------------------- #

CURRENT_USER = utils.has_admin()
WIN_PROXY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
WIN_ENV_LOCAL_KEY = 'Environment' # HKCU branch
WIN_ENV_SYSTEM_KEY = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment' # HKLM branch
UNIX_PROFILE_FILES = ['~/.profile', '~/.bashrc', '~/.zshrc', '/etc/profile', '/etc/environment', '/etc/bash.bashrc', '/etc/zsh/zshrc']
REGEX_PROXY_EXPORT = r'(export\s{}=)(.*)'

# --------------------------------------------------------------- #

@dataclasses.dataclass
class Dclass:
    persist: bool = False
    on_setattr: Callable = None

    @property
    def proxystr(self):
        return ''

    def asdict(self):
        # return dataclasses.asdict(self)
        return dict((field.name, getattr(self, field.name)) for field in dataclasses.fields(self) if field.name != 'on_setattr')

    def __str__(self):
        return self.proxystr

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if getattr(self, 'on_setattr', None) and name != 'on_setattr':
            self.on_setattr(self, name, value)

# --------------------------------------------------------------- #

@dataclasses.dataclass
class Proxyconf(Dclass):
    protocol: str = 'http'
    host: str = ''
    port: int = 3128
    auth: bool = False
    uname: str = ''
    password: str = ''

    @property
    def proxystr(self):
        if self.auth and self.uname:
            auth_ = ':'.join((self.uname, self.password)) + '@'
        else:
            auth_ = ''
        return f'{self.protocol}://{auth_}{self.host}:{self.port}'

# --------------------------------------------------------------- #

@dataclasses.dataclass
class Noproxy(Dclass):
    noproxies: str = ''

    def getstr(self, winreg=False):
        l_noproxies = self.getlist()
        if not l_noproxies:
            return ''
        if winreg:
            vals = [val for val in l_noproxies if not val in ('localhost', '127.0.0.1')]
            if 'localhost' in l_noproxies or '127.0.0.1' in l_noproxies:
                vals.append('<local>')
            return ';'.join(vals)
        else:
            return ','.join(l_noproxies)

    def getlist(self):
        if not self.noproxies:
            return []
        l_noproxies = self.noproxies.split(',')
        if len(l_noproxies) < 2:
            l_noproxies = self.noproxies.split(';')
        return sorted(set(sl.strip() if sl.strip() != '<local>' else 'localhost' for sl in l_noproxies))

    def asdict(self):
        return {'persist': self.persist, 'noproxies': str(self)}

    @property
    def proxystr(self):
        return self.getstr(False)

    def __bool__(self):
        return bool(self.noproxies)

# --------------------------------------------------------------- #

class Sysproxy:

    def __init__(self, unix_file='~/.profile'):
        self.unix_file = unix_file
        self.update_vars()

    def update_vars(self):
        if OS == 'Windows':
            # propagate env vars by calling setx
            subprocess.run(f'setx ttt t > nul', shell=True)
            self.locals = self.win_list_reg(WIN_ENV_LOCAL_KEY) or {}
            self.globals = self.win_list_reg(WIN_ENV_SYSTEM_KEY, 'HKLM') or {}
        else:
            self.locals = {}
            for fname in {self.unix_file, '~/.profile', '~/.bashrc', '~/.zshrc'}:
                res = self._unix_get_envs(fname)
                if res:
                    self.locals.update(res)
            self.globals = {}
            for fname in {'/etc/profile', '/etc/environment', '/etc/bash.bashrc', '/etc/zsh/zshrc'}:
                res = self._unix_get_envs(fname)
                if res:
                    self.globals.update(res)

    def _unix_get_envs(self, filepath):
        if OS == 'Windows' or not os.path.isfile(filepath):
            return None
        try:
            res = {}
            with open(filepath, 'r', encoding=utils.CODING) as f_:
                ftext = f_.read().strip()
            reg = re.compile(r'^export\s([\w\d_]+)=(.*)$', re.I)
            for m in reg.finditer(ftext):
                if m:
                    res[m[1]] = m[2]
            return res
        except:
            traceback.print_exc()
            return None

    def win_get_reg(self, keyname, valname, branch='HKEY_CURRENT_USER') -> tuple[str, int]:
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        if isinstance(branch, str):
            branch = WIN_REG_BRANCHES[branch]
        k = None
        res = None
        try:
            k = winreg.OpenKeyEx(branch, keyname)
            res = winreg.QueryValueEx(k, valname)
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_set_reg(self, keyname, valname, value, branch='HKEY_CURRENT_USER') -> tuple[str, int]:
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        if isinstance(branch, str):
            branch = WIN_REG_BRANCHES[branch]
        k = None
        res = None
        try:
            k = winreg.OpenKeyEx(branch, keyname, 0, winreg.KEY_ALL_ACCESS)
            val = winreg.QueryValueEx(k, valname)
            if val[0] != value:
                winreg.SetValueEx(k, valname, 0, val[1], value)
            res = winreg.QueryValueEx(k, valname)
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_del_reg(self, keyname, valname, branch='HKEY_CURRENT_USER') -> bool:
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        if isinstance(branch, str):
            branch = WIN_REG_BRANCHES[branch]
        k = None
        res = False
        try:
            k = winreg.OpenKeyEx(branch, keyname, 0, winreg.KEY_ALL_ACCESS)
            winreg.DeleteValue(k, valname)
            res = True
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_list_reg(self, keyname, branch='HKEY_CURRENT_USER', expand_vars=True) -> dict:
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        if isinstance(branch, str):
            branch = WIN_REG_BRANCHES[branch]
        res = {}
        if expand_vars:
            reg = re.compile(r'%(.+?)%')
        try:
            k = winreg.OpenKeyEx(branch, keyname, 0, winreg.KEY_READ)
            info = winreg.QueryInfoKey(k)
            for i in range(info[1]):
                try:
                    val = winreg.EnumValue(k, i)
                    if not expand_vars:
                        res[val[0]] = val[1:]
                    else:
                        v = reg.sub(lambda m: os.environ.get(m[1], m[0]), val[1])
                        res[val[0]] = (v, val[2])
                except OSError:
                    break
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_get_reg_proxy(self, valname) -> str:
        res = self.win_get_reg(WIN_PROXY_KEY, valname)
        if res is None:
            utils.log(f'ERROR getting win reg key {WIN_PROXY_KEY}\\{valname}', 'error')
            return None
        utils.log(f'Get win reg key {WIN_PROXY_KEY}\\{valname} = {res[0]}', 'debug')
        return res[0]

    def win_set_reg_proxy(self, valname, value) -> str:
        res = self.win_set_reg(WIN_PROXY_KEY, valname, value)
        if res is None:
            utils.log(f'ERROR setting win reg key {WIN_PROXY_KEY}\\{valname} = {value}', 'error')
            return None
        utils.log(f'Set win reg key {WIN_PROXY_KEY}\\{valname} = {res[0]}', 'debug')
        return res[0]

    def list_sys_envs_proxy(self) -> dict:
        proxies = [item for sublist in [[p.lower(), p.upper()] for p in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'no_proxy')] for item in sublist]
        return {'user': {k: v for k, v in self.locals if k in proxies},
                'system': {k: v for k, v in self.globals if k in proxies}}

    def get_sys_env(self, envname: str, default=None):
        return 

    def set_sys_env(self, envname: str, value, create=True, modes=('user',)):
        if ('system' in modes) and (not CURRENT_USER[1]):
            raise Exception('Cannot execute command: SU privilege asked!')
        env = self.get_sys_env(envname)
        if OS == 'Windows':
            # Method 1
            """
            m = ' /M' if superuser else ''
            subprocess.run(f'setx{m} {envname.upper()} "{value}" > nul', shell=True)
            subprocess.run(f'setx ttt t > nul', shell=True)
            """
            # Method 2
            for mode in modes:
                if create or not env[mode] is None:
                    if mode == 'user':
                        self.win_set_reg(WIN_ENV_LOCAL_KEY, envname.upper(), value, 'HKCU')
                    elif mode == 'system':
                        self.win_set_reg(WIN_ENV_SYSTEM_KEY, envname.upper(), value, 'HKLM')
            # propagate env vars by calling setx
            subprocess.run(f'setx ttt t > nul', shell=True)
        else:
            for e_ in (envname.lower(), envname.upper()):
                os.environ[e_] = value
        utils.log(f'Set system env {envname} = {value}', 'debug')


    def unset_sys_env(self, envname: str, modes=('user',)):
        if ('system' in modes) and (not CURRENT_USER[1]):
            raise Exception('Cannot execute command: SU privilege asked!')
        if OS == 'Windows':
            # Method 1
            """
            m = ' /M' if superuser else ''
            subprocess.run(f'setx{m} {envname.upper()} "" > nul', shell=True)
            subprocess.run(f'setx ttt t > nul', shell=True)
            """
            # Method 2
            for mode in modes:
                if mode == 'user':
                    self.win_del_reg(WIN_ENV_LOCAL_KEY, envname.upper(), 'HKCU')
                elif mode == 'system':
                    self.win_del_reg(WIN_ENV_SYSTEM_KEY, envname.upper(), 'HKLM')
            # propagate env vars by calling setx
            subprocess.run(f'setx ttt t > nul', shell=True)
        else:
            for e_ in (envname.lower(), envname.upper()):
                if e_ in os.environ:
                    del os.environ[e_]
        utils.log(f'Delete system env {envname}', 'debug')


    def get_sys_http_proxy(self) -> str:
        if OS == 'Windows':
            res = self.win_get_reg_proxy('ProxyServer')
            if res is None:
                res = self.get_sys_env('http_proxy') or self.get_sys_env('all_proxy')
            return res
        return self.get_sys_env('http_proxy') or self.get_sys_env('all_proxy')


    def get_sys_proxy_enabled(self) -> bool:
        if OS == 'Windows':
            res = self.win_get_reg('ProxyEnable')
            if res is None: return False
            return bool(res)

        # Linux doesn't have separate 'proxy enable' switch, so try to get 'http_proxy' ENV...
        return (not self.get_sys_http_proxy() is None)


    def get_sys_noproxy(self) -> Noproxy:
        if OS == 'Windows':
            res = self.win_get_reg('ProxyOverride')
            return None if res is None else Noproxy(True, None, res)

        res = self.get_sys_env('no_proxy')
        pers = self.get_sys_persist('no_proxy')
        return None if res is None else Noproxy(pers, None, res)


    def get_sys_proxy_parsed(self, proxy='http_proxy') -> Proxyconf:
        _proxy = self.get_sys_http_proxy() if proxy == 'http_proxy' else self.get_sys_env(proxy)
        if _proxy is None: return None
        spl = _proxy.split('://')
        prot = spl[0].lower() if len(spl) > 1 else 'http'
        other = spl[1] if len(spl) > 1 else _proxy
        spl1 = other.split('@')
        if len(spl1) > 1:
            spl11 = spl1[0].split(':')
            uname = spl11[0]
            passw = spl11[1] if len(spl11) > 1 else None
        else:
            uname, passw = (None, None)
        other2 = spl1[1] if len(spl1) > 1 else other
        spl2 = other2.split(':')
        host = spl2[0]
        port = int(spl2[1]) if len(spl2) > 1 else None
        return Proxyconf(self.get_sys_persist(proxy), None, prot, host or '', port or 3128, not uname is None, uname or '', passw or '')


    def get_sys_persist(self, proxy='http_proxy') -> bool:
        # there is no 'non-persistent' mode on Windows
        if OS == 'Windows':
            return True
        # on UNIXes search these files (in succession):
        # '~/.profile', '~/.bashrc', '~/.zshrc', '/etc/profile', '/etc/environment', '/etc/bash.bashrc', '/etc/zsh/zshrc'
        for fname in UNIX_PROFILE_FILES:
            if not os.path.isfile(fname):
                continue
            try:
                with open(fname, 'r', encoding=utils.CODING) as f_:
                    ftext = f_.read().strip()
                m = re.match(REGEX_PROXY_EXPORT.format(proxy), ftext, re.I)
                if m is None:
                    return False
                utils.log(f'Found {m[2].strip()} in file {fname}', 'debug')
                return m[2].strip() != ''
            except:
                # traceback.print_exc()
                continue
        return False


    def set_sys_persist(self, proxy: str, value: str, unix_file='~/.profile'):
        # there is no 'non-persistent' mode on Windows
        if OS == 'Windows': return True
        try:
            with open(unix_file, 'a', encoding=utils.CODING) as f_:
                for p_ in (proxy.lower(), proxy.upper()):
                    f_.write(f'export {p_}={value}{utils.NL}')
                    utils.log(f'Written {p_} to file {unix_file}', 'debug')
            return True
        except:
            traceback.print_exc()
            return False


    def del_sys_persist(self, proxy: str, unix_files=None):
        if OS == 'Windows': return

        unix_files = unix_files or UNIX_PROFILE_FILES
        reg = re.compile(REGEX_PROXY_EXPORT.format(proxy), flags=re.I)

        for fname in unix_files:
            try:
                if not os.path.isfile(fname):
                    continue
                with open(fname, 'r', encoding=utils.CODING) as f_:
                    ftext = f_.read().strip()
                if not reg.match(ftext):
                    continue
                ftext = reg.sub('\n', ftext)
                with open(fname, 'w', encoding=utils.CODING) as f_:
                    f_.write(ftext)
                utils.log(f'Deleted "{REGEX_PROXY_EXPORT.format(proxy)}" from file {fname}', 'debug')

            except:
                traceback.print_exc()
                continue

# --------------------------------------------------------------- #

class Proxy:

    def __init__(self, storage_file='proxy_config.json', unix_file='~/.profile'):
        self.storage_file = utils.make_abspath(storage_file) if not os.path.isabs(storage_file) else storage_file
        self.unix_file = unix_file
        self.read_system()
        self.save()

    def __del__(self):
        self.do_persist()

    def asdict(self):
        d = {'enabled': self.enabled}
        for attr in ('noproxy', 'http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            prop = getattr(self, attr, None)
            d[attr] = prop.asdict() if prop else None
        return d

    def fromdict(self, dconfig: dict):
        for attr in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            if not attr in dconfig: continue
            obj = None if dconfig[attr] is None else Proxyconf(dconfig[attr]['persist'], self._on_setattr, dconfig[attr]['protocol'], dconfig[attr]['host'],
                                                               dconfig[attr]['port'], dconfig[attr]['auth'], dconfig[attr]['uname'], dconfig[attr]['password'])
            setattr(self, attr, obj)
        if 'noproxy' in dconfig:
            self.noproxy = None if dconfig['noproxy'] is None else Noproxy(dconfig['noproxy']['persist'], self._on_setattr, dconfig['noproxy']['noproxies'])
        if 'enabled' in dconfig:
            self.enabled = dconfig['enabled']

    def _get_sys_noproxy(self):
        noproxy = Sysproxy.get_sys_noproxy()
        if noproxy:
            noproxy.on_setattr = self._on_setattr
        return noproxy

    def _get_sys_proxy(self, proxystr):
        proxy = Sysproxy.get_sys_proxy_parsed(proxystr)
        if proxy:
            proxy.on_setattr = self._on_setattr
        return proxy

    def read_system(self):
        self._enabled = Sysproxy.get_sys_proxy_enabled()
        self._noproxy = self._get_sys_noproxy()
        self._http_proxy = self._get_sys_proxy('http_proxy')
        self._https_proxy = self._get_sys_proxy('https_proxy')
        self._ftp_proxy = self._get_sys_proxy('ftp_proxy')
        self._rsync_proxy = self._get_sys_proxy('rsync_proxy')

    def store_config(self, config_file=None):
        if not config_file:
            config_file = self.storage_file
        else:
            config_file = utils.make_abspath(config_file) if not os.path.isabs(config_file) else config_file
        with open(config_file, 'w', encoding=utils.CODING) as f_:
            json.dump(self.asdict(), f_, indent=4)

    def read_config(self, config_file=None):
        if not config_file:
            config_file = self.storage_file
        else:
            config_file = utils.make_abspath(config_file) if not os.path.isabs(config_file) else config_file
        if not os.path.isfile(config_file):
            print(f'File "{config_file}" is not available!')
            return
        with open(config_file, 'r', encoding=utils.CODING) as f_:
            d = json.load(f_)
            self.fromdict(d)

    def do_persist(self):
        if OS == 'Windows':
            return
        for attr in ('no_proxy', 'http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            prop = getattr(self, attr, None)
            if not prop: continue
            if prop.persist:
                Sysproxy.set_sys_persist(attr, str(prop), True, self.unix_file)
            else:
                Sysproxy.del_sys_persist(attr, True)

    def _on_setattr(self, obj, name, value):
        if isinstance(obj, Noproxy):
            if OS == 'Windows':
                Sysproxy.win_set_reg('ProxyOverride', obj.getstr(True))
            if obj:
                Sysproxy.set_sys_env('no_proxy', obj.getstr(False))
            else:
                Sysproxy.unset_sys_env('no_proxy')
        elif isinstance(obj, Proxyconf):
            if obj is self._http_proxy:
                proxy = 'http_proxy'
            elif obj is self._https_proxy:
                proxy = 'https_proxy'
            elif obj is self._ftp_proxy:
                proxy = 'ftp_proxy'
            elif obj is self._rsync_proxy:
                proxy = 'rsync_proxy'
            else:
                return
            if proxy == 'http_proxy' and OS == 'Windows':
                Sysproxy.win_set_reg('ProxyServer', f'{obj.host}:{obj.port}')
            Sysproxy.set_sys_env(proxy, str(obj))

    @property
    def enabled(self):
        if getattr(self, '_enabled', None) is None:
            self._enabled = Sysproxy.get_sys_proxy_enabled()
        return self._enabled

    @enabled.setter
    def enabled(self, is_enabled) -> bool:
        if is_enabled == self._enabled:
            return
        if not is_enabled:
            Sysproxy.unset_sys_env('http_proxy')
            Sysproxy.unset_sys_env('all_proxy')
        else:
            proxy = self.http_proxy or self.https_proxy or self.ftp_proxy
            if not proxy:
                return
            Sysproxy.set_sys_env('http_proxy', str(proxy))
            # if OS == 'Windows':
            #     Sysproxy.win_set_reg('ProxyServer', f'{self.http_proxy.host}:{self.http_proxy.port}')
        if OS == 'Windows':
            Sysproxy.win_set_reg('ProxyEnable', int(is_enabled))

        self._enabled = is_enabled

    @property
    def noproxy(self) -> Noproxy:
        if getattr(self, '_noproxy', None) is None:
            self._noproxy = self._get_sys_noproxy()
        return self._noproxy

    @noproxy.setter
    def noproxy(self, value: Noproxy):
        if (self._noproxy == value) or (self._noproxy.noproxies == value.noproxies and self._noproxy.persist == value.persist):
            return
        if OS == 'Windows':
            Sysproxy.win_set_reg('ProxyOverride', value.getstr(True) if value else '')
        if not value:
            Sysproxy.unset_sys_env('no_proxy')
        elif value.noproxies:
            Sysproxy.set_sys_env('no_proxy', value.getstr(False))
        self._noproxy = value

    @property
    def http_proxy(self) -> Proxyconf:
        if getattr(self, '_http_proxy', None) is None:
            self._http_proxy = self._get_sys_proxy('http_proxy')
        return self._http_proxy

    @http_proxy.setter
    def http_proxy(self, value: Proxyconf):
        if self._http_proxy == value:
            return
        if OS == 'Windows':
            if not value:
                self.enabled = False
            else:
                Sysproxy.win_set_reg('ProxyServer', f'{value.host}:{value.port}')
        if not value:
            Sysproxy.unset_sys_env('http_proxy')
        else:
            Sysproxy.set_sys_env('http_proxy', str(value))
        self._http_proxy = value

    @property
    def https_proxy(self) -> Proxyconf:
        if getattr(self, '_https_proxy', None) is None:
            self._https_proxy = self._get_sys_proxy('https_proxy')
        return self._https_proxy

    @https_proxy.setter
    def https_proxy(self, value: Proxyconf):
        if self._https_proxy == value:
            return
        if not value:
            Sysproxy.unset_sys_env('https_proxy')
        else:
            Sysproxy.set_sys_env('https_proxy', str(value))
        self._https_proxy = value

    @property
    def ftp_proxy(self) -> Proxyconf:
        if getattr(self, '_ftp_proxy', None) is None:
            self._ftp_proxy = self._get_sys_proxy('ftp_proxy')
        return self._ftp_proxy

    @ftp_proxy.setter
    def ftp_proxy(self, value: Proxyconf):
        if self._ftp_proxy == value:
            return
        if not value:
            Sysproxy.unset_sys_env('ftp_proxy')
        else:
            Sysproxy.set_sys_env('ftp_proxy', str(value))
        self._ftp_proxy = value

    @property
    def rsync_proxy(self) -> Proxyconf:
        if getattr(self, '_rsync_proxy', None) is None:
            self._rsync_proxy = self._get_sys_proxy('rsync_proxy')
        return self._rsync_proxy

    @rsync_proxy.setter
    def rsync_proxy(self, value: Proxyconf):
        if self._rsync_proxy == value:
            return
        if not value:
            Sysproxy.unset_sys_env('rsync_proxy')
        else:
            Sysproxy.set_sys_env('rsync_proxy', str(value))
        self._rsync_proxy = value

    def proxy_by_name(self, proxy='http'):
        if proxy == 'http':
            return self.http_proxy
        if proxy == 'https':
            return self.https_proxy
        if proxy == 'ftp':
            return self.ftp_proxy
        if proxy == 'rsync':
            return self.rsync_proxy

    def copy_from(self, source='http', targets=['https', 'ftp', 'rsync']):
        src = self.proxy_by_name(source)
        if not src: return
        if not targets:
            self.http_proxy = src
            self.https_proxy = src
            self.ftp_proxy = src
            self.rsync_proxy = src
        else:
            for t in targets:
                if t == source:
                    continue
                if t == 'http':
                    self.http_proxy = src
                elif t == 'https':
                    self.https_proxy = src
                elif t == 'ftp':
                    self.ftp_proxy = src
                elif t == 'rsync':
                    self.rsync_proxy = src

    def save(self):
        self.stored = self.asdict()

    def restore(self):
        if not getattr(self, 'stored', None):
            return
        self.noproxy = self.stored['noproxy']
        self.http_proxy = self.stored['http_proxy']
        self.https_proxy = self.stored['https_proxy']
        self.ftp_proxy = self.stored['ftp_proxy']
        self.rsync_proxy = self.stored['rsync_proxy']
        self.enabled = self.stored['enabled']