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
"""Some utilities for the CubicWeb server.

"""
__docformat__ = "restructuredtext en"

import sys
import string
from threading import Timer, Thread
from getpass import getpass
from random import choice

from logilab.common.configuration import Configuration

from cubicweb.server import SOURCE_TYPES

try:
    from crypt import crypt
except ImportError:
    # crypt is not available (eg windows)
    from cubicweb.md5crypt import crypt


def getsalt(chars=string.letters + string.digits):
    """generate a random 2-character 'salt'"""
    return choice(chars) + choice(chars)


def crypt_password(passwd, salt=None):
    """return the encrypted password using the given salt or a generated one
    """
    if passwd is None:
        return None
    if salt is None:
        salt = getsalt()
    return crypt(passwd, salt)


def cartesian_product(seqin):
    """returns a generator which returns the cartesian product of `seqin`

    for more details, see :
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/302478
    """
    def rloop(seqin, comb):
        """recursive looping function"""
        if seqin:                   # any more sequences to process?
            for item in seqin[0]:
                newcomb = comb + [item]     # add next item to current combination
                # call rloop w/ remaining seqs, newcomb
                for item in rloop(seqin[1:], newcomb):
                    yield item          # seqs and newcomb
        else:                           # processing last sequence
            yield comb                  # comb finished, add to list
    return rloop(seqin, [])


def cleanup_solutions(rqlst, solutions):
    for sol in solutions:
        for vname in sol.keys():
            if not (vname in rqlst.defined_vars or vname in rqlst.aliases):
                del sol[vname]


def eschema_eid(session, eschema):
    """get eid of the CWEType entity for the given yams type. You should use
    this because when schema has been loaded from the file-system, not from the
    database, (e.g. during tests), eschema.eid is not set.
    """
    if eschema.eid is None:
        eschema.eid = session.execute(
            'Any X WHERE X is CWEType, X name %(name)s',
            {'name': str(eschema)})[0][0]
    return eschema.eid


DEFAULT_MSG = 'we need a manager connection on the repository \
(the server doesn\'t have to run, even should better not)'

def manager_userpasswd(user=None, msg=DEFAULT_MSG, confirm=False,
                       passwdmsg='password'):
    if not user:
        if msg:
            print msg
        while not user:
            user = raw_input('login: ')
        user = unicode(user, sys.stdin.encoding)
    passwd = getpass('%s: ' % passwdmsg)
    if confirm:
        while True:
            passwd2 = getpass('confirm password: ')
            if passwd == passwd2:
                break
            print 'password doesn\'t match'
            passwd = getpass('password: ')
    # XXX decode password using stdin encoding then encode it using appl'encoding
    return user, passwd


def ask_source_config(sourcetype, inputlevel=0):
    sconfig = Configuration(options=SOURCE_TYPES[sourcetype].options)
    sconfig.adapter = sourcetype
    sconfig.input_config(inputlevel=inputlevel)
    return sconfig


class LoopTask(object):
    """threaded task restarting itself once executed"""
    def __init__(self, interval, func, args):
        self.interval = interval
        def auto_restart_func(self=self, func=func, args=args):
            try:
                func(*args)
            finally:
                self.start()
        self.func = auto_restart_func
        self.name = func.__name__

    def __str__(self):
        return '%s (%s seconds)' % (self.name, self.interval)

    def start(self):
        self._t = Timer(self.interval, self.func)
        self._t.start()

    def cancel(self):
        self._t.cancel()

    def join(self):
        self._t.join()


class RepoThread(Thread):
    """subclass of thread so it auto remove itself from a given list once
    executed
    """
    def __init__(self, target, running_threads):
        def auto_remove_func(self=self, func=target):
            try:
                func()
            finally:
                self.running_threads.remove(self)
        Thread.__init__(self, target=auto_remove_func)
        self.running_threads = running_threads
        self._name = target.__name__

    def start(self):
        self.running_threads.append(self)
        self.daemon = True
        Thread.start(self)

    def getName(self):
        return '%s(%s)' % (self._name, Thread.getName(self))
