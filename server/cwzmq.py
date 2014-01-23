# -*- coding: utf-8 -*-
# copyright 2012-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import cPickle
import traceback
from threading import Thread
from logging import getLogger

import zmq
from zmq.eventloop import ioloop
import zmq.eventloop.zmqstream

from cubicweb import set_log_methods
from cubicweb.server.server import QuitEvent, Finished

ctx = zmq.Context()

def cwproto_to_zmqaddr(address):
    """ converts a cw-zmq address (like zmqpickle-tcp://<ip>:<port>)
    into a proper zmq address (tcp://<ip>:<port>)
    """
    assert address.startswith('zmqpickle-'), 'bad protocol string %s' % address
    return address.split('-', 1)[1] # chop the `zmqpickle-` prefix

class ZMQComm(object):
    """
    A simple ZMQ-based notification bus.

    There should at most one instance of this class attached to a
    Repository. A typical usage may be something like::

        def callback(msg):
            self.info('received message: %s', ' '.join(msg))
        repo.app_instances_bus.subscribe('hello', callback)

    to subsribe to the 'hello' kind of message. On the other side, to
    emit a notification, call::

       repo.app_instances_bus.publish(['hello', 'world'])

    See http://docs.cubicweb.org for more details.
    """
    def __init__(self):
        self.ioloop = ioloop.IOLoop()
        self._topics = {}
        self._subscribers = []
        self.publisher = None

    def add_publisher(self, address):
        assert self.publisher is None, "more than one publisher is not supported"
        self.publisher = Publisher(self.ioloop, address)

    def add_subscription(self, topic, callback):
        for subscriber in self._subscribers:
            subscriber.subscribe(topic, callback)
        self._topics[topic] = callback

    def add_subscriber(self, address):
        subscriber = Subscriber(self.ioloop, address)
        for topic, callback in self._topics.iteritems():
            subscriber.subscribe(topic, callback)
        self._subscribers.append(subscriber)

    def publish(self, msg):
        if self.publisher is None:
            return
        self.publisher.send(msg)

    def start(self):
        Thread(target=self.ioloop.start).start()

    def stop(self):
        self.ioloop.add_callback(self.ioloop.stop)

    def __del__(self):
        self.ioloop.close()


class Publisher(object):
    def __init__(self, ioloop, address):
        self.address = address
        self._topics = {}
        self._subscribers = []
        self.ioloop = ioloop
        def callback():
            s = ctx.socket(zmq.PUB)
            self.stream = zmq.eventloop.zmqstream.ZMQStream(s, io_loop=ioloop)
            self.stream.bind(self.address)
            self.debug('start publisher on %s', self.address)
        ioloop.add_callback(callback)

    def send(self, msg):
        self.ioloop.add_callback(lambda:self.stream.send_multipart(msg))


class Subscriber(object):
    def __init__(self, ioloop, address):
        self.address = address
        self.dispatch_table = {}
        self.ioloop = ioloop
        def callback():
            s = ctx.socket(zmq.SUB)
            self.stream = zmq.eventloop.zmqstream.ZMQStream(s, io_loop=ioloop)
            self.stream.on_recv(self.dispatch)
            self.stream.connect(self.address)
            self.debug('start subscriber on %s', self.address)
        ioloop.add_callback(callback)

    def dispatch(self, msg):
        try:
            f = self.dispatch_table[msg[0]]
        except KeyError:
            return
        f(msg)

    def subscribe(self, topic, callback):
        self.dispatch_table[topic] = callback
        self.ioloop.add_callback(lambda: self.stream.setsockopt(zmq.SUBSCRIBE, topic))


class ZMQRepositoryServer(object):

    def __init__(self, repository):
        """make the repository available as a PyRO object"""
        self.address = None
        self.repo = repository
        self.socket = None
        self.stream = None
        self.loop = ioloop.IOLoop()

        # event queue
        self.events = []

    def connect(self, address):
        self.address = cwproto_to_zmqaddr(address)

    def run(self):
        """enter the service loop"""
        # start repository looping tasks
        self.socket = ctx.socket(zmq.REP)
        self.stream = zmq.eventloop.zmqstream.ZMQStream(self.socket, io_loop=self.loop)
        self.stream.bind(self.address)
        self.info('ZMQ server bound on: %s', self.address)

        self.stream.on_recv(self.process_cmds)

        try:
            self.loop.start()
        except zmq.ZMQError:
            self.warning('ZMQ event loop killed')
        self.quit()

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

    def process_cmd(self, cmd):
        """Delegate the given command to the repository.

        ``cmd`` is a list of (method_name, args, kwargs)
        where ``args`` is a list of positional arguments
        and ``kwargs`` is a dictionnary of named arguments.

        >>> rset = delegate_to_repo(["execute", [sessionid], {'rql': rql}])

        :note1: ``kwargs`` may be ommited

            >>> rset = delegate_to_repo(["execute", [sessionid, rql]])

        :note2: both ``args`` and ``kwargs`` may be omitted

            >>> schema = delegate_to_repo(["get_schema"])
            >>> schema = delegate_to_repo("get_schema") # also allowed

        """
        cmd = cPickle.loads(cmd)
        if not cmd:
            raise AttributeError('function name required')
        if isinstance(cmd, basestring):
            cmd = [cmd]
        if len(cmd) < 2:
            cmd.append(())
        if len(cmd) < 3:
            cmd.append({})
        cmd  = list(cmd) + [(), {}]
        funcname, args, kwargs = cmd[:3]
        result = getattr(self.repo, funcname)(*args, **kwargs)
        return result

    def process_cmds(self, cmds):
        """Callback intended to be used with ``on_recv``.

        Call ``delegate_to_repo`` on each command and send a pickled of
        each result recursively.

        Any exception are catched, pickled and sent.
        """
        try:
            for cmd in cmds:
                result = self.process_cmd(cmd)
                self.send_data(result)
        except Exception as exc:
            traceback.print_exc()
            self.send_data(exc)

    def send_data(self, data):
        self.socket.send_pyobj(data)

    def quit(self, shutdown_repo=False):
        """stop the server"""
        self.info('Quitting ZMQ server')
        try:
            self.loop.add_callback(self.loop.stop)
            self.stream.on_recv(None)
            self.stream.close()
        except Exception as e:
            print e
            pass
        if shutdown_repo and not self.repo.shutting_down:
            event = QuitEvent()
            event.fire(self)

    # server utilitities ######################################################

    def install_sig_handlers(self):
        """install signal handlers"""
        import signal
        self.info('installing signal handlers')
        signal.signal(signal.SIGINT, lambda x, y, s=self: s.quit(shutdown_repo=True))
        signal.signal(signal.SIGTERM, lambda x, y, s=self: s.quit(shutdown_repo=True))


    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    @classmethod
    def info(cls, msg, *a, **kw):
        pass


set_log_methods(Publisher, getLogger('cubicweb.zmq.pub'))
set_log_methods(Subscriber, getLogger('cubicweb.zmq.sub'))
set_log_methods(ZMQRepositoryServer, getLogger('cubicweb.zmq.repo'))
