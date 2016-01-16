# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""

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
