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
"""Unit tests for cw.web.views.magicsearch"""

import sys

from logilab.common.testlib import TestCase, unittest_main

from rql import BadRQLQuery, RQLSyntaxError

from cubicweb.devtools.testlib import CubicWebTC


translations = {
    u'CWUser' : u"Utilisateur",
    u'EmailAddress' : u"Adresse",
    u'name' : u"nom",
    u'alias' : u"nom",
    u'surname' : u"nom",
    u'firstname' : u"prÃ©nom",
    u'state' : u"Ã©tat",
    u'address' : u"adresse",
    u'use_email' : u"adel",
    }

def _translate(msgid):
    return translations.get(msgid, msgid)

def _ctxtranslate(ctx, msgid):
    return _translate(msgid)

from cubicweb.web.views.magicsearch import translate_rql_tree, QSPreProcessor, QueryTranslator

class QueryTranslatorTC(CubicWebTC):
    """test suite for QueryTranslatorTC"""

    def setUp(self):
        super(QueryTranslatorTC, self).setUp()
        self.req = self.request()
        self.vreg.config.translations = {'en': (_translate, _ctxtranslate)}
        proc = self.vreg['components'].select('magicsearch', self.req)
        self.proc = [p for p in proc.processors if isinstance(p, QueryTranslator)][0]

    def test_basic_translations(self):
        """tests basic translations (no ambiguities)"""
        rql = "Any C WHERE C is Adresse, P adel C, C adresse 'Logilab'"
        rql, = self.proc.preprocess_query(rql)
        self.assertEquals(rql, "Any C WHERE C is EmailAddress, P use_email C, C address 'Logilab'")

    def test_ambiguous_translations(self):
        """tests possibly ambiguous translations"""
        rql = "Any P WHERE P adel C, C is EmailAddress, C nom 'Logilab'"
        rql, = self.proc.preprocess_query(rql)
        self.assertEquals(rql, "Any P WHERE P use_email C, C is EmailAddress, C alias 'Logilab'")
        rql = "Any P WHERE P is Utilisateur, P adel C, P nom 'Smith'"
        rql, = self.proc.preprocess_query(rql)
        self.assertEquals(rql, "Any P WHERE P is CWUser, P use_email C, P surname 'Smith'")


class QSPreProcessorTC(CubicWebTC):
    """test suite for QSPreProcessor"""
    def setUp(self):
        super(QSPreProcessorTC, self).setUp()
        self.vreg.config.translations = {'en': (_translate, _ctxtranslate)}
        self.req = self.request()
        proc = self.vreg['components'].select('magicsearch', self.req)
        self.proc = [p for p in proc.processors if isinstance(p, QSPreProcessor)][0]
        self.proc._cw = self.req

    def test_entity_translation(self):
        """tests QSPreProcessor._get_entity_name()"""
        translate = self.proc._get_entity_type
        self.assertEquals(translate(u'EmailAddress'), "EmailAddress")
        self.assertEquals(translate(u'emailaddress'), "EmailAddress")
        self.assertEquals(translate(u'Adresse'), "EmailAddress")
        self.assertEquals(translate(u'adresse'), "EmailAddress")
        self.assertRaises(BadRQLQuery, translate, 'whatever')

    def test_attribute_translation(self):
        """tests QSPreProcessor._get_attribute_name"""
        translate = self.proc._get_attribute_name
        eschema = self.schema.eschema('CWUser')
        self.assertEquals(translate(u'prÃ©nom', eschema), "firstname")
        self.assertEquals(translate(u'nom', eschema), 'surname')
        eschema = self.schema.eschema('EmailAddress')
        self.assertEquals(translate(u'adresse', eschema), "address")
        self.assertEquals(translate(u'nom', eschema), 'alias')
        # should fail if the name is not an attribute for the given entity schema
        self.assertRaises(BadRQLQuery, translate, 'whatever', eschema)
        self.assertRaises(BadRQLQuery, translate, 'prÃ©nom', eschema)

    def test_one_word_query(self):
        """tests the 'one word shortcut queries'"""
        transform = self.proc._one_word_query
        self.assertEquals(transform('123'),
                          ('Any X WHERE X eid %(x)s', {'x': 123}, 'x'))
        self.assertEquals(transform('CWUser'),
                          ('CWUser C',))
        self.assertEquals(transform('Utilisateur'),
                          ('CWUser C',))
        self.assertEquals(transform('Adresse'),
                          ('EmailAddress E',))
        self.assertEquals(transform('adresse'),
                          ('EmailAddress E',))
        self.assertRaises(BadRQLQuery, transform, 'Workcases')

    def test_two_words_query(self):
        """tests the 'two words shortcut queries'"""
        transform = self.proc._two_words_query
        self.assertEquals(transform('CWUser', 'E'),
                          ("CWUser E",))
        self.assertEquals(transform('CWUser', 'Smith'),
                          ('CWUser C ORDERBY FTIRANK(C) DESC WHERE C has_text %(text)s', {'text': 'Smith'}))
        self.assertEquals(transform('utilisateur', 'Smith'),
                          ('CWUser C ORDERBY FTIRANK(C) DESC WHERE C has_text %(text)s', {'text': 'Smith'}))
        self.assertEquals(transform(u'adresse', 'Logilab'),
                          ('EmailAddress E ORDERBY FTIRANK(E) DESC WHERE E has_text %(text)s', {'text': 'Logilab'}))
        self.assertEquals(transform(u'adresse', 'Logi%'),
                          ('EmailAddress E WHERE E alias LIKE %(text)s', {'text': 'Logi%'}))
        self.assertRaises(BadRQLQuery, transform, "pers", "taratata")

    def test_three_words_query(self):
        """tests the 'three words shortcut queries'"""
        transform = self.proc._three_words_query
        self.assertEquals(transform('utilisateur', u'prÃ©nom', 'cubicweb'),
                          ('CWUser C WHERE C firstname %(text)s', {'text': 'cubicweb'}))
        self.assertEquals(transform('utilisateur', 'nom', 'cubicweb'),
                          ('CWUser C WHERE C surname %(text)s', {'text': 'cubicweb'}))
        self.assertEquals(transform(u'adresse', 'nom', 'cubicweb'),
                          ('EmailAddress E WHERE E alias %(text)s', {'text': 'cubicweb'}))
        self.assertEquals(transform('EmailAddress', 'nom', 'cubicweb'),
                          ('EmailAddress E WHERE E alias %(text)s', {'text': 'cubicweb'}))
        self.assertEquals(transform('utilisateur', u'prÃ©nom', 'cubicweb%'),
                          ('CWUser C WHERE C firstname LIKE %(text)s', {'text': 'cubicweb%'}))
        # expanded shortcuts
        self.assertEquals(transform('CWUser', 'use_email', 'Logilab'),
                          ('CWUser C ORDERBY FTIRANK(C1) DESC WHERE C use_email C1, C1 has_text %(text)s', {'text': 'Logilab'}))
        self.assertEquals(transform('CWUser', 'use_email', '%Logilab'),
                          ('CWUser C WHERE C use_email C1, C1 alias LIKE %(text)s', {'text': '%Logilab'}))
        self.assertRaises(BadRQLQuery, transform, 'word1', 'word2', 'word3')

    def test_quoted_queries(self):
        """tests how quoted queries are handled"""
        queries = [
            (u'Adresse "My own EmailAddress"', ('EmailAddress E ORDERBY FTIRANK(E) DESC WHERE E has_text %(text)s', {'text': u'My own EmailAddress'})),
            (u'Utilisateur prÃ©nom "Jean Paul"', ('CWUser C WHERE C firstname %(text)s', {'text': 'Jean Paul'})),
            (u'Utilisateur firstname "Jean Paul"', ('CWUser C WHERE C firstname %(text)s', {'text': 'Jean Paul'})),
            (u'CWUser firstname "Jean Paul"', ('CWUser C WHERE C firstname %(text)s', {'text': 'Jean Paul'})),
            ]
        transform = self.proc._quoted_words_query
        for query, expected in queries:
            self.assertEquals(transform(query), expected)
        self.assertRaises(BadRQLQuery, transform, "unquoted rql")
        self.assertRaises(BadRQLQuery, transform, 'pers "Jean Paul"')
        self.assertRaises(BadRQLQuery, transform, 'CWUser firstname other "Jean Paul"')

    def test_process_query(self):
        """tests how queries are processed"""
        queries = [
            (u'Utilisateur', (u"CWUser C",)),
            (u'Utilisateur P', (u"CWUser P",)),
            (u'Utilisateur cubicweb', (u'CWUser C ORDERBY FTIRANK(C) DESC WHERE C has_text %(text)s', {'text': u'cubicweb'})),
            (u'CWUser prÃ©nom cubicweb', (u'CWUser C WHERE C firstname %(text)s', {'text': 'cubicweb'},)),
            ]
        for query, expected in queries:
            self.assertEquals(self.proc.preprocess_query(query), expected)
        self.assertRaises(BadRQLQuery,
                          self.proc.preprocess_query, 'Any X WHERE X is Something')



## Processor Chains tests ############################################


class ProcessorChainTC(CubicWebTC):
    """test suite for magic_search's processor chains"""

    def setUp(self):
        super(ProcessorChainTC, self).setUp()
        self.vreg.config.translations = {'en': (_translate, _ctxtranslate)}
        self.req = self.request()
        self.proc = self.vreg['components'].select('magicsearch', self.req)

    def test_main_preprocessor_chain(self):
        """tests QUERY_PROCESSOR"""
        queries = [
            (u'foo',
             ("Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s", {'text': u'foo'})),
            # XXX this sounds like a language translator test...
            # and it fails
            (u'Utilisateur Smith',
             ('CWUser C ORDERBY FTIRANK(C) DESC WHERE C has_text %(text)s', {'text': u'Smith'})),
            (u'utilisateur nom Smith',
             ('CWUser C WHERE C surname %(text)s', {'text': u'Smith'})),
            (u'Any P WHERE P is Utilisateur, P nom "Smith"',
             ('Any P WHERE P is CWUser, P surname "Smith"', None)),
            ]
        for query, expected in queries:
            rset = self.proc.process_query(query)
            self.assertEquals((rset.rql, rset.args), expected)

    def test_accentuated_fulltext(self):
        """we must be able to type accentuated characters in the search field"""
        rset = self.proc.process_query(u'écrire')
        self.assertEquals(rset.rql, "Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s")
        self.assertEquals(rset.args, {'text': u'écrire'})

    def test_explicit_component(self):
        self.assertRaises(RQLSyntaxError,
                          self.proc.process_query, u'rql: CWUser E WHERE E noattr "Smith",')
        self.assertRaises(BadRQLQuery,
                          self.proc.process_query, u'rql: CWUser E WHERE E noattr "Smith"')
        rset = self.proc.process_query(u'text: utilisateur Smith')
        self.assertEquals(rset.rql, 'Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s')
        self.assertEquals(rset.args, {'text': u'utilisateur Smith'})

if __name__ == '__main__':
    unittest_main()
