# -*- coding: utf-8 -*-
# copyright 2018 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for module cubicweb.statsd_logger"""

import threading
import socket
import time
import re

from unittest import TestCase
from cubicweb import statsd_logger as statsd


UDP_PORT = None
RUNNING = True
SOCK = socket.socket(socket.AF_INET,
                     socket.SOCK_DGRAM)
SOCK.settimeout(0.1)
STATSD = None
DATA = []


def statsd_rcv():
    while RUNNING:
        try:
            data, addr = SOCK.recvfrom(1024)
            if data:
                rcv = [row.strip().decode() for row in data.splitlines()]
                DATA.extend(rcv)
        except socket.timeout:
            pass


def setUpModule(*args):
    global UDP_PORT, STATSD
    SOCK.bind(('127.0.0.1', 0))
    UDP_PORT = SOCK.getsockname()[1]
    STATSD = threading.Thread(target=statsd_rcv)
    STATSD.start()
    statsd.setup('test', ('127.0.0.1', UDP_PORT))


def tearDownModule(*args):
    global RUNNING
    RUNNING = False
    STATSD.join()
    statsd.teardown()


class StatsdTC(TestCase):

    def setUp(self):
        super(StatsdTC, self).setUp()
        DATA[:] = []

    def check_received(self, value):
        for i in range(10):
            if value in DATA:
                break
            time.sleep(0.01)
        else:
            self.assertIn(value, DATA)

    def check_received_ms(self, value):
        value = re.compile(value.replace('?', '\d'))
        for i in range(10):
            if [x for x in DATA if value.match(x)]:
                break
            time.sleep(0.01)
        else:
            self.assertTrue([x for x in DATA if value.match(x)], DATA)

    def test_statsd_c(self):
        statsd.statsd_c('context')
        self.check_received('test.context:1|c')
        statsd.statsd_c('context', 10)
        self.check_received('test.context:10|c')

    def test_statsd_g(self):
        statsd.statsd_g('context', 42)
        self.check_received('test.context:42|g')
        statsd.statsd_g('context', 'Igorrr')
        self.check_received('test.context:Igorrr|g')

    def test_statsd_t(self):
        statsd.statsd_t('context', 1)
        self.check_received('test.context:1.0000|ms')
        statsd.statsd_t('context', 10)
        self.check_received('test.context:10.0000|ms')
        statsd.statsd_t('context', 0.12344)
        self.check_received('test.context:0.1234|ms')
        statsd.statsd_t('context', 0.12345)
        self.check_received('test.context:0.1235|ms')

    def test_decorator(self):

        @statsd.statsd_timeit
        def measure_me_please():
            "some nice function"
            return 42

        self.assertEqual(measure_me_please.__doc__,
                         "some nice function")

        measure_me_please()
        self.check_received_ms('test.measure_me_please:0.0???|ms')
        self.check_received('test.measure_me_please:1|c')

    def test_context_manager(self):

        with statsd.statsd_timethis('cm'):
            time.sleep(0.1)

        self.check_received_ms('test.cm:100.????|ms')
        self.check_received('test.cm:1|c')


if __name__ == '__main__':
    from unittest import main
    main()
