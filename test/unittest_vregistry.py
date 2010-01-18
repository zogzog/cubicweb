"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import unittest_main, TestCase

from os.path import join

from cubicweb import CW_SOFTWARE_ROOT as BASE
from cubicweb.appobject import AppObject
from cubicweb.cwvreg import CubicWebVRegistry, UnknownProperty
from cubicweb.devtools import TestServerConfiguration
from cubicweb.interfaces import IMileStone

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
        self.assertEquals(len(self.vreg['views']['primary']), 2)
        self.vreg.initialization_completed()
        self.assertEquals(len(self.vreg['views']['primary']), 1)

    def test_properties(self):
        self.failIf('system.version.cubicweb' in self.vreg['propertydefs'])
        self.failUnless(self.vreg.property_info('system.version.cubicweb'))
        self.assertRaises(UnknownProperty, self.vreg.property_info, 'a.non.existent.key')

    def test_load_subinterface_based_appobjects(self):
        self.vreg.reset()
        self.vreg.register_objects([join(BASE, 'web', 'views', 'iprogress.py')])
        # check progressbar was kicked
        self.failIf(self.vreg['views'].get('progressbar'))
        class MyCard(Card):
            __implements__ = (IMileStone,)
        self.vreg.reset()
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register_appobject_class(MyCard)
        self.vreg.register_objects([join(BASE, 'entities', '__init__.py'),
                                    join(BASE, 'web', 'views', 'iprogress.py')])
        # check progressbar isn't kicked
        self.assertEquals(len(self.vreg['views']['progressbar']), 1)


if __name__ == '__main__':
    unittest_main()
