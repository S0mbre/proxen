# -*- coding: utf-8 -*-
import os, platform, traceback, re, json, subprocess
import dataclasses
from collections.abc import Callable

OS = platform.system()

if not OS in ('Windows', 'Linux', 'Darwin'):
    raise Exception(f'Your platform ({OS}) is not [yet] supported, sorry! ((')

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
WIN_DUMMY_KEYNAME = 'ttt'

UNIX_LOCAL_FILE = '~/.profile'
if OS != 'Windows':
    shenv = os.environ.get('SHELL', None)
    if shenv:
        shell = shenv.split(os.sep)[-1].lower()
        if shell == 'bash':
            UNIX_LOCAL_FILE = '~/.bashrc'
        elif shell == 'zsh':
            UNIX_LOCAL_FILE = '~/.zshrc'
        elif shell == 'csh':
            UNIX_LOCAL_FILE = '~/.cshrc'
UNIX_PROFILE_FILES_USR = ['~/.profile', '~/.bashrc', '~/.bash_profile', '~/.zshrc', '~/.cshrc', '~/.tcshrc', ' ~/.login']
UNIX_PROFILE_FILES_SYS = ['/etc/profile', '/etc/environment', '/etc/bash.bashrc', '/etc/bashrc', '/etc/zsh/zshrc', '/etc/csh.cshrc', '/etc/csh.login']
REGEX_PROXY_EXPORT = r'(export\s{}=)(.*)'

# --------------------------------------------------------------- #

@dataclasses.dataclass
class Dclass:
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

    def asstr(self, winreg=False):
        l_noproxies = self.aslist()
        if not l_noproxies:
            return ''
        if winreg:
            vals = [val for val in l_noproxies if not val in ('localhost', '127.0.0.1')]
            if 'localhost' in l_noproxies or '127.0.0.1' in l_noproxies:
                vals.append('<local>')
            return ';'.join(vals)
        else:
            return ','.join(l_noproxies)

    def aslist(self):
        if not self.noproxies:
            return []
        l_noproxies = self.noproxies.split(',')
        if len(l_noproxies) < 2:
            l_noproxies = self.noproxies.split(';')
        return sorted(set(sl.strip() if sl.strip() != '<local>' else 'localhost' for sl in l_noproxies))

    def asdict(self):
        return {'noproxies': str(self)}

    @property
    def proxystr(self):
        return self.asstr(False)

    def __bool__(self):
        return bool(self.noproxies)

# --------------------------------------------------------------- #

class Sysproxy:

    def __init__(self, update_now=True, unix_file=UNIX_LOCAL_FILE):
        self.unix_file = os.path.expanduser(unix_file)
        self.locals = {}
        self.globals = {}
        if update_now: self.update_vars()

    def _unix_write_local(self) -> bool:
        return not self.unix_file.startswith('/etc')

    def update_vars(self):
        self.locals = {}
        self.globals = {}
        if OS == 'Windows':            
            self.locals = self.win_list_reg(WIN_ENV_LOCAL_KEY) or {}
            self.globals = self.win_list_reg(WIN_ENV_SYSTEM_KEY, 'HKLM') or {}
        else:
            # subprocess.run(f'source {self.unix_file}', shell=True, executable='/bin/bash')
            self.locals.update(**os.environ)

        utils.log('Env variables updated', 'debug')

    def get_env(self, envname, case_sensitive=False, modes=('user', 'system'), default=None): 
        res = None      
        if 'user' in modes:
            res = self.locals.get(envname, default if case_sensitive else self.locals.get(envname.upper(), self.locals.get(envname.lower(), default)))
        if res is None and 'system' in modes:
            res = self.globals.get(envname, default if case_sensitive else self.globals.get(envname.upper(), self.globals.get(envname.lower(), default)))
        return res

    def unix_del_env(self, envname, modes=('user',)) -> bool:
        if OS == 'Windows':
            raise Exception('This method is only for UNIX platforms!')
        if ('system' in modes) and (not CURRENT_USER[1]):
            raise Exception('Cannot modify system files: SU privilege asked!')
        try:
            reg = re.compile(r'^\s*export\s{}.*$'.format(envname), re.I | re.MULTILINE)
            for mode in modes:
                if mode == 'user':
                    file_list = UNIX_PROFILE_FILES_USR
                elif mode == 'system':
                    file_list = UNIX_PROFILE_FILES_SYS
                else:
                    continue
                for fname in file_list: 
                    fname = os.path.expanduser(fname)
                    if not os.path.isfile(fname): continue
                    with open(fname, 'r', encoding=utils.CODING) as f_:
                        ftext = f_.read().strip()
                    if reg.search(ftext) is None:
                        continue
                    ftext = reg.sub('\n:', ftext)
                    with open(fname, 'w', encoding=utils.CODING) as f_:
                        f_.write(ftext)
                    utils.log(f'Deleted env "{envname}" from file "{fname}"', 'debug')
            return True
        except:
            traceback.print_exc()
            return False

    def unix_write_env(self, filepath, envname, value) -> bool:
        if OS == 'Windows':
            raise Exception('This method is only for UNIX platforms!')        
        filepath = os.path.abspath(os.path.expanduser(filepath))
        if not os.path.isfile(filepath):
            return False
        wr_local = not filepath.startswith('/etc')
        if not wr_local and not CURRENT_USER[1]:
            raise Exception(f'Cannot write to {filepath}: SU privilege asked!')
        try:
            # 1 - delete exports in local OR systems files with this env
            self.unix_del_env(envname, ['user' if wr_local else 'system'])

            # 2 - write env to indicated file
            with open(filepath, 'a', encoding=utils.CODING) as f_:               
                for e_ in (envname.lower(), envname.upper()):
                    f_.write(f'{utils.NL}export {e_}="{value}"')

            utils.log(f'Written env "{envname}" = "{value}" to file "{filepath}"', 'debug')
            return True
        except:
            traceback.print_exc()
            return False

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
        if keyname == WIN_ENV_LOCAL_KEY and valname == WIN_DUMMY_KEYNAME:
            return ('t', winreg.REG_SZ)
        k = None
        res = None
        try:
            k = winreg.OpenKeyEx(branch, keyname, 0, winreg.KEY_ALL_ACCESS)
            try:
                val = winreg.QueryValueEx(k, valname)
            except:
                utils.log(f'Unable to set win reg key "{keyname}\\{valname}" (value does not exist!)', 'debug')
                res = None
            else:
                if isinstance(value, str) and not val[1] in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                    # need convert...
                    if val[1] == winreg.REG_BINARY:
                        value = bytes.fromhex(value)
                    elif val[1] == winreg.REG_DWORD:
                        value = int(value)
                if val[0] != value:
                    winreg.SetValueEx(k, valname, 0, val[1], value)
                    # propagate env vars by calling setx
                    subprocess.run(f'setx ttt t > nul', shell=True)                    
                    res = winreg.QueryValueEx(k, valname) 
                    utils.log(f'Set win reg key "{keyname}\\{valname}" = "{res[0]}"', 'debug')
                else:                    
                    res = val    
                    utils.log(f'Win reg key "{keyname}\\{valname}" is already "{res[0]}", skipping reset', 'debug')
        except:
            traceback.print_exc()
            utils.log(f'Error setting win reg key "{keyname}\\{valname}" = "{value}"', 'debug')
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_create_reg(self, keyname, valname, value, valtype=None, branch='HKEY_CURRENT_USER') -> tuple[str, int]:
        if OS != 'Windows':
            raise Exception('This method is available only on Windows platforms!')
        if isinstance(branch, str):
            branch = WIN_REG_BRANCHES[branch]
        if keyname == WIN_ENV_LOCAL_KEY and valname == WIN_DUMMY_KEYNAME:
            return None
        if not valtype:
            if isinstance(value, str):
                if re.match(r'%(.+?)%', value, re.I):
                    valtype = winreg.REG_EXPAND_SZ
                else:
                    valtype = winreg.REG_SZ
            elif isinstance(value, int) or isinstance(value, float):
                valtype = winreg.REG_DWORD
            elif isinstance(value, bytes) or isinstance(value, bytearray):
                valtype - winreg.REG_BINARY
        elif isinstance(valtype, str):
            if valtype == 'string':
                valtype = winreg.REG_SZ
            elif valtype == 'number':
                valtype = winreg.REG_DWORD
            elif valtype == 'binary':
                valtype = winreg.REG_BINARY
            elif valtype == 'macro':
                valtype = winreg.REG_EXPAND_SZ
            else:
                valtype = winreg.REG_SZ       
        if isinstance(value, str) and not valtype in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            # need convert...
            if valtype == winreg.REG_BINARY:
                value = bytes.fromhex(value)
            elif valtype == winreg.REG_DWORD:
                value = int(value) 
        k = None
        res = None
        try:
            k = winreg.OpenKeyEx(branch, keyname, 0, winreg.KEY_ALL_ACCESS)
            try:
                res = winreg.QueryValueEx(k, valname)
                utils.log(f'Failed to create win reg key "{keyname}\\{valname}" (already exists!)', 'debug')
                res = None
            except FileNotFoundError:
                winreg.SetValueEx(k, valname, 0, valtype, value)
                res = winreg.QueryValueEx(k, valname)
                # propagate env vars by calling setx
                subprocess.run(f'setx ttt t > nul', shell=True)
                utils.log(f'Created win reg key "{keyname}\\{valname}" = "{res[0]}"', 'debug')
        except:
            traceback.print_exc()
            utils.log(f'Error creating win reg key "{keyname}\\{valname}" = "{value}"', 'debug')
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
            try:
                winreg.DeleteValue(k, valname)
                # propagate env vars by calling setx
                subprocess.run(f'setx ttt t > nul', shell=True)
                utils.log(f'Deleted win reg key "{keyname}\\{valname}"', 'debug')
            except FileNotFoundError:
                utils.log(f'Win reg key "{keyname}\\{valname}" is not found, skipping delete', 'debug')            
            res = True
        except:
            traceback.print_exc()
            utils.log(f'Error deleting win reg key "{keyname}\\{valname}"', 'debug')
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_list_reg(self, keyname, branch='HKEY_CURRENT_USER', expand_vars=True, with_types=False) -> dict:
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
                    if val[0] == WIN_DUMMY_KEYNAME:
                        continue
                    if not expand_vars or not isinstance(val[1], str):
                        res[val[0]] = val[1:] if with_types else val[1]
                    else:                        
                        v = reg.sub(lambda m: os.environ.get(m[1], m[0]), val[1])
                        res[val[0]] = (v, val[2]) if with_types else v
                except OSError:
                    break
        except:
            traceback.print_exc()
        finally:
            if k: winreg.CloseKey(k)
        return res

    def win_get_reg_proxy(self, valname) -> str:
        res = self.win_get_reg(WIN_PROXY_KEY, valname)
        return res[0] if res else None

    def win_set_reg_proxy(self, valname, value) -> str:
        res = self.win_set_reg(WIN_PROXY_KEY, valname, value)
        return res[0] if res else None

    def list_sys_envs_proxy(self) -> dict:
        proxies = [item for sublist in [[p.lower(), p.upper()] for p in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'no_proxy')] for item in sublist]
        return {'user': {k: v for k, v in self.locals if k in proxies},
                'system': {k: v for k, v in self.globals if k in proxies}}

    def get_sys_env(self, envname: str, default=None) -> dict:
        return {'user': self.get_env(envname, False, ('user',), default),
                'system': self.get_env(envname, False, ('system',), default)}

    def set_sys_env(self, envname: str, value, create=True, valtype=None, modes=('user',), update_vars=True) -> bool:
        if ('system' in modes) and (not CURRENT_USER[1]):
            raise Exception('Cannot execute command: SU privilege asked!')
        
        env = self.get_sys_env(envname)
        if ('user' in modes and env['user'] == value) or ('system' in modes and env['system'] == value):
            utils.log(f'System env "{envname}" is already "{value}", skipping reset', 'debug')
            return True

        res = False
        if OS == 'Windows':
            envname = envname.upper()
            res = []
            for mode in modes:
                try:          
                    if mode == 'user':
                        if env['user']:
                            res.append(self.win_set_reg(WIN_ENV_LOCAL_KEY, envname, value, 'HKCU'))
                        elif create:
                            res.append(self.win_create_reg(WIN_ENV_LOCAL_KEY, envname, value, valtype, 'HKCU'))
                        else:
                            res.append(False)
                    elif mode == 'system':
                        if env['system']:
                            res.append(self.win_set_reg(WIN_ENV_SYSTEM_KEY, envname, value, 'HKLM'))
                        elif create:
                            res.append(self.win_create_reg(WIN_ENV_SYSTEM_KEY, envname, value, valtype, 'HKLM'))
                        else:
                            res.append(False)
                except:
                    res.append(False)   
            res = all(res)            
        else:
            if create or ('user' in modes and env['user']) or ('system' in modes and env['system']):
                res = self.unix_write_env(self.unix_file, envname, value)
            else:
                res = None
        
        if res and isinstance(value, str):
            for e_ in {envname, envname.lower(), envname.upper()}:
                os.environ[e_] = value
        
        if update_vars: 
            self.update_vars()
        if res:    
            utils.log(f'Set system env "{envname}" = "{value}"', 'debug')
        return res

    def unset_sys_env(self, envname: str, modes=('user',), update_vars=True) -> bool:
        if ('system' in modes) and (not CURRENT_USER[1]):
            raise Exception('Cannot execute command: SU privilege asked!')
        env = self.get_sys_env(envname)
        if ('user' in modes and not env['user']) or ('system' in modes and not env['system']):
            utils.log(f'System env "{envname}" does not exist, skipping unset', 'debug')
            return True
        res = False
        if OS == 'Windows':            
            res = []
            for e_ in {envname, envname.lower(), envname.upper()}:
                for mode in modes:
                    try:
                        if mode == 'user':
                            res.append(self.win_del_reg(WIN_ENV_LOCAL_KEY, e_, 'HKCU'))
                        elif mode == 'system':
                            res.append(self.win_del_reg(WIN_ENV_SYSTEM_KEY, e_, 'HKLM'))
                    except:
                        res.append(False)
            res = all(res)         
        else:
            res = self.unix_del_env(envname, modes)

        if res:
            for e_ in {envname, envname.lower(), envname.upper()}:
                if e_ in os.environ:
                    os.environ.pop(e_, None)

        if update_vars: self.update_vars()
        utils.log(f'Delete system env "{envname}"', 'debug')
        return res

    def get_sys_http_proxy(self) -> dict:
        env1 = self.get_sys_env('all_proxy')
        env2 = self.get_sys_env('http_proxy')
        env = {'user': env1['user'] or env2['user'], 'system': env1['system'] or env2['system']}

        if OS == 'Windows':
            res = self.win_get_reg_proxy('ProxyServer')            
            if not res is None:
                if not '@' in res:
                    # try to get auth from env variable
                    env_str = env['user'] or env['system']
                    if env_str and '@' in env_str:
                        env_str_sp = env_str.split('://')
                        if len(env_str_sp) > 1:
                            env_str = env_str_sp[1]
                        env_str_sp = env_str.split('@')
                        if len(env_str_sp[0]):
                            res = f'{env_str_sp[0]}@{res}'
                res = {'user': f'http://{res}', 'system': None}
            else:
                res = env
            return res

        return env

    def get_sys_proxy_enabled(self) -> bool:
        if OS == 'Windows':
            res = self.win_get_reg_proxy('ProxyEnable')
            if res is None: return False
            return bool(res)

        # Linux doesn't have separate 'proxy enable' switch, so try to get 'http_proxy' ENV...
        env = self.get_sys_http_proxy()
        return not (env['user'] is None and env['system'] is None)

    def get_sys_noproxy(self) -> Noproxy:
        if OS == 'Windows':
            res = self.win_get_reg_proxy('ProxyOverride')
            return None if res is None else Noproxy(None, res)
        res = self.get_sys_env('no_proxy')
        return None if res is None else Noproxy(None, res)

    def get_sys_proxy_parsed(self, proxy='http_proxy') -> Proxyconf:
        _proxy = self.get_sys_http_proxy() if proxy == 'http_proxy' else self.get_sys_env(proxy)
        if (_proxy is None) or not (_proxy['user'] or _proxy['system']): 
            return None
        # prefer user (local) proxy config over system
        _proxy = _proxy['user'] or _proxy['system']
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
        return Proxyconf(None, prot, host or '', port or 3128, not uname is None, uname or '', passw or '')

# --------------------------------------------------------------- #

class Proxy:

    def __init__(self, storage_file='proxy_config.json', unix_file=UNIX_LOCAL_FILE):
        self.storage_file = utils.make_abspath(storage_file) if not os.path.isabs(storage_file) else storage_file
        self.sysproxy = Sysproxy(True, unix_file)
        self._isupdating = 0
        self.read_system()
        self.save()

    def asdict(self) -> dict:
        d = {'enabled': self.enabled, 'noproxy': str(self.noproxy)}
        for attr in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            prop = getattr(self, attr, None)
            d[attr] = prop.asdict() if prop else None
        return d

    def asstr(self) -> str:
        return json.dumps(self.asdict())

    def fromdict(self, dconfig: dict):
        if self.asdict() == dconfig:
            return
        self.begin_updates()
        for attr in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            obj = dconfig.get(attr, None)
            if not obj is None:
                obj = Proxyconf(self._on_setattr, obj.get('protocol', 'http'), obj.get('host', ''),
                                obj.get('port', 3128), obj.get('auth', False), 
                                obj.get('uname', ''), obj.get('password', ''))
            setattr(self, attr, obj)
        self.noproxy = Noproxy(self._on_setattr, dconfig['noproxy']) if dconfig.get('noproxy', None) else None
        self.enabled = dconfig.get('enabled', self.enabled)
        self.end_updates()

    def fromstr(self, strconfig: str):
        self.fromdict(json.loads(strconfig))

    def begin_updates(self):
        self._isupdating += 1

    def end_updates(self):
        if self._isupdating == 0:
            return
        self._isupdating -= 1
        if self._isupdating == 0:
            self.sysproxy.update_vars()

    def _get_sys_noproxy(self):
        noproxy = self.sysproxy.get_sys_noproxy()
        if noproxy:
            noproxy.on_setattr = self._on_setattr
        return noproxy

    def _get_sys_proxy(self, proxystr):
        proxy = self.sysproxy.get_sys_proxy_parsed(proxystr)
        if proxy:
            proxy.on_setattr = self._on_setattr
        return proxy

    def read_system(self):
        self._enabled = self.sysproxy.get_sys_proxy_enabled()
        self._noproxy = self._get_sys_noproxy()
        self._http_proxy = self._get_sys_proxy('http_proxy')
        self._https_proxy = self._get_sys_proxy('https_proxy')
        self._ftp_proxy = self._get_sys_proxy('ftp_proxy')
        self._rsync_proxy = self._get_sys_proxy('rsync_proxy')
        utils.log(f'SYSTEM SETTINGS: {str(self)}', 'debug')

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

    def _on_setattr(self, obj, name, value):
        if isinstance(obj, Noproxy):
            if OS == 'Windows':
                self.sysproxy.win_set_reg_proxy('ProxyOverride', obj.asstr(True))
            if obj:
                self.sysproxy.set_sys_env('no_proxy', obj.asstr(False), update_vars=not self._isupdating)
            else:
                self.sysproxy.unset_sys_env('no_proxy', update_vars=not self._isupdating)
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
                self.sysproxy.win_set_reg_proxy('ProxyServer', f'{obj.host}:{obj.port}')
            self.sysproxy.set_sys_env(proxy, str(obj), update_vars=not self._isupdating)

    @property
    def enabled(self):
        if getattr(self, '_enabled', None) is None:
            self._enabled = self.sysproxy.get_sys_proxy_enabled()
        return self._enabled

    @enabled.setter
    def enabled(self, is_enabled) -> bool:
        if is_enabled == self._enabled:
            return
        if not is_enabled:
            self.sysproxy.unset_sys_env('http_proxy', update_vars=False)
            self.sysproxy.unset_sys_env('all_proxy', update_vars=False)
        else:
            proxy = self.http_proxy or self.https_proxy or self.ftp_proxy
            if not proxy:
                return
            self.sysproxy.set_sys_env('http_proxy', str(proxy), update_vars=False)
        if OS == 'Windows':
            self.sysproxy.win_set_reg_proxy('ProxyEnable', int(is_enabled))

        if not self._isupdating:
            self.sysproxy.update_vars()
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
            self.sysproxy.win_set_reg_proxy('ProxyOverride', value.asstr(True) if value else '')
        if not value:
            self.sysproxy.unset_sys_env('no_proxy', update_vars=not self._isupdating)
        elif value.noproxies:
            self.sysproxy.set_sys_env('no_proxy', value.asstr(False), update_vars=not self._isupdating)
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
        if not value:
            self.sysproxy.unset_sys_env('http_proxy', update_vars=False)
            self.sysproxy.unset_sys_env('all_proxy', update_vars=False)
            if OS == 'Windows':
                self.sysproxy.win_set_reg_proxy('ProxyEnable', 0)
                self._enabled = False
        else:
            self.sysproxy.set_sys_env('http_proxy', str(value), update_vars=False)
            if OS == 'Windows':
                self.sysproxy.win_set_reg_proxy('ProxyServer', f'{value.host}:{value.port}')
        
        if not self._isupdating:
            self.sysproxy.update_vars()
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
            self.sysproxy.unset_sys_env('https_proxy', update_vars=not self._isupdating)
        else:
            self.sysproxy.set_sys_env('https_proxy', str(value), update_vars=not self._isupdating)
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
            self.sysproxy.unset_sys_env('ftp_proxy', update_vars=not self._isupdating)
        else:
            self.sysproxy.set_sys_env('ftp_proxy', str(value), update_vars=not self._isupdating)
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
            self.sysproxy.unset_sys_env('rsync_proxy', update_vars=not self._isupdating)
        else:
            self.sysproxy.set_sys_env('rsync_proxy', str(value), update_vars=not self._isupdating)
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
        self.begin_updates()
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
        self.end_updates()

    def save(self):
        self.stored = self.asdict()

    def restore(self):
        if getattr(self, 'stored', None):
            self.fromdict(self.stored)
    
    def __str__(self):
        return self.asstr()