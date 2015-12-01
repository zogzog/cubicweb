# -*- coding: utf-8 -*-
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
"""unit tests for module cubicweb.mail"""

import os
import re
from socket import gethostname
import sys
from unittest import TestCase

from logilab.common.umessage import message_from_string

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.mail import format_mail, construct_message_id, parse_message_id


def getlogin():
    """avoid using os.getlogin() because of strange tty / stdin problems
    (man 3 getlogin)
    Another solution would be to use $LOGNAME, $USER or $USERNAME
    """
    if sys.platform != 'win32':
        import pwd
        return pwd.getpwuid(os.getuid())[0]
    else:
        return os.environ.get('USERNAME')


class EmailTC(CubicWebTC):

    def test_format_mail(self):
        self.set_option('sender-addr', 'bim@boum.fr')
        self.set_option('sender-name', 'BimBam')

        mail = format_mail({'name': 'oim', 'email': 'oim@logilab.fr'},
                           ['test@logilab.fr'], u'un petit cöucou', u'bïjour',
                           config=self.config)
        result = mail.as_string()
        result = re.sub('^Date: .*$', 'Date: now', result, flags=re.MULTILINE)
        self.assertMultiLineEqual(result, """\
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: base64
Subject: =?utf-8?q?b=C3=AFjour?=
From: =?utf-8?q?oim?= <oim@logilab.fr>
Reply-to: =?utf-8?q?oim?= <oim@logilab.fr>, =?utf-8?q?BimBam?= <bim@boum.fr>
X-CW: data
To: test@logilab.fr
Date: now

dW4gcGV0aXQgY8O2dWNvdQ==
""")
        msg = message_from_string(mail.as_string())
        self.assertEqual(msg.get('subject'), u'bïjour')
        self.assertEqual(msg.get('from'), u'oim <oim@logilab.fr>')
        self.assertEqual(msg.get('to'), u'test@logilab.fr')
        self.assertEqual(msg.get('reply-to'), u'oim <oim@logilab.fr>, BimBam <bim@boum.fr>')
        self.assertEqual(msg.get_payload(decode=True), u'un petit cöucou')

    def test_format_mail_euro(self):
        mail = format_mail({'name': u'oîm', 'email': u'oim@logilab.fr'},
                           ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €')
        result = mail.as_string()
        result = re.sub('^Date: .*$', 'Date: now', result, flags=re.MULTILINE)
        self.assertMultiLineEqual(result, """\
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: base64
Subject: =?utf-8?b?YsOvam91ciDigqw=?=
From: =?utf-8?q?o=C3=AEm?= <oim@logilab.fr>
Reply-to: =?utf-8?q?o=C3=AEm?= <oim@logilab.fr>
To: test@logilab.fr
Date: now

dW4gcGV0aXQgY8O2dWNvdSDigqw=
""")
        msg = message_from_string(mail.as_string())
        self.assertEqual(msg.get('subject'), u'bïjour €')
        self.assertEqual(msg.get('from'), u'oîm <oim@logilab.fr>')
        self.assertEqual(msg.get('to'), u'test@logilab.fr')
        self.assertEqual(msg.get('reply-to'), u'oîm <oim@logilab.fr>')
        self.assertEqual(msg.get_payload(decode=True), u'un petit cöucou €')

    def test_format_mail_from_reply_to(self):
        # no sender-name, sender-addr in the configuration
        self.set_option('sender-name', '')
        self.set_option('sender-addr', '')
        msg = format_mail({'name': u'', 'email': u''},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        self.assertEqual(msg.get('from'), u'')
        self.assertEqual(msg.get('reply-to'), None)
        msg = format_mail({'name': u'tutu', 'email': u'tutu@logilab.fr'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEqual(msg.get('from'), u'tutu <tutu@logilab.fr>')
        self.assertEqual(msg.get('reply-to'), u'tutu <tutu@logilab.fr>')
        msg = format_mail({'name': u'tutu', 'email': u'tutu@logilab.fr'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €')
        msg = message_from_string(msg.as_string())
        self.assertEqual(msg.get('from'), u'tutu <tutu@logilab.fr>')
        self.assertEqual(msg.get('reply-to'), u'tutu <tutu@logilab.fr>')
        # set sender name and address as expected
        self.set_option('sender-name', 'cubicweb-test')
        self.set_option('sender-addr', 'cubicweb-test@logilab.fr')
        # anonymous notification: no name and no email specified
        msg = format_mail({'name': u'', 'email': u''},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEqual(msg.get('from'), u'cubicweb-test <cubicweb-test@logilab.fr>')
        self.assertEqual(msg.get('reply-to'), u'cubicweb-test <cubicweb-test@logilab.fr>')
        # anonymous notification: only email specified
        msg = format_mail({'email': u'tutu@logilab.fr'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEqual(msg.get('from'), u'cubicweb-test <tutu@logilab.fr>')
        self.assertEqual(
            msg.get('reply-to'),
            u'cubicweb-test <tutu@logilab.fr>, cubicweb-test <cubicweb-test@logilab.fr>')
        # anonymous notification: only name specified
        msg = format_mail({'name': u'tutu'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEqual(msg.get('from'), u'tutu <cubicweb-test@logilab.fr>')
        self.assertEqual(msg.get('reply-to'), u'tutu <cubicweb-test@logilab.fr>')


class MessageIdTC(TestCase):

    def test_base(self):
        msgid1 = construct_message_id('testapp', 21)
        msgid2 = construct_message_id('testapp', 21)
        self.assertNotEqual(msgid1, msgid2)
        self.assertNotIn('&', msgid1)
        self.assertNotIn('=', msgid1)
        self.assertNotIn('/', msgid1)
        self.assertNotIn('+', msgid1)
        values = parse_message_id(msgid1, 'testapp')
        self.assertTrue(values)
        # parse_message_id should work with or without surrounding <>
        self.assertEqual(values, parse_message_id(msgid1[1:-1], 'testapp'))
        self.assertEqual(values['eid'], '21')
        self.assertIn('timestamp', values)
        self.assertEqual(parse_message_id(msgid1[1:-1], 'anotherapp'), None)

    def test_notimestamp(self):
        msgid1 = construct_message_id('testapp', 21, False)
        construct_message_id('testapp', 21, False)
        values = parse_message_id(msgid1, 'testapp')
        self.assertEqual(values, {'eid': '21'})

    def test_parse_message_doesnt_raise(self):
        self.assertEqual(parse_message_id('oijioj@bla.bla', 'tesapp'), None)
        self.assertEqual(parse_message_id('oijioj@bla', 'tesapp'), None)
        self.assertEqual(parse_message_id('oijioj', 'tesapp'), None)

    def test_nonregr_empty_message_id(self):
        for eid in (1, 12, 123, 1234):
            msgid1 = construct_message_id('testapp', eid, 12)
            self.assertNotEqual(msgid1, '<@testapp.%s>' % gethostname())


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
