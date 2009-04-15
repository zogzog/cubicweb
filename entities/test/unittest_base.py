# -*- coding: utf-8 -*-
"""unit tests for cubicweb.entities.base module"""

from logilab.common.testlib import unittest_main
from logilab.common.decorators import clear_cache
from logilab.common.interface import implements

from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb import ValidationError
from cubicweb.interfaces import IMileStone, IWorkflowable
from cubicweb.entities import AnyEntity
from cubicweb.entities.authobjs import EUser
from cubicweb.web.widgets import AutoCompletionWidget


class BaseEntityTC(EnvBasedTC):

    def setup_database(self):
        self.member = self.create_user('member')
    
                     
    
class MetadataTC(BaseEntityTC):

    def test_creator(self):
        self.login(u'member')
        card = self.add_entity('Card', title=u"hello")
        self.commit()
        self.assertEquals(card.creator.eid, self.member.eid)
        self.assertEquals(card.dc_creator(), u'member')

    def test_type(self):
        self.assertEquals(self.member.dc_type(), 'euser')
        

    def test_entity_meta_attributes(self):
        # XXX move to yams
        self.assertEquals(self.schema['EUser'].meta_attributes(), {})
        self.assertEquals(dict((str(k), v) for k, v in self.schema['Card'].meta_attributes().iteritems()),
                          {'content_format': ('format', 'content')})
        

class EUserTC(BaseEntityTC):
    def test_dc_title_and_name(self):
        e = self.entity('EUser U WHERE U login "member"')
        self.assertEquals(e.dc_title(), 'member')
        self.assertEquals(e.name(), 'member')
        self.execute(u'SET X firstname "bouah" WHERE X is EUser, X login "member"')
        self.assertEquals(e.dc_title(), 'member')
        self.assertEquals(e.name(), u'bouah')
        self.execute(u'SET X surname "lôt" WHERE X is EUser, X login "member"')
        self.assertEquals(e.dc_title(), 'member')
        self.assertEquals(e.name(), u'bouah lôt')

    
class StateAndTransitionsTC(BaseEntityTC):
        
    def test_transitions(self):
        user = self.entity('EUser X')
        e = self.entity('State S WHERE S name "activated"')
        trs = list(e.transitions(user))
        self.assertEquals(len(trs), 1)
        self.assertEquals(trs[0].name, u'deactivate')
        self.assertEquals(trs[0].destination().name, u'deactivated')
        self.assert_(user.can_pass_transition('deactivate'))
        self.assert_(not user.can_pass_transition('activate'))
        # test a std user get no possible transition
        self.login('member')
        # fetch the entity using the new session
        e = self.entity('State S WHERE S name "activated"')
        trs = list(e.transitions(user))
        self.assertEquals(len(trs), 0)
        user = self.entity('EUser X')
        self.assert_(not user.can_pass_transition('deactivate'))
        self.assert_(not user.can_pass_transition('activate'))
        
    def test_transitions_with_dest_specfied(self):
        user = self.entity('EUser X')
        e = self.entity('State S WHERE S name "activated"')
        e2 = self.entity('State S WHERE S name "deactivated"')
        trs = list(e.transitions(user, e2.eid))
        self.assertEquals(len(trs), 1)
        self.assertEquals(trs[0].name, u'deactivate')
        self.assertEquals(trs[0].destination().name, u'deactivated')
        trs = list(e.transitions(user, e.eid))
        self.assertEquals(len(trs), 0)
    
    def test_transitions_maybe_passed(self):
        self.execute('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                     'X expression "X owned_by U", T condition X '
                     'WHERE T name "deactivate"')
        self._test_deactivated()
        
    def test_transitions_maybe_passed_using_has_update_perm(self):
        self.execute('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                     'X expression "U has_update_permission X", T condition X '
                     'WHERE T name "deactivate"')
        self._test_deactivated()
        
        
    def _test_deactivated(self):
        ueid = self.create_user('toto').eid
        self.create_user('tutu')
        cnx = self.login('tutu')
        cu = cnx.cursor()
        self.assertRaises(ValidationError,
                          cu.execute, 'SET X in_state S WHERE X eid %(x)s, S name "deactivated"',
                          {'x': ueid}, 'x')
        cnx.close()
        cnx = self.login('toto')
        cu = cnx.cursor()
        cu.execute('SET X in_state S WHERE X eid %(x)s, S name "deactivated"',
                   {'x': ueid}, 'x')
        cnx.commit()
        self.assertRaises(ValidationError,
                          cu.execute, 'SET X in_state S WHERE X eid %(x)s, S name "activated"',
                          {'x': ueid}, 'x')
    

    def test_transitions_selection(self):
        """
        ------------------------  tr1    -----------------
        | state1 (Card, Bookmark) | ------> | state2 (Card) |
        ------------------------         -----------------
                  |  tr2    ------------------
                  `------>  | state3 (Bookmark) |
                            ------------------
        """
        state1 = self.add_entity('State', name=u'state1')
        state2 = self.add_entity('State', name=u'state2')
        state3 = self.add_entity('State', name=u'state3')
        tr1 = self.add_entity('Transition', name=u'tr1')
        tr2 = self.add_entity('Transition', name=u'tr2')
        self.execute('SET X state_of Y WHERE X eid in (%s, %s), Y is EEType, Y name "Card"' %
                      (state1.eid, state2.eid))
        self.execute('SET X state_of Y WHERE X eid in (%s, %s), Y is EEType, Y name "Bookmark"' %
                      (state1.eid, state3.eid))
        self.execute('SET X transition_of Y WHERE X eid %s, Y name "Card"' % tr1.eid)
        self.execute('SET X transition_of Y WHERE X eid %s, Y name "Bookmark"' % tr2.eid)
        self.execute('SET X allowed_transition Y WHERE X eid %s, Y eid %s' %
                      (state1.eid, tr1.eid))
        self.execute('SET X allowed_transition Y WHERE X eid %s, Y eid %s' %
                      (state1.eid, tr2.eid))
        self.execute('SET X destination_state Y WHERE X eid %s, Y eid %s' %
                      (tr1.eid, state2.eid))
        self.execute('SET X destination_state Y WHERE X eid %s, Y eid %s' %
                      (tr2.eid, state3.eid))
        self.execute('SET X initial_state Y WHERE Y eid %s, X name "Card"' % state1.eid)
        self.execute('SET X initial_state Y WHERE Y eid %s, X name "Bookmark"' % state1.eid)
        card = self.add_entity('Card', title=u't1')
        bookmark = self.add_entity('Bookmark', title=u'111', path=u'/view')
        
        transitions = list(state1.transitions(card))
        self.assertEquals(len(transitions), 1)
        self.assertEquals(transitions[0].name, 'tr1')
        transitions = list(state1.transitions(bookmark))
        self.assertEquals(len(transitions), 1)
        self.assertEquals(transitions[0].name, 'tr2')
        

    def test_transitions_selection2(self):
        """
        ------------------------  tr1 (Bookmark)   -----------------------
        | state1 (Card, Bookmark) | -------------> | state2 (Card,Bookmark) |
        ------------------------                -----------------------
                  |  tr2 (Card)                     |
                  `---------------------------------/
        """
        state1 = self.add_entity('State', name=u'state1')
        state2 = self.add_entity('State', name=u'state2')
        tr1 = self.add_entity('Transition', name=u'tr1')
        tr2 = self.add_entity('Transition', name=u'tr2')
        self.execute('SET X state_of Y WHERE X eid in (%s, %s), Y is EEType, Y name "Card"' %
                      (state1.eid, state2.eid))
        self.execute('SET X state_of Y WHERE X eid in (%s, %s), Y is EEType, Y name "Bookmark"' %
                      (state1.eid, state2.eid))
        self.execute('SET X transition_of Y WHERE X eid %s, Y name "Card"' % tr1.eid)
        self.execute('SET X transition_of Y WHERE X eid %s, Y name "Bookmark"' % tr2.eid)
        self.execute('SET X allowed_transition Y WHERE X eid %s, Y eid %s' %
                      (state1.eid, tr1.eid))
        self.execute('SET X allowed_transition Y WHERE X eid %s, Y eid %s' %
                      (state1.eid, tr2.eid))
        self.execute('SET X destination_state Y WHERE X eid %s, Y eid %s' %
                      (tr1.eid, state2.eid))
        self.execute('SET X destination_state Y WHERE X eid %s, Y eid %s' %
                      (tr2.eid, state2.eid))
        self.execute('SET X initial_state Y WHERE Y eid %s, X name "Card"' % state1.eid)
        self.execute('SET X initial_state Y WHERE Y eid %s, X name "Bookmark"' % state1.eid)
        card = self.add_entity('Card', title=u't1')
        bookmark = self.add_entity('Bookmark', title=u'111', path=u'/view')
        
        transitions = list(state1.transitions(card))
        self.assertEquals(len(transitions), 1)
        self.assertEquals(transitions[0].name, 'tr1')
        transitions = list(state1.transitions(bookmark))
        self.assertEquals(len(transitions), 1)
        self.assertEquals(transitions[0].name, 'tr2')
        

class EmailAddressTC(BaseEntityTC):
    def test_canonical_form(self):
        eid1 = self.execute('INSERT EmailAddress X: X address "maarten.ter.huurne@philips.com"')[0][0]
        eid2 = self.execute('INSERT EmailAddress X: X address "maarten@philips.com", X canonical TRUE')[0][0]
        self.execute('SET X identical_to Y WHERE X eid %s, Y eid %s' % (eid1, eid2))
        email1 = self.entity('Any X WHERE X eid %(x)s', {'x':eid1}, 'x')
        email2 = self.entity('Any X WHERE X eid %(x)s', {'x':eid2}, 'x')
        self.assertEquals(email1.canonical_form().eid, eid2)
        self.assertEquals(email2.canonical_form(), email2)
        eid3 = self.execute('INSERT EmailAddress X: X address "toto@logilab.fr"')[0][0]
        email3 = self.entity('Any X WHERE X eid %s'%eid3)
        self.assertEquals(email3.canonical_form(), None)

    def test_mangling(self):
        eid = self.execute('INSERT EmailAddress X: X address "maarten.ter.huurne@philips.com"')[0][0]
        email = self.entity('Any X WHERE X eid %(x)s', {'x':eid}, 'x')
        self.assertEquals(email.display_address(), 'maarten.ter.huurne@philips.com')
        self.assertEquals(email.printable_value('address'), 'maarten.ter.huurne@philips.com')
        self.vreg.config.global_set_option('mangle-emails', True)
        self.assertEquals(email.display_address(), 'maarten.ter.huurne at philips dot com')
        self.assertEquals(email.printable_value('address'), 'maarten.ter.huurne at philips dot com')
        eid = self.execute('INSERT EmailAddress X: X address "syt"')[0][0]
        email = self.entity('Any X WHERE X eid %(x)s', {'x':eid}, 'x')
        self.assertEquals(email.display_address(), 'syt')
        self.assertEquals(email.printable_value('address'), 'syt')


class EUserTC(BaseEntityTC):
    
    def test_complete(self):
        e = self.entity('EUser X WHERE X login "admin"')
        e.complete()

        
    def test_matching_groups(self):
        e = self.entity('EUser X WHERE X login "admin"')
        self.failUnless(e.matching_groups('managers'))
        self.failIf(e.matching_groups('xyz'))
        self.failUnless(e.matching_groups(('xyz', 'managers')))
        self.failIf(e.matching_groups(('xyz', 'abcd')))

    def test_workflow_base(self):
        e = self.create_user('toto')
        self.assertEquals(e.state, 'activated')
        activatedeid = self.execute('State X WHERE X name "activated"')[0][0]
        deactivatedeid = self.execute('State X WHERE X name "deactivated"')[0][0]
        e.change_state(deactivatedeid, u'deactivate 1')
        self.commit()
        e.change_state(activatedeid, u'activate 1')
        self.commit()
        e.change_state(deactivatedeid, u'deactivate 2')
        self.commit()
        # get a fresh user to avoid potential cache issues
        e = self.entity('EUser X WHERE X eid %s' % e.eid)
        self.assertEquals([tr.comment for tr in e.reverse_wf_info_for],
                          [None, 'deactivate 1', 'activate 1', 'deactivate 2'])
        self.assertEquals(e.latest_trinfo().comment, 'deactivate 2')


class InterfaceTC(EnvBasedTC):

    def test_nonregr_subclasses_and_mixins_interfaces(self):
        class MyUser(EUser):
            __implements__ = (IMileStone,)
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register_vobject_class(MyUser)
        self.failUnless(implements(EUser, IWorkflowable))
        self.failUnless(implements(MyUser, IMileStone))
        self.failUnless(implements(MyUser, IWorkflowable))


class SpecializedEntityClassesTC(EnvBasedTC):

    def select_eclass(self, etype):
        # clear selector cache
        clear_cache(self.vreg, 'etype_class')
        return self.vreg.etype_class(etype)
        
    def test_etype_class_selection_and_specialization(self):
        # no specific class for Subdivisions, the default one should be selected
        eclass = self.select_eclass('SubDivision')
        self.failUnless(eclass.__autogenerated__)
        #self.assertEquals(eclass.__bases__, (AnyEntity,))
        # build class from most generic to most specific and make
        # sure the most specific is always selected
        self.vreg._loadedmods[__name__] = {}
        for etype in ('Company', 'Division', 'SubDivision'):
            class Foo(AnyEntity):
                id = etype
            self.vreg.register_vobject_class(Foo)
            eclass = self.select_eclass('SubDivision')
            if etype == 'SubDivision':
                self.failUnless(eclass is Foo)
            else:
                self.failUnless(eclass.__autogenerated__)
                self.assertEquals(eclass.__bases__, (Foo,))
        # check Division eclass is still selected for plain Division entities
        eclass = self.select_eclass('Division')
        self.assertEquals(eclass.id, 'Division')
        
if __name__ == '__main__':
    unittest_main()
