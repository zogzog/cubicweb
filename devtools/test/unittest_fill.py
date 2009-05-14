"""unit tests for cubicweb.devtools.fill module"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.schema import Schema, EntitySchema

import re
from cubicweb.devtools.fill import ValueGenerator, _ValueGenerator

ISODATE_SRE = re.compile('(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$')


class AutoExtendableTC(TestCase):

    def setUp(self):
        self.attrvalues = dir(_ValueGenerator)

    def tearDown(self):
        attrvalues = set(dir(_ValueGenerator))
        for attrname in attrvalues - set(self.attrvalues):
            delattr(_ValueGenerator, attrname)


    def test_autoextend(self):
        self.failIf('generate_server' in dir(ValueGenerator))
        class MyValueGenerator(ValueGenerator):
            def generate_server(self, index):
                return attrname
        self.failUnless('generate_server' in dir(ValueGenerator))


    def test_bad_signature_detection(self):
        self.failIf('generate_server' in dir(ValueGenerator))
        try:
            class MyValueGenerator(ValueGenerator):
                def generate_server(self):
                    pass
        except TypeError:
            self.failIf('generate_server' in dir(ValueGenerator))
        else:
            self.fail('TypeError not raised')


    def test_signature_extension(self):
        self.failIf('generate_server' in dir(ValueGenerator))
        class MyValueGenerator(ValueGenerator):
            def generate_server(self, index, foo):
                pass
        self.failUnless('generate_server' in dir(ValueGenerator))


if __name__ == '__main__':
    unittest_main()
