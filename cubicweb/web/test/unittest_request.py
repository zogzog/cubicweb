"""misc. unittests for utility functions
"""

import unittest
from functools import partial

from cubicweb.devtools.fake import FakeConfig, FakeCWRegistryStore

from cubicweb.web.request import (CubicWebRequestBase, _parse_accept_header,
                                  _mimetype_sort_key, _mimetype_parser, _charset_sort_key)



class AcceptParserTC(unittest.TestCase):

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


class WebRequestTC(unittest.TestCase):

    def test_negotiated_language(self):
        vreg = FakeCWRegistryStore(FakeConfig(), initlog=False)
        vreg.config.translations = {'fr': (None, None), 'en': (None, None)}
        headers = {
            'Accept-Language': 'fr,fr-fr;q=0.8,en-us;q=0.5,en;q=0.3',
        }
        req = CubicWebRequestBase(vreg, headers=headers)
        self.assertEqual(req.negotiated_language(), 'fr')

    def test_build_url_language_from_url(self):
        vreg = FakeCWRegistryStore(FakeConfig(), initlog=False)
        vreg.config['base-url'] = 'http://testing.fr/cubicweb/'
        vreg.config['language-mode'] = 'url-prefix'
        vreg.config.translations['fr'] = str, str
        req = CubicWebRequestBase(vreg)
        # Override from_controller to avoid getting into relative_path method,
        # which is not implemented in CubicWebRequestBase.
        req.from_controller = lambda : 'not view'
        self.assertEqual(req.lang, 'en')  # site's default language
        self.assertEqual(req.build_url(), 'http://testing.fr/cubicweb/en/view')
        self.assertEqual(req.build_url('foo'), 'http://testing.fr/cubicweb/en/foo')
        req.set_language('fr')
        self.assertEqual(req.lang, 'fr')
        self.assertEqual(req.build_url(), 'http://testing.fr/cubicweb/fr/view')
        self.assertEqual(req.build_url('foo'), 'http://testing.fr/cubicweb/fr/foo')
        # no language prefix in URL
        vreg.config['language-mode'] = ''
        self.assertEqual(req.build_url(), 'http://testing.fr/cubicweb/view')
        self.assertEqual(req.build_url('foo'), 'http://testing.fr/cubicweb/foo')
        req.set_language('fr')
        self.assertEqual(req.build_url(), 'http://testing.fr/cubicweb/view')
        self.assertEqual(req.build_url('foo'), 'http://testing.fr/cubicweb/foo')


if __name__ == '__main__':
    unittest.main()
