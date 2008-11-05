from logilab.common.testlib import unittest_main, TestCase

from os.path import join

from cubicweb import CW_SOFTWARE_ROOT as BASE
from cubicweb.vregistry import VObject
from cubicweb.cwvreg import CubicWebRegistry, UnknownProperty
from cubicweb.cwconfig import CubicWebConfiguration

class YesSchema:
    def __contains__(self, something):
        return True
    
class VRegistryTC(TestCase):

    def setUp(self):
        config = CubicWebConfiguration('data')
        self.vreg = CubicWebRegistry(config)
        self.vreg.schema = YesSchema()

    def test_load(self):
        self.vreg.load_file(join(BASE, 'web', 'views'), 'euser.py')
        self.vreg.load_file(join(BASE, 'web', 'views'), 'baseviews.py')
        fpvc = [v for v in self.vreg.registry_objects('views', 'primary') if v.accepts[0] == 'EUser'][0]
        fpv = fpvc(None, None)
        # don't want a TypeError due to super call
        self.assertRaises(AttributeError, fpv.render_entity_attributes, None, None)

    def test_load_interface_based_vojects(self):
        self.vreg.load_file(join(BASE, 'web', 'views'), 'idownloadable.py')
        self.vreg.load_file(join(BASE, 'web', 'views'), 'baseviews.py')
        # check loading baseviews after idownloadable isn't kicking interface based views
        self.assertEquals(len(self.vreg['views']['primary']), 2)
                              
    def test_autoselectors(self):
        myselector1 = lambda *args: 1
        myselector2 = lambda *args: 1
        class AnAppObject(VObject):
            __selectors__ = (myselector1, myselector2)
        self.assertEquals(AnAppObject.__select__(), 2)

    def test_properties(self):
        self.failIf('system.version.cubicweb' in self.vreg['propertydefs'])
        self.failUnless(self.vreg.property_info('system.version.cubicweb'))
        self.assertRaises(UnknownProperty, self.vreg.property_info, 'a.non.existent.key')
        

if __name__ == '__main__':
    unittest_main()
