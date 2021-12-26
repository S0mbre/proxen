# -*- coding: utf-8 -*-
import os, platform, traceback, copy, re, json, subprocess
import dataclasses
from collections.abc import Callable

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
        utils.log(f'Get win reg key {WIN_PROXY_KEY}\\{valname} = {res}', 'debug')
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
        utils.log(f'Set win reg key {WIN_PROXY_KEY}\\{valname} = {value}', 'debug')
        return res

    @staticmethod
    def get_sys_env(envname: str, both_cases=True, default=None):
        if OS == 'Windows':
            envs = subprocess.check_output(['set'], shell=True, encoding=utils.CODING, errors='ignore')
            if not envs: return None
            for str_env in envs.split('\n'):
                sp = str_env.strip().split('=')
                if len(sp) == 2 and sp[0].upper() == envname.upper():
                    return sp[1]
            return None
        else:
            if both_cases:
                res = os.environ.get(envname.lower(), os.environ.get(envname.upper(), default))
            else:
                res = os.environ.get(envname, default)
        utils.log(f'Get system env {envname} = {res}', 'debug')
        return res

    @staticmethod
    def list_sys_envs_proxy():
        proxies = [item for sublist in [[p.lower(), p.upper()] for p in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'no_proxy')] for item in sublist]
        return {proxy: Sysproxy.get_sys_env(proxy, False) for proxy in proxies}

    @staticmethod
    def set_sys_env(envname: str, value, both_cases=True, create=True):
        env = Sysproxy.get_sys_env(envname, both_cases)
        if env is None and not create:
            return
        if both_cases:
            for e_ in (envname.lower(), envname.upper()):
                os.environ[e_] = value
                if OS == 'Windows':
                    subprocess.run(['set', f'{e_}={value}'], shell=True)
                utils.log(f'Set system env {e_} = {value}', 'debug')
        else:
            os.environ[envname] = value
            utils.log(f'Set system env {envname} = {value}', 'debug')

    @staticmethod
    def unset_sys_env(envname: str, both_cases=True):
        if both_cases:
            for e_ in (envname.lower(), envname.upper()):
                if e_ in os.environ:
                    del os.environ[e_]
                    if OS == 'Windows':
                        subprocess.run(['set', f'{e_}='], shell=True)
                    utils.log(f'Delete system env {e_}', 'debug')
        else:
            os.environ.pop(envname, default=None)
            utils.log(f'Delete system env {envname}', 'debug')

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
            return None if res is None else Noproxy(True, None, res)
        
        res = Sysproxy.get_sys_env('no_proxy')
        pers = Sysproxy.get_sys_persist('no_proxy')
        return None if res is None else Noproxy(pers, None, res)

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
        return Proxyconf(Sysproxy.get_sys_persist(proxy), None, prot, host or '', port or 3128, not uname is None, uname or '', passw or '')

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
                utils.log(f'Found {m[2].strip()} in file {fname}', 'debug')
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
                    for p_ in (proxy.lower(), proxy.upper()):
                        f_.write(f'export {p_}={value}{utils.NL}')
                        utils.log(f'Written {p_} to file {unix_file}', 'debug')
                else:
                    p_ = f'export {proxy}={value}{utils.NL}'
                    f_.write(p_)
                    utils.log(f'Written {p_} to file {unix_file}', 'debug')
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