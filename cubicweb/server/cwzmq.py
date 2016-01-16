# -*- coding: utf-8 -*-
# copyright 2012-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from threading import Thread
from logging import getLogger

import zmq
from zmq.eventloop import ioloop
import zmq.eventloop.zmqstream

from cubicweb import set_log_methods


ctx = zmq.Context()


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
        for topic, callback in self._topics.items():
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


set_log_methods(Publisher, getLogger('cubicweb.zmq.pub'))
set_log_methods(Subscriber, getLogger('cubicweb.zmq.sub'))
