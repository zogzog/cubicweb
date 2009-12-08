# -*- coding: utf-8 -*-
"""unit tests for module cubicweb.mail

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import os
import sys

from logilab.common.testlib import unittest_main
from logilab.common.umessage import message_from_string

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.mail import format_mail


def getlogin():
    """avoid usinng os.getlogin() because of strange tty / stdin problems
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
        self.assertLinesEquals(mail.as_string(), """\
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: base64
Subject: =?utf-8?q?b=C3=AFjour?=
From: =?utf-8?q?oim?= <oim@logilab.fr>
Reply-to: =?utf-8?q?oim?= <oim@logilab.fr>, =?utf-8?q?BimBam?= <bim@boum.fr>
X-CW: data
To: test@logilab.fr

dW4gcGV0aXQgY8O2dWNvdQ==
""")
        msg = message_from_string(mail.as_string())
        self.assertEquals(msg.get('subject'), u'bïjour')
        self.assertEquals(msg.get('from'), u'oim <oim@logilab.fr>')
        self.assertEquals(msg.get('to'), u'test@logilab.fr')
        self.assertEquals(msg.get('reply-to'), u'oim <oim@logilab.fr>, BimBam <bim@boum.fr>')
        self.assertEquals(msg.get_payload(decode=True), u'un petit cöucou')


    def test_format_mail_euro(self):
        mail = format_mail({'name': u'oîm', 'email': u'oim@logilab.fr'},
                           ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €')
        self.assertLinesEquals(mail.as_string(), """\
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: base64
Subject: =?utf-8?b?YsOvam91ciDigqw=?=
From: =?utf-8?q?o=C3=AEm?= <oim@logilab.fr>
Reply-to: =?utf-8?q?o=C3=AEm?= <oim@logilab.fr>
To: test@logilab.fr

dW4gcGV0aXQgY8O2dWNvdSDigqw=
""")
        msg = message_from_string(mail.as_string())
        self.assertEquals(msg.get('subject'), u'bïjour €')
        self.assertEquals(msg.get('from'), u'oîm <oim@logilab.fr>')
        self.assertEquals(msg.get('to'), u'test@logilab.fr')
        self.assertEquals(msg.get('reply-to'), u'oîm <oim@logilab.fr>')
        self.assertEquals(msg.get_payload(decode=True), u'un petit cöucou €')


    def test_format_mail_from_reply_to(self):
        # no sender-name, sender-addr in the configuration
        self.set_option('sender-name', '')
        self.set_option('sender-addr', '')
        msg = format_mail({'name': u'', 'email': u''},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        self.assertEquals(msg.get('from'), u'')
        self.assertEquals(msg.get('reply-to'), None)
        msg = format_mail({'name': u'tutu', 'email': u'tutu@logilab.fr'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEquals(msg.get('from'), u'tutu <tutu@logilab.fr>')
        self.assertEquals(msg.get('reply-to'), u'tutu <tutu@logilab.fr>')
        msg = format_mail({'name': u'tutu', 'email': u'tutu@logilab.fr'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €')
        msg = message_from_string(msg.as_string())
        self.assertEquals(msg.get('from'), u'tutu <tutu@logilab.fr>')
        self.assertEquals(msg.get('reply-to'), u'tutu <tutu@logilab.fr>')
        # set sender name and address as expected
        self.set_option('sender-name', 'cubicweb-test')
        self.set_option('sender-addr', 'cubicweb-test@logilab.fr')
        # anonymous notification: no name and no email specified
        msg = format_mail({'name': u'', 'email': u''},
                           ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                           config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEquals(msg.get('from'), u'cubicweb-test <cubicweb-test@logilab.fr>')
        self.assertEquals(msg.get('reply-to'), u'cubicweb-test <cubicweb-test@logilab.fr>')
        # anonymous notification: only email specified
        msg = format_mail({'email': u'tutu@logilab.fr'},
                           ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                           config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEquals(msg.get('from'), u'cubicweb-test <tutu@logilab.fr>')
        self.assertEquals(msg.get('reply-to'), u'cubicweb-test <tutu@logilab.fr>, cubicweb-test <cubicweb-test@logilab.fr>')
        # anonymous notification: only name specified
        msg = format_mail({'name': u'tutu'},
                          ['test@logilab.fr'], u'un petit cöucou €', u'bïjour €',
                          config=self.config)
        msg = message_from_string(msg.as_string())
        self.assertEquals(msg.get('from'), u'tutu <cubicweb-test@logilab.fr>')
        self.assertEquals(msg.get('reply-to'), u'tutu <cubicweb-test@logilab.fr>')



if __name__ == '__main__':
    unittest_main()

