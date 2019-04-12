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

from functools import wraps
import logging
from threading import Thread
from getpass import getpass

from passlib.utils import handlers as uh, to_hash_str
from passlib.context import CryptContext

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

    def _calc_checksum(self, secret):
        return md5crypt(secret, self.salt.encode('ascii')).decode('utf-8')


_CRYPTO_CTX = CryptContext(['sha512_crypt', CustomMD5Crypt, 'des_crypt', 'ldap_salted_sha1'],
                           deprecated=['cubicwebmd5crypt', 'des_crypt'])

verify_and_update = _CRYPTO_CTX.verify_and_update


def crypt_password(passwd, salt=None):
    """return the encrypted password using the given salt or a generated one
    """
    if salt is None:
        return _CRYPTO_CTX.hash(passwd).encode('ascii')
    # empty hash, accept any password for backwards compat
    if salt == '':
        return salt
    try:
        if _CRYPTO_CTX.verify(passwd, salt):
            return salt
    except ValueError:  # e.g. couldn't identify hash
        pass
    # wrong password
    return b''


DEFAULT_MSG = 'we need a manager connection on the repository \
(the server doesn\'t have to run, even should better not)'


def manager_userpasswd(user=None, msg=DEFAULT_MSG, confirm=False,
                       passwdmsg='password'):
    if not user:
        if msg:
            print(msg)
        while not user:
            user = input('login: ')
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


def schedule_periodic_task(scheduler, interval, func, *args):
    """Enter a task with `func(*args)` as a periodic event in `scheduler`
    executing at `interval` seconds. Once executed, the task would re-schedule
    itself unless a BaseException got raised.
    """
    @wraps(func)
    def task(*args):
        restart = True
        try:
            func(*args)
        except Exception:
            logger = logging.getLogger('cubicweb.scheduler')
            logger.exception('Unhandled exception in periodic task "%s"',
                             func.__name__)
        except BaseException as exc:
            logger = logging.getLogger('cubicweb.scheduler')
            logger.error('periodic task "%s" not re-scheduled due to %r',
                         func.__name__, exc)
            restart = False
        finally:
            if restart:
                scheduler.enter(interval, 1, task, argument=args)

    return scheduler.enter(interval, 1, task, argument=args)


_MARKER = object()


def func_name(func):
    name = getattr(func, '__name__', _MARKER)
    if name is _MARKER:
        name = getattr(func, 'func_name', _MARKER)
    if name is _MARKER:
        name = repr(func)
    return name


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
