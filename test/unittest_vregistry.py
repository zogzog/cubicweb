from logilab.common.testlib import unittest_main, TestCase

from os.path import join

from cubicweb import CW_SOFTWARE_ROOT as BASE
from cubicweb.vregistry import VObject
from cubicweb.cwvreg import CubicWebRegistry, UnknownProperty
from cubicweb.devtools import TestServerConfiguration
from cubicweb.entities.lib import Card
from cubicweb.interfaces import IMileStone

class YesSchema:
    def __contains__(self, something):
        return True

WEBVIEWSDIR = join(BASE, 'web', 'views')
    
class VRegistryTC(TestCase):

    def setUp(self):
        config = TestServerConfiguration('data')
        self.vreg = CubicWebRegistry(config)
        config.bootstrap_cubes()
        self.vreg.schema = config.load_schema()
        
    def test_load(self):
        self.vreg.init_registration([WEBVIEWSDIR])
        self.vreg.load_file(join(WEBVIEWSDIR, 'euser.py'), 'cubicweb.web.views.euser')
        self.vreg.load_file(join(WEBVIEWSDIR, 'baseviews.py'), 'cubicweb.web.views.baseviews')
        fpvc = [v for v in self.vreg.registry_objects('views', 'primary')
               if v.__module__ == 'cubicweb.web.views.euser'][0]
        fpv = fpvc(None, None)
        # don't want a TypeError due to super call
        self.assertRaises(AttributeError, fpv.render_entity_attributes, None, None)

    def test_load_interface_based_vojects(self):
        self.vreg.init_registration([WEBVIEWSDIR])
        self.vreg.load_file(join(WEBVIEWSDIR, 'idownloadable.py'), 'cubicweb.web.views.idownloadable')
        self.vreg.load_file(join(WEBVIEWSDIR, 'baseviews.py'), 'cubicweb.web.views.baseviews')
        # check loading baseviews after idownloadable isn't kicking interface based views
        self.assertEquals(len(self.vreg['views']['primary']), 2)
                              
    def test___selectors__compat(self):
        myselector1 = lambda *args: 1
        myselector2 = lambda *args: 1
        class AnAppObject(VObject):
            __selectors__ = (myselector1, myselector2)
        AnAppObject.build___select__()
        self.assertEquals(AnAppObject.__select__(AnAppObject), 2)

    def test_properties(self):
        self.failIf('system.version.cubicweb' in self.vreg['propertydefs'])
        self.failUnless(self.vreg.property_info('system.version.cubicweb'))
        self.assertRaises(UnknownProperty, self.vreg.property_info, 'a.non.existent.key')

    def test_load_subinterface_based_vobjects(self):
        self.vreg.reset()
        self.vreg.register_objects([join(BASE, 'web', 'views', 'iprogress.py')])
        # check progressbar was kicked
        self.failIf(self.vreg['views'].get('progressbar'))
        class MyCard(Card):
            __implements__ = (IMileStone,)
        self.vreg.reset()
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register_vobject_class(MyCard)
        self.vreg.register_objects([join(BASE, 'web', 'views', 'iprogress.py')])
        # check progressbar isn't kicked
        self.assertEquals(len(self.vreg['views']['progressbar']), 1)
        

if __name__ == '__main__':
    unittest_main()
