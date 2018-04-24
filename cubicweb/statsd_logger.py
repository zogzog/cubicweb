# copyright 2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

"""Simple statsd_ logger for cubicweb.

This module is meant to be configured by setting a couple of global variables:

- ``bucket`` global variable will be used as statsd bucket in every
statsd_ UDP sent packet.

`- `address`` is a pair (IP, port) specifying the address of the
statsd_ server


There are 3 kinds of statds_ message::

- ``statsd_c(context, n)`` is a simple function to send statsd_
  counter-type of messages like::

    <bucket>.<context>:<n>|c\n

- ``statsd_g(context, value)`` to send statsd_ gauge-type of messages
  like::

    <bucket>.<context>:<n>|g\n

- ``statsd_t(context, ms)`` to send statsd_ time-type of messages
  like::

    <bucket>.<context>:<ms>|ms\n

There is also a decorator (``statsd_timeit``) that may be used to
measure and send to the statsd_ server the time passed in a function
or a method and the number of calls. It will send a message like::

    <bucket>.<funcname>:<ms>|ms\n<bucket>.<funcname>:1|c\n


.. _statsd: https://github.com/etsy/statsd

"""


import time
import socket
from contextlib import contextmanager

_bucket = 'cubicweb'
_address = None
_socket = None


def setup(bucket, address):
    """Configure the statsd endpoint

    :param bucket: the name of the statsd bucket that will be used to
                   build messages.

    :param address: the UDP endpoint of the statsd server. Must a
                    couple (ip, port).
    """
    global _bucket, _address, _socket
    packed = None
    for family in (socket.AF_INET6, socket.AF_INET):
        try:
            packed = socket.inet_pton(family, address[0])
            break
        except socket.error:
            continue
    if packed is None:
        return
    _bucket, _address = bucket, address
    _socket = socket.socket(family, socket.SOCK_DGRAM)


def teardown():
    """Unconfigure the statsd endpoint

    This is most likely only useful for unit tests"""
    global _bucket, _address, _socket
    _bucket = 'cubicweb'
    _address = None
    _socket = None


def statsd_c(context, n=1):
    if _address is not None:
        _socket.sendto('{0}.{1}:{2}|c\n'.format(_bucket, context, n).encode(),
                       _address)


def statsd_g(context, value):
    if _address is not None:
        _socket.sendto('{0}.{1}:{2}|g\n'.format(_bucket, context, value).encode(),
                       _address)


def statsd_t(context, value):
    if _address is not None:
        _socket.sendto('{0}.{1}:{2:.4f}|ms\n'.format(_bucket, context, value).encode(),
                       _address)


class statsd_timeit(object):
    __slots__ = ('callable',)

    def __init__(self, callableobj):
        self.callable = callableobj

    @property
    def __doc__(self):
        return self.callable.__doc__

    @property
    def __name__(self):
        return self.callable.__name__

    def __call__(self, *args, **kw):
        if _address is None:
            return self.callable(*args, **kw)
        t0 = time.time()
        try:
            return self.callable(*args, **kw)
        finally:
            dt = 1000 * (time.time() - t0)
            msg = '{0}.{1}:{2:.4f}|ms\n{0}.{1}:1|c\n'.format(
                _bucket, self.__name__, dt).encode()
            _socket.sendto(msg, _address)

    def __get__(self, obj, objtype):
        """Support instance methods."""
        if obj is None:  # class method or some already wrapped method
            return self
        import functools
        return functools.partial(self.__call__, obj)


@contextmanager
def statsd_timethis(ctxmsg):
    if _address is not None:
        t0 = time.time()
    try:
        yield
    finally:
        if _address is not None:
            dt = 1000 * (time.time() - t0)
            msg = '{0}.{1}:{2:.4f}|ms\n{0}.{1}:1|c\n'.format(
                _bucket, ctxmsg, dt).encode()
            _socket.sendto(msg, _address)
