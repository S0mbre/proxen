# -*- coding: utf-8 -*-
import os, platform, traceback, copy, re, json
import dataclasses

OS = platform.system()

if OS == 'Windows':
    import winreg

import utils

# --------------------------------------------------------------- #    

WIN_PROXY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
UNIX_PROFILE_FILES = ['~/.profile', '~/.bashrc', '~/.zshrc', '/etc/profile', '/etc/environment', '/etc/bash.bashrc', '/etc/zsh/zshrc']
REGEX_PROXY_EXPORT = r'(export\s{}=)(.*)'

# --------------------------------------------------------------- #

@dataclasses.dataclass
class Proxyconf:
    protocol: str = 'http'
    host: str = ''
    port: int = 3128
    auth: bool = False
    uname: str = ''
    password: str = ''
    persist: bool = False

    @property
    def proxystr(self):
        if self.auth and self.uname:
            auth_ = ':'.join((self.uname, self.password)) + '@'
        else:
            auth_ = ''
        return f'{self.protocol}://{auth_}{self.host}:{self.port}'

    def asdict(self):
        return dataclasses.asdict(self)

    def __str__(self):
        return self.proxystr

# --------------------------------------------------------------- #          

@dataclasses.dataclass
class Noproxy:
    noproxies: list = dataclasses.field(default_factory=list)
    persist: bool = False

    @property
    def proxystr(self):
        if OS == 'Windows':
            vals = [val for val in self.noproxies if not val in ('localhost', '127.0.0.1')]
            if 'localhost' in self.noproxies or '127.0.0.1' in self.noproxies:
                vals.append('<local>')
            return ';'.join(vals)
        else:
            return ', '.join(self.noproxies)

    def asdict(self):
        return dataclasses.asdict(self)

    def __str__(self):
        return self.proxystr

    def __bool__(self):
        return len(self.noproxies) > 0

    def __len__(self):
        return len(self.noproxies)

# --------------------------------------------------------------- #

class Sysproxy: 

    @staticmethod
    def win_get_reg(valname):
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        k = None
        res = None   
        try:
            k = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, WIN_PROXY_KEY)
            res = winreg.QueryValueEx(k, valname)[0]
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    @staticmethod
    def win_set_reg(valname, value, create=True):
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        k = None
        res = None   
        try:
            k = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, WIN_PROXY_KEY, 0, winreg.KEY_ALL_ACCESS if create else winreg.KEY_READ)
            val = winreg.QueryValueEx(k, valname)
            if val[0] != value:
                winreg.SetValueEx(k, valname, 0, val[1], value)
            res = winreg.QueryValueEx(k, valname)[0]
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    @staticmethod
    def get_sys_env(envname: str, both_cases=True, default=None):
        if both_cases:
            return os.environ.get(envname.lower(), os.environ.get(envname.upper(), default))
        else:
            return os.environ.get(envname, default)

    @staticmethod
    def set_sys_env(envname: str, value, both_cases=True, create=True):
        env = Sysproxy.get_sys_env(envname, both_cases)
        if env is None and not create:
            return
        if not env is None and env == value:
            return
        if both_cases:
            os.environ[envname.lower()] = value
            os.environ[envname.upper()] = value
        else:
            os.environ[envname] = value

    @staticmethod
    def unset_sys_env(envname: str, both_cases=True):
        if both_cases:
            os.environ.pop(envname.lower(), default=None)
            os.environ.pop(envname.upper(), default=None)
        else:
            os.environ.pop(envname, default=None)

    @staticmethod
    def get_sys_http_proxy() -> str:
        if OS == 'Windows':
            res = Sysproxy.win_get_reg('ProxyServer')
            if res is None:
                res = Sysproxy.get_sys_env('http_proxy') or Sysproxy.get_sys_env('all_proxy')
            return res
        return Sysproxy.get_sys_env('http_proxy') or Sysproxy.get_sys_env('all_proxy')

    @staticmethod
    def get_sys_proxy_enabled() -> bool:
        if OS == 'Windows':
            res = Sysproxy.win_get_reg('ProxyEnable')
            if res is None: return False
            return bool(res)        

        # Linux doesn't have separate 'proxy enable' switch, so try to get 'http_proxy' ENV...
        return (not Sysproxy.get_sys_http_proxy() is None)

    @staticmethod
    def get_sys_noproxy() -> Noproxy:
        if OS == 'Windows':
            res = Sysproxy.win_get_reg('ProxyOverride')
            if res is None: return Noproxy([], True)
            return Noproxy([x.strip() if x.strip() != '<local>' else 'localhost' for x in res.split(';')], True)
        
        res = Sysproxy.get_sys_env('no_proxy')
        pers = Sysproxy.get_sys_persist('no_proxy')
        if res is None: Noproxy([], pers)

        return Noproxy([x.strip() for x in res.split(',')], pers)

    @staticmethod
    def get_sys_proxy_parsed(proxy='http_proxy') -> Proxyconf:
        _proxy = Sysproxy.get_sys_http_proxy() if proxy == 'http_proxy' else Sysproxy.get_sys_env(proxy)
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
        return Proxyconf(prot, host or '', port or 3128, not uname is None, uname or '', passw or '')

    @staticmethod
    def get_sys_persist(proxy='http_proxy') -> bool:
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
                return m[2].strip() != ''
            except:
                # traceback.print_exc()
                continue 
        return False

    @staticmethod
    def set_sys_persist(proxy: str, value: str, both_cases=True, unix_file='~/.profile'):
        # there is no 'non-persistent' mode on Windows
        if OS == 'Windows': return True
        try:
            with open(unix_file, 'a', encoding=utils.CODING) as f_:
                if both_cases:
                    f_.write(f'export {proxy.lower()}={value}{utils.NL}')
                    f_.write(f'export {proxy.upper()}={value}{utils.NL}')
                else:
                    f_.write(f'export {proxy}={value}{utils.NL}')
            return True
        except:
            traceback.print_exc()
            return False

    @staticmethod
    def del_sys_persist(proxy: str, both_cases=True, unix_files=None):
        if OS == 'Windows': return
        
        unix_files = unix_files or UNIX_PROFILE_FILES
        reg = re.compile(REGEX_PROXY_EXPORT.format(proxy), flags=re.I if both_cases else 0)

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

            except:
                traceback.print_exc()
                continue

# --------------------------------------------------------------- #

class Proxy:    

    def __init__(self, storage_file='proxy_config.json'):
        self.storage_file = utils.make_abspath(storage_file) if not os.path.isabs(storage_file) else storage_file
        self.read_system()
        self.save()

    def asdict(self):
        d = {'enabled': self.enabled}
        for attr in ('no_proxy', 'http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            prop = getattr(self, attr, None)
            d[attr] = prop.asdict() if prop else None
        return d

    def read_system(self):
        self._enabled = Sysproxy.get_sys_proxy_enabled()
        self._noproxy = Sysproxy.get_sys_noproxy()
        self._http_proxy = Sysproxy.get_sys_proxy_parsed('http_proxy')
        self._https_proxy = Sysproxy.get_sys_proxy_parsed('https_proxy')
        self._ftp_proxy = Sysproxy.get_sys_proxy_parsed('ftp_proxy')
        self._rsync_proxy = Sysproxy.get_sys_proxy_parsed('rsync_proxy')

    def store_config(self):
        with open(self.storage_file, 'w', encoding=utils.CODING) as f_:
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
        if 'enabled' in d:
            self.enabled = d['enabled']
        if 'noproxy' in d:
            self.noproxy = None if d['noproxy'] is None else Noproxy(d['noproxy']['noproxies'], d['noproxy']['persist'])
        for attr in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            if not attr in d: continue
            obj = None if d[attr] is None else Proxyconf(d[attr]['protocol'], d[attr]['host'], d[attr]['port'], 
                                                         d[attr]['auth'], d[attr]['uname'], d[attr]['password'], d[attr]['persist'])
            setattr(self, attr, obj)

    @property
    def enabled(self):
        if getattr(self, '_enabled', None) is None:
            self._enabled = Sysproxy.get_sys_proxy_enabled()
        return self._enabled

    @enabled.setter
    def enabled(self, is_enabled) -> bool:
        if is_enabled == self._enabled:
            return
        if OS == 'Windows':
            Sysproxy.win_set_reg('ProxyEnable', int(is_enabled))
        if not is_enabled:
            Sysproxy.unset_sys_env('http_proxy')
        self._enabled = is_enabled

    @property
    def noproxy(self) -> Noproxy:
        if getattr(self, '_noproxy', None) is None:
            self._noproxy = Sysproxy.get_sys_noproxy()
        return self._noproxy

    @noproxy.setter
    def noproxy(self, value: Noproxy):
        if self._noproxy == value:
            return
        if OS == 'Windows':
            if not value:
                Sysproxy.win_set_reg('ProxyOverride', '')
            else:
                Sysproxy.win_set_reg('ProxyOverride', str(value))       
        if not value:
            Sysproxy.unset_sys_env('no_proxy')
        else:
            Sysproxy.set_sys_env('no_proxy', ', '.join(value.noproxies))
        self._noproxy = value.copy()

    @property
    def http_proxy(self) -> Proxyconf:
        if getattr(self, '_http_proxy', None) is None:
            self._http_proxy = Sysproxy.get_sys_proxy_parsed('http_proxy')
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

    @property
    def https_proxy(self) -> Proxyconf:
        if getattr(self, '_https_proxy', None) is None:
            self._https_proxy = Sysproxy.get_sys_proxy_parsed('https_proxy')
        return self._https_proxy

    @https_proxy.setter
    def https_proxy(self, value: Proxyconf):
        if self._https_proxy == value:
            return
        if not value:
            Sysproxy.unset_sys_env('https_proxy')
        else:
            Sysproxy.set_sys_env('https_proxy', str(value))

    @property
    def ftp_proxy(self) -> Proxyconf:
        if getattr(self, '_ftp_proxy', None) is None:
            self._ftp_proxy = Sysproxy.get_sys_proxy_parsed('ftp_proxy')
        return self._ftp_proxy

    @ftp_proxy.setter
    def ftp_proxy(self, value: Proxyconf):
        if self._ftp_proxy == value:
            return
        if not value:
            Sysproxy.unset_sys_env('ftp_proxy')
        else:
            Sysproxy.set_sys_env('ftp_proxy', str(value))

    @property
    def rsync_proxy(self) -> Proxyconf:
        if getattr(self, '_rsync_proxy', None) is None:
            self._rsync_proxy = Sysproxy.get_sys_proxy_parsed('rsync_proxy')
        return self._rsync_proxy

    @rsync_proxy.setter
    def rsync_proxy(self, value: Proxyconf):
        if self._rsync_proxy == value:
            return
        if not value:
            Sysproxy.unset_sys_env('rsync_proxy')
        else:
            Sysproxy.set_sys_env('rsync_proxy', str(value))

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
        self.stored = copy(self)

    def restore(self):
        if not getattr(self, 'stored', None):
            return        
        self.noproxy = self.stored.noproxy
        self.http_proxy = self.stored.http_proxy
        self.https_proxy = self.stored.https_proxy
        self.ftp_proxy = self.stored.ftp_proxy
        self.rsync_proxy = self.stored.rsync_proxy
        self.enabled = self.stored.enabled