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
"""unit tests for cubicweb.web.views.entities module"""

from datetime import datetime

from cubicweb import Binary, Unauthorized
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.mttransforms import HAS_TAL
from cubicweb.entities import fetch_config

class EntityTC(CubicWebTC):

    def test_boolean_value(self):
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        self.failUnless(e)

    def test_yams_inheritance(self):
        from entities import Note
        e = self.vreg['etypes'].etype_class('SubNote')(self.request())
        self.assertIsInstance(e, Note)
        e2 = self.vreg['etypes'].etype_class('SubNote')(self.request())
        self.assertIs(e.__class__, e2.__class__)

    def test_has_eid(self):
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        self.assertEqual(e.eid, None)
        self.assertEqual(e.has_eid(), False)
        e.eid = 'X'
        self.assertEqual(e.has_eid(), False)
        e.eid = 0
        self.assertEqual(e.has_eid(), True)
        e.eid = 2
        self.assertEqual(e.has_eid(), True)

    def test_copy(self):
        req = self.request()
        req.create_entity('Tag', name=u'x')
        p = req.create_entity('Personne', nom=u'toto')
        oe = req.create_entity('Note', type=u'x')
        self.execute('SET T ecrit_par U WHERE T eid %(t)s, U eid %(u)s',
                     {'t': oe.eid, 'u': p.eid})
        self.execute('SET TAG tags X WHERE X eid %(x)s', {'x': oe.eid})
        e = req.create_entity('Note', type=u'z')
        e.copy_relations(oe.eid)
        self.assertEqual(len(e.ecrit_par), 1)
        self.assertEqual(e.ecrit_par[0].eid, p.eid)
        self.assertEqual(len(e.reverse_tags), 1)
        # check meta-relations are not copied, set on commit
        self.assertEqual(len(e.created_by), 0)

    def test_copy_with_nonmeta_composite_inlined(self):
        req = self.request()
        p = req.create_entity('Personne', nom=u'toto')
        oe = req.create_entity('Note', type=u'x')
        self.schema['ecrit_par'].rdef('Note', 'Personne').composite = 'subject'
        self.execute('SET T ecrit_par U WHERE T eid %(t)s, U eid %(u)s',
                     {'t': oe.eid, 'u': p.eid})
        e = req.create_entity('Note', type=u'z')
        e.copy_relations(oe.eid)
        self.failIf(e.ecrit_par)
        self.failUnless(oe.ecrit_par)

    def test_copy_with_composite(self):
        user = self.user()
        adeleid = self.execute('INSERT EmailAddress X: X address "toto@logilab.org", U use_email X WHERE U login "admin"')[0][0]
        e = self.execute('Any X WHERE X eid %(x)s', {'x': user.eid}).get_entity(0, 0)
        self.assertEqual(e.use_email[0].address, "toto@logilab.org")
        self.assertEqual(e.use_email[0].eid, adeleid)
        usereid = self.execute('INSERT CWUser X: X login "toto", X upassword "toto", X in_group G '
                               'WHERE G name "users"')[0][0]
        e = self.execute('Any X WHERE X eid %(x)s', {'x': usereid}).get_entity(0, 0)
        e.copy_relations(user.eid)
        self.failIf(e.use_email)
        self.failIf(e.primary_email)

    def test_copy_with_non_initial_state(self):
        user = self.user()
        user = self.execute('INSERT CWUser X: X login "toto", X upassword %(pwd)s, X in_group G WHERE G name "users"',
                           {'pwd': 'toto'}).get_entity(0, 0)
        self.commit()
        user.cw_adapt_to('IWorkflowable').fire_transition('deactivate')
        self.commit()
        eid2 = self.execute('INSERT CWUser X: X login "tutu", X upassword %(pwd)s', {'pwd': 'toto'})[0][0]
        e = self.execute('Any X WHERE X eid %(x)s', {'x': eid2}).get_entity(0, 0)
        e.copy_relations(user.eid)
        self.commit()
        e.cw_clear_relation_cache('in_state', 'subject')
        self.assertEqual(e.cw_adapt_to('IWorkflowable').state, 'activated')

    def test_related_cache_both(self):
        user = self.execute('Any X WHERE X eid %(x)s', {'x':self.user().eid}).get_entity(0, 0)
        adeleid = self.execute('INSERT EmailAddress X: X address "toto@logilab.org", U use_email X WHERE U login "admin"')[0][0]
        self.commit()
        self.assertEqual(user._cw_related_cache, {})
        email = user.primary_email[0]
        self.assertEqual(sorted(user._cw_related_cache), ['primary_email_subject'])
        self.assertEqual(email._cw_related_cache.keys(), ['primary_email_object'])
        groups = user.in_group
        self.assertEqual(sorted(user._cw_related_cache), ['in_group_subject', 'primary_email_subject'])
        for group in groups:
            self.failIf('in_group_subject' in group._cw_related_cache, group._cw_related_cache.keys())

    def test_related_limit(self):
        req = self.request()
        p = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        for tag in u'abcd':
            req.create_entity('Tag', name=tag)
        self.execute('SET X tags Y WHERE X is Tag, Y is Personne')
        self.assertEqual(len(p.related('tags', 'object', limit=2)), 2)
        self.assertEqual(len(p.related('tags', 'object')), 4)


    def test_fetch_rql(self):
        user = self.user()
        Personne = self.vreg['etypes'].etype_class('Personne')
        Societe = self.vreg['etypes'].etype_class('Societe')
        Note = self.vreg['etypes'].etype_class('Note')
        peschema = Personne.e_schema
        seschema = Societe.e_schema
        peschema.subjrels['travaille'].rdef(peschema, seschema).cardinality = '1*'
        peschema.subjrels['connait'].rdef(peschema, peschema).cardinality = '11'
        peschema.subjrels['evaluee'].rdef(peschema, Note.e_schema).cardinality = '1*'
        seschema.subjrels['evaluee'].rdef(seschema, Note.e_schema).cardinality = '1*'
        # testing basic fetch_attrs attribute
        self.assertEqual(Personne.fetch_rql(user),
                          'Any X,AA,AB,AC ORDERBY AA ASC '
                          'WHERE X is Personne, X nom AA, X prenom AB, X modification_date AC')
        pfetch_attrs = Personne.fetch_attrs
        sfetch_attrs = Societe.fetch_attrs
        try:
            # testing unknown attributes
            Personne.fetch_attrs = ('bloug', 'beep')
            self.assertEqual(Personne.fetch_rql(user), 'Any X WHERE X is Personne')
            # testing one non final relation
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
            self.assertEqual(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD ORDERBY AA ASC '
                              'WHERE X is Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD')
            # testing two non final relations
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille', 'evaluee')
            self.assertEqual(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD,AE,AF ORDERBY AA ASC,AF DESC '
                              'WHERE X is Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD, '
                              'X evaluee AE?, AE modification_date AF')
            # testing one non final relation with recursion
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
            Societe.fetch_attrs = ('nom', 'evaluee')
            self.assertEqual(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD,AE,AF ORDERBY AA ASC,AF DESC '
                              'WHERE X is Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD, '
                              'AC evaluee AE?, AE modification_date AF'
                              )
            # testing symmetric relation
            Personne.fetch_attrs = ('nom', 'connait')
            self.assertEqual(Personne.fetch_rql(user), 'Any X,AA,AB ORDERBY AA ASC '
                              'WHERE X is Personne, X nom AA, X connait AB?')
            # testing optional relation
            peschema.subjrels['travaille'].rdef(peschema, seschema).cardinality = '?*'
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
            Societe.fetch_attrs = ('nom',)
            self.assertEqual(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD ORDERBY AA ASC WHERE X is Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD')
            # testing relation with cardinality > 1
            peschema.subjrels['travaille'].rdef(peschema, seschema).cardinality = '**'
            self.assertEqual(Personne.fetch_rql(user),
                              'Any X,AA,AB ORDERBY AA ASC WHERE X is Personne, X nom AA, X prenom AB')
            # XXX test unauthorized attribute
        finally:
            Personne.fetch_attrs = pfetch_attrs
            Societe.fetch_attrs = sfetch_attrs

    def test_related_rql_base(self):
        Personne = self.vreg['etypes'].etype_class('Personne')
        Note = self.vreg['etypes'].etype_class('Note')
        SubNote = self.vreg['etypes'].etype_class('SubNote')
        self.failUnless(issubclass(self.vreg['etypes'].etype_class('SubNote'), Note))
        Personne.fetch_attrs, Personne.fetch_order = fetch_config(('nom', 'type'))
        Note.fetch_attrs, Note.fetch_order = fetch_config(('type',))
        SubNote.fetch_attrs, SubNote.fetch_order = fetch_config(('type',))
        p = self.request().create_entity('Personne', nom=u'pouet')
        self.assertEqual(p.cw_related_rql('evaluee'),
                          'Any X,AA,AB ORDERBY AA ASC WHERE E eid %(x)s, E evaluee X, '
                          'X type AA, X modification_date AB')
        Personne.fetch_attrs, Personne.fetch_order = fetch_config(('nom', ))
        # XXX
        self.assertEqual(p.cw_related_rql('evaluee'),
                          'Any X,AA ORDERBY AA DESC '
                          'WHERE E eid %(x)s, E evaluee X, X modification_date AA')

        tag = self.vreg['etypes'].etype_class('Tag')(self.request())
        self.assertEqual(tag.cw_related_rql('tags', 'subject'),
                          'Any X,AA ORDERBY AA DESC '
                          'WHERE E eid %(x)s, E tags X, X modification_date AA')
        self.assertEqual(tag.cw_related_rql('tags', 'subject', ('Personne',)),
                          'Any X,AA,AB ORDERBY AA ASC '
                          'WHERE E eid %(x)s, E tags X, X is IN (Personne), X nom AA, '
                          'X modification_date AB')

    def test_related_rql_ambigous_cant_use_fetch_order(self):
        tag = self.vreg['etypes'].etype_class('Tag')(self.request())
        for ttype in self.schema['tags'].objects():
            self.vreg['etypes'].etype_class(ttype).fetch_attrs = ('modification_date',)
        self.assertEqual(tag.cw_related_rql('tags', 'subject'),
                          'Any X,AA ORDERBY AA DESC '
                          'WHERE E eid %(x)s, E tags X, X modification_date AA')

    def test_unrelated_rql_security_1(self):
        user = self.request().user
        rql = user.cw_unrelated_rql('use_email', 'EmailAddress', 'subject')[0]
        self.assertEqual(rql, 'Any O,AA,AB,AC ORDERBY AC DESC '
                          'WHERE NOT S use_email O, S eid %(x)s, O is EmailAddress, O address AA, O alias AB, O modification_date AC')
        self.create_user('toto')
        self.login('toto')
        user = self.request().user
        rql = user.cw_unrelated_rql('use_email', 'EmailAddress', 'subject')[0]
        self.assertEqual(rql, 'Any O,AA,AB,AC ORDERBY AC DESC '
                          'WHERE NOT S use_email O, S eid %(x)s, O is EmailAddress, O address AA, O alias AB, O modification_date AC')
        user = self.execute('Any X WHERE X login "admin"').get_entity(0, 0)
        self.assertRaises(Unauthorized, user.cw_unrelated_rql, 'use_email', 'EmailAddress', 'subject')
        self.login('anon')
        user = self.request().user
        self.assertRaises(Unauthorized, user.cw_unrelated_rql, 'use_email', 'EmailAddress', 'subject')

    def test_unrelated_rql_security_2(self):
        email = self.execute('INSERT EmailAddress X: X address "hop"').get_entity(0, 0)
        rql = email.cw_unrelated_rql('use_email', 'CWUser', 'object')[0]
        self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AA ASC '
                          'WHERE NOT S use_email O, O eid %(x)s, S is CWUser, S login AA, S firstname AB, S surname AC, S modification_date AD')
        #rql = email.cw_unrelated_rql('use_email', 'Person', 'object')[0]
        #self.assertEqual(rql, '')
        self.login('anon')
        email = self.execute('Any X WHERE X eid %(x)s', {'x': email.eid}).get_entity(0, 0)
        rql = email.cw_unrelated_rql('use_email', 'CWUser', 'object')[0]
        self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AA '
                          'WHERE NOT EXISTS(S use_email O), O eid %(x)s, S is CWUser, S login AA, S firstname AB, S surname AC, S modification_date AD, '
                          'A eid %(B)s, EXISTS(S identity A, NOT A in_group C, C name "guests", C is CWGroup)')
        #rql = email.cw_unrelated_rql('use_email', 'Person', 'object')[0]
        #self.assertEqual(rql, '')

    def test_unrelated_rql_security_nonexistant(self):
        self.login('anon')
        email = self.vreg['etypes'].etype_class('EmailAddress')(self.request())
        rql = email.cw_unrelated_rql('use_email', 'CWUser', 'object')[0]
        self.assertEqual(rql, 'Any S,AA,AB,AC,AD ORDERBY AA '
                          'WHERE S is CWUser, S login AA, S firstname AB, S surname AC, S modification_date AD, '
                          'A eid %(B)s, EXISTS(S identity A, NOT A in_group C, C name "guests", C is CWGroup)')

    def test_unrelated_base(self):
        req = self.request()
        p = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        e = req.create_entity('Tag', name=u'x')
        related = [r.eid for r in e.tags]
        self.failUnlessEqual(related, [])
        unrelated = [r[0] for r in e.unrelated('tags', 'Personne', 'subject')]
        self.failUnless(p.eid in unrelated)
        self.execute('SET X tags Y WHERE X is Tag, Y is Personne')
        e = self.execute('Any X WHERE X is Tag').get_entity(0, 0)
        unrelated = [r[0] for r in e.unrelated('tags', 'Personne', 'subject')]
        self.failIf(p.eid in unrelated)

    def test_unrelated_limit(self):
        req = self.request()
        e = req.create_entity('Tag', name=u'x')
        req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        req.create_entity('Personne', nom=u'thenault', prenom=u'sylvain')
        self.assertEqual(len(e.unrelated('tags', 'Personne', 'subject', limit=1)),
                          1)

    def test_unrelated_security(self):
        email = self.execute('INSERT EmailAddress X: X address "hop"').get_entity(0, 0)
        rset = email.unrelated('use_email', 'CWUser', 'object')
        self.assertEqual([x.login for x in rset.entities()], [u'admin', u'anon'])
        user = self.request().user
        rset = user.unrelated('use_email', 'EmailAddress', 'subject')
        self.assertEqual([x.address for x in rset.entities()], [u'hop'])
        self.create_user('toto')
        self.login('toto')
        email = self.execute('Any X WHERE X eid %(x)s', {'x': email.eid}).get_entity(0, 0)
        rset = email.unrelated('use_email', 'CWUser', 'object')
        self.assertEqual([x.login for x in rset.entities()], ['toto'])
        user = self.request().user
        rset = user.unrelated('use_email', 'EmailAddress', 'subject')
        self.assertEqual([x.address for x in rset.entities()], ['hop'])
        user = self.execute('Any X WHERE X login "admin"').get_entity(0, 0)
        rset = user.unrelated('use_email', 'EmailAddress', 'subject')
        self.assertEqual([x.address for x in rset.entities()], [])
        self.login('anon')
        email = self.execute('Any X WHERE X eid %(x)s', {'x': email.eid}).get_entity(0, 0)
        rset = email.unrelated('use_email', 'CWUser', 'object')
        self.assertEqual([x.login for x in rset.entities()], [])
        user = self.request().user
        rset = user.unrelated('use_email', 'EmailAddress', 'subject')
        self.assertEqual([x.address for x in rset.entities()], [])

    def test_unrelated_new_entity(self):
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        unrelated = [r[0] for r in e.unrelated('in_group', 'CWGroup', 'subject')]
        # should be default groups but owners, i.e. managers, users, guests
        self.assertEqual(len(unrelated), 3)

    def test_printable_value_string(self):
        e = self.request().create_entity('Card', title=u'rest test', content=u'du :eid:`1:*ReST*`',
                                         content_format=u'text/rest')
        self.assertEqual(e.printable_value('content'),
                         '<p>du <a class="reference" href="http://testing.fr/cubicweb/cwsource/system">*ReST*</a></p>\n')
        e.cw_attr_cache['content'] = 'du <em>html</em> <ref rql="CWUser X">users</ref>'
        e.cw_attr_cache['content_format'] = 'text/html'
        self.assertEqual(e.printable_value('content'),
                          'du <em>html</em> <a href="http://testing.fr/cubicweb/view?rql=CWUser%20X">users</a>')
        e.cw_attr_cache['content'] = 'du *texte*'
        e.cw_attr_cache['content_format'] = 'text/plain'
        self.assertEqual(e.printable_value('content'),
                          '<p>\ndu *texte*<br/>\n</p>')
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
        req = self.request()
        e = req.create_entity('File', data=Binary('lambda x: 1'), data_format=u'text/x-python',
                            data_encoding=u'ascii', data_name=u'toto.py')
        from cubicweb import mttransforms
        if mttransforms.HAS_PYGMENTS_TRANSFORMS:
            import pygments
            if tuple(int(i) for i in pygments.__version__.split('.')[:2]) >= (1, 3):
                self.assertEqual(e.printable_value('data'),
                                  '''<div class="highlight"><pre><span class="k">lambda</span> <span class="n">x</span><span class="p">:</span> <span class="mi">1</span>
</pre></div>
''')
            else:
                self.assertEqual(e.printable_value('data'),
                                  '''<div class="highlight"><pre><span class="k">lambda</span> <span class="n">x</span><span class="p">:</span> <span class="mf">1</span>
</pre></div>
''')
        else:
            self.assertEqual(e.printable_value('data'),
                              '''<pre class="python">
<span style="color: #C00000;">lambda</span> <span style="color: #000000;">x</span><span style="color: #0000C0;">:</span> <span style="color: #0080C0;">1</span>
</pre>
''')

        e = req.create_entity('File', data=Binary('*héhéhé*'), data_format=u'text/rest',
                            data_encoding=u'utf-8', data_name=u'toto.txt')
        self.assertEqual(e.printable_value('data'),
                          u'<p><em>héhéhé</em></p>\n')

    def test_printable_value_bad_html(self):
        """make sure we don't crash if we try to render invalid XHTML strings"""
        req = self.request()
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
        self.skipTest('fix soup2xhtml to handle this test')
        req = self.request()
        e = req.create_entity('Card', title=u'bad html', content=u'<div>R&D<br>',
                            content_format=u'text/html')
        tidy = lambda x: x.replace('\n', '')
        e.cw_attr_cache['content'] = u'<div x:foo="bar">ms orifice produces weird html</div>'
        self.assertEqual(tidy(e.printable_value('content')),
                          u'<div>ms orifice produces weird html</div>')
        import tidy as tidymod # apt-get install python-tidy
        tidy = lambda x: str(tidymod.parseString(x.encode('utf-8'),
                                                 **{'drop_proprietary_attributes': True,
                                                    'output_xhtml': True,
                                                    'show_body_only' : True,
                                                    'quote-nbsp' : False,
                                                    'char_encoding' : 'utf8'})).decode('utf-8').strip()
        self.assertEqual(tidy(e.printable_value('content')),
                          u'<div>ms orifice produces weird html</div>')


    def test_fulltextindex(self):
        e = self.vreg['etypes'].etype_class('File')(self.request())
        e.cw_attr_cache['description'] = 'du <em>html</em>'
        e.cw_attr_cache['description_format'] = 'text/html'
        e.cw_attr_cache['data'] = Binary('some <em>data</em>')
        e.cw_attr_cache['data_name'] = 'an html file'
        e.cw_attr_cache['data_format'] = 'text/html'
        e.cw_attr_cache['data_encoding'] = 'ascii'
        e._cw.transaction_data = {} # XXX req should be a session
        self.assertEqual(e.cw_adapt_to('IFTIndexable').get_words(),
                          {'C': ['an', 'html', 'file', 'du', 'html', 'some', 'data']})


    def test_nonregr_relation_cache(self):
        req = self.request()
        p1 = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        p2 = req.create_entity('Personne', nom=u'toto')
        self.execute('SET X evaluee Y WHERE X nom "di mascio", Y nom "toto"')
        self.assertEqual(p1.evaluee[0].nom, "toto")
        self.failUnless(not p1.reverse_evaluee)

    def test_complete_relation(self):
        session = self.session
        eid = session.execute(
            'INSERT TrInfo X: X comment "zou", X wf_info_for U, X from_state S1, X to_state S2 '
            'WHERE U login "admin", S1 name "activated", S2 name "deactivated"')[0][0]
        trinfo = self.execute('Any X WHERE X eid %(x)s', {'x': eid}).get_entity(0, 0)
        trinfo.complete()
        self.failUnless(isinstance(trinfo.cw_attr_cache['creation_date'], datetime))
        self.failUnless(trinfo.cw_relation_cached('from_state', 'subject'))
        self.failUnless(trinfo.cw_relation_cached('to_state', 'subject'))
        self.failUnless(trinfo.cw_relation_cached('wf_info_for', 'subject'))
        self.assertEqual(trinfo.by_transition, ())

    def test_request_cache(self):
        req = self.request()
        user = self.execute('CWUser X WHERE X login "admin"', req=req).get_entity(0, 0)
        state = user.in_state[0]
        samestate = self.execute('State X WHERE X name "activated"', req=req).get_entity(0, 0)
        self.failUnless(state is samestate)

    def test_rest_path(self):
        req = self.request()
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
        person.clear_all_caches()
        self.assertEqual(person.rest_path(), 'personne/eid/%s' % person.eid)
        self.assertEqual(person2.rest_path(), 'personne/eid/%s' % person2.eid)
        # unique attr with None value (wikiid in this case)
        card1 = req.create_entity('Card', title=u'hop')
        self.assertEqual(card1.rest_path(), 'card/eid/%s' % card1.eid)
        # don't use rest if we have /, ? or & in the path (breaks mod_proxy)
        card2 = req.create_entity('Card', title=u'pod', wikiid=u'zo/bi')
        self.assertEqual(card2.rest_path(), 'card/eid/%d' % card2.eid)
        card3 = req.create_entity('Card', title=u'pod', wikiid=u'zo&bi')
        self.assertEqual(card3.rest_path(), 'card/eid/%d' % card3.eid)
        card4 = req.create_entity('Card', title=u'pod', wikiid=u'zo?bi')
        self.assertEqual(card4.rest_path(), 'card/eid/%d' % card4.eid)


    def test_set_attributes(self):
        req = self.request()
        person = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        self.assertEqual(person.prenom, u'adrien')
        self.assertEqual(person.nom, u'di mascio')
        person.set_attributes(prenom=u'sylvain', nom=u'thénault')
        person = self.execute('Personne P').get_entity(0, 0) # XXX retreival needed ?
        self.assertEqual(person.prenom, u'sylvain')
        self.assertEqual(person.nom, u'thénault')

    def test_metainformation_and_external_absolute_url(self):
        req = self.request()
        note = req.create_entity('Note', type=u'z')
        metainf = note.cw_metainformation()
        self.assertEqual(metainf, {'source': {'type': 'native', 'uri': 'system'}, 'type': u'Note', 'extid': None})
        self.assertEqual(note.absolute_url(), 'http://testing.fr/cubicweb/note/%s' % note.eid)
        metainf['source'] = metainf['source'].copy()
        metainf['source']['base-url']  = 'http://cubicweb2.com/'
        metainf['extid']  = 1234
        self.assertEqual(note.absolute_url(), 'http://cubicweb2.com/note/1234')

    def test_absolute_url_empty_field(self):
        req = self.request()
        card = req.create_entity('Card', wikiid=u'', title=u'test')
        self.assertEqual(card.absolute_url(),
                          'http://testing.fr/cubicweb/card/eid/%s' % card.eid)

    def test_create_entity(self):
        req = self.request()
        p1 = req.create_entity('Personne', nom=u'fayolle', prenom=u'alexandre')
        p2 = req.create_entity('Personne', nom=u'campeas', prenom=u'aurelien')
        note = req.create_entity('Note', type=u'z')
        req = self.request()
        p = req.create_entity('Personne', nom=u'di mascio', prenom=u'adrien',
                              connait=p1, evaluee=[p1, p2],
                              reverse_ecrit_par=note)
        self.assertEqual(p.nom, 'di mascio')
        self.assertEqual([c.nom for c in p.connait], ['fayolle'])
        self.assertEqual(sorted([c.nom for c in p.evaluee]), ['campeas', 'fayolle'])
        self.assertEqual([c.type for c in p.reverse_ecrit_par], ['z'])



if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()

