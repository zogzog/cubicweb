# -*- coding: utf-8 -*-
# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for cubicweb.web.views.entities module"""

from datetime import datetime

from logilab.common import tempattr
from logilab.common.decorators import clear_cache

from cubicweb import Binary
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.mttransforms import HAS_TAL
from cubicweb.entity import can_use_rest_path
from cubicweb.entities import fetch_config
from cubicweb.uilib import soup2xhtml
from cubicweb.schema import RRQLExpression


class EntityTC(CubicWebTC):

    def setUp(self):
        super(EntityTC, self).setUp()
        self.backup_dict = {}
        for cls in self.vreg['etypes'].iter_classes():
            self.backup_dict[cls] = (cls.fetch_attrs, cls.cw_fetch_order)

    def tearDown(self):
        super(EntityTC, self).tearDown()
        for cls in self.vreg['etypes'].iter_classes():
            cls.fetch_attrs, cls.cw_fetch_order = self.backup_dict[cls]

    def test_no_prefill_related_cache_bug(self):
        with self.admin_access.repo_cnx() as cnx:
            usine = cnx.create_entity('Usine', lieu=u'Montbeliard')
            produit = cnx.create_entity('Produit')
            # usine was prefilled in glob_add_entity
            # let's simulate produit creation without prefill
            produit._cw_related_cache.clear()
            # use add_relations
            cnx.add_relations([('fabrique_par', [(produit.eid, usine.eid)])])
            self.assertEqual(1, len(usine.reverse_fabrique_par))
            self.assertEqual(1, len(produit.fabrique_par))

    def test_boolean_value(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            self.assertTrue(e)

    def test_yams_inheritance(self):
        from entities import Note
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('SubNote')(req)
            self.assertIsInstance(e, Note)
            e2 = self.vreg['etypes'].etype_class('SubNote')(req)
            self.assertIs(e.__class__, e2.__class__)

    def test_has_eid(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            self.assertEqual(e.eid, None)
            self.assertEqual(e.has_eid(), False)
            e.eid = 'X'
            self.assertEqual(e.has_eid(), False)
            e.eid = 0
            self.assertEqual(e.has_eid(), True)
            e.eid = 2
            self.assertEqual(e.has_eid(), True)

    def test_copy(self):
        with self.admin_access.web_request() as req:
            req.create_entity('Tag', name=u'x')
            p = req.create_entity('Personne', nom=u'toto')
            oe = req.create_entity('Note', type=u'x')
            req.execute('SET T ecrit_par U WHERE T eid %(t)s, U eid %(u)s',
                         {'t': oe.eid, 'u': p.eid})
            req.execute('SET TAG tags X WHERE X eid %(x)s', {'x': oe.eid})
            e = req.create_entity('Note', type=u'z')
            e.copy_relations(oe.eid)
            self.assertEqual(len(e.ecrit_par), 1)
            self.assertEqual(e.ecrit_par[0].eid, p.eid)
            self.assertEqual(len(e.reverse_tags), 1)
            # check meta-relations are not copied, set on commit
            self.assertEqual(len(e.created_by), 0)

    def test_copy_with_nonmeta_composite_inlined(self):
        with self.admin_access.web_request() as req:
            p = req.create_entity('Personne', nom=u'toto')
            oe = req.create_entity('Note', type=u'x')
            self.schema['ecrit_par'].rdef('Note', 'Personne').composite = 'subject'
            req.execute('SET T ecrit_par U WHERE T eid %(t)s, U eid %(u)s',
                        {'t': oe.eid, 'u': p.eid})
            e = req.create_entity('Note', type=u'z')
            e.copy_relations(oe.eid)
            self.assertFalse(e.ecrit_par)
            self.assertTrue(oe.ecrit_par)

    def test_copy_with_composite(self):
        with self.admin_access.web_request() as req:
            adeleid = req.execute('INSERT EmailAddress X: X address "toto@logilab.org", U use_email X WHERE U login "admin"')[0][0]
            e = req.execute('Any X WHERE X eid %(x)s', {'x': req.user.eid}).get_entity(0, 0)
            self.assertEqual(e.use_email[0].address, "toto@logilab.org")
            self.assertEqual(e.use_email[0].eid, adeleid)
            usereid = req.execute('INSERT CWUser X: X login "toto", X upassword "toto", X in_group G '
                                   'WHERE G name "users"')[0][0]
            e = req.execute('Any X WHERE X eid %(x)s', {'x': usereid}).get_entity(0, 0)
            e.copy_relations(req.user.eid)
            self.assertFalse(e.use_email)
            self.assertFalse(e.primary_email)

    def test_copy_with_non_initial_state(self):
        with self.admin_access.web_request() as req:
            user = req.execute('INSERT CWUser X: X login "toto", X upassword %(pwd)s, X in_group G WHERE G name "users"',
                               {'pwd': 'toto'}).get_entity(0, 0)
            req.cnx.commit()
            user.cw_adapt_to('IWorkflowable').fire_transition('deactivate')
            req.cnx.commit()
            eid2 = req.execute('INSERT CWUser X: X login "tutu", X upassword %(pwd)s', {'pwd': 'toto'})[0][0]
            e = req.execute('Any X WHERE X eid %(x)s', {'x': eid2}).get_entity(0, 0)
            e.copy_relations(user.eid)
            req.cnx.commit()
            e.cw_clear_relation_cache('in_state', 'subject')
            self.assertEqual(e.cw_adapt_to('IWorkflowable').state, 'activated')

    def test_copy_exclude_computed_relations(self):
        """The `CWUser buddies CWUser` (computed) relation should not be copied.
        """
        with self.admin_access.cnx() as cnx:
            friends = cnx.create_entity('CWGroup', name=u'friends')
            bob = self.create_user(cnx, u'bob', groups=('friends',))
            cnx.create_entity('EmailAddress', address=u'bob@cubicweb.org',
                              reverse_use_email=bob)
            alice = self.create_user(cnx, u'alices', groups=('friends',))
            cnx.commit()
            charles = self.create_user(cnx, u'charles')
            cnx.commit()
            # Just ensure this does not crash (it would if computed relation
            # attempted to be copied).
            charles.copy_relations(bob.eid)

    def test_related_cache_both(self):
        with self.admin_access.web_request() as req:
            user = req.execute('Any X WHERE X eid %(x)s', {'x':req.user.eid}).get_entity(0, 0)
            adeleid = req.execute('INSERT EmailAddress X: X address "toto@logilab.org", U use_email X WHERE U login "admin"')[0][0]
            req.cnx.commit()
            self.assertEqual(user._cw_related_cache, {})
            email = user.primary_email[0]
            self.assertEqual(sorted(user._cw_related_cache), ['primary_email_subject'])
            self.assertEqual(list(email._cw_related_cache), ['primary_email_object'])
            groups = user.in_group
            self.assertEqual(sorted(user._cw_related_cache), ['in_group_subject', 'primary_email_subject'])
            for group in groups:
                self.assertNotIn('in_group_subject', group._cw_related_cache)
            user.cw_clear_all_caches()
            user.related('in_group', entities=True)
            self.assertIn('in_group_subject', user._cw_related_cache)
            user.cw_clear_all_caches()
            user.related('in_group', targettypes=('CWGroup',), entities=True)
            self.assertNotIn('in_group_subject', user._cw_related_cache)

    def test_related_limit(self):
        with self.admin_access.web_request() as req:
            p = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
            for tag in u'abcd':
                req.create_entity('Tag', name=tag)
            req.execute('SET X tags Y WHERE X is Tag, Y is Personne')
            self.assertEqual(len(p.related('tags', 'object', limit=2)), 2)
            self.assertFalse(p.cw_relation_cached('tags', 'object'))
            self.assertEqual(len(p.related('tags', 'object')), 4)
            self.assertTrue(p.cw_relation_cached('tags', 'object'))
            p.cw_clear_all_caches()
            self.assertFalse(p.cw_relation_cached('tags', 'object'))
            self.assertEqual(len(p.related('tags', 'object', entities=True, limit=2)), 2)
            self.assertFalse(p.cw_relation_cached('tags', 'object'))
            self.assertEqual(len(p.related('tags', 'object', entities=True)), 4)
            self.assertTrue(p.cw_relation_cached('tags', 'object'))

    def test_related_targettypes(self):
        with self.admin_access.web_request() as req:
            p = req.create_entity('Personne', nom=u'Loxodonta', prenom=u'Babar')
            n = req.create_entity('Note', type=u'scratch', ecrit_par=p)
            t = req.create_entity('Tag', name=u'a tag', tags=(p, n))
            req.cnx.commit()
        with self.admin_access.web_request() as req:
            t = req.entity_from_eid(t.eid)
            self.assertEqual(2, t.related('tags').rowcount)
            self.assertEqual(1, t.related('tags', targettypes=('Personne',)).rowcount)
            self.assertEqual(1, t.related('tags', targettypes=('Note',)).rowcount)

    def test_cw_instantiate_relation(self):
        with self.admin_access.web_request() as req:
            p1 = req.create_entity('Personne', nom=u'di')
            p2 = req.create_entity('Personne', nom=u'mascio')
            t = req.create_entity('Tag', name=u't0', tags=[])
            self.assertCountEqual(t.tags, [])
            t = req.create_entity('Tag', name=u't1', tags=p1)
            self.assertCountEqual(t.tags, [p1])
            t = req.create_entity('Tag', name=u't2', tags=p1.eid)
            self.assertCountEqual(t.tags, [p1])
            t = req.create_entity('Tag', name=u't3', tags=[p1, p2.eid])
            self.assertCountEqual(t.tags, [p1, p2])

    def test_cw_instantiate_reverse_relation(self):
        with self.admin_access.web_request() as req:
            t1 = req.create_entity('Tag', name=u't1')
            t2 = req.create_entity('Tag', name=u't2')
            p = req.create_entity('Personne', nom=u'di mascio', reverse_tags=t1)
            self.assertCountEqual(p.reverse_tags, [t1])
            p = req.create_entity('Personne', nom=u'di mascio', reverse_tags=t1.eid)
            self.assertCountEqual(p.reverse_tags, [t1])
            p = req.create_entity('Personne', nom=u'di mascio', reverse_tags=[t1, t2.eid])
            self.assertCountEqual(p.reverse_tags, [t1, t2])

    def test_fetch_rql(self):
        Personne = self.vreg['etypes'].etype_class('Personne')
        Societe = self.vreg['etypes'].etype_class('Societe')
        Note = self.vreg['etypes'].etype_class('Note')
        peschema = Personne.e_schema
        seschema = Societe.e_schema
        torestore = []
        for rdef, card in [(peschema.subjrels['travaille'].rdef(peschema, seschema), '1*'),
                           (peschema.subjrels['connait'].rdef(peschema, peschema), '11'),
                           (peschema.subjrels['evaluee'].rdef(peschema, Note.e_schema), '1*'),
                           (seschema.subjrels['evaluee'].rdef(seschema, Note.e_schema), '1*')]:
            cm = tempattr(rdef, 'cardinality', card)
            cm.__enter__()
            torestore.append(cm)
        try:
            with self.admin_access.web_request() as req:
                user = req.user
                # testing basic fetch_attrs attribute
                self.assertEqual(Personne.fetch_rql(user),
                                 'Any X,AA,AB,AC ORDERBY AB '
                                 'WHERE X is_instance_of Personne, X modification_date AA, X nom AB, X prenom AC')
                # testing unknown attributes
                Personne.fetch_attrs = ('bloug', 'beep')
                self.assertEqual(Personne.fetch_rql(user), 'Any X WHERE X is_instance_of Personne')
                # testing one non final relation
                Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
                self.assertEqual(Personne.fetch_rql(user),
                                 'Any X,AA,AB,AC,AD ORDERBY AA '
                                 'WHERE X is_instance_of Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD')
                # testing two non final relations
                Personne.fetch_attrs = ('nom', 'prenom', 'travaille', 'evaluee')
                self.assertEqual(Personne.fetch_rql(user),
                                 'Any X,AA,AB,AC,AD,AE ORDERBY AB '
                                 'WHERE X is_instance_of Personne, X evaluee AA?, X nom AB, X prenom AC, X travaille AD?, '
                                 'AD nom AE')
                # testing one non final relation with recursion
                Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
                Societe.fetch_attrs = ('nom', 'evaluee')
                self.assertEqual(Personne.fetch_rql(user),
                                 'Any X,AA,AB,AC,AD,AE,AF ORDERBY AA '
                                 'WHERE X is_instance_of Personne, X nom AA, X prenom AB, X travaille AC?, '
                                 'AC evaluee AD?, AD modification_date AE, AC nom AF')
                # testing symmetric relation
                Personne.fetch_attrs = ('nom', 'connait')
                self.assertEqual(Personne.fetch_rql(user), 'Any X,AA,AB ORDERBY AB '
                                 'WHERE X is_instance_of Personne, X connait AA?, X nom AB')
                # testing optional relation
                peschema.subjrels['travaille'].rdef(peschema, seschema).cardinality = '?*'
                Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
                Societe.fetch_attrs = ('nom',)
                self.assertEqual(Personne.fetch_rql(user),
                                 'Any X,AA,AB,AC,AD ORDERBY AA WHERE X is_instance_of Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD')
                # testing relation with cardinality > 1
                peschema.subjrels['travaille'].rdef(peschema, seschema).cardinality = '**'
                self.assertEqual(Personne.fetch_rql(user),
                                 'Any X,AA,AB ORDERBY AA WHERE X is_instance_of Personne, X nom AA, X prenom AB')
                # XXX test unauthorized attribute
        finally:
            # fetch_attrs restored by generic tearDown
            for cm in torestore:
                cm.__exit__(None, None, None)

    def test_related_rql_base(self):
        Personne = self.vreg['etypes'].etype_class('Personne')
        Note = self.vreg['etypes'].etype_class('Note')
        SubNote = self.vreg['etypes'].etype_class('SubNote')
        self.assertTrue(issubclass(self.vreg['etypes'].etype_class('SubNote'), Note))
        Personne.fetch_attrs, Personne.cw_fetch_order = fetch_config(('nom', 'type'))
        Note.fetch_attrs, Note.cw_fetch_order = fetch_config(('type',))
        SubNote.fetch_attrs, SubNote.cw_fetch_order = fetch_config(('type',))
        with self.admin_access.web_request() as req:
            p = req.create_entity('Personne', nom=u'pouet')
            self.assertEqual(p.cw_related_rql('evaluee'),
                             'Any X,AA,AB ORDERBY AB WHERE E eid %(x)s, E evaluee X, '
                             'X modification_date AA, X type AB')
            n = req.create_entity('Note')
            self.assertEqual(n.cw_related_rql('evaluee', role='object',
                                              targettypes=('Societe', 'Personne')),
                             "Any X,AA ORDERBY AB DESC WHERE E eid %(x)s, X evaluee E, "
                             "X is IN(Personne, Societe), X nom AA, "
                             "X modification_date AB")
            Personne.fetch_attrs, Personne.cw_fetch_order = fetch_config(('nom', ))
            # XXX
            self.assertEqual(p.cw_related_rql('evaluee'),
                             'Any X,AA ORDERBY AA DESC '
                             'WHERE E eid %(x)s, E evaluee X, X modification_date AA')

            tag = self.vreg['etypes'].etype_class('Tag')(req)
            select = tag.cw_related_rqlst('tags', 'subject')
            self.assertEqual(select.as_string(),
                             'Any X,AA ORDERBY AA DESC '
                             'WHERE E eid %(x)s, E tags X, X modification_date AA')
            self.assertEqual(tag.cw_related_rql('tags', 'subject', ('Personne',)),
                             'Any X,AA,AB ORDERBY AB '
                             'WHERE E eid %(x)s, E tags X, X is Personne, X modification_date AA, '
                             'X nom AB')

    def test_related_rql_sort_terms(self):
        with self.admin_access.web_request() as req:
            tag = self.vreg['etypes'].etype_class('Tag')(req)
            select = tag.cw_related_rqlst('tags', 'subject',
                                          sort_terms=(('nom', True),
                                                      ('modification_date', False)))
            expected = (
                'Any X,AA ORDERBY AB,AA DESC '
                'WHERE E eid %(x)s, E tags X, X modification_date AA, X nom AB')
            self.assertEqual(select.as_string(), expected)

    def test_related_rql_ambiguous_cant_use_fetch_order(self):
        with self.admin_access.web_request() as req:
            tag = self.vreg['etypes'].etype_class('Tag')(req)
            for ttype in self.schema['tags'].objects():
                self.vreg['etypes'].etype_class(ttype).fetch_attrs = ('modification_date',)
            self.assertEqual(tag.cw_related_rql('tags', 'subject'),
                              'Any X,AA ORDERBY AA DESC '
                              'WHERE E eid %(x)s, E tags X, X modification_date AA')

    def test_related_rql_fetch_ambiguous_rtype(self):
        etvreg = self.vreg['etypes']
        soc_etype = etvreg.etype_class('Societe')
        with self.admin_access.web_request() as req:
            soc = soc_etype(req)
            soc_etype.fetch_attrs = ('fournit',)
            etvreg.etype_class('Service').fetch_attrs = ('fabrique_par',)
            etvreg.etype_class('Produit').fetch_attrs = ('fabrique_par',)
            etvreg.etype_class('Usine').fetch_attrs = ('lieu',)
            etvreg.etype_class('Personne').fetch_attrs = ('nom',)
            self.assertEqual(soc.cw_related_rql('fournit', 'subject'),
                             'Any X,A WHERE E eid %(x)s, E fournit X, X fabrique_par A')

    def test_unrelated_rql_security_1_manager(self):
        with self.admin_access.web_request() as req:
            user = req.user
            rql = user.cw_unrelated_rql('use_email', 'EmailAddress', 'subject')[0]
            self.assertEqual(rql,
                             'Any O,AA,AB,AC ORDERBY AC DESC '
                             'WHERE NOT A use_email O, S eid %(x)s, '
                             'O is_instance_of EmailAddress, O address AA, O alias AB, '
                             'O modification_date AC')

    def test_unrelated_rql_security_1_user(self):
        with self.admin_access.web_request() as req:
            self.create_user(req, 'toto')
        with self.new_access('toto').web_request() as req:
            user = req.user # XXX
            rql = user.cw_unrelated_rql('use_email', 'EmailAddress', 'subject')[0]
            self.assertEqual(rql,
                             'Any O,AA,AB,AC ORDERBY AC DESC '
                             'WHERE NOT A use_email O, S eid %(x)s, '
                             'O is_instance_of EmailAddress, O address AA, O alias AB, O modification_date AC')
            user = req.execute('Any X WHERE X login "admin"').get_entity(0, 0)
            rql = user.cw_unrelated_rql('use_email', 'EmailAddress', 'subject')[0]
            self.assertEqual(rql, 'Any O,AA,AB,AC ORDERBY AC DESC '
                             'WHERE NOT A use_email O, S eid %(x)s, '
                             'O is EmailAddress, O address AA, O alias AB, O modification_date AC, AD eid %(AE)s, '
                             'EXISTS(S identity AD, NOT AD in_group AF, AF name "guests", AF is CWGroup), A is CWUser')

    def test_unrelated_rql_security_1_anon(self):
        with self.new_access('anon').web_request() as req:
            user = req.user
            rql = user.cw_unrelated_rql('use_email', 'EmailAddress', 'subject')[0]
            self.assertEqual(rql, 'Any O,AA,AB,AC ORDERBY AC DESC '
                             'WHERE NOT A use_email O, S eid %(x)s, '
                             'O is EmailAddress, O address AA, O alias AB, O modification_date AC, AD eid %(AE)s, '
                             'EXISTS(S identity AD, NOT AD in_group AF, AF name "guests", AF is CWGroup), A is CWUser')

    def test_unrelated_rql_security_2(self):
        with self.admin_access.web_request() as req:
            email = req.execute('INSERT EmailAddress X: X address "hop"').get_entity(0, 0)
            rql = email.cw_unrelated_rql('use_email', 'CWUser', 'object')[0]
            self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AB '
                             'WHERE NOT S use_email O, O eid %(x)s, S is_instance_of CWUser, '
                             'S firstname AA, S login AB, S modification_date AC, S surname AD')
            req.cnx.commit()
        rperms = self.schema['EmailAddress'].permissions['read']
        clear_cache(self.schema['EmailAddress'], 'get_groups')
        clear_cache(self.schema['EmailAddress'], 'get_rqlexprs')
        self.schema['EmailAddress'].permissions['read'] = ('managers', 'users', 'guests',)
        try:
            with self.new_access('anon').web_request() as req:
                email = req.execute('Any X WHERE X eid %(x)s', {'x': email.eid}).get_entity(0, 0)
                rql = email.cw_unrelated_rql('use_email', 'CWUser', 'object')[0]
                self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AB '
                             'WHERE NOT S use_email O, O eid %(x)s, S is CWUser, '
                             'S firstname AA, S login AB, S modification_date AC, S surname AD, '
                             'AE eid %(AF)s, EXISTS(S identity AE, NOT AE in_group AG, AG name "guests", AG is CWGroup)')
        finally:
            clear_cache(self.schema['EmailAddress'], 'get_groups')
            clear_cache(self.schema['EmailAddress'], 'get_rqlexprs')
            self.schema['EmailAddress'].permissions['read'] = rperms

    def test_cw_linkable_rql(self):
        with self.admin_access.web_request() as req:
            email = req.execute('INSERT EmailAddress X: X address "hop"').get_entity(0, 0)
            rql = email.cw_linkable_rql('use_email', 'CWUser', 'object')[0]
            self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AB '
                             'WHERE O eid %(x)s, S is_instance_of CWUser, '
                             'S firstname AA, S login AB, S modification_date AC, S surname AD')

    def test_unrelated_rql_security_nonexistant(self):
        with self.new_access('anon').web_request() as req:
            email = self.vreg['etypes'].etype_class('EmailAddress')(req)
            rql = email.cw_unrelated_rql('use_email', 'CWUser', 'object')[0]
            self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AB '
                         'WHERE S is CWUser, '
                         'S firstname AA, S login AB, S modification_date AC, S surname AD, '
                         'AE eid %(AF)s, EXISTS(S identity AE, NOT AE in_group AG, AG name "guests", AG is CWGroup)')

    def test_unrelated_rql_constraints_creation_subject(self):
        with self.admin_access.web_request() as req:
            person = self.vreg['etypes'].etype_class('Personne')(req)
            rql = person.cw_unrelated_rql('connait', 'Personne', 'subject')[0]
            self.assertEqual(
            rql, 'Any O,AA,AB,AC ORDERBY AA DESC WHERE '
            'O is_instance_of Personne, O modification_date AA, O nom AB, O prenom AC')

    def test_unrelated_rql_constraints_creation_object(self):
        with self.admin_access.web_request() as req:
            person = self.vreg['etypes'].etype_class('Personne')(req)
            rql = person.cw_unrelated_rql('connait', 'Personne', 'object')[0]
            self.assertEqual(
            rql, 'Any S,AA,AB,AC ORDERBY AA DESC WHERE '
            'S is Personne, S modification_date AA, S nom AB, S prenom AC, '
            'NOT (S connait AD, AD nom "toto"), AD is Personne, '
            'EXISTS(S travaille AE, AE nom "tutu")')

    def test_unrelated_rql_security_rel_perms(self):
        '''check `connait` add permission has no effect for a new entity on the
        unrelated rql'''
        rdef = self.schema['Personne'].rdef('connait')
        perm_rrqle = RRQLExpression('U has_update_permission S')
        with self.temporary_permissions((rdef, {'add': (perm_rrqle,)})):
            with self.admin_access.web_request() as req:
                person = self.vreg['etypes'].etype_class('Personne')(req)
                rql = person.cw_unrelated_rql('connait', 'Personne', 'subject')[0]
                self.assertEqual(rql, 'Any O,AA,AB,AC ORDERBY AA DESC WHERE '
                         'O is_instance_of Personne, O modification_date AA, O nom AB, '
                         'O prenom AC')

    def test_unrelated_rql_constraints_edition_subject(self):
        with self.admin_access.web_request() as req:
            person = req.create_entity('Personne', nom=u'sylvain')
            rql = person.cw_unrelated_rql('connait', 'Personne', 'subject')[0]
            self.assertEqual(
                rql, 'Any O,AA,AB,AC ORDERBY AA DESC WHERE '
            'NOT S connait O, S eid %(x)s, O is Personne, '
            'O modification_date AA, O nom AB, O prenom AC, '
            'NOT S identity O')

    def test_unrelated_rql_constraints_edition_object(self):
        with self.admin_access.web_request() as req:
            person = req.create_entity('Personne', nom=u'sylvain')
            rql = person.cw_unrelated_rql('connait', 'Personne', 'object')[0]
            self.assertEqual(
            rql, 'Any S,AA,AB,AC ORDERBY AA DESC WHERE '
            'NOT S connait O, O eid %(x)s, S is Personne, '
            'S modification_date AA, S nom AB, S prenom AC, '
            'NOT S identity O, NOT (S connait AD, AD nom "toto"), '
            'EXISTS(S travaille AE, AE nom "tutu")')

    def test_unrelated_rql_s_linkto_s(self):
        with self.admin_access.web_request() as req:
            person = self.vreg['etypes'].etype_class('Personne')(req)
            self.vreg['etypes'].etype_class('Personne').fetch_attrs = ()
            soc = req.create_entity('Societe', nom=u'logilab')
            lt_infos = {('actionnaire', 'subject'): [soc.eid]}
            rql, args = person.cw_unrelated_rql('associe', 'Personne', 'subject',
                                            lt_infos=lt_infos)
            self.assertEqual(u'Any O ORDERBY O WHERE O is Personne, '
                             u'EXISTS(AA eid %(SOC)s, O actionnaire AA)', rql)
            self.assertEqual({'SOC': soc.eid}, args)

    def test_unrelated_rql_s_linkto_o(self):
        with self.admin_access.web_request() as req:
            person = self.vreg['etypes'].etype_class('Personne')(req)
            self.vreg['etypes'].etype_class('Societe').fetch_attrs = ()
            soc = req.create_entity('Societe', nom=u'logilab')
            lt_infos = {('contrat_exclusif', 'object'): [soc.eid]}
            rql, args = person.cw_unrelated_rql('actionnaire', 'Societe', 'subject',
                                                lt_infos=lt_infos)
            self.assertEqual(u'Any O ORDERBY O WHERE NOT A actionnaire O, '
                             u'O is_instance_of Societe, NOT EXISTS(O eid %(O)s), '
                             u'A is Personne', rql)
            self.assertEqual({'O': soc.eid}, args)

    def test_unrelated_rql_o_linkto_s(self):
        with self.admin_access.web_request() as req:
            soc = self.vreg['etypes'].etype_class('Societe')(req)
            self.vreg['etypes'].etype_class('Personne').fetch_attrs = ()
            person = req.create_entity('Personne', nom=u'florent')
            lt_infos = {('contrat_exclusif', 'subject'): [person.eid]}
            rql, args = soc.cw_unrelated_rql('actionnaire', 'Personne', 'object',
                                             lt_infos=lt_infos)
            self.assertEqual(u'Any S ORDERBY S WHERE NOT S actionnaire A, '
                             u'S is_instance_of Personne, NOT EXISTS(S eid %(S)s), '
                             u'A is Societe', rql)
            self.assertEqual({'S': person.eid}, args)

    def test_unrelated_rql_o_linkto_o(self):
        with self.admin_access.web_request() as req:
            soc = self.vreg['etypes'].etype_class('Societe')(req)
            self.vreg['etypes'].etype_class('Personne').fetch_attrs = ()
            person = req.create_entity('Personne', nom=u'florent')
            lt_infos = {('actionnaire', 'object'): [person.eid]}
            rql, args = soc.cw_unrelated_rql('dirige', 'Personne', 'object',
                                             lt_infos=lt_infos)
            self.assertEqual(u'Any S ORDERBY S WHERE NOT S dirige A, '
                             u'S is_instance_of Personne, EXISTS(S eid %(S)s), '
                             u'A is Societe', rql)
            self.assertEqual({'S': person.eid}, args)

    def test_unrelated_rql_s_linkto_s_no_info(self):
        with self.admin_access.web_request() as req:
            person = self.vreg['etypes'].etype_class('Personne')(req)
            self.vreg['etypes'].etype_class('Personne').fetch_attrs = ()
            soc = req.create_entity('Societe', nom=u'logilab')
            rql, args = person.cw_unrelated_rql('associe', 'Personne', 'subject')
            self.assertEqual(u'Any O ORDERBY O WHERE O is_instance_of Personne', rql)
            self.assertEqual({}, args)

    def test_unrelated_rql_s_linkto_s_unused_info(self):
        with self.admin_access.web_request() as req:
            person = self.vreg['etypes'].etype_class('Personne')(req)
            self.vreg['etypes'].etype_class('Personne').fetch_attrs = ()
            other_p = req.create_entity('Personne', nom=u'titi')
            lt_infos = {('dirige', 'subject'): [other_p.eid]}
            rql, args = person.cw_unrelated_rql('associe', 'Personne', 'subject',
                                                lt_infos=lt_infos)
            self.assertEqual(u'Any O ORDERBY O WHERE O is_instance_of Personne', rql)

    def test_unrelated_base(self):
        with self.admin_access.web_request() as req:
            p = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
            e = req.create_entity('Tag', name=u'x')
            related = [r.eid for r in e.tags]
            self.assertEqual(related, [])
            unrelated = [r[0] for r in e.unrelated('tags', 'Personne', 'subject')]
            self.assertIn(p.eid, unrelated)
            req.execute('SET X tags Y WHERE X is Tag, Y is Personne')
            e = req.execute('Any X WHERE X is Tag').get_entity(0, 0)
            unrelated = [r[0] for r in e.unrelated('tags', 'Personne', 'subject')]
            self.assertNotIn(p.eid, unrelated)

    def test_unrelated_limit(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Tag', name=u'x')
            req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
            req.create_entity('Personne', nom=u'thenault', prenom=u'sylvain')
            self.assertEqual(len(e.unrelated('tags', 'Personne', 'subject', limit=1)),
                              1)

    def test_unrelated_security(self):
        rperms = self.schema['EmailAddress'].permissions['read']
        clear_cache(self.schema['EmailAddress'], 'get_groups')
        clear_cache(self.schema['EmailAddress'], 'get_rqlexprs')
        self.schema['EmailAddress'].permissions['read'] = ('managers', 'users', 'guests',)
        try:
            with self.admin_access.web_request() as req:
                email = req.execute('INSERT EmailAddress X: X address "hop"').get_entity(0, 0)
                rset = email.unrelated('use_email', 'CWUser', 'object')
                self.assertEqual([x.login for x in rset.entities()], [u'admin', u'anon'])
                user = req.user
                rset = user.unrelated('use_email', 'EmailAddress', 'subject')
                self.assertEqual([x.address for x in rset.entities()], [u'hop'])
                self.create_user(req, 'toto')
            with self.new_access('toto').web_request() as req:
                email = req.execute('Any X WHERE X eid %(x)s', {'x': email.eid}).get_entity(0, 0)
                rset = email.unrelated('use_email', 'CWUser', 'object')
                self.assertEqual([x.login for x in rset.entities()], ['toto'])
                user = req.user
                rset = user.unrelated('use_email', 'EmailAddress', 'subject')
                self.assertEqual([x.address for x in rset.entities()], ['hop'])
                user = req.execute('Any X WHERE X login "admin"').get_entity(0, 0)
                rset = user.unrelated('use_email', 'EmailAddress', 'subject')
                self.assertEqual([x.address for x in rset.entities()], [])
            with self.new_access('anon').web_request() as req:
                email = req.execute('Any X WHERE X eid %(x)s', {'x': email.eid}).get_entity(0, 0)
                rset = email.unrelated('use_email', 'CWUser', 'object')
                self.assertEqual([x.login for x in rset.entities()], [])
                user = req.user
                rset = user.unrelated('use_email', 'EmailAddress', 'subject')
                self.assertEqual([x.address for x in rset.entities()], [])
        finally:
            clear_cache(self.schema['EmailAddress'], 'get_groups')
            clear_cache(self.schema['EmailAddress'], 'get_rqlexprs')
            self.schema['EmailAddress'].permissions['read'] = rperms

    def test_unrelated_new_entity(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            unrelated = [r[0] for r in e.unrelated('in_group', 'CWGroup', 'subject')]
            # should be default groups but owners, i.e. managers, users, guests
            self.assertEqual(len(unrelated), 3)

    def test_markdown_printable_value_string(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Card', title=u'rest markdown',
                                  content=u'This is [an example](http://example.com/ "Title") inline link`',
                                  content_format=u'text/markdown')
            self.assertEqual(
                u'<p>This is <a href="http://example.com/" '
                u'title="Title">an example</a> inline link`</p>',
                e.printable_value('content'))

    def test_printable_value_string(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Card', title=u'rest test',
                                  content=u'du :eid:`1:*ReST*`',
                                  content_format=u'text/rest')
            self.assertEqual(e.printable_value('content'),
                             '<p>du <a class="reference" href="http://testing.fr/cubicweb/cwsource/system">*ReST*</a></p>')
            e.cw_attr_cache['content'] = 'du <em>html</em> <ref rql="CWUser X">users</ref>'
            e.cw_attr_cache['content_format'] = 'text/html'
            self.assertEqual(e.printable_value('content'),
                              'du <em>html</em> <a href="http://testing.fr/cubicweb/view?rql=CWUser%20X">users</a>')
            e.cw_attr_cache['content'] = 'du *texte*'
            e.cw_attr_cache['content_format'] = 'text/plain'
            self.assertEqual(e.printable_value('content').replace("\n", ""),
                             '<p>du *texte*<br/></p>')
            e.cw_attr_cache['title'] = 'zou'
            e.cw_attr_cache['content'] = '''\
a title
=======
du :eid:`1:*ReST*`'''
            e.cw_attr_cache['content_format'] = 'text/rest'
            self.assertEqual(e.printable_value('content', format='text/plain'),
                              e.cw_attr_cache['content'])

            e.cw_attr_cache['content'] = u'<b>yo (zou éà ;)</b>'
            e.cw_attr_cache['content_format'] = 'text/html'
            self.assertEqual(e.printable_value('content', format='text/plain').strip(),
                             u'**yo (zou éà ;)**')
            if HAS_TAL:
                e.cw_attr_cache['content'] = '<h1 tal:content="self/title">titre</h1>'
                e.cw_attr_cache['content_format'] = 'text/cubicweb-page-template'
                self.assertEqual(e.printable_value('content'),
                                  '<h1>zou</h1>')


    def test_printable_value_bytes(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('FakeFile', data=Binary(b'lambda x: 1'), data_format=u'text/x-python',
                                  data_encoding=u'ascii', data_name=u'toto.py')
            from cubicweb import mttransforms
            if mttransforms.HAS_PYGMENTS_TRANSFORMS:
                import pygments
                if tuple(int(i) for i in pygments.__version__.split('.')[:3]) >= (2, 1, 1):
                    span = '<span/>'
                else:
                    span = ''
                if tuple(int(i) for i in pygments.__version__.split('.')[:2]) >= (1, 3):
                    mi = 'mi'
                else:
                    mi = 'mf'

                self.assertEqual(e.printable_value('data'),
                                 '''<div class="highlight"><pre>%s<span class="k">lambda</span> <span class="n">x</span><span class="p">:</span> <span class="%s">1</span>
</pre></div>''' % (span, mi))
            else:
                self.assertEqual(e.printable_value('data'),
                                  '''<pre class="python">
    <span style="color: #C00000;">lambda</span> <span style="color: #000000;">x</span><span style="color: #0000C0;">:</span> <span style="color: #0080C0;">1</span>
</pre>''')

            e = req.create_entity('FakeFile',
                                  data=Binary(u'*héhéhé*'.encode('utf-8')),
                                  data_format=u'text/rest',
                                  data_encoding=u'utf-8', data_name=u'toto.txt')
            self.assertEqual(e.printable_value('data'),
                              u'<p><em>héhéhé</em></p>')

    def test_printable_value_bad_html(self):
        """make sure we don't crash if we try to render invalid XHTML strings"""
        with self.admin_access.web_request() as req:
            e = req.create_entity('Card', title=u'bad html', content=u'<div>R&D<br>',
                                content_format=u'text/html')
            tidy = lambda x: x.replace('\n', '')
            self.assertEqual(tidy(e.printable_value('content')),
                              '<div>R&amp;D<br/></div>')
            e.cw_attr_cache['content'] = u'yo !! R&D <div> pas fermé'
            self.assertEqual(tidy(e.printable_value('content')),
                              u'yo !! R&amp;D <div> pas fermé</div>')
            e.cw_attr_cache['content'] = u'R&D'
            self.assertEqual(tidy(e.printable_value('content')), u'R&amp;D')
            e.cw_attr_cache['content'] = u'R&D;'
            self.assertEqual(tidy(e.printable_value('content')), u'R&amp;D;')
            e.cw_attr_cache['content'] = u'yo !! R&amp;D <div> pas fermé'
            self.assertEqual(tidy(e.printable_value('content')),
                             u'yo !! R&amp;D <div> pas fermé</div>')
            e.cw_attr_cache['content'] = u'été <div> été'
            self.assertEqual(tidy(e.printable_value('content')),
                             u'été <div> été</div>')
            e.cw_attr_cache['content'] = u'C&apos;est un exemple s&eacute;rieux'
            self.assertEqual(tidy(e.printable_value('content')),
                             u"C'est un exemple sérieux")
            # make sure valid xhtml is left untouched
            e.cw_attr_cache['content'] = u'<div>R&amp;D<br/></div>'
            self.assertEqual(e.printable_value('content'), e.cw_attr_cache['content'])
            e.cw_attr_cache['content'] = u'<div>été</div>'
            self.assertEqual(e.printable_value('content'), e.cw_attr_cache['content'])
            e.cw_attr_cache['content'] = u'été'
            self.assertEqual(e.printable_value('content'), e.cw_attr_cache['content'])
            e.cw_attr_cache['content'] = u'hop\r\nhop\nhip\rmomo'
            self.assertEqual(e.printable_value('content'), u'hop\nhop\nhip\nmomo')

    def test_printable_value_bad_html_ms(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Card', title=u'bad html', content=u'<div>R&D<br>',
                                content_format=u'text/html')
            tidy = lambda x: x.replace('\n', '')
            e.cw_attr_cache['content'] = u'<div x:foo="bar">ms orifice produces weird html</div>'
            # Caution! current implementation of soup2xhtml strips first div element
            content = soup2xhtml(e.printable_value('content'), 'utf-8')
            self.assertMultiLineEqual(content, u'<div>ms orifice produces weird html</div>')

    def test_fulltextindex(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('FakeFile')(req)
            e.cw_attr_cache['description'] = 'du <em>html</em>'
            e.cw_attr_cache['description_format'] = 'text/html'
            e.cw_attr_cache['data'] = Binary(b'some <em>data</em>')
            e.cw_attr_cache['data_name'] = 'an html file'
            e.cw_attr_cache['data_format'] = 'text/html'
            e.cw_attr_cache['data_encoding'] = 'ascii'
            e._cw.transaction_data.clear()
            words = e.cw_adapt_to('IFTIndexable').get_words()
            words['C'].sort()
            self.assertEqual({'C': sorted(['an', 'html', 'file', 'du', 'html', 'some', 'data'])},
                             words)


    def test_nonregr_relation_cache(self):
        with self.admin_access.web_request() as req:
            p1 = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
            p2 = req.create_entity('Personne', nom=u'toto')
            req.execute('SET X evaluee Y WHERE X nom "di mascio", Y nom "toto"')
            self.assertEqual(p1.evaluee[0].nom, "toto")
            self.assertFalse(p1.reverse_evaluee)

    def test_complete_relation(self):
        with self.admin_access.repo_cnx() as cnx:
            eid = cnx.execute(
                'INSERT TrInfo X: X comment "zou", X wf_info_for U, X from_state S1, X to_state S2 '
                'WHERE U login "admin", S1 name "activated", S2 name "deactivated"')[0][0]
            trinfo = cnx.execute('Any X WHERE X eid %(x)s', {'x': eid}).get_entity(0, 0)
            trinfo.complete()
            self.assertIsInstance(trinfo.cw_attr_cache['creation_date'], datetime)
            self.assertTrue(trinfo.cw_relation_cached('from_state', 'subject'))
            self.assertTrue(trinfo.cw_relation_cached('to_state', 'subject'))
            self.assertTrue(trinfo.cw_relation_cached('wf_info_for', 'subject'))
            self.assertEqual(trinfo.by_transition, ())

    def test_request_cache(self):
        with self.admin_access.web_request() as req:
            user = req.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)
            state = user.in_state[0]
            samestate = req.execute('State X WHERE X name "activated"').get_entity(0, 0)
            self.assertIs(state, samestate)

    def test_rest_path(self):
        with self.admin_access.web_request() as req:
            note = req.create_entity('Note', type=u'z')
            self.assertEqual(note.rest_path(), 'note/%s' % note.eid)
            # unique attr
            tag = req.create_entity('Tag', name=u'x')
            self.assertEqual(tag.rest_path(), 'tag/x')
            # test explicit rest_attr
            person = req.create_entity('Personne', prenom=u'john', nom=u'doe')
            self.assertEqual(person.rest_path(), 'personne/doe')
            # ambiguity test
            person2 = req.create_entity('Personne', prenom=u'remi', nom=u'doe')
            person.cw_clear_all_caches()
            self.assertEqual(person.rest_path(), str(person.eid))
            self.assertEqual(person2.rest_path(), str(person2.eid))
            # unique attr with None value (nom in this case)
            friend = req.create_entity('Ami', prenom=u'bob')
            self.assertEqual(friend.rest_path(), str(friend.eid))
            # 'ref' below is created without the unique but not required
            # attribute, make sur that the unique _and_ required 'ean' is used
            # as the rest attribute
            ref = req.create_entity('Reference', ean=u'42-1337-42')
            self.assertEqual(ref.rest_path(), 'reference/42-1337-42')

    def test_can_use_rest_path(self):
        self.assertTrue(can_use_rest_path(u'zobi'))
        # don't use rest if we have /, ? or & in the path (breaks mod_proxy)
        self.assertFalse(can_use_rest_path(u'zo/bi'))
        self.assertFalse(can_use_rest_path(u'zo&bi'))
        self.assertFalse(can_use_rest_path(u'zo?bi'))

    def test_cw_set_attributes(self):
        with self.admin_access.web_request() as req:
            person = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
            self.assertEqual(person.prenom, u'adrien')
            self.assertEqual(person.nom, u'di mascio')
            person.cw_set(prenom=u'sylvain', nom=u'thénault')
            person = req.execute('Personne P').get_entity(0, 0) # XXX retreival needed ?
            self.assertEqual(person.prenom, u'sylvain')
            self.assertEqual(person.nom, u'thénault')

    def test_cw_set_relations(self):
        with self.admin_access.web_request() as req:
            person = req.create_entity('Personne', nom=u'chauvat', prenom=u'nicolas')
            note = req.create_entity('Note', type=u'x')
            note.cw_set(ecrit_par=person)
            note = req.create_entity('Note', type=u'y')
            note.cw_set(ecrit_par=person.eid)
            self.assertEqual(len(person.reverse_ecrit_par), 2)

    def test_absolute_url_empty_field(self):
        with self.admin_access.web_request() as req:
            card = req.create_entity('Card', wikiid=u'', title=u'test')
            self.assertEqual(card.absolute_url(),
                              'http://testing.fr/cubicweb/%s' % card.eid)

    def test_create_and_compare_entity(self):
        access = self.admin_access
        with access.web_request() as req:
            p1 = req.create_entity('Personne', nom=u'fayolle', prenom=u'alexandre')
            p2 = req.create_entity('Personne', nom=u'campeas', prenom=u'aurelien')
            note = req.create_entity('Note', type=u'z')
            p = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien',
                                  connait=p1, evaluee=[p1, p2],
                                  reverse_ecrit_par=note)
            self.assertEqual(p.nom, 'di mascio')
            self.assertEqual([c.nom for c in p.connait], ['fayolle'])
            self.assertEqual(sorted([c.nom for c in p.evaluee]), ['campeas', 'fayolle'])
            self.assertEqual([c.type for c in p.reverse_ecrit_par], ['z'])
            req.cnx.commit()
        with access.web_request() as req:
            auc = req.execute('Personne P WHERE P prenom "aurelien"').get_entity(0,0)
            persons = set()
            persons.add(p1)
            persons.add(p2)
            persons.add(auc)
            self.assertEqual(2, len(persons))
            self.assertNotEqual(p1, p2)
            self.assertEqual(p2, auc)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
