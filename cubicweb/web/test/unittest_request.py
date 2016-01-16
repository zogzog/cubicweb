"""misc. unittests for utility functions
"""

from logilab.common.testlib import TestCase, unittest_main

from functools import partial

from cubicweb.devtools.fake import FakeConfig

from cubicweb.web.request import (CubicWebRequestBase, _parse_accept_header,
                                  _mimetype_sort_key, _mimetype_parser, _charset_sort_key)



class AcceptParserTC(TestCase):

    def test_parse_accept(self):
        parse_accept_header = partial(_parse_accept_header,
                                      value_parser=_mimetype_parser,
                                      value_sort_key=_mimetype_sort_key)
        # compare scores
        self.assertEqual(parse_accept_header("audio/*;q=0.2, audio/basic"),
                         [( ('audio/basic', ('audio', 'basic', {}), 1.0 ) ),
                          ( ('audio/*', ('audio', '*', {}), 0.2 ) )])
        self.assertEqual(parse_accept_header("text/plain;q=0.5, text/html, text/x-dvi;q=0.8, text/x-c"),
                         [( ('text/html', ('text', 'html', {}), 1.0 ) ),
                          ( ('text/x-c', ('text', 'x-c', {}), 1.0 ) ),
                          ( ('text/x-dvi', ('text', 'x-dvi', {}), 0.8 ) ),
                          ( ('text/plain', ('text', 'plain', {}), 0.5 ) )])
        # compare mimetype precedence for a same given score
        self.assertEqual(parse_accept_header("audio/*, audio/basic"),
                         [( ('audio/basic', ('audio', 'basic', {}), 1.0 ) ),
                          ( ('audio/*', ('audio', '*', {}), 1.0 ) )])
        self.assertEqual(parse_accept_header("text/*, text/html, text/html;level=1, */*"),
                         [( ('text/html', ('text', 'html', {'level': '1'}), 1.0 ) ),
                          ( ('text/html', ('text', 'html', {}), 1.0 ) ),
                          ( ('text/*', ('text', '*', {}), 1.0 ) ),
                          ( ('*/*', ('*', '*', {}), 1.0 ) )])
        # free party
        self.assertEqual(parse_accept_header("text/*;q=0.3, text/html;q=0.7, text/html;level=1, text/html;level=2;q=0.4, */*;q=0.5"),
                         [( ('text/html', ('text', 'html', {'level': '1'}), 1.0 ) ),
                          ( ('text/html', ('text', 'html', {}), 0.7 ) ),
                          ( ('*/*', ('*', '*', {}), 0.5 ) ),
                          ( ('text/html', ('text', 'html', {'level': '2'}), 0.4 ) ),
                          ( ('text/*', ('text', '*', {}), 0.3 ) )
                          ])
        # chrome sample header
        self.assertEqual(parse_accept_header("application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5"),
                         [( ('application/xhtml+xml', ('application', 'xhtml+xml', {}), 1.0 ) ),
                          ( ('application/xml', ('application', 'xml', {}), 1.0 ) ),
                          ( ('image/png', ('image', 'png', {}), 1.0 ) ),
                          ( ('text/html', ('text', 'html', {}), 0.9 ) ),
                          ( ('text/plain', ('text', 'plain', {}), 0.8 ) ),
                          ( ('*/*', ('*', '*', {}), 0.5 ) ),
                          ])

    def test_parse_accept_language(self):
        self.assertEqual(_parse_accept_header('fr,fr-fr;q=0.8,en-us;q=0.5,en;q=0.3'),
                         [('fr', 'fr', 1.0), ('fr-fr', 'fr-fr', 0.8),
                          ('en-us', 'en-us', 0.5), ('en', 'en', 0.3)])

    def test_parse_accept_charset(self):
        parse_accept_header = partial(_parse_accept_header,
                                      value_sort_key=_charset_sort_key)
        self.assertEqual(parse_accept_header('ISO-8859-1,utf-8;q=0.7,*;q=0.7'),
                         [('ISO-8859-1', 'ISO-8859-1', 1.0),
                          ('utf-8', 'utf-8', 0.7),
                          ('*', '*', 0.7)])

    def test_base_url(self):
        dummy_vreg = type('DummyVreg', (object,), {})()
        dummy_vreg.config = FakeConfig()
        dummy_vreg.config['base-url'] = 'http://babar.com/'
        dummy_vreg.config['https-url'] = 'https://toto.com/'

        req = CubicWebRequestBase(dummy_vreg, https=False)
        self.assertEqual('http://babar.com/', req.base_url())
        self.assertEqual('http://babar.com/', req.base_url(False))
        self.assertEqual('https://toto.com/', req.base_url(True))

        req = CubicWebRequestBase(dummy_vreg, https=True)
        self.assertEqual('https://toto.com/', req.base_url())
        self.assertEqual('http://babar.com/', req.base_url(False))
        self.assertEqual('https://toto.com/', req.base_url(True))



if __name__ == '__main__':
    unittest_main()
