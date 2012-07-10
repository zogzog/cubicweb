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

from logilab.common.testlib import unittest_main, TestCase

from os.path import join

from cubicweb import CW_SOFTWARE_ROOT as BASE
from cubicweb.appobject import AppObject
from cubicweb.cwvreg import CubicWebVRegistry, UnknownProperty
from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.view import EntityAdapter

from cubes.card.entities import Card

class YesSchema:
    def __contains__(self, something):
        return True

WEBVIEWSDIR = join(BASE, 'web', 'views')

class VRegistryTC(TestCase):

    def setUp(self):
        config = TestServerConfiguration('data')
        self.vreg = CubicWebVRegistry(config)
        config.bootstrap_cubes()
        self.vreg.schema = config.load_schema()

    def test_load_interface_based_vojects(self):
        self.vreg.init_registration([WEBVIEWSDIR])
        self.vreg.load_file(join(BASE, 'entities', '__init__.py'), 'cubicweb.entities.__init__')
        self.vreg.load_file(join(WEBVIEWSDIR, 'idownloadable.py'), 'cubicweb.web.views.idownloadable')
        self.vreg.load_file(join(WEBVIEWSDIR, 'primary.py'), 'cubicweb.web.views.primary')
        self.assertEqual(len(self.vreg['views']['primary']), 2)
        self.vreg.initialization_completed()
        self.assertEqual(len(self.vreg['views']['primary']), 1)


    def test_load_subinterface_based_appobjects(self):
        self.vreg.register_objects([join(BASE, 'web', 'views', 'iprogress.py')])
        # check progressbar was kicked
        self.assertFalse(self.vreg['views'].get('progressbar'))
        # we've to emulate register_objects to add custom MyCard objects
        path = [join(BASE, 'entities', '__init__.py'),
                join(BASE, 'entities', 'adapters.py'),
                join(BASE, 'web', 'views', 'iprogress.py')]
        filemods = self.vreg.init_registration(path, None)
        for filepath, modname in filemods:
            self.vreg.load_file(filepath, modname)
        class CardIProgressAdapter(EntityAdapter):
            __regid__ = 'IProgress'
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(CardIProgressAdapter)
        self.vreg.initialization_completed()
        # check progressbar isn't kicked
        self.assertEqual(len(self.vreg['views']['progressbar']), 1)

    def test_properties(self):
        self.vreg.reset()
        self.assertFalse('system.version.cubicweb' in self.vreg['propertydefs'])
        self.assertTrue(self.vreg.property_info('system.version.cubicweb'))
        self.assertRaises(UnknownProperty, self.vreg.property_info, 'a.non.existent.key')


class CWVregTC(CubicWebTC):

    def test_property_default_overriding(self):
        # see data/views.py
        from cubicweb.web.views.xmlrss import RSSIconBox
        self.assertEqual(self.vreg.property_info(RSSIconBox._cwpropkey('visible'))['default'], True)

if __name__ == '__main__':
    unittest_main()
