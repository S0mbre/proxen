# -*- coding: utf-8 -*-
import os, platform, traceback
OS = platform.system()

if OS == 'Windows':
    import winreg

# --------------------------------------------------------------- #    

WIN_PROXY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'

# --------------------------------------------------------------- #

class Sysproxy:    

    def __init__(self, persist=True):
        self._persist = persist
        self._enabled = Sysproxy.get_sys_proxy_enabled()
        self._noproxy = Sysproxy.get_sys_noproxy() 

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
    def get_sys_http_proxy():
        if OS == 'Windows':
            res = Sysproxy.win_get_reg('ProxyServer')
            if res is None:
                res = Sysproxy.get_sys_env('http_proxy')
            return res
        return Sysproxy.get_sys_env('http_proxy')

    @staticmethod
    def get_sys_proxy_enabled():
        if OS == 'Windows':
            res = Sysproxy.win_get_reg('ProxyEnable')
            if res is None: return False
            return bool(res)        

        # Linux doesn't have separate 'proxy enable' switch, so try to get 'http_proxy' ENV...
        return (not Sysproxy.get_sys_http_proxy() is None)

    @staticmethod
    def get_sys_noproxy():
        if OS == 'Windows':
            res = Sysproxy.win_get_reg('ProxyOverride')
            if res is None: return []
            return [x.strip() if x.strip() != '<local>' else 'localhost' for x in res.split(';')]
        
        res = Sysproxy.get_sys_env('no_proxy')
        if res is None: return []
        return [x.strip() for x in res.split(',')]

    @staticmethod
    def get_sys_proxy_parsed(proxy='http_proxy'):
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
        return {'prot': prot, 'uname': uname, 'pass': passw, 'host': host, 'port': port}

    # =====================================

    @property
    def enabled(self):
        if getattr(self, '_enabled', None) is None:
            self._enabled = Sysproxy.get_sys_proxy_enabled()
        return self._enabled

    @enabled.setter
    def enabled(self, is_enabled):
        if is_enabled == self._enabled:
            return
        if OS == 'Windows':
            Sysproxy.win_set_reg('ProxyEnable', int(is_enabled))
        else:
            if is_enabled:
                Sysproxy.unset_sys_env('http_proxy')

    @property
    def noproxy(self):
        if getattr(self, '_noproxy', None) is None:
            self._noproxy = Sysproxy.get_sys_noproxy()
        return self._noproxy       
