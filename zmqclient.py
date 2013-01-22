# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Source to query another RQL repository using pyro"""

__docformat__ = "restructuredtext en"
_ = unicode

from functools import partial
import zmq

from cubicweb.server.cwzmq import cwproto_to_zmqaddr

# XXX hack to overpass old zmq limitation that force to have
# only one context per python process
try:
    from cubicweb.server.cwzmq import ctx
except ImportError:
    ctx = zmq.Context()

class ZMQRepositoryClient(object):
    """
    This class delegates the overall repository stuff to a remote source.

    So calling a method of this repository will result on calling the
    corresponding method of the remote source repository.

    Any raised exception on the remote source is propagated locally.

    ZMQ is used as the transport layer and cPickle is used to serialize data.
    """

    def __init__(self, zmq_address):
        """A zmq address provided here will be like
        `zmqpickle-tcp://127.0.0.1:42000`.  W

        We chop the prefix to get a real zmq address.
        """
        self.socket = ctx.socket(zmq.REQ)
        self.socket.connect(cwproto_to_zmqaddr(zmq_address))

    def __zmqcall__(self, name, *args, **kwargs):
         self.socket.send_pyobj([name, args, kwargs])
         result = self.socket.recv_pyobj()
         if isinstance(result, BaseException):
             raise result
         return result

    def __getattr__(self, name):
        return partial(self.__zmqcall__, name)
