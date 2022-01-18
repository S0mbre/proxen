# -*- coding: utf-8 -*-
## @package proxen.sysproxy
# @brief Implements classes to work with the system proxy configuration. See Sysenv and Proxy.
import os, platform, traceback, re, json, subprocess
import dataclasses
from collections.abc import Callable
from typing import Union

## @brief `str` the current OS platform name, e.g. 'Windows', 'Linux' or 'Darwin' (MacOS)
OS = platform.system()

if not OS in ('Windows', 'Linux', 'Darwin'):
    raise Exception(f'Your platform ({OS}) is not [yet] supported, sorry! ((')

if OS == 'Windows':
    import winreg
    ## `dict` Windows registry branch names
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

## `tuple` current user name and admin privileges mark (see utils::has_admin())
CURRENT_USER = utils.has_admin()
## `str` Windows registry key containing current proxy settings
WIN_PROXY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
## `str` Windows registry key containing user environment variables (in HKCU branch)
WIN_ENV_LOCAL_KEY = 'Environment'
## `str` Windows registry key containing system-wide environment variables (in HKLM branch)
WIN_ENV_SYSTEM_KEY = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
## `str` Windows dummy registry entry to update environment variables
WIN_DUMMY_KEYNAME = 'ttt'
## `list` Unix user settings files
UNIX_PROFILE_FILES_USR = ['~/.profile', '~/.bashrc', '~/.bash_profile', '~/.zshrc', '~/.cshrc', '~/.tcshrc', ' ~/.login']
## `list` Unix root/system settings files
UNIX_PROFILE_FILES_SYS = ['/etc/environment', '/etc/profile', '/etc/bashrc', '/etc/bash.bashrc', '/etc/zsh/zshrc', '/etc/csh.cshrc', '/etc/csh.login']
## `str` default Unix local settings file (loaded on user logon)
UNIX_LOCAL_FILE = '~/.profile'
## `str` default Unix system settings file
UNIX_SYSTEM_FILE = '/etc/environment'
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
    for fn in UNIX_PROFILE_FILES_SYS:
        if os.path.isfile(fn):
            UNIX_SYSTEM_FILE = fn
            break
## `str` regex template to search for env vars in Unix files
REGEX_ENV_EXPORT = r'(export\s{}=)(.*)'
## `str` regex template to search for proxy env vars
REGEX_PROXY_EXPORT = r'export\s[\w_]+proxy'

# --------------------------------------------------------------- #

## @brief Base data class for proxy / noproxy config classes.
@dataclasses.dataclass
class Dclass:
    ## `callable` called when a member attribute is written to (set)
    on_setattr: Callable = None

    ## @returns `str` string representation of the object (must be implemented in child classes)
    @property
    def proxystr(self):
        return ''

    ## @returns `dict` dict representation of the object (default = all members)
    def asdict(self):
        # return dataclasses.asdict(self)
        return dict((field.name, getattr(self, field.name)) for field in dataclasses.fields(self) if field.name != 'on_setattr')

    ## @returns `str` string representation of the object (calls Dclass::proxystr())
    def __str__(self):
        return self.proxystr

    ## Hook executed when a member attribute is written to (set)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if getattr(self, 'on_setattr', None) and name != 'on_setattr':
            self.on_setattr(self, name, value)

# --------------------------------------------------------------- #

## @brief System proxy configuration object, e.g. for HTTP_PROXY or HTTPS_PROXY.
@dataclasses.dataclass
class Proxyconf(Dclass):
    ## `str` the proxy protocol (type): any of 'http', 'https', 'ftp' or 'rsync'
    protocol: str = 'http'
    ## `str` the proxy host / IP, e.g. '192.168.1.0'
    host: str = ''
    ## `int` the proxy port (default = 3128)
    port: int = 3128
    ## `bool` whether the proxy server must use authentication (default = `False`)
    auth: bool = False
    ## `str` proxy user name (if auth is `True`)
    uname: str = ''
    ## `str` proxy user password (if auth is `True`)
    password: str = ''

    ## @returns `str` string representation in the format: 
    # `protocol://[username:password@]host:port`
    @property
    def proxystr(self):
        if self.auth and self.uname:
            auth_ = ':'.join((self.uname, self.password)) + '@'
        else:
            auth_ = ''
        return f'{self.protocol}://{auth_}{self.host}:{self.port}'

# --------------------------------------------------------------- #

## @brief Proxy bypass (no-proxy) configuration object.
@dataclasses.dataclass
class Noproxy(Dclass):
    ## `str` comma-separated list of proxy bypass addresses, e.g.
    # `localhost, 127.0.0.1, *.example.com`
    noproxies: str = ''

    ## Returns the concatenated string representation of the bypassed addresses.
    # @param winreg `bool` if `True`, the string will be formatted using the Windows
    # registry convention (`HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\ProxyOverrid`e)
    # @returns `str` delimited list of proxy bypass addresses
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

    ## @returns `list` bypassed addresses as a list, e.g.
    # ```['localhost', '127.0.0.1', '*.example.com']```
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

    ## @returns `bool` convenience to check object validity:
    # returns `False` if Noproxy::noproxies is empty and `True` otherwise
    def __bool__(self):
        return bool(self.noproxies)

# --------------------------------------------------------------- #

## @brief A class to operate system environment variables (cross-platform).
#
# This class provides a set of relatively low-level tools to manipulate
# the system environment variables, such as:
# - list environment variables in the user and system domains
# - get and set variable values
# - create and delete variables
# - perform some proxy-specific tasks parsing related variable values
#
# Most operations allow of two separate variable domains: *user* and *system*.
# Environment variables in the *user* domain affect only the current user and not the
# entire system; each user can create / set their own variables, even with the same names.
# *User* variables are stored in the corresponding locations
# depending on the platform:
# - **Windows**: `HKEY_CURRENT_USER` registry branch (`Environment` key)
# - **Linux and Mac**: user files such as `~/.profile` (see sysproxy::UNIX_PROFILE_FILES_USR)
#
# Correspondingly, *system* variables affect the entire system and are used in default of
# the user variables. For example, if the variable 'HTTP_PROXY' is not set in the *user*
# domain, the OS will use the value of 'HTTP_PROXY' in the *system* domain (if present).
# If a variable exists in both domains, the *user* one prevails.\n
# *System* variables are stored in:
# - **Windows**: `HKEY_LOCAL_MACHINE` registry branch (`SYSTEM\CurrentControlSet\Control\Session Manager\Environment` key)
# - **Linux and Mac**: user files such as `/etc/profile` (see sysproxy::UNIX_PROFILE_FILES_SYS)
# 
# This class provides a unified interface for writing (creating / setting) environment variables
# in both domains and persisting them in the system by writing to the corresponding files
# and registry values.
#
# @warning This class persists all proxy configurations in the system!
# For Windows, it will set / create registry values in `HKCU\Environment`.
# For Unix systems (Linux and Max), it will write the proxy environment variables to
# the indicated profile / environment file (like `~/.bashrc` or `~/.profile`).
class Sysenv:

    ## @param update_now `bool` if `True`, retrieves the env variables on object creation
    def __init__(self, update_now=True):
        ## `str` for Unix, the file with user settings where the proxy 
        # environment variables will be written (= sysproxy::UNIX_LOCAL_FILE)
        self.unix_file_local = os.path.expanduser(UNIX_LOCAL_FILE)
        ## `str` for Unix, the file with system settings where the proxy 
        # environment variables will be written (= sysproxy::UNIX_SYSTEM_FILE)
        self.unix_file_system = os.path.expanduser(UNIX_SYSTEM_FILE)
        ## `dict` local (user) environment variables 
        # (key = variable name, value = variable value)
        self.locals = {}
        ## `dict` global (system) environment variables 
        # (key = variable name, value = variable value)
        self.globals = {}
        if update_now: self.update_vars()

    ## Reads environment variables into Sysenv::locals and Sysenv::globals.
    def update_vars(self):
        self.locals = {}
        self.globals = {}
        if OS == 'Windows':
            # on Win it's possible to get local and system (machine) vars separately from the registry
            self.locals = self.win_list_reg(WIN_ENV_LOCAL_KEY) or {}
            self.globals = self.win_list_reg(WIN_ENV_SYSTEM_KEY, 'HKLM') or {}
        else:
            # hard to separate 'user' from 'system' vars on Unix, so use only user domain
            self.locals.update(**os.environ)

        utils.log('Env variables updated', 'debug')

    ## Gets the value(s) of the specified environment variable.
    # @param envname `str` the environment variable name, e.g. 'http_proxy'
    # @param case_sensitive `bool` if `True`, match the var name exactly; otherwise,
    # search both lower- and upper-case name
    # @param modes `iterable` an iterable of either or both of these elements:
    # - `user`: search the variable in Sysenv::locals
    # - `system`: search the variable in Sysenv::globals
    # @param default `Any` value used in default of the variable value, if not found
    # (default = `None`)
    # @returns `dict` a dictionary of 2 elements:
    # ```python
    # {'user': value or None, 'system': value or None}
    # ```
    def get_env(self, envname, case_sensitive=False, modes=('user', 'system'), default=None) -> dict: 
        res = None      
        if 'user' in modes:
            res = self.locals.get(envname, default if case_sensitive else self.locals.get(envname.upper(), self.locals.get(envname.lower(), default)))
        if res is None and 'system' in modes:
            res = self.globals.get(envname, default if case_sensitive else self.globals.get(envname.upper(), self.globals.get(envname.lower(), default)))
        return res

    def _unix_get_from_file(self, envname_pattern, filename, case_sensitive=False, reverse=False, raw=False) -> Union[dict, str]:
        if OS == 'Windows':
            raise Exception('This method is only for UNIX platforms!')
        flags = ''
        if not case_sensitive:
            flags = '-i'
        if reverse:
            flags = '-v' if not flags else f'{flags}v'
        if flags:
            flags = f' {flags}'
        try:
            res = subprocess.run(f'grep{flags} "export\s{envname_pattern}" "{filename}"', shell=True, check=True, capture_output=True, encoding=utils.CODING)
            res.check_returncode()
            if raw:
                return res.stdout
            else:
                ret = {}
                sp1 = res.stdout.split('\n')
                for line in sp1:
                    line = line[line.index('export')+7:]
                    sp2 = line.split('=')
                    if len(sp2) == 2:
                        val = sp2[1].strip()
                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                            val = val[1:-1]
                        ret[sp2[0]] = val
                return ret
        except subprocess.CalledProcessError as err:
            utils.log('Shell command %s returned %d: %s', 'exception', err.cmd, err.returncode, err.output)
            return None
        except:
            return None

    def _unix_delete_from_file(self, envname_pattern, filename, case_sensitive=False) -> bool:
        if OS == 'Windows':
            raise Exception('This method is only for UNIX platforms!')
        txt = ''
        with open(filename, 'r', encoding=utils.CODING) as f_:
            txt = f_.read()
        res = self._unix_get_from_file(envname_pattern, filename, case_sensitive, True, True)
        if res is None:
            return False
        if res == txt:
            utils.log(f'No envs with pattern "{envname_pattern}" are found in file "{filename}"', 'debug')
            return True
        with open(filename, 'w', encoding=utils.CODING) as f_:
            f_.write(res)
        utils.log(f'Deleted envs with pattern "{envname_pattern}" from file "{filename}"', 'debug')
        return True

    ## Deletes (unsets) an env variable on Unix systems.
    # @param envname `str` the environment variable name, e.g. 'http_proxy'
    # @param modes `iterable` an iterable of either or both of these elements:
    # - `user`: unset user variable (from `~/...` files)
    # - `system`: unset system variable (from `/etc/...` files)
    # @returns `bool` success = `True`, failure = `False`
    def unix_del_env(self, envname, modes=('user', 'system')) -> bool:
        if OS == 'Windows':
            raise Exception('This method is only for UNIX platforms!')
        try:
            # reg = re.compile(r'^\s*export\s{}.*$'.format(envname), re.I | re.MULTILINE)
            for mode in modes:
                if mode == 'user':
                    file_list = UNIX_PROFILE_FILES_USR
                elif mode == 'system':
                    if not CURRENT_USER[1]:
                        continue
                    else:
                        file_list = UNIX_PROFILE_FILES_SYS
                else:
                    continue
                for fname in file_list: 
                    fname = os.path.expanduser(fname)
                    if not os.path.isfile(fname): continue
                    self._unix_delete_from_file(envname, fname)
                    """
                    with open(fname, 'r', encoding=utils.CODING) as f_:
                        ftext = f_.read().strip()
                    if reg.search(ftext) is None:
                        continue
                    ftext = reg.sub('\n:', ftext)
                    with open(fname, 'w', encoding=utils.CODING) as f_:
                        f_.write(ftext)
                    utils.log(f'Deleted env "{envname}" from file "{fname}"', 'debug')
                    """                    
            return True

        except:
            traceback.print_exc()
            return False

    ## (Re)sets the value of an env variable on Unix systems.
    # @param envname `str` the environment variable name, e.g. 'http_proxy'
    # @param value `Any` the variable value, e.g. '192.168.1.0' (string) or 25 (number)
    # @returns `bool` success = `True`, failure = `False`
    def unix_write_env(self, envname, value, write_system=True) -> bool:
        if OS == 'Windows':
            raise Exception('This method is only for UNIX platforms!')
        try:
            # 1 - delete exports in local AND/OR systems files with this env
            self.unix_del_env(envname)

            # 2 - write env to files
            files = [self.unix_file_local]
            if write_system and CURRENT_USER[1]:
                files.append(self.unix_file_system)

            for fname in files:
                with open(fname, 'a', encoding=utils.CODING) as f_:               
                    for e_ in (envname.lower(), envname.upper()):
                        f_.write(f'{utils.NL}export {e_}="{value}"')
                utils.log(f'Written env "{envname}" = "{value}" to file "{fname}"', 'debug')
                
            return True

        except:
            traceback.print_exc()
            return False

    ## Gets the value of a specified key/val from the Windows registry.
    # @param keyname `str` the registry key path
    # @param valname `str` the registry value name
    # @param branch `str` the registry branch name
    # @returns `tuple` a 2-tuple containing the following elements:
    # -# `str` the retrieved value (as a string)
    # -# `int` the value type (see [winreg docs](https://docs.python.org/3/library/winreg.html#value-types))
    # `None` is returned on error
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
            utils.log(f'!!! Failed to get Win reg value {keyname}\\{valname}', 'debug')
        finally:
            if k: winreg.CloseKey(k)
        return res

    ## Sets the value of a variable in the Windows registry.
    # @param keyname `str` the registry key path
    # @param valname `str` the registry value name
    # @param value `str` the value to set 
    # (will be converted as needed to `int` or `bytes` depending on the value type in the registry)
    # @param branch `str` the registry branch name
    # @returns `tuple` a 2-tuple containing the following elements:
    # -# `str` the value of the entry written to (as a string)
    # -# `int` the value type (see [winreg docs](https://docs.python.org/3/library/winreg.html#value-types))
    # `None` is returned on error (e.g. if the value doesn't exist in the registry)
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
                    subprocess.run('setx ttt t > nul', shell=True)
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

    ## Creates a new entry in the Windows registry.
    # @param keyname `str` the registry key path
    # @param valname `str` the registry value name
    # @param value `str` the value to set
    # @param valtype `str`|`int` the type of the value to create.
    # If it is passed as `None`, the method will attempt to guess the type automatically
    # from the Python type of `value`. If it is passed as a string, it should be any of:
    # - `string` or empty: corresponds the `REG_SZ` type in the Windows registry
    # - `number`: corresponds the `REG_DWORD` type in the Windows registry
    # - `binary`: corresponds the `REG_BINARY` type in the Windows registry
    # - `macro`: corresponds the `REG_EXPAND_SZ` type in the Windows registry
    # If passed as an `int`, it should be any of the [winreg type constants](https://docs.python.org/3/library/winreg.html#value-types).
    # @param branch `str` the registry branch name
    # @returns `tuple` a 2-tuple containing the following elements:
    # -# `str` the value of the created entry (as a string)
    # -# `int` the value type (see [winreg docs](https://docs.python.org/3/library/winreg.html#value-types))
    # `None` is returned on error (e.g. if the value already exists in the registry)
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
                subprocess.run('setx ttt t > nul', shell=True)
                utils.log(f'Created win reg key "{keyname}\\{valname}" = "{res[0]}"', 'debug')
        except:
            traceback.print_exc()
            utils.log(f'Error creating win reg key "{keyname}\\{valname}" = "{value}"', 'debug')
        finally:
            if k: winreg.CloseKey(k)
        return res

    ## Deletes an entry in the Windows registry.
    # @param keyname `str` the registry key path
    # @param valname `str` the registry value name
    # @param branch `str` the registry branch name
    # @returns `bool` success = `True`, failure = `False`
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
                subprocess.run('setx ttt t > nul', shell=True)
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

    ## Retrieves variables from a Windows registry key.
    # @param keyname `str` the registry key path
    # @param branch `str` the registry branch name
    # @param expand_vars `bool` whether to resolve internal macros (like '%PATH%)
    # @param with_types `bool` whether to return values as 2-tuples: `(value, type)`
    # @returns `dict` a dictionary of variables:
    # ```python
    # {'variable name': value}               # if with_types == False
    # {'variable name': (value, value_type)} # if with_types == True
    # ```
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

    ## @brief Retrieves the value of a proxy setting from the Windows registry.
    # Proxy settings are located in `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings`
    # @param valname `str` the value (setting) name, e.g. 'ProxyServer'
    # @returns `str` the retreived value or `None` on failure
    def win_get_reg_proxy(self, valname) -> str:
        res = self.win_get_reg(WIN_PROXY_KEY, valname)
        return res[0] if res else None

    ## @brief Sets the value of a proxy setting in the Windows registry.
    # Proxy settings are located in `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings`
    # @param valname `str` the value (setting) name, e.g. 'ProxyServer'
    # @param value `str` the value to set
    # @returns `str` the newly set value or `None` on failure
    def win_set_reg_proxy(self, valname, value) -> str:
        res = self.win_set_reg(WIN_PROXY_KEY, valname, value)
        if res is None:
            res = self.win_create_reg(WIN_PROXY_KEY, valname, value)
        return res[0] if res else None

    ## @brief Gets the values of all proxy-related environment variables in the user and system domains.
    # @returns `dict` a dictionary in the following format:
    # ```python
    # {
    #    'user': {'http_proxy': value, 'https_proxy': value, ...},
    #    'system': {'http_proxy': value, 'https_proxy': value, ...}
    # }
    # ```
    def list_sys_envs_proxy(self) -> dict:
        proxies = [item for sublist in [[p.lower(), p.upper()] for p in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy', 'no_proxy')] for item in sublist]
        return {'user': {k: v for k, v in self.locals if k in proxies},
                'system': {k: v for k, v in self.globals if k in proxies}}

    ## Gets the value of an environment variable.
    # @param envname `str` the variable to get
    # @param default `Any` the default value to return on failure
    # @returns `dict` a dictionary of 2 elements:
    # ```python
    # {'user': value or None, 'system': value or None}
    # ```
    def get_sys_env(self, envname, default=None) -> dict:
        return {'user': self.get_env(envname, False, ('user',), default),
                'system': self.get_env(envname, False, ('system',), default)}

    ## Sets or creates an environment variable.
    # @param envname `str` the variable to get
    # @param value `str` the value to set (will be converted as needed)
    # @param create `bool` whether the variable must be created if absent
    # @param valtype `str`|`int` the type of the value to create (see Sysenv::win_create_reg())
    # @param modes `iterable` an iterable of either or both of 'user' and 'system',
    # to indicate the domain(s) where the variable must be persisted
    # @param update_vars `bool` whether to repopulate the variables after this operation
    # @returns `bool` success = `True`, failure = `False`
    def set_sys_env(self, envname, value, create=True, valtype=None, modes=('user',), update_vars=True) -> bool:
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
                res = self.unix_write_env(envname, value)
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

    ## Deletes (unsets) an environment variable.
    # @param envname `str` the environment variable name, e.g. 'http_proxy'
    # @param modes `iterable` an iterable of either or both of 'user' and 'system',
    # to indicate the domain(s) where the variable must be deleted from
    # @param update_vars `bool` whether to repopulate the variables after this operation
    # @returns `bool` success = `True`, failure = `False`
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
            res = self.unix_del_env(envname)

        if res:
            for e_ in {envname, envname.lower(), envname.upper()}:
                if e_ in os.environ:
                    os.environ.pop(e_, None)

        if update_vars: self.update_vars()
        utils.log(f'Delete system env "{envname}"', 'debug')
        return res

    ## @brief Gets the current HTTP proxy setting from the system.
    # The config is retrieved from the registry on Windows systems
    # and from the environment on Unix systems.
    # @returns `dict` a dictionary of 2 elements:
    # ```python
    # {'user': value or None, 'system': value or None}
    # ``` 
    def get_sys_http_proxy(self) -> dict:
        env1 = self.get_sys_env('all_proxy')
        env2 = self.get_sys_env('http_proxy')
        env = {'user': env1['user'] or env2['user'], 'system': env1['system'] or env2['system']}

        if OS == 'Windows':
            if not self.get_sys_proxy_enabled():
                return {'user': None, 'system': None}
            res = self.win_get_reg_proxy('ProxyServer')            
            if res:
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

    ## @returns `True` if system proxy is enabled and `False` otherwise
    def get_sys_proxy_enabled(self) -> bool:
        if OS == 'Windows':
            res = self.win_get_reg_proxy('ProxyEnable')
            return bool(res)

        # Linux doesn't have separate 'proxy enable' switch, so try to get 'http_proxy' ENV...
        env = self.get_sys_http_proxy()
        return not (env['user'] is None and env['system'] is None)

    ## @returns `sysproxy::Noproxy` the current proxy bypass configuration or `None`
    # if not present.
    def get_sys_noproxy(self) -> Noproxy:
        if OS == 'Windows':
            res = self.win_get_reg_proxy('ProxyOverride')
            return None if res is None else Noproxy(None, res)
        res = self.get_sys_env('no_proxy')
        return None if res is None else Noproxy(None, res['user'] or res['system'] or '')

    ## Gets the value of a proxy setting as a `sysproxy::Proxyconf` object.
    # @param proxy `str` the proxy type (protocol) to get:
    # - `http_proxy`: the HTTP proxy
    # - `https_proxy`: the HTTPS proxy
    # - `ftp_proxy`: the FTP proxy
    # - `rsync_proxy`: the RSYNC proxy
    ## @returns `sysproxy::Proxyconf` the parsed proxy configuration or `None` if not present.
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

##  @brief A class to operate system proxy settings (cross-platform).
# 
# The class provides read/write properties for the common proxy types: 
# - `Proxy::http_proxy`
# - `Proxy::https_proxy`
# - `Proxy::ftp_proxy`
# - `Proxy::rsync_proxy`
#
# Each of these has the type sysproxy::Proxyconf, so their internal attributes like
# host, port etc. can be accesssed directly, e.g. to set a new port for the HTTP
# proxy: `proxyobj.http_proxy.port = 3000`
#
# It also exposes the property `Proxy::noproxy` to manipulate the proxy bypasses
# (most commonly, the localhost). Its `Proxy::enabled` property lets one enable or
# disable all the proxies in a single operation, simply by: `proxyobj.enabled = True # False`
#
# There are also a number of convenience methods to store and read the proxy settings
# in / from a JSON file, apply settings from a `dict` or serialize them as a `dict` or `str`.
#
# In its internal operations, the class replies on a sysproxy::Sysenv object to manipulate
# the corresponding environment variables and system files.
class Proxy:

    ## @param storage_file `str` default settings file that can be used to read and store
    # the proxy settings
    def __init__(self, storage_file='proxy_config.json'):
        ## `str` default settings file that can be used to read and store the proxy settings 
        self.storage_file = utils.make_abspath(storage_file) if not os.path.isabs(storage_file) else storage_file
        ## `sysproxy::Sysenv` object to operate proxy-related environment variables
        self.sysenv = Sysenv(True)
        ## `bool` update mode counter
        self._isupdating = 0
        self.read_system()
        self.save()

    ## @returns `dict` proxy settings serialized as a Python dictionary
    def asdict(self) -> dict:
        d = {'enabled': self.enabled, 'noproxy': str(self.noproxy)}
        for attr in ('http_proxy', 'https_proxy', 'ftp_proxy', 'rsync_proxy'):
            prop = getattr(self, attr, None)
            d[attr] = prop.asdict() if prop else None
        return d

    ## @returns `str` proxy settings serialized as a string (in JSON format)
    def asstr(self) -> str:
        return json.dumps(self.asdict())

    ## @brief Sets member properties reading from a Python dictionary.
    # The dictionary may have been produced by a previous call to Proxy::asdict().
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
        ## `sysproxy::Noproxy` proxy bypass configuration object
        self.noproxy = Noproxy(self._on_setattr, dconfig['noproxy']) if dconfig.get('noproxy', None) else None
        ## `bool` property to get and set the enabled status of the system proxy
        self.enabled = dconfig.get('enabled', self.enabled)
        self.end_updates()

    ## @brief Sets member properties reading from a JSON-formatted string.
    # The string may have been produced by a previous call to Proxy::asstr().
    def fromstr(self, strconfig: str):
        self.fromdict(json.loads(strconfig))

    ## Increments the update mode counter (Proxy::_isupdating) to show that a new
    # update operation is under way.
    def begin_updates(self):
        self._isupdating += 1

    ## Decrements the update mode counter (Proxy::_isupdating) and updates the 
    # underlying environment variables if the counter is zero.
    def end_updates(self):
        if self._isupdating == 0:
            return
        self._isupdating -= 1
        if self._isupdating == 0:
            self.sysenv.update_vars()

    ## @returns `sysproxy::Noproxy` the system no-proxy (proxy bypass) configuration
    def _get_sys_noproxy(self):
        noproxy = self.sysenv.get_sys_noproxy()
        if noproxy:
            noproxy.on_setattr = self._on_setattr
        return noproxy

    ## Gets the system settings for a specific proxy.
    # @param proxystr `str` the proxy type to get the config for (e.g. 'http_proxy')
    # @returns `sysproxy::Proxyconf` the system proxy configuration for the given proxy.
    # If no proxy setting exists, `None` is returned.
    # @see sysproxy::Sysenv::get_sys_proxy_parsed().
    def _get_sys_proxy(self, proxystr):
        proxy = self.sysenv.get_sys_proxy_parsed(proxystr)
        if proxy:
            proxy.on_setattr = self._on_setattr
        return proxy

    ## Initializes the member properties from the current system proxy settings.
    def read_system(self):
        ## `bool` current proxy enabled status
        self._enabled = self.sysenv.get_sys_proxy_enabled()
        ## `sysproxy::Noproxy` proxy bypass configuration object (or `None` if not set)
        self._noproxy = self._get_sys_noproxy()
        ## `sysproxy::Proxyconf` HTTP proxy object (or `None` if not set)
        self._http_proxy = self._get_sys_proxy('http_proxy')
        ## `sysproxy::Proxyconf` HTTPS proxy object (or `None` if not set)
        self._https_proxy = self._get_sys_proxy('https_proxy')
        ## `sysproxy::Proxyconf` FTP proxy object (or `None` if not set)
        self._ftp_proxy = self._get_sys_proxy('ftp_proxy')
        ## `sysproxy::Proxyconf` RSYNC proxy object (or `None` if not set)
        self._rsync_proxy = self._get_sys_proxy('rsync_proxy')
        utils.log(f'SYSTEM SETTINGS: {str(self)}', 'debug')

    ## Stores the current proxy settings in a JSON file.
    def store_config(self, config_file=None):
        if not config_file:
            config_file = self.storage_file
        else:
            config_file = utils.make_abspath(config_file) if not os.path.isabs(config_file) else config_file
        with open(config_file, 'w', encoding=utils.CODING) as f_:
            json.dump(self.asdict(), f_, indent=4)

    ## Reads proxy settings from a JSON file and applies them.
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

    ## Hook callback method to monitor setting proxy attributes and make corresponding
    # changes in the system (writing the env variables).
    def _on_setattr(self, obj, name, value):
        if isinstance(obj, Noproxy):
            if OS == 'Windows':
                self.sysenv.win_set_reg_proxy('ProxyOverride', obj.asstr(True))
            if obj:
                self.sysenv.set_sys_env('no_proxy', obj.asstr(False), update_vars=not self._isupdating)
            else:
                self.sysenv.unset_sys_env('no_proxy', update_vars=not self._isupdating)
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
                self.sysenv.win_set_reg_proxy('ProxyServer', f'{obj.host}:{obj.port}')
            self.sysenv.set_sys_env(proxy, str(obj), update_vars=not self._isupdating)

    ## Getter for Proxy::_enabled.
    @property
    def enabled(self):
        if getattr(self, '_enabled', None) is None:
            self._enabled = self.sysenv.get_sys_proxy_enabled()
        return self._enabled

    ## Setter for Proxy::_enabled: enables or disables the system proxy.
    @enabled.setter
    def enabled(self, is_enabled) -> bool:
        if is_enabled == self._enabled:
            return
        if not is_enabled:
            self.sysenv.unset_sys_env('http_proxy', update_vars=False)
            self.sysenv.unset_sys_env('all_proxy', update_vars=False)
        else:
            proxy = self.http_proxy or self.https_proxy or self.ftp_proxy
            if not proxy:
                return
            self.sysenv.set_sys_env('http_proxy', str(proxy), update_vars=False)
        if OS == 'Windows':
            self.sysenv.win_set_reg_proxy('ProxyEnable', int(is_enabled))

        if not self._isupdating:
            self.sysenv.update_vars()
        self._enabled = is_enabled

    ## Getter for Proxy::_noproxy.
    @property
    def noproxy(self) -> Noproxy:
        if getattr(self, '_noproxy', None) is None:
            self._noproxy = self._get_sys_noproxy()
        return self._noproxy

    ## Setter for Proxy::_noproxy: sets or unsets the proxy bypass addresses.
    @noproxy.setter
    def noproxy(self, value: Noproxy):
        if self._noproxy == value:
            return
        if OS == 'Windows':
            self.sysenv.win_set_reg_proxy('ProxyOverride', value.asstr(True) if value else '')
        if not value:
            self.sysenv.unset_sys_env('no_proxy', update_vars=not self._isupdating)
        elif value.noproxies:
            self.sysenv.set_sys_env('no_proxy', value.asstr(False), update_vars=not self._isupdating)
        self._noproxy = value

    ## Getter for Proxy::_http_proxy.
    @property
    def http_proxy(self) -> Proxyconf:
        if getattr(self, '_http_proxy', None) is None:
            self._http_proxy = self._get_sys_proxy('http_proxy')
        return self._http_proxy

    ## Setter for Proxy::_http_proxy.
    @http_proxy.setter
    def http_proxy(self, value: Proxyconf):
        if self._http_proxy == value:
            return
        if not value:
            self.sysenv.unset_sys_env('http_proxy', update_vars=False)
            self.sysenv.unset_sys_env('all_proxy', update_vars=False)
            if OS == 'Windows':
                self.sysenv.win_set_reg_proxy('ProxyServer', '')
                self.sysenv.win_set_reg_proxy('ProxyEnable', 0)
                self._enabled = False
        else:
            self.sysenv.set_sys_env('http_proxy', str(value), update_vars=False)
            if OS == 'Windows':
                self.sysenv.win_set_reg_proxy('ProxyServer', f'{value.host}:{value.port}')
        
        if not self._isupdating:
            self.sysenv.update_vars()
        self._http_proxy = value

    ## Getter for Proxy::_https_proxy.
    @property
    def https_proxy(self) -> Proxyconf:
        if getattr(self, '_https_proxy', None) is None:
            self._https_proxy = self._get_sys_proxy('https_proxy')
        return self._https_proxy

    ## Setter for Proxy::_https_proxy.
    @https_proxy.setter
    def https_proxy(self, value: Proxyconf):
        if self._https_proxy == value:
            return
        if not value:
            self.sysenv.unset_sys_env('https_proxy', update_vars=not self._isupdating)
        else:
            self.sysenv.set_sys_env('https_proxy', str(value), update_vars=not self._isupdating)
        self._https_proxy = value

    ## Getter for Proxy::_ftp_proxy.
    @property
    def ftp_proxy(self) -> Proxyconf:
        if getattr(self, '_ftp_proxy', None) is None:
            self._ftp_proxy = self._get_sys_proxy('ftp_proxy')
        return self._ftp_proxy

    ## Setter for Proxy::_ftp_proxy.
    @ftp_proxy.setter
    def ftp_proxy(self, value: Proxyconf):
        if self._ftp_proxy == value:
            return
        if not value:
            self.sysenv.unset_sys_env('ftp_proxy', update_vars=not self._isupdating)
        else:
            self.sysenv.set_sys_env('ftp_proxy', str(value), update_vars=not self._isupdating)
        self._ftp_proxy = value

    ## Getter for Proxy::_rsync_proxy.
    @property
    def rsync_proxy(self) -> Proxyconf:
        if getattr(self, '_rsync_proxy', None) is None:
            self._rsync_proxy = self._get_sys_proxy('rsync_proxy')
        return self._rsync_proxy

    ## Setter for Proxy::_rsync_proxy.
    @rsync_proxy.setter
    def rsync_proxy(self, value: Proxyconf):
        if self._rsync_proxy == value:
            return
        if not value:
            self.sysenv.unset_sys_env('rsync_proxy', update_vars=not self._isupdating)
        else:
            self.sysenv.set_sys_env('rsync_proxy', str(value), update_vars=not self._isupdating)
        self._rsync_proxy = value

    ## Returns a proxy object by its short name, e.g. 'http' -> `self.http_proxy`.
    # @param proxy `str` alias for the proxy, e.g. 'http', 'https', 'ftp' or 'rsync'
    # @returns `sysproxy::Proxyconf` the corresponding proxy object
    def proxy_by_name(self, proxy='http') -> Proxyconf:
        if proxy == 'http':
            return self.http_proxy
        if proxy == 'https':
            return self.https_proxy
        if proxy == 'ftp':
            return self.ftp_proxy
        if proxy == 'rsync':
            return self.rsync_proxy

    ## Applies the settings from one proxy object to all the others.
    # @param source `str` alias of the source proxy object, e.g. 'http'
    # @param targets `list of str` aliases of the target proxy objects;
    # if `None` or empty, all the *other* proxies are used.
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

    ## Saves the current proxy config to a dictonary as backup.
    # @see Proxy::restore()
    def save(self):
        ## `dict` backup proxy settings as a dictionary
        self.stored = self.asdict()

    ## Restores the proxy settings from the backup.
    # @see Proxy::save()
    def restore(self):
        if getattr(self, 'stored', None):
            self.fromdict(self.stored)
    
    ## Serializes the proxy settings as a string -- see Proxy::asstr().
    def __str__(self):
        return self.asstr()