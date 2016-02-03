# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Some utilities for the CubicWeb server."""
from __future__ import print_function

__docformat__ = "restructuredtext en"

import sys
import logging
from threading import Timer, Thread
from getpass import getpass

from six import PY2, text_type
from six.moves import input

from passlib.utils import handlers as uh, to_hash_str
from passlib.context import CryptContext

from logilab.common.deprecation import deprecated

from cubicweb.md5crypt import crypt as md5crypt


class CustomMD5Crypt(uh.HasSalt, uh.GenericHandler):
    name = 'cubicwebmd5crypt'
    setting_kwds = ('salt',)
    min_salt_size = 0
    max_salt_size = 8
    salt_chars = uh.H64_CHARS

    @classmethod
    def from_string(cls, hash):
        salt, chk = uh.parse_mc2(hash, u'')
        if chk is None:
            raise ValueError('missing checksum')
        return cls(salt=salt, checksum=chk)

    def to_string(self):
        return to_hash_str(u'%s$%s' % (self.salt, self.checksum or u''))

    # passlib 1.5 wants calc_checksum, 1.6 wants _calc_checksum
    def calc_checksum(self, secret):
        return md5crypt(secret, self.salt.encode('ascii')).decode('utf-8')
    _calc_checksum = calc_checksum

_CRYPTO_CTX = CryptContext(['sha512_crypt', CustomMD5Crypt, 'des_crypt', 'ldap_salted_sha1'],
                           deprecated=['cubicwebmd5crypt', 'des_crypt'])
verify_and_update = _CRYPTO_CTX.verify_and_update

def crypt_password(passwd, salt=None):
    """return the encrypted password using the given salt or a generated one
    """
    if salt is None:
        return _CRYPTO_CTX.encrypt(passwd).encode('ascii')
    # empty hash, accept any password for backwards compat
    if salt == '':
        return salt
    try:
        if _CRYPTO_CTX.verify(passwd, salt):
            return salt
    except ValueError: # e.g. couldn't identify hash
        pass
    # wrong password
    return b''

@deprecated('[3.22] no more necessary, directly get eschema.eid')
def eschema_eid(cnx, eschema):
    """get eid of the CWEType entity for the given yams type.

    This used to be necessary because when the schema has been loaded from the
    file-system, not from the database, (e.g. during tests), eschema.eid was
    not set.
    """
    return eschema.eid


DEFAULT_MSG = 'we need a manager connection on the repository \
(the server doesn\'t have to run, even should better not)'

def manager_userpasswd(user=None, msg=DEFAULT_MSG, confirm=False,
                       passwdmsg='password'):
    if not user:
        if msg:
            print(msg)
        while not user:
            user = input('login: ')
        if PY2:
            user = unicode(user, sys.stdin.encoding)
    passwd = getpass('%s: ' % passwdmsg)
    if confirm:
        while True:
            passwd2 = getpass('confirm password: ')
            if passwd == passwd2:
                break
            print('password doesn\'t match')
            passwd = getpass('password: ')
    # XXX decode password using stdin encoding then encode it using appl'encoding
    return user, passwd


_MARKER = object()
def func_name(func):
    name = getattr(func, '__name__', _MARKER)
    if name is _MARKER:
        name = getattr(func, 'func_name', _MARKER)
    if name is _MARKER:
        name = repr(func)
    return name

class LoopTask(object):
    """threaded task restarting itself once executed"""
    def __init__(self, tasks_manager, interval, func, args):
        if interval < 0:
            raise ValueError('Loop task interval must be >= 0 '
                             '(current value: %f for %s)' % \
                             (interval, func_name(func)))
        self._tasks_manager = tasks_manager
        self.interval = interval
        def auto_restart_func(self=self, func=func, args=args):
            restart = True
            try:
                func(*args)
            except Exception:
                logger = logging.getLogger('cubicweb.repository')
                logger.exception('Unhandled exception in LoopTask %s', self.name)
                raise
            except BaseException:
                restart = False
            finally:
                if restart and tasks_manager.running:
                    self.start()
        self.func = auto_restart_func
        self.name = func_name(func)

    def __str__(self):
        return '%s (%s seconds)' % (self.name, self.interval)

    def start(self):
        self._t = Timer(self.interval, self.func)
        self._t.setName('%s-%s[%d]' % (self._t.getName(), self.name, self.interval))
        self._t.start()

    def cancel(self):
        self._t.cancel()

    def join(self):
        if self._t.isAlive():
            self._t.join()


class RepoThread(Thread):
    """subclass of thread so it auto remove itself from a given list once
    executed
    """
    def __init__(self, target, running_threads):
        def auto_remove_func(self=self, func=target):
            try:
                func()
            except Exception:
                logger = logging.getLogger('cubicweb.repository')
                logger.exception('Unhandled exception in RepoThread %s', self._name)
                raise
            finally:
                self.running_threads.remove(self)
        Thread.__init__(self, target=auto_remove_func)
        self.running_threads = running_threads
        self._name = func_name(target)

    def start(self):
        self.running_threads.append(self)
        self.daemon = True
        Thread.start(self)

    def getName(self):
        return '%s(%s)' % (self._name, Thread.getName(self))

class TasksManager(object):
    """Object dedicated manage background task"""

    def __init__(self):
        self.running = False
        self._tasks = []
        self._looping_tasks = []

    def add_looping_task(self, interval, func, *args):
        """register a function to be called every `interval` seconds.

        If interval is negative, no looping task is registered.
        """
        if interval < 0:
            self.debug('looping task %s ignored due to interval %f < 0',
                       func_name(func), interval)
            return
        task = LoopTask(self, interval, func, args)
        if self.running:
            self._start_task(task)
        else:
            self._tasks.append(task)

    def _start_task(self, task):
        self._looping_tasks.append(task)
        self.info('starting task %s with interval %.2fs', task.name,
                  task.interval)
        task.start()

    def start(self):
        """Start running looping task"""
        assert self.running == False # bw compat purpose maintly
        while self._tasks:
            task = self._tasks.pop()
            self._start_task(task)
        self.running = True

    def stop(self):
        """Stop all running task.

        returns when all task have been cancel and none are running anymore"""
        if self.running:
            while self._looping_tasks:
                looptask = self._looping_tasks.pop()
                self.info('canceling task %s...', looptask.name)
                looptask.cancel()
                looptask.join()
                self.info('task %s finished', looptask.name)

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(TasksManager, getLogger('cubicweb.repository'))
