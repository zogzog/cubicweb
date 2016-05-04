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
from contextlib import contextmanager

from six.moves import range

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

    @contextmanager
    def proc(self):
        with self.admin_access.web_request() as req:
            self.vreg.config.translations = {'en': (_translate, _ctxtranslate)}
            proc = self.vreg['components'].select('magicsearch', req)
            proc = [p for p in proc.processors if isinstance(p, QueryTranslator)][0]
            yield proc

    def test_basic_translations(self):
        """tests basic translations (no ambiguities)"""
        with self.proc() as proc:
            rql = u"Any C WHERE C is Adresse, P adel C, C adresse 'Logilab'"
            rql, = proc.preprocess_query(rql)
            self.assertEqual(rql, 'Any C WHERE C is EmailAddress, P use_email C, C address "Logilab"')

    def test_ambiguous_translations(self):
        """tests possibly ambiguous translations"""
        with self.proc() as proc:
            rql = u"Any P WHERE P adel C, C is EmailAddress, C nom 'Logilab'"
            rql, = proc.preprocess_query(rql)
            self.assertEqual(rql, 'Any P WHERE P use_email C, C is EmailAddress, C alias "Logilab"')
            rql = u"Any P WHERE P is Utilisateur, P adel C, P nom 'Smith'"
            rql, = proc.preprocess_query(rql)
            self.assertEqual(rql, 'Any P WHERE P is CWUser, P use_email C, P surname "Smith"')


class QSPreProcessorTC(CubicWebTC):
    """test suite for QSPreProcessor"""

    @contextmanager
    def proc(self):
        self.vreg.config.translations = {'en': (_translate, _ctxtranslate)}
        with self.admin_access.web_request() as req:
            proc = self.vreg['components'].select('magicsearch', req)
            proc = [p for p in proc.processors if isinstance(p, QSPreProcessor)][0]
            proc._cw = req
            yield proc

    def test_entity_translation(self):
        """tests QSPreProcessor._get_entity_name()"""
        with self.proc() as proc:
            translate = proc._get_entity_type
            self.assertEqual(translate(u'EmailAddress'), "EmailAddress")
            self.assertEqual(translate(u'emailaddress'), "EmailAddress")
            self.assertEqual(translate(u'Adresse'), "EmailAddress")
            self.assertEqual(translate(u'adresse'), "EmailAddress")
            self.assertRaises(BadRQLQuery, translate, 'whatever')

    def test_attribute_translation(self):
        """tests QSPreProcessor._get_attribute_name"""
        with self.proc() as proc:
            translate = proc._get_attribute_name
            eschema = self.schema.eschema('CWUser')
            self.assertEqual(translate(u'prÃ©nom', eschema), "firstname")
            self.assertEqual(translate(u'nom', eschema), 'surname')
            eschema = self.schema.eschema('EmailAddress')
            self.assertEqual(translate(u'adresse', eschema), "address")
            self.assertEqual(translate(u'nom', eschema), 'alias')
            # should fail if the name is not an attribute for the given entity schema
            self.assertRaises(BadRQLQuery, translate, 'whatever', eschema)
            self.assertRaises(BadRQLQuery, translate, 'prÃ©nom', eschema)

    def test_one_word_query(self):
        """tests the 'one word shortcut queries'"""
        with self.proc() as proc:
            transform = proc._one_word_query
            self.assertEqual(transform('123'),
                              ('Any X WHERE X eid %(x)s', {'x': 123}, 'x'))
            self.assertEqual(transform('CWUser'),
                              ('CWUser C',))
            self.assertEqual(transform('Utilisateur'),
                              ('CWUser C',))
            self.assertEqual(transform('Adresse'),
                              ('EmailAddress E',))
            self.assertEqual(transform('adresse'),
                              ('EmailAddress E',))
            self.assertRaises(BadRQLQuery, transform, 'Workcases')

    def test_two_words_query(self):
        """tests the 'two words shortcut queries'"""
        with self.proc() as proc:
            transform = proc._two_words_query
            self.assertEqual(transform('CWUser', 'E'),
                              ("CWUser E",))
            self.assertEqual(transform('CWUser', 'Smith'),
                              ('CWUser C ORDERBY FTIRANK(C) DESC WHERE C has_text %(text)s', {'text': 'Smith'}))
            self.assertEqual(transform('utilisateur', 'Smith'),
                              ('CWUser C ORDERBY FTIRANK(C) DESC WHERE C has_text %(text)s', {'text': 'Smith'}))
            self.assertEqual(transform(u'adresse', 'Logilab'),
                              ('EmailAddress E ORDERBY FTIRANK(E) DESC WHERE E has_text %(text)s', {'text': 'Logilab'}))
            self.assertEqual(transform(u'adresse', 'Logi%'),
                              ('EmailAddress E WHERE E alias LIKE %(text)s', {'text': 'Logi%'}))
            self.assertRaises(BadRQLQuery, transform, "pers", "taratata")

    def test_three_words_query(self):
        """tests the 'three words shortcut queries'"""
        with self.proc() as proc:
            transform = proc._three_words_query
            self.assertEqual(transform('utilisateur', u'prÃ©nom', 'cubicweb'),
                              ('CWUser C WHERE C firstname %(text)s', {'text': 'cubicweb'}))
            self.assertEqual(transform('utilisateur', 'nom', 'cubicweb'),
                              ('CWUser C WHERE C surname %(text)s', {'text': 'cubicweb'}))
            self.assertEqual(transform(u'adresse', 'nom', 'cubicweb'),
                              ('EmailAddress E WHERE E alias %(text)s', {'text': 'cubicweb'}))
            self.assertEqual(transform('EmailAddress', 'nom', 'cubicweb'),
                              ('EmailAddress E WHERE E alias %(text)s', {'text': 'cubicweb'}))
            self.assertEqual(transform('utilisateur', u'prÃ©nom', 'cubicweb%'),
                              ('CWUser C WHERE C firstname LIKE %(text)s', {'text': 'cubicweb%'}))
            # expanded shortcuts
            self.assertEqual(transform('CWUser', 'use_email', 'Logilab'),
                              ('CWUser C ORDERBY FTIRANK(C1) DESC WHERE C use_email C1, C1 has_text %(text)s', {'text': 'Logilab'}))
            self.assertEqual(transform('CWUser', 'use_email', '%Logilab'),
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
        with self.proc() as proc:
            transform = proc._quoted_words_query
            for query, expected in queries:
                self.assertEqual(transform(query), expected)
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
        with self.proc() as proc:
            for query, expected in queries:
                self.assertEqual(proc.preprocess_query(query), expected)
            self.assertRaises(BadRQLQuery,
                              proc.preprocess_query, 'Any X WHERE X is Something')



## Processor Chains tests ############################################

class ProcessorChainTC(CubicWebTC):
    """test suite for magic_search's processor chains"""

    @contextmanager
    def proc(self):
        self.vreg.config.translations = {'en': (_translate, _ctxtranslate)}
        with self.admin_access.web_request() as req:
            proc = self.vreg['components'].select('magicsearch', req)
            yield proc

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
        with self.proc() as proc:
            for query, expected in queries:
                rset = proc.process_query(query)
                self.assertEqual((rset.rql, rset.args), expected)

    def test_accentuated_fulltext(self):
        """we must be able to type accentuated characters in the search field"""
        with self.proc() as proc:
            rset = proc.process_query(u'écrire')
            self.assertEqual(rset.rql, "Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s")
            self.assertEqual(rset.args, {'text': u'écrire'})

    def test_explicit_component(self):
        with self.proc() as proc:
            self.assertRaises(RQLSyntaxError,
                              proc.process_query, u'rql: CWUser E WHERE E noattr "Smith",')
            self.assertRaises(BadRQLQuery,
                              proc.process_query, u'rql: CWUser E WHERE E noattr "Smith"')
            rset = proc.process_query(u'text: utilisateur Smith')
            self.assertEqual(rset.rql, 'Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s')
            self.assertEqual(rset.args, {'text': u'utilisateur Smith'})


class RQLSuggestionsBuilderTC(CubicWebTC):
    def suggestions(self, rql):
        with self.admin_access.web_request() as req:
            rbs = self.vreg['components'].select('rql.suggestions', req)
            return rbs.build_suggestions(rql)

    def test_no_restrictions_rql(self):
        self.assertListEqual([], self.suggestions(''))
        self.assertListEqual([], self.suggestions('An'))
        self.assertListEqual([], self.suggestions('Any X'))
        self.assertListEqual([], self.suggestions('Any X, Y'))

    def test_invalid_rql(self):
        self.assertListEqual([], self.suggestions('blabla'))
        self.assertListEqual([], self.suggestions('Any X WHERE foo, bar'))

    def test_is_rql(self):
        self.assertListEqual(['Any X WHERE X is %s' % eschema
                              for eschema in sorted(self.vreg.schema.entities())
                              if not eschema.final],
                             self.suggestions('Any X WHERE X is'))

        self.assertListEqual(['Any X WHERE X is Personne', 'Any X WHERE X is Project'],
                             self.suggestions('Any X WHERE X is P'))

        self.assertListEqual(['Any X WHERE X is Personne, Y is Personne',
                              'Any X WHERE X is Personne, Y is Project'],
                             self.suggestions('Any X WHERE X is Personne, Y is P'))


    def test_relations_rql(self):
        self.assertListEqual(['Any X WHERE X is Personne, X ass A',
                              'Any X WHERE X is Personne, X datenaiss A',
                              'Any X WHERE X is Personne, X description A',
                              'Any X WHERE X is Personne, X fax A',
                              'Any X WHERE X is Personne, X nom A',
                              'Any X WHERE X is Personne, X prenom A',
                              'Any X WHERE X is Personne, X promo A',
                              'Any X WHERE X is Personne, X salary A',
                              'Any X WHERE X is Personne, X sexe A',
                              'Any X WHERE X is Personne, X tel A',
                              'Any X WHERE X is Personne, X test A',
                              'Any X WHERE X is Personne, X titre A',
                              'Any X WHERE X is Personne, X travaille A',
                              'Any X WHERE X is Personne, X tzdatenaiss A',
                              'Any X WHERE X is Personne, X web A',
                              ],
                             self.suggestions('Any X WHERE X is Personne, X '))
        self.assertListEqual(['Any X WHERE X is Personne, X tel A',
                              'Any X WHERE X is Personne, X test A',
                              'Any X WHERE X is Personne, X titre A',
                              'Any X WHERE X is Personne, X travaille A',
                              'Any X WHERE X is Personne, X tzdatenaiss A',
                              ],
                             self.suggestions('Any X WHERE X is Personne, X t'))
        # try completion on selected
        self.assertListEqual(['Any X WHERE X is Personne, Y is Societe, X tel A',
                              'Any X WHERE X is Personne, Y is Societe, X test A',
                              'Any X WHERE X is Personne, Y is Societe, X titre A',
                              'Any X WHERE X is Personne, Y is Societe, X travaille Y',
                              'Any X WHERE X is Personne, Y is Societe, X tzdatenaiss A',
                              ],
                             self.suggestions('Any X WHERE X is Personne, Y is Societe, X t'))
        # invalid relation should not break
        self.assertListEqual([],
                             self.suggestions('Any X WHERE X is Personne, X asdasd'))

    def test_attribute_vocabulary_rql(self):
        self.assertListEqual(['Any X WHERE X is Personne, X promo "bon"',
                              'Any X WHERE X is Personne, X promo "pasbon"',
                              ],
                             self.suggestions('Any X WHERE X is Personne, X promo "'))
        self.assertListEqual(['Any X WHERE X is Personne, X promo "pasbon"',
                              ],
                             self.suggestions('Any X WHERE X is Personne, X promo "p'))
        # "bon" should be considered complete, hence no suggestion
        self.assertListEqual([],
                             self.suggestions('Any X WHERE X is Personne, X promo "bon"'))
        # no valid vocabulary starts with "po"
        self.assertListEqual([],
                             self.suggestions('Any X WHERE X is Personne, X promo "po'))

    def test_attribute_value_rql(self):
        # suggestions should contain any possible value for
        # a given attribute (limited to 10)
        with self.admin_access.web_request() as req:
            for i in range(15):
                req.create_entity('Personne', nom=u'n%s' % i, prenom=u'p%s' % i)
            req.cnx.commit()
        self.assertListEqual(['Any X WHERE X is Personne, X nom "n0"',
                              'Any X WHERE X is Personne, X nom "n1"',
                              'Any X WHERE X is Personne, X nom "n10"',
                              'Any X WHERE X is Personne, X nom "n11"',
                              'Any X WHERE X is Personne, X nom "n12"',
                              'Any X WHERE X is Personne, X nom "n13"',
                              'Any X WHERE X is Personne, X nom "n14"',
                              'Any X WHERE X is Personne, X nom "n2"',
                              'Any X WHERE X is Personne, X nom "n3"',
                              'Any X WHERE X is Personne, X nom "n4"',
                              'Any X WHERE X is Personne, X nom "n5"',
                              'Any X WHERE X is Personne, X nom "n6"',
                              'Any X WHERE X is Personne, X nom "n7"',
                              'Any X WHERE X is Personne, X nom "n8"',
                              'Any X WHERE X is Personne, X nom "n9"',
                              ],
                             self.suggestions('Any X WHERE X is Personne, X nom "'))
        self.assertListEqual(['Any X WHERE X is Personne, X nom "n1"',
                              'Any X WHERE X is Personne, X nom "n10"',
                              'Any X WHERE X is Personne, X nom "n11"',
                              'Any X WHERE X is Personne, X nom "n12"',
                              'Any X WHERE X is Personne, X nom "n13"',
                              'Any X WHERE X is Personne, X nom "n14"',
                              ],
                             self.suggestions('Any X WHERE X is Personne, X nom "n1'))


if __name__ == '__main__':
    unittest_main()
