# -*- coding: utf-8 -*-
# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.server import hook

class ZMQStopHook(hook.Hook):
    __regid__ = 'zmqstop'
    events = ('server_shutdown',)

    def __call__(self):
        self.repo.app_instances_bus.stop()

class ZMQStartHook(hook.Hook):
    __regid__ = 'zmqstart'
    events = ('server_startup',)
    order = -1

    def __call__(self):
        config = self.repo.config
        address_pub = config.get('zmq-address-pub')
        address_sub = config.get('zmq-address-sub')
        if not address_pub and not address_sub:
            return
        from cubicweb.server import cwzmq
        self.repo.app_instances_bus = cwzmq.ZMQComm()
        if address_pub:
            self.repo.app_instances_bus.add_publisher(address_pub)
        def clear_cache_callback(msg):
            self.debug('clear_caches: %s', ' '.join(msg))
            self.repo.clear_caches(msg[1:])
        self.repo.app_instances_bus.add_subscription('delete', clear_cache_callback)
        for address in address_sub:
            self.repo.app_instances_bus.add_subscriber(address)
        self.repo.app_instances_bus.start()
