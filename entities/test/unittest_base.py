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
"""unit tests for cubicweb.entities.base module
"""

from logilab.common.testlib import unittest_main
from logilab.common.decorators import clear_cache
from logilab.common.interface import implements

from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.interfaces import IMileStone, ICalendarable
from cubicweb.entities import AnyEntity


class BaseEntityTC(CubicWebTC):

    def setup_database(self):
        req = self.request()
        self.member = self.create_user(req, 'member')



class MetadataTC(BaseEntityTC):

    def test_creator(self):
        self.login(u'member')
        entity = self.request().create_entity('Bookmark', title=u"hello", path=u'project/cubicweb')
        self.commit()
        self.assertEqual(entity.creator.eid, self.member.eid)
        self.assertEqual(entity.dc_creator(), u'member')

    def test_type(self):
        #dc_type may be translated
        self.assertEqual(self.member.dc_type(), 'CWUser')

    def test_cw_etype(self):
        #cw_etype is never translated
        self.assertEqual(self.member.cw_etype, 'CWUser')

    def test_entity_meta_attributes(self):
        # XXX move to yams
        self.assertEqual(self.schema['CWUser'].meta_attributes(), {})
        self.assertEqual(dict((str(k), v) for k, v in self.schema['State'].meta_attributes().iteritems()),
                          {'description_format': ('format', 'description')})

    def test_fti_rql_method(self):
        eclass = self.vreg['etypes'].etype_class('EmailAddress')
        self.assertEqual(['Any X, ALIAS, ADDRESS WHERE X is EmailAddress, '
                          'X alias ALIAS, X address ADDRESS'],
                         eclass.cw_fti_index_rql_queries(self.request()))


class EmailAddressTC(BaseEntityTC):
    def test_canonical_form(self):
        email1 = self.execute('INSERT EmailAddress X: X address "maarten.ter.huurne@philips.com"').get_entity(0, 0)
        email2 = self.execute('INSERT EmailAddress X: X address "maarten@philips.com"').get_entity(0, 0)
        email3 = self.execute('INSERT EmailAddress X: X address "toto@logilab.fr"').get_entity(0, 0)
        email1.cw_set(prefered_form=email2)
        self.assertEqual(email1.prefered.eid, email2.eid)
        self.assertEqual(email2.prefered.eid, email2.eid)
        self.assertEqual(email3.prefered.eid, email3.eid)

    def test_mangling(self):
        email = self.execute('INSERT EmailAddress X: X address "maarten.ter.huurne@philips.com"').get_entity(0, 0)
        self.assertEqual(email.display_address(), 'maarten.ter.huurne@philips.com')
        self.assertEqual(email.printable_value('address'), 'maarten.ter.huurne@philips.com')
        self.vreg.config.global_set_option('mangle-emails', True)
        try:
            self.assertEqual(email.display_address(), 'maarten.ter.huurne at philips dot com')
            self.assertEqual(email.printable_value('address'), 'maarten.ter.huurne at philips dot com')
            email = self.execute('INSERT EmailAddress X: X address "syt"').get_entity(0, 0)
            self.assertEqual(email.display_address(), 'syt')
            self.assertEqual(email.printable_value('address'), 'syt')
        finally:
            self.vreg.config.global_set_option('mangle-emails', False)

    def test_printable_value_escape(self):
        email = self.execute('INSERT EmailAddress X: X address "maarten&ter@philips.com"').get_entity(0, 0)
        self.assertEqual(email.printable_value('address'), 'maarten&amp;ter@philips.com')
        self.assertEqual(email.printable_value('address', format='text/plain'), 'maarten&ter@philips.com')

class CWUserTC(BaseEntityTC):

    def test_complete(self):
        e = self.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)
        e.complete()

    def test_matching_groups(self):
        e = self.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)
        self.assertTrue(e.matching_groups('managers'))
        self.assertFalse(e.matching_groups('xyz'))
        self.assertTrue(e.matching_groups(('xyz', 'managers')))
        self.assertFalse(e.matching_groups(('xyz', 'abcd')))

    def test_dc_title_and_name(self):
        e = self.execute('CWUser U WHERE U login "member"').get_entity(0, 0)
        self.assertEqual(e.dc_title(), 'member')
        self.assertEqual(e.name(), 'member')
        e.cw_set(firstname=u'bouah')
        self.assertEqual(e.dc_title(), 'member')
        self.assertEqual(e.name(), u'bouah')
        e.cw_set(surname=u'lôt')
        self.assertEqual(e.dc_title(), 'member')
        self.assertEqual(e.name(), u'bouah lôt')

    def test_allowed_massmail_keys(self):
        e = self.execute('CWUser U WHERE U login "member"').get_entity(0, 0)
        # Bytes/Password attributes should be omited
        self.assertEqual(e.cw_adapt_to('IEmailable').allowed_massmail_keys(),
                          set(('surname', 'firstname', 'login', 'last_login_time',
                               'creation_date', 'modification_date', 'cwuri', 'eid'))
                          )

    def test_cw_instantiate_object_relation(self):
        """ a weird non regression test """
        e = self.execute('CWUser U WHERE U login "member"').get_entity(0, 0)
        self.request().create_entity('CWGroup', name=u'logilab', reverse_in_group=e)


class InterfaceTC(CubicWebTC):

    def test_nonregr_subclasses_and_mixins_interfaces(self):
        from cubicweb.entities.wfobjs import WorkflowableMixIn
        WorkflowableMixIn.__implements__ = (ICalendarable,)
        CWUser = self.vreg['etypes'].etype_class('CWUser')
        class MyUser(CWUser):
            __implements__ = (IMileStone,)
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(MyUser)
        self.vreg['etypes'].initialization_completed()
        MyUser_ = self.vreg['etypes'].etype_class('CWUser')
        # a copy is done systematically
        self.assertTrue(issubclass(MyUser_, MyUser))
        self.assertTrue(implements(MyUser_, IMileStone))
        self.assertTrue(implements(MyUser_, ICalendarable))
        # original class should not have beed modified, only the copy
        self.assertTrue(implements(MyUser, IMileStone))
        self.assertFalse(implements(MyUser, ICalendarable))


class SpecializedEntityClassesTC(CubicWebTC):

    def select_eclass(self, etype):
        # clear selector cache
        clear_cache(self.vreg['etypes'], 'etype_class')
        return self.vreg['etypes'].etype_class(etype)

    def test_etype_class_selection_and_specialization(self):
        # no specific class for Subdivisions, the default one should be selected
        eclass = self.select_eclass('SubDivision')
        self.assertTrue(eclass.__autogenerated__)
        #self.assertEqual(eclass.__bases__, (AnyEntity,))
        # build class from most generic to most specific and make
        # sure the most specific is always selected
        self.vreg._loadedmods[__name__] = {}
        for etype in ('Company', 'Division', 'SubDivision'):
            class Foo(AnyEntity):
                __regid__ = etype
            self.vreg.register(Foo)
            eclass = self.select_eclass('SubDivision')
            self.assertTrue(eclass.__autogenerated__)
            self.assertFalse(eclass is Foo)
            if etype == 'SubDivision':
                self.assertEqual(eclass.__bases__, (Foo,))
            else:
                self.assertEqual(eclass.__bases__[0].__bases__, (Foo,))
        # check Division eclass is still selected for plain Division entities
        eclass = self.select_eclass('Division')
        self.assertEqual(eclass.cw_etype, 'Division')

if __name__ == '__main__':
    unittest_main()
