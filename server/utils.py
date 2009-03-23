"""Some utilities for the CubicWeb server.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
import string
from threading import Timer, Thread
from getpass import getpass
from random import choice

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


DEFAULT_MSG = 'we need a manager connection on the repository \
(the server doesn\'t have to run, even should better not)'

def manager_userpasswd(user=None, passwd=None, msg=DEFAULT_MSG, confirm=False):
    if not user:
        print msg
        while not user:
            user = raw_input('login: ')
        passwd = getpass('password: ')
        if confirm:
            while True:
                passwd2 = getpass('confirm password: ')
                if passwd == passwd2:
                    break
                print 'password doesn\'t match'
                passwd = getpass('password: ')
        user = unicode(user, sys.stdin.encoding)
    elif not passwd:
        assert not confirm
        passwd = getpass('password for %s: ' % user)
    # XXX decode password using stdin encoding then encode it using appl'encoding
    return user, passwd


class LoopTask(object):
    """threaded task restarting itself once executed"""
    def __init__(self, interval, func):
        self.interval = interval
        def auto_restart_func(self=self, func=func):
            try:
                func()
            finally:
                self.start()
        self.func = auto_restart_func
        self.name = func.__name__
        
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
        Thread.__init__(self, target=target)
        self.running_threads = running_threads
        self._name = target.__name__
        
    def start(self):
        self.running_threads.append(self)
        Thread.start(self)

    @property
    def name(self):
        return '%s(%s)' % (self._name, Thread.getName(self))
