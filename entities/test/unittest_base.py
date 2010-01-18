# -*- coding: utf-8 -*-
"""unit tests for cubicweb.entities.base module

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import unittest_main
from logilab.common.decorators import clear_cache
from logilab.common.interface import implements

from cubicweb.devtools.testlib import CubicWebTC

from cubicweb import ValidationError
from cubicweb.interfaces import IMileStone, IWorkflowable
from cubicweb.entities import AnyEntity


class BaseEntityTC(CubicWebTC):

    def setup_database(self):
        self.member = self.create_user('member')



class MetadataTC(BaseEntityTC):

    def test_creator(self):
        self.login(u'member')
        entity = self.request().create_entity('Bookmark', title=u"hello", path=u'project/cubicweb')
        self.commit()
        self.assertEquals(entity.creator.eid, self.member.eid)
        self.assertEquals(entity.dc_creator(), u'member')

    def test_type(self):
        self.assertEquals(self.member.dc_type(), 'cwuser')

    def test_entity_meta_attributes(self):
        # XXX move to yams
        self.assertEquals(self.schema['CWUser'].meta_attributes(), {})
        self.assertEquals(dict((str(k), v) for k, v in self.schema['State'].meta_attributes().iteritems()),
                          {'description_format': ('format', 'description')})


class EmailAddressTC(BaseEntityTC):
    def test_canonical_form(self):
        email1 = self.execute('INSERT EmailAddress X: X address "maarten.ter.huurne@philips.com"').get_entity(0, 0)
        email2 = self.execute('INSERT EmailAddress X: X address "maarten@philips.com"').get_entity(0, 0)
        email3 = self.execute('INSERT EmailAddress X: X address "toto@logilab.fr"').get_entity(0, 0)
        email1.set_relations(prefered_form=email2)
        self.assertEquals(email1.prefered.eid, email2.eid)
        self.assertEquals(email2.prefered.eid, email2.eid)
        self.assertEquals(email3.prefered.eid, email3.eid)

    def test_mangling(self):
        email = self.execute('INSERT EmailAddress X: X address "maarten.ter.huurne@philips.com"').get_entity(0, 0)
        self.assertEquals(email.display_address(), 'maarten.ter.huurne@philips.com')
        self.assertEquals(email.printable_value('address'), 'maarten.ter.huurne@philips.com')
        self.vreg.config.global_set_option('mangle-emails', True)
        self.assertEquals(email.display_address(), 'maarten.ter.huurne at philips dot com')
        self.assertEquals(email.printable_value('address'), 'maarten.ter.huurne at philips dot com')
        email = self.execute('INSERT EmailAddress X: X address "syt"').get_entity(0, 0)
        self.assertEquals(email.display_address(), 'syt')
        self.assertEquals(email.printable_value('address'), 'syt')


class CWUserTC(BaseEntityTC):

    def test_complete(self):
        e = self.entity('CWUser X WHERE X login "admin"')
        e.complete()

    def test_matching_groups(self):
        e = self.entity('CWUser X WHERE X login "admin"')
        self.failUnless(e.matching_groups('managers'))
        self.failIf(e.matching_groups('xyz'))
        self.failUnless(e.matching_groups(('xyz', 'managers')))
        self.failIf(e.matching_groups(('xyz', 'abcd')))

    def test_dc_title_and_name(self):
        e = self.entity('CWUser U WHERE U login "member"')
        self.assertEquals(e.dc_title(), 'member')
        self.assertEquals(e.name(), 'member')
        e.set_attributes(firstname=u'bouah')
        self.assertEquals(e.dc_title(), 'member')
        self.assertEquals(e.name(), u'bouah')
        e.set_attributes(surname=u'lôt')
        self.assertEquals(e.dc_title(), 'member')
        self.assertEquals(e.name(), u'bouah lôt')

    def test_allowed_massmail_keys(self):
        e = self.entity('CWUser U WHERE U login "member"')
        # Bytes/Password attributes should be omited
        self.assertEquals(e.allowed_massmail_keys(),
                          set(('surname', 'firstname', 'login', 'last_login_time',
                               'creation_date', 'modification_date', 'cwuri', 'eid'))
                          )


class InterfaceTC(CubicWebTC):

    def test_nonregr_subclasses_and_mixins_interfaces(self):
        CWUser = self.vreg['etypes'].etype_class('CWUser')
        self.failUnless(implements(CWUser, IWorkflowable))
        class MyUser(CWUser):
            __implements__ = (IMileStone,)
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register_appobject_class(MyUser)
        self.vreg['etypes'].initialization_completed()
        MyUser_ = self.vreg['etypes'].etype_class('CWUser')
        # a copy is done systematically
        self.failUnless(issubclass(MyUser_, MyUser))
        self.failUnless(implements(MyUser_, IMileStone))
        self.failUnless(implements(MyUser_, IWorkflowable))
        # original class should not have beed modified, only the copy
        self.failUnless(implements(MyUser, IMileStone))
        self.failIf(implements(MyUser, IWorkflowable))


class SpecializedEntityClassesTC(CubicWebTC):

    def select_eclass(self, etype):
        # clear selector cache
        clear_cache(self.vreg['etypes'], 'etype_class')
        return self.vreg['etypes'].etype_class(etype)

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
                __regid__ = etype
            self.vreg.register_appobject_class(Foo)
            eclass = self.select_eclass('SubDivision')
            self.failUnless(eclass.__autogenerated__)
            self.failIf(eclass is Foo)
            if etype == 'SubDivision':
                self.assertEquals(eclass.__bases__, (Foo,))
            else:
                self.assertEquals(eclass.__bases__[0].__bases__, (Foo,))
        # check Division eclass is still selected for plain Division entities
        eclass = self.select_eclass('Division')
        self.assertEquals(eclass.__regid__, 'Division')

if __name__ == '__main__':
    unittest_main()
