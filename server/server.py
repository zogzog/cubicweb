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
"""Pyro RQL server

"""
__docformat__ = "restructuredtext en"

import os
import sys
import select
import warnings
from time import localtime, mktime

from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.server.repository import Repository

class Finished(Exception):
    """raise to remove an event from the event loop"""

class TimeEvent:
    """base event"""
    # timefunc = staticmethod(localtime)
    timefunc = localtime

    def __init__(self, absolute=None, period=None):
        # local time tuple
        if absolute is None:
            absolute = self.timefunc()
        self.absolute = absolute
        # optional period in seconds
        self.period = period

    def is_ready(self):
        """return  true if the event is ready to be fired"""
        now = self.timefunc()
        if self.absolute < now:
            return True
        return False

    def fire(self, server):
        """fire the event
        must be overridden by concrete events
        """
        raise NotImplementedError()

    def update(self):
        """update the absolute date for the event or raise a finished exception
        """
        if self.period is None:
            raise Finished
        self.absolute = localtime(mktime(self.absolute) + self.period)


class QuitEvent(TimeEvent):
    """stop the server"""
    def fire(self, server):
        server.repo.shutdown()
        server.quiting = True


class RepositoryServer(object):

    def __init__(self, config, debug=False):
        """make the repository available as a PyRO object"""
        self.config = config
        self.repo = Repository(config, debug=debug)
        self.ns = None
        self.quiting = None
        # event queue
        self.events = []
        # start repository looping tasks

    def add_event(self, event):
        """add an event to the loop"""
        self.info('adding event %s', event)
        self.events.append(event)

    def trigger_events(self):
        """trigger ready events"""
        for event in self.events[:]:
            if event.is_ready():
                self.info('starting event %s', event)
                event.fire(self)
                try:
                    event.update()
                except Finished:
                    self.events.remove(event)

    def run(self, req_timeout=5.0):
        """enter the service loop"""
        self.repo.start_looping_tasks()
        while self.quiting is None:
            try:
                self.daemon.handleRequests(req_timeout)
            except select.error:
                continue
            self.trigger_events()

    def quit(self):
        """stop the server"""
        self.add_event(QuitEvent())

    def connect(self, host='', port=0):
        """the connect method on the repository only register to pyro if
        necessary
        """
        self.daemon = self.repo.pyro_register(host)

    # server utilitities ######################################################

    def install_sig_handlers(self):
        """install signal handlers"""
        import signal
        self.info('installing signal handlers')
        signal.signal(signal.SIGINT, lambda x, y, s=self: s.quit())
        signal.signal(signal.SIGTERM, lambda x, y, s=self: s.quit())

    def daemonize(self, pid_file=None):
        """daemonize the process"""
        # fork so the parent can exist
        if (os.fork()):
            return -1
        # deconnect from tty and create a new session
        os.setsid()
        # fork again so the parent, (the session group leader), can exit.
        # as a non-session group leader, we can never regain a controlling
        # terminal.
        if (os.fork()):
            return -1
        # move to the root to avoit mount pb
        os.chdir('/')
        # set paranoid umask
        os.umask(077)
        if pid_file is not None:
            # write pid in a file
            f = open(pid_file, 'w')
            f.write(str(os.getpid()))
            f.close()
        # filter warnings
        warnings.filterwarnings('ignore')
        # close standard descriptors
        sys.stdin.close()
        sys.stdout.close()
        sys.stderr.close()

from logging import getLogger
from cubicweb import set_log_methods
LOGGER = getLogger('cubicweb.reposerver')
set_log_methods(CubicWebConfiguration, LOGGER)
