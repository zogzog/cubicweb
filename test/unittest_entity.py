# -*- coding: utf-8 -*-
"""unit tests for cubicweb.web.views.entities module"""

from cubicweb.devtools.apptest import EnvBasedTC

from mx.DateTime import DateTimeType, now
from cubicweb import Binary

class EntityTC(EnvBasedTC):

##     def setup_database(self):
##         self.add_entity('Personne', nom=u'di mascio', prenom=u'adrien')
##         self.add_entity('Task', title=u'fait ca !', description=u'et plus vite', start=now())
##         self.add_entity('Tag', name=u'x')
##         self.add_entity('Link', title=u'perdu', url=u'http://www.perdu.com',
##                         embed=False)
    
    def test_boolean_value(self):
        e = self.etype_instance('Tag')
        self.failUnless(e)

    def test_yams_inheritance(self):
        from entities import AnotherNote
        e = self.etype_instance('SubNote')
        self.assertIsInstance(e, AnotherNote)
        e2 = self.etype_instance('SubNote')
        self.assertIs(e.__class__, e2.__class__)

    def test_has_eid(self):
        e = self.etype_instance('Tag')
        self.assertEquals(e.eid, None)
        self.assertEquals(e.has_eid(), False)
        e.eid = 'X'
        self.assertEquals(e.has_eid(), False)
        e.eid = 0
        self.assertEquals(e.has_eid(), True)
        e.eid = 2
        self.assertEquals(e.has_eid(), True)
        
    def test_copy(self):
        self.add_entity('Tag', name=u'x')
        p = self.add_entity('Personne', nom=u'toto')
        oe = self.add_entity('Note', type=u'x')
        self.execute('SET T ecrit_par U WHERE T eid %(t)s, U eid %(u)s',
                     {'t': oe.eid, 'u': p.eid}, ('t','u'))
        self.execute('SET TAG tags X WHERE X eid %(x)s', {'x': oe.eid}, 'x')
        e = self.add_entity('Note', type=u'z')
        e.copy_relations(oe.eid)
        self.assertEquals(len(e.ecrit_par), 1)
        self.assertEquals(e.ecrit_par[0].eid, p.eid)
        self.assertEquals(len(e.reverse_tags), 0)
        
    def test_copy_with_nonmeta_composite_inlined(self):
        p = self.add_entity('Personne', nom=u'toto')
        oe = self.add_entity('Note', type=u'x')
        self.schema['ecrit_par'].set_rproperty('Note', 'Personne', 'composite', 'subject')
        self.execute('SET T ecrit_par U WHERE T eid %(t)s, U eid %(u)s',
                     {'t': oe.eid, 'u': p.eid}, ('t','u'))
        e = self.add_entity('Note', type=u'z')
        e.copy_relations(oe.eid)
        self.failIf(e.ecrit_par)
        self.failUnless(oe.ecrit_par)
            
    def test_copy_with_composite(self):
        user = self.user()
        adeleid = self.execute('INSERT EmailAddress X: X address "toto@logilab.org", U use_email X WHERE U login "admin"')[0][0]
        e = self.entity('Any X WHERE X eid %(x)s', {'x':user.eid}, 'x')
        self.assertEquals(e.use_email[0].address, "toto@logilab.org")
        self.assertEquals(e.use_email[0].eid, adeleid)
        usereid = self.execute('INSERT EUser X: X login "toto", X upassword "toto", X in_group G, X in_state S '
                               'WHERE G name "users", S name "activated"')[0][0]
        e = self.entity('Any X WHERE X eid %(x)s', {'x':usereid}, 'x')
        e.copy_relations(user.eid)
        self.failIf(e.use_email)
        self.failIf(e.primary_email)
        
    def test_copy_with_non_initial_state(self):
        user = self.user()
        eid = self.execute('INSERT EUser X: X login "toto", X upassword %(pwd)s, X in_group G WHERE G name "users"',
                           {'pwd': 'toto'})[0][0]
        self.commit()
        self.execute('SET X in_state S WHERE X eid %(x)s, S name "deactivated"', {'x': eid}, 'x')
        self.commit()
        eid2 = self.execute('INSERT EUser X: X login "tutu", X upassword %(pwd)s', {'pwd': 'toto'})[0][0]
        e = self.entity('Any X WHERE X eid %(x)s', {'x': eid2}, 'x')
        e.copy_relations(eid)
        self.commit()
        e.clear_related_cache('in_state', 'subject')
        self.assertEquals(e.state, 'activated')

    def test_related_cache_both(self):
        user = self.entity('Any X WHERE X eid %(x)s', {'x':self.user().eid}, 'x')
        adeleid = self.execute('INSERT EmailAddress X: X address "toto@logilab.org", U use_email X WHERE U login "admin"')[0][0]
        self.commit()
        self.assertEquals(user._related_cache.keys(), [])
        email = user.primary_email[0]
        self.assertEquals(sorted(user._related_cache), ['primary_email_subject'])
        self.assertEquals(email._related_cache.keys(), ['primary_email_object'])
        groups = user.in_group
        self.assertEquals(sorted(user._related_cache), ['in_group_subject', 'primary_email_subject'])
        for group in groups:
            self.failIf('in_group_subject' in group._related_cache, group._related_cache.keys())

    def test_related_limit(self):
        p = self.add_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        for tag in u'abcd':
            self.add_entity('Tag', name=tag)
        self.execute('SET X tags Y WHERE X is Tag, Y is Personne')
        self.assertEquals(len(p.related('tags', 'object', limit=2)), 2)
        self.assertEquals(len(p.related('tags', 'object')), 4)

        
    def test_fetch_rql(self):
        user = self.user()
        Personne = self.vreg.etype_class('Personne')
        Societe = self.vreg.etype_class('Societe')
        Note = self.vreg.etype_class('Note')
        peschema = Personne.e_schema
        seschema = Societe.e_schema
        peschema.subject_relation('travaille').set_rproperty(peschema, seschema, 'cardinality', '1*')
        peschema.subject_relation('connait').set_rproperty(peschema, peschema, 'cardinality', '11')
        peschema.subject_relation('evaluee').set_rproperty(peschema, Note.e_schema, 'cardinality', '1*')
        seschema.subject_relation('evaluee').set_rproperty(seschema, Note.e_schema, 'cardinality', '1*')
        # testing basic fetch_attrs attribute
        self.assertEquals(Personne.fetch_rql(user),
                          'Any X,AA,AB,AC ORDERBY AA ASC WHERE X is Personne, X nom AA, X prenom AB, X modification_date AC')
        pfetch_attrs = Personne.fetch_attrs
        sfetch_attrs = Societe.fetch_attrs
        try:
            # testing unknown attributes
            Personne.fetch_attrs = ('bloug', 'beep')
            self.assertEquals(Personne.fetch_rql(user), 'Any X WHERE X is Personne')            
            # testing one non final relation
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
            self.assertEquals(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD ORDERBY AA ASC WHERE X is Personne, X nom AA, X prenom AB, X travaille AC, AC nom AD')
            # testing two non final relations
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille', 'evaluee')
            self.assertEquals(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD,AE,AF ORDERBY AA ASC,AF DESC WHERE X is Personne, X nom AA, '
                              'X prenom AB, X travaille AC, AC nom AD, X evaluee AE, AE modification_date AF')
            # testing one non final relation with recursion
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
            Societe.fetch_attrs = ('nom', 'evaluee')
            self.assertEquals(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD,AE,AF ORDERBY AA ASC,AF DESC WHERE X is Personne, X nom AA, X prenom AB, '
                              'X travaille AC, AC nom AD, AC evaluee AE, AE modification_date AF'
                              )
            # testing symetric relation
            Personne.fetch_attrs = ('nom', 'connait')
            self.assertEquals(Personne.fetch_rql(user), 'Any X,AA,AB ORDERBY AA ASC WHERE X is Personne, X nom AA, X connait AB')
            # testing optional relation
            peschema.subject_relation('travaille').set_rproperty(peschema, seschema, 'cardinality', '?*')
            Personne.fetch_attrs = ('nom', 'prenom', 'travaille')
            Societe.fetch_attrs = ('nom',)
            self.assertEquals(Personne.fetch_rql(user),
                              'Any X,AA,AB,AC,AD ORDERBY AA ASC WHERE X is Personne, X nom AA, X prenom AB, X travaille AC?, AC nom AD')
            # testing relation with cardinality > 1
            peschema.subject_relation('travaille').set_rproperty(peschema, seschema, 'cardinality', '**')
            self.assertEquals(Personne.fetch_rql(user),
                              'Any X,AA,AB ORDERBY AA ASC WHERE X is Personne, X nom AA, X prenom AB')
            # XXX test unauthorized attribute
        finally:
            Personne.fetch_attrs = pfetch_attrs
            Societe.fetch_attrs = sfetch_attrs

    def test_related_rql(self):
        from cubicweb.entities import fetch_config
        Personne = self.vreg.etype_class('Personne')
        Societe = self.vreg.etype_class('Societe')
        Personne.fetch_attrs, Personne.fetch_order = fetch_config(('nom', 'prenom', 'sexe'))
        Societe.fetch_attrs, Societe.fetch_order = fetch_config(('nom', 'web'))
        aff = self.add_entity('Affaire', sujet=u'my subject', ref=u'the ref')
        self.assertEquals(aff.related_rql('liee_a'),
                          'Any X,AA,AB ORDERBY AA ASC WHERE E eid %(x)s, E liee_a X, '
                          'X nom AA, X modification_date AB')
        Societe.fetch_attrs = ('web',)
        self.assertEquals(aff.related_rql('liee_a'),
                          'Any X ORDERBY Z DESC WHERE X modification_date Z, E eid %(x)s, E liee_a X')
    
    def test_entity_unrelated(self):
        p = self.add_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        e = self.add_entity('Tag', name=u'x')
        rschema = e.e_schema.subject_relation('tags')
        related = [r.eid for r in e.tags]
        self.failUnlessEqual(related, [])
        unrelated = [reid for rview, reid in e.vocabulary(rschema, 'subject')]
        self.failUnless(p.eid in unrelated)
        self.execute('SET X tags Y WHERE X is Tag, Y is Personne')
        e = self.entity('Any X WHERE X is Tag')
        unrelated = [reid for rview, reid in e.vocabulary(rschema, 'subject')]
        self.failIf(p.eid in unrelated)

    def test_entity_unrelated_limit(self):
        e = self.add_entity('Tag', name=u'x')
        self.add_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        self.add_entity('Personne', nom=u'di mascio', prenom=u'gwen')
        rschema = e.e_schema.subject_relation('tags')
        self.assertEquals(len(e.vocabulary(rschema, 'subject', limit=1)),
                          1)
        
    def test_new_entity_unrelated(self):
        e = self.etype_instance('EUser')
        rschema = e.e_schema.subject_relation('in_group')
        unrelated = [reid for rview, reid in e.vocabulary(rschema, 'subject')]
        # should be default groups but owners, i.e. managers, users, guests
        self.assertEquals(len(unrelated), 3)


    def test_rtags_expansion(self):
        from cubicweb.entities import AnyEntity
        class Personne(AnyEntity):
            id = 'Personne'
            __rtags__ = {
                ('travaille', 'Societe', 'subject') : set(('primary',)),
                ('evaluee', '*', 'subject') : set(('secondary',)),
                'ecrit_par' : set(('inlineview',)),
                }
        self.vreg.register_vobject_class(Personne)
        rtags = Personne.rtags
        self.assertEquals(rtags.get_tags('evaluee', 'Note', 'subject'), set(('secondary', 'link')))
        self.assertEquals(rtags.is_inlined('evaluee', 'Note', 'subject'), False)
        self.assertEquals(rtags.get_tags('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
        self.assertEquals(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)
        self.assertEquals(rtags.get_tags('ecrit_par', 'Note', 'object'), set(('inlineview', 'link')))
        self.assertEquals(rtags.is_inlined('ecrit_par', 'Note', 'object'), True)
        class Personne2(Personne):
            id = 'Personne'
            __rtags__ = {
                ('evaluee', 'Note', 'subject') : set(('inlineview',)),
                }
        self.vreg.register_vobject_class(Personne2)
        rtags = Personne2.rtags
        self.assertEquals(rtags.get_tags('evaluee', 'Note', 'subject'), set(('inlineview', 'link')))
        self.assertEquals(rtags.is_inlined('evaluee', 'Note', 'subject'), True)
        self.assertEquals(rtags.get_tags('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
        self.assertEquals(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)
    
    def test_relations_by_category(self):
        e = self.etype_instance('EUser')
        def rbc(iterable):
            return [(rschema.type, x) for rschema, tschemas, x in iterable]
        self.assertEquals(rbc(e.relations_by_category('primary')),
                          [('login', 'subject'), ('upassword', 'subject'),
                           ('in_group', 'subject'), ('in_state', 'subject'),
                           ('eid', 'subject'),])
        # firstname and surname are put in secondary category in views.entities.EUserEntity
        self.assertListEquals(rbc(e.relations_by_category('secondary')),
                              [('firstname', 'subject'), ('surname', 'subject')])
        self.assertListEquals(rbc(e.relations_by_category('generic')),
                              [('primary_email', 'subject'),
                               ('evaluee', 'subject'),
                               ('for_user', 'object')])
        # owned_by is defined both as subject and object relations on EUser
        self.assertListEquals(rbc(e.relations_by_category('generated')),
                              [('last_login_time', 'subject'),
                               ('created_by', 'subject'),
                               ('creation_date', 'subject'),
                               ('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('modification_date', 'subject'),
                               ('owned_by', 'subject'),
                               ('created_by', 'object'),
                               ('wf_info_for', 'object'),
                               ('owned_by', 'object'),
                               ('bookmarked_by', 'object')])
        e = self.etype_instance('Personne')
        self.assertListEquals(rbc(e.relations_by_category('primary')),
                              [('nom', 'subject'), ('eid', 'subject')])
        self.assertListEquals(rbc(e.relations_by_category('secondary')),
                              [('prenom', 'subject'),
                               ('sexe', 'subject'),
                               ('promo', 'subject'),
                               ('titre', 'subject'),
                               ('adel', 'subject'),
                               ('ass', 'subject'),
                               ('web', 'subject'),
                               ('tel', 'subject'),
                               ('fax', 'subject'),
                               ('datenaiss', 'subject'),
                               ('test', 'subject'),
                               ('description', 'subject'),
                               ('salary', 'subject')])
        self.assertListEquals(rbc(e.relations_by_category('generic')),
                              [('concerne', 'subject'),
                               ('connait', 'subject'),
                               ('evaluee', 'subject'),
                               ('travaille', 'subject'),
                               ('ecrit_par', 'object'),
                               ('evaluee', 'object'),
                               ('liee_a', 'object'),
                               ('tags', 'object')])
        self.assertListEquals(rbc(e.relations_by_category('generated')),
                              [('created_by', 'subject'),
                               ('creation_date', 'subject'),
                               ('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('modification_date', 'subject'),
                               ('owned_by', 'subject')])
        

    def test_printable_value_string(self):
        e = self.add_entity('Card', title=u'rest test', content=u'du :eid:`1:*ReST*`',
                            content_format=u'text/rest')
        self.assertEquals(e.printable_value('content'),
                          '<p>du <a class="reference" href="http://testing.fr/cubicweb/egroup/managers">*ReST*</a></p>\n')
        e['content'] = 'du <em>html</em> <ref rql="EUser X">users</ref>'
        e['content_format'] = 'text/html'
        self.assertEquals(e.printable_value('content'),
                          'du <em>html</em> <a href="http://testing.fr/cubicweb/view?rql=EUser%20X">users</a>')
        e['content'] = 'du *texte*'
        e['content_format'] = 'text/plain'
        self.assertEquals(e.printable_value('content'),
                          '<p>\ndu *texte*\n</p>')
        e['title'] = 'zou'
        e['content'] = '<h1 tal:content="self/title">titre</h1>'
        e['content_format'] = 'text/cubicweb-page-template'
        self.assertEquals(e.printable_value('content'),
                          '<h1>zou</h1>')
        
        #e = self.etype_instance('Task')
        e['content'] = '''\
a title
=======
du :eid:`1:*ReST*`'''
        e['content_format'] = 'text/rest'
        self.assertEquals(e.printable_value('content', format='text/plain'),
                          e['content'])

        e['content'] = u'<b>yo (zou éà ;)</b>'
        e['content_format'] = 'text/html'
        self.assertEquals(e.printable_value('content', format='text/plain').strip(),
                          u'**yo (zou éà ;)**')

    def test_printable_value_bytes(self):
        e = self.add_entity('File', data=Binary('lambda x: 1'), data_format=u'text/x-python',
                            data_encoding=u'ascii', name=u'toto.py')
        from cubicweb.common import mttransforms
        if mttransforms.HAS_PYGMENTS_TRANSFORMS:
            self.assertEquals(e.printable_value('data'),
                              '''<div class="highlight"><pre><span class="k">lambda</span> <span class="n">x</span><span class="p">:</span> <span class="mf">1</span>
</pre></div>
''')
        else:
            self.assertEquals(e.printable_value('data'),
                              '''<pre class="python">
<span style="color: #C00000;">lambda</span> <span style="color: #000000;">x</span><span style="color: #0000C0;">:</span> <span style="color: #0080C0;">1</span>
</pre>
''')
        
        e = self.add_entity('File', data=Binary('*héhéhé*'), data_format=u'text/rest',
                            data_encoding=u'utf-8', name=u'toto.txt')
        self.assertEquals(e.printable_value('data'),
                          u'<p><em>héhéhé</em></p>\n')

    def test_printable_value_bad_html(self):
        """make sure we don't crash if we try to render invalid XHTML strings"""
        e = self.add_entity('Card', title=u'bad html', content=u'<div>R&D<br>',
                            content_format=u'text/html')
        tidy = lambda x: x.replace('\n', '')
        self.assertEquals(tidy(e.printable_value('content')),
                          '<div>R&amp;D<br/></div>')
        e['content'] = u'yo !! R&D <div> pas fermé'
        self.assertEquals(tidy(e.printable_value('content')),
                          u'yo !! R&amp;D <div> pas fermé</div>')
        e['content'] = u'R&D'
        self.assertEquals(tidy(e.printable_value('content')), u'R&amp;D')
        e['content'] = u'R&D;'
        self.assertEquals(tidy(e.printable_value('content')), u'R&amp;D;')
        e['content'] = u'yo !! R&amp;D <div> pas fermé'
        self.assertEquals(tidy(e.printable_value('content')),
                          u'yo !! R&amp;D <div> pas fermé</div>')
        e['content'] = u'été <div> été'
        self.assertEquals(tidy(e.printable_value('content')),
                          u'été <div> été</div>')
        e['content'] = u'C&apos;est un exemple s&eacute;rieux'
        self.assertEquals(tidy(e.printable_value('content')),
                          u"C'est un exemple sérieux")
        # make sure valid xhtml is left untouched
        e['content'] = u'<div>R&amp;D<br/></div>'
        self.assertEquals(e.printable_value('content'), e['content'])
        e['content'] = u'<div>été</div>'
        self.assertEquals(e.printable_value('content'), e['content'])
        e['content'] = u'été'
        self.assertEquals(e.printable_value('content'), e['content'])
        

    def test_entity_formatted_attrs(self):
        e = self.etype_instance('Note')
        self.assertEquals(e.formatted_attrs(), [])
        e = self.etype_instance('File')
        self.assertEquals(e.formatted_attrs(), ['description'])
        e = self.etype_instance('AnotherNote')
        self.assertEquals(e.formatted_attrs(), ['descr', 'descr2'])
        
        
    def test_fulltextindex(self):
        e = self.etype_instance('File')
        e['name'] = 'an html file'
        e['description'] = 'du <em>html</em>'
        e['description_format'] = 'text/html'
        e['data'] = Binary('some <em>data</em>')
        e['data_format'] = 'text/html'
        e['data_encoding'] = 'ascii'
        self.assertEquals(set(e.get_words()), 
                          set(['an', 'html', 'file', 'du', 'html', 'some', 'data']))

        
    def test_nonregr_relation_cache(self):
        p1 = self.add_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        p2 = self.add_entity('Personne', nom=u'toto')
        self.execute('SET X evaluee Y WHERE X nom "di mascio", Y nom "toto"')
        self.assertEquals(p1.evaluee[0].nom, "toto")
        self.failUnless(not p1.reverse_evaluee)
        
    def test_complete_relation(self):
        self.execute('SET RT add_permission G WHERE RT name "wf_info_for", G name "managers"')
        self.commit()
        try:
            eid = self.execute('INSERT TrInfo X: X comment "zou", X wf_info_for U,'
                               'X from_state S1, X to_state S2 WHERE '
                               'U login "admin", S1 name "activated", S2 name "deactivated"')[0][0]
            trinfo = self.entity('Any X WHERE X eid %(x)s', {'x': eid}, 'x')
            trinfo.complete()
            self.failUnless(trinfo.relation_cached('from_state', 'subject'))
            self.failUnless(trinfo.relation_cached('to_state', 'subject'))
            self.failUnless(trinfo.relation_cached('wf_info_for', 'subject'))
            # check with a missing relation
            eid = self.execute('INSERT TrInfo X: X comment "zou", X wf_info_for U,'
                               'X to_state S2 WHERE '
                               'U login "admin", S2 name "activated"')[0][0]
            trinfo = self.entity('Any X WHERE X eid %(x)s', {'x': eid}, 'x')
            trinfo.complete()
            self.failUnless(isinstance(trinfo.creation_date, DateTimeType))
            self.failUnless(trinfo.relation_cached('from_state', 'subject'))
            self.failUnless(trinfo.relation_cached('to_state', 'subject'))
            self.failUnless(trinfo.relation_cached('wf_info_for', 'subject'))
            self.assertEquals(trinfo.from_state, [])
        finally:
            self.rollback()
            self.execute('DELETE RT add_permission G WHERE RT name "wf_info_for", G name "managers"')
            self.commit()

    def test_request_cache(self):
        req = self.request()
        user = self.entity('EUser X WHERE X login "admin"', req=req)
        state = user.in_state[0]
        samestate = self.entity('State X WHERE X name "activated"', req=req)
        self.failUnless(state is samestate)

    def test_rest_path(self):
        note = self.add_entity('Note', type=u'z')
        self.assertEquals(note.rest_path(), 'note/%s' % note.eid)
        # unique attr
        tag = self.add_entity('Tag', name=u'x')
        self.assertEquals(tag.rest_path(), 'tag/x')
        # test explicit rest_attr
        person = self.add_entity('Personne', prenom=u'john', nom=u'doe')
        self.assertEquals(person.rest_path(), 'personne/doe')
        # ambiguity test
        person2 = self.add_entity('Personne', prenom=u'remi', nom=u'doe')
        self.assertEquals(person.rest_path(), 'personne/eid/%s' % person.eid)
        self.assertEquals(person2.rest_path(), 'personne/eid/%s' % person2.eid)
        # unique attr with None value (wikiid in this case)
        card1 = self.add_entity('Card', title=u'hop')
        self.assertEquals(card1.rest_path(), 'card/eid/%s' % card1.eid)
        card2 = self.add_entity('Card', title=u'pod', wikiid=u'zob/i')
        self.assertEquals(card2.rest_path(), 'card/zob%2Fi')

    def test_set_attributes(self):
        person = self.add_entity('Personne', nom=u'di mascio', prenom=u'adrien')
        self.assertEquals(person.prenom, u'adrien')
        self.assertEquals(person.nom, u'di mascio')
        person.set_attributes(prenom=u'sylvain', nom=u'thénault')
        person = self.entity('Personne P') # XXX retreival needed ?
        self.assertEquals(person.prenom, u'sylvain')
        self.assertEquals(person.nom, u'thénault')

    def test_metainformation(self):
        note = self.add_entity('Note', type=u'z')
        metainf = note.metainformation()
        self.assertEquals(metainf, {'source': {'adapter': 'native', 'uri': 'system'}, 'type': u'Note', 'extid': None})
        self.assertEquals(note.absolute_url(), 'http://testing.fr/cubicweb/note/%s' % note.eid)
        metainf['source'] = metainf['source'].copy()
        metainf['source']['base-url']  = 'http://cubicweb2.com/'
        self.assertEquals(note.absolute_url(), 'http://cubicweb2.com/note/%s' % note.eid)
        
if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()

