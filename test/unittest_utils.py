# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for module cubicweb.utils"""

import re
import decimal
import datetime


from logilab.common.testlib import TestCase, DocTest, unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.utils import (make_uid, UStringIO, SizeConstrainedList,
                            RepeatList, HTMLHead, QueryCache, parse_repo_uri)
from cubicweb.entity import Entity

try:
    from cubicweb.utils import CubicWebJsonEncoder, json
except ImportError:
    json = None

class MakeUidTC(TestCase):
    def test_1(self):
        self.assertNotEqual(make_uid('xyz'), make_uid('abcd'))
        self.assertNotEqual(make_uid('xyz'), make_uid('xyz'))

    def test_2(self):
        d = set()
        while len(d)<10000:
            uid = make_uid('xyz')
            if uid in d:
                self.fail(len(d))
            if re.match('\d', uid):
                self.fail('make_uid must not return something begining with '
                          'some numeric character, got %s' % uid)
            d.add(uid)


class TestParseRepoUri(TestCase):

    def test_parse_repo_uri(self):
        self.assertEqual(('inmemory', None, 'myapp'),
                         parse_repo_uri('myapp'))
        self.assertEqual(('inmemory', None, 'myapp'),
                         parse_repo_uri('inmemory://myapp'))
        self.assertEqual(('pyro', 'pyro-ns-host:pyro-ns-port', '/myapp'),
                         parse_repo_uri('pyro://pyro-ns-host:pyro-ns-port/myapp'))
        self.assertEqual(('pyroloc', 'host:port', '/appkey'),
                         parse_repo_uri('pyroloc://host:port/appkey'))
        self.assertEqual(('zmqpickle-tcp', '127.0.0.1:666', ''),
                         parse_repo_uri('zmqpickle-tcp://127.0.0.1:666'))
        with self.assertRaises(NotImplementedError):
            parse_repo_uri('foo://bar')



class TestQueryCache(TestCase):
    def test_querycache(self):
        c = QueryCache(ceiling=20)
        # write only
        for x in xrange(10):
            c[x] = x
        self.assertEqual(c._usage_report(),
                         {'transientcount': 0,
                          'itemcount': 10,
                          'permanentcount': 0})
        c = QueryCache(ceiling=10)
        # we should also get a warning
        for x in xrange(20):
            c[x] = x
        self.assertEqual(c._usage_report(),
                         {'transientcount': 0,
                          'itemcount': 10,
                          'permanentcount': 0})
        # write + reads
        c = QueryCache(ceiling=20)
        for n in xrange(4):
            for x in xrange(10):
                c[x] = x
                c[x]
        self.assertEqual(c._usage_report(),
                         {'transientcount': 10,
                          'itemcount': 10,
                          'permanentcount': 0})
        c = QueryCache(ceiling=20)
        for n in xrange(17):
            for x in xrange(10):
                c[x] = x
                c[x]
        self.assertEqual(c._usage_report(),
                         {'transientcount': 0,
                          'itemcount': 10,
                          'permanentcount': 10})
        c = QueryCache(ceiling=20)
        for n in xrange(17):
            for x in xrange(10):
                c[x] = x
                if n % 2:
                    c[x]
                if x % 2:
                    c[x]
        self.assertEqual(c._usage_report(),
                         {'transientcount': 5,
                          'itemcount': 10,
                          'permanentcount': 5})

class UStringIOTC(TestCase):
    def test_boolean_value(self):
        self.assert_(UStringIO())


class RepeatListTC(TestCase):

    def test_base(self):
        l = RepeatList(3, (1, 3))
        self.assertEqual(l[0], (1, 3))
        self.assertEqual(l[2], (1, 3))
        self.assertEqual(l[-1], (1, 3))
        self.assertEqual(len(l), 3)
        # XXX
        self.assertEqual(l[4], (1, 3))

        self.assertFalse(RepeatList(0, None))

    def test_slice(self):
        l = RepeatList(3, (1, 3))
        self.assertEqual(l[0:1], [(1, 3)])
        self.assertEqual(l[0:4], [(1, 3)]*3)
        self.assertEqual(l[:], [(1, 3)]*3)

    def test_iter(self):
        self.assertEqual(list(RepeatList(3, (1, 3))),
                          [(1, 3)]*3)

    def test_add(self):
        l = RepeatList(3, (1, 3))
        self.assertEqual(l + [(1, 4)], [(1, 3)]*3  + [(1, 4)])
        self.assertEqual([(1, 4)] + l, [(1, 4)] + [(1, 3)]*3)
        self.assertEqual(l + RepeatList(2, (2, 3)), [(1, 3)]*3 + [(2, 3)]*2)

        x = l + RepeatList(2, (1, 3))
        self.assertIsInstance(x, RepeatList)
        self.assertEqual(len(x), 5)
        self.assertEqual(x[0], (1, 3))

        x = l + [(1, 3)] * 2
        self.assertEqual(x, [(1, 3)] * 5)

    def test_eq(self):
        self.assertEqual(RepeatList(3, (1, 3)),
                          [(1, 3)]*3)

    def test_pop(self):
        l = RepeatList(3, (1, 3))
        l.pop(2)
        self.assertEqual(l, [(1, 3)]*2)


class SizeConstrainedListTC(TestCase):

    def test_append(self):
        l = SizeConstrainedList(10)
        for i in xrange(12):
            l.append(i)
        self.assertEqual(l, range(2, 12))

    def test_extend(self):
        testdata = [(range(5), range(5)),
                    (range(10), range(10)),
                    (range(12), range(2, 12)),
                    ]
        for extension, expected in testdata:
            l = SizeConstrainedList(10)
            l.extend(extension)
            yield self.assertEqual, l, expected


class JSONEncoderTC(TestCase):
    def setUp(self):
        if json is None:
            self.skipTest('json not available')

    def encode(self, value):
        return json.dumps(value, cls=CubicWebJsonEncoder)

    def test_encoding_dates(self):
        self.assertEqual(self.encode(datetime.datetime(2009, 9, 9, 20, 30)),
                          '"2009/09/09 20:30:00"')
        self.assertEqual(self.encode(datetime.date(2009, 9, 9)),
                          '"2009/09/09"')
        self.assertEqual(self.encode(datetime.time(20, 30)),
                          '"20:30:00"')

    def test_encoding_decimal(self):
        self.assertEqual(self.encode(decimal.Decimal('1.2')), '1.2')

    def test_encoding_bare_entity(self):
        e = Entity(None)
        e.cw_attr_cache['pouet'] = 'hop'
        e.eid = 2
        self.assertEqual(json.loads(self.encode(e)),
                          {'pouet': 'hop', 'eid': 2})

    def test_encoding_entity_in_list(self):
        e = Entity(None)
        e.cw_attr_cache['pouet'] = 'hop'
        e.eid = 2
        self.assertEqual(json.loads(self.encode([e])),
                          [{'pouet': 'hop', 'eid': 2}])

    def test_encoding_unknown_stuff(self):
        self.assertEqual(self.encode(TestCase), 'null')

class HTMLHeadTC(CubicWebTC):

    def htmlhead(self, datadir_url):
        req = self.request()
        base_url = u'http://test.fr/data/'
        req.datadir_url = base_url
        head = HTMLHead(req)
        return head

    def test_concat_urls(self):
        base_url = u'http://test.fr/data/'
        head = self.htmlhead(base_url)
        urls = [base_url + u'bob1.js',
                base_url + u'bob2.js',
                base_url + u'bob3.js']
        result = head.concat_urls(urls)
        expected = u'http://test.fr/data/??bob1.js,bob2.js,bob3.js'
        self.assertEqual(result, expected)

    def test_group_urls(self):
        base_url = u'http://test.fr/data/'
        head = self.htmlhead(base_url)
        urls_spec = [(base_url + u'bob0.js', None),
                     (base_url + u'bob1.js', None),
                     (u'http://ext.com/bob2.js', None),
                     (u'http://ext.com/bob3.js', None),
                     (base_url + u'bob4.css', 'all'),
                     (base_url + u'bob5.css', 'all'),
                     (base_url + u'bob6.css', 'print'),
                     (base_url + u'bob7.css', 'print'),
                     (base_url + u'bob8.css', ('all', u'[if IE 8]')),
                     (base_url + u'bob9.css', ('print', u'[if IE 8]'))
                     ]
        result = head.group_urls(urls_spec)
        expected = [(base_url + u'??bob0.js,bob1.js', None),
                    (u'http://ext.com/bob2.js', None),
                    (u'http://ext.com/bob3.js', None),
                    (base_url + u'??bob4.css,bob5.css', 'all'),
                    (base_url + u'??bob6.css,bob7.css', 'print'),
                    (base_url + u'bob8.css', ('all', u'[if IE 8]')),
                    (base_url + u'bob9.css', ('print', u'[if IE 8]'))
                    ]
        self.assertEqual(list(result), expected)

    def test_getvalue_with_concat(self):
        self.config.global_set_option('concat-resources', True)
        base_url = u'http://test.fr/data/'
        head = self.htmlhead(base_url)
        head.add_js(base_url + u'bob0.js')
        head.add_js(base_url + u'bob1.js')
        head.add_js(u'http://ext.com/bob2.js')
        head.add_js(u'http://ext.com/bob3.js')
        head.add_css(base_url + u'bob4.css')
        head.add_css(base_url + u'bob5.css')
        head.add_css(base_url + u'bob6.css', 'print')
        head.add_css(base_url + u'bob7.css', 'print')
        head.add_ie_css(base_url + u'bob8.css')
        head.add_ie_css(base_url + u'bob9.css', 'print', u'[if lt IE 7]')
        result = head.getvalue()
        expected = u"""<head>
<link rel="stylesheet" type="text/css" media="all" href="http://test.fr/data/??bob4.css,bob5.css"/>
<link rel="stylesheet" type="text/css" media="print" href="http://test.fr/data/??bob6.css,bob7.css"/>
<!--[if lt IE 8]>
<link rel="stylesheet" type="text/css" media="all" href="http://test.fr/data/bob8.css"/>
<!--[if lt IE 7]>
<link rel="stylesheet" type="text/css" media="print" href="http://test.fr/data/bob9.css"/>
<![endif]--> 
<script type="text/javascript" src="http://test.fr/data/??bob0.js,bob1.js"></script>
<script type="text/javascript" src="http://ext.com/bob2.js"></script>
<script type="text/javascript" src="http://ext.com/bob3.js"></script>
</head>
"""
        self.assertEqual(result, expected)

    def test_getvalue_without_concat(self):
        self.config.global_set_option('concat-resources', False)
        try:
            base_url = u'http://test.fr/data/'
            head = self.htmlhead(base_url)
            head.add_js(base_url + u'bob0.js')
            head.add_js(base_url + u'bob1.js')
            head.add_js(u'http://ext.com/bob2.js')
            head.add_js(u'http://ext.com/bob3.js')
            head.add_css(base_url + u'bob4.css')
            head.add_css(base_url + u'bob5.css')
            head.add_css(base_url + u'bob6.css', 'print')
            head.add_css(base_url + u'bob7.css', 'print')
            head.add_ie_css(base_url + u'bob8.css')
            head.add_ie_css(base_url + u'bob9.css', 'print', u'[if lt IE 7]')
            result = head.getvalue()
            expected = u"""<head>
<link rel="stylesheet" type="text/css" media="all" href="http://test.fr/data/bob4.css"/>
<link rel="stylesheet" type="text/css" media="all" href="http://test.fr/data/bob5.css"/>
<link rel="stylesheet" type="text/css" media="print" href="http://test.fr/data/bob6.css"/>
<link rel="stylesheet" type="text/css" media="print" href="http://test.fr/data/bob7.css"/>
<!--[if lt IE 8]>
<link rel="stylesheet" type="text/css" media="all" href="http://test.fr/data/bob8.css"/>
<!--[if lt IE 7]>
<link rel="stylesheet" type="text/css" media="print" href="http://test.fr/data/bob9.css"/>
<![endif]--> 
<script type="text/javascript" src="http://test.fr/data/bob0.js"></script>
<script type="text/javascript" src="http://test.fr/data/bob1.js"></script>
<script type="text/javascript" src="http://ext.com/bob2.js"></script>
<script type="text/javascript" src="http://ext.com/bob3.js"></script>
</head>
"""
            self.assertEqual(result, expected)
        finally:
            self.config.global_set_option('concat-resources', True)

class DocTest(DocTest):
    from cubicweb import utils as module

if __name__ == '__main__':
    unittest_main()
