"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.server.hook import Hook

CALLED_EVENTS = {}

class StartupHook(Hook):
    __regid__ = 'mystartup'
    events = ('server_startup',)
    def __call__(self):
        CALLED_EVENTS['server_startup'] = True

class ShutdownHook(Hook):
    __regid__ = 'myshutdown'
    events = ('server_shutdown',)
    def __call__(self):
        CALLED_EVENTS['server_shutdown'] = True


class LoginHook(Hook):
    __regid__ = 'mylogin'
    events = ('session_open',)
    def __call__(self):
        CALLED_EVENTS['session_open'] = self._cw.user.login

class LogoutHook(Hook):
    __regid__ = 'mylogout'
    events = ('session_close',)
    def __call__(self):
        CALLED_EVENTS['session_close'] = self._cw.user.login
