"""unit tests for selectors mechanism

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.vregistry import Selector, AndSelector, OrSelector

class _1_(Selector):
    def __call__(self, *args, **kwargs):
        return 1

class _0_(Selector):
    def __call__(self, *args, **kwargs):
        return 0

def _2_(*args, **kwargs):
    return 2


class SelectorsTC(TestCase):
    def test_basic_and(self):
        selector = _1_() & _1_()
        self.assertEquals(selector(None), 2)
        selector = _1_() & _0_()
        self.assertEquals(selector(None), 0)
        selector = _0_() & _1_()
        self.assertEquals(selector(None), 0)

    def test_basic_or(self):
        selector = _1_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _1_() | _0_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _0_()
        self.assertEquals(selector(None), 0)

    def test_selector_and_function(self):
        selector = _1_() & _2_
        self.assertEquals(selector(None), 3)
        selector = _2_ & _1_()
        self.assertEquals(selector(None), 3)
        
    def test_three_and(self):
        selector = _1_() & _1_() & _1_()
        self.assertEquals(selector(None), 3)
        selector = _1_() & _0_() & _1_()
        self.assertEquals(selector(None), 0)
        selector = _0_() & _1_() & _1_()
        self.assertEquals(selector(None), 0)

    def test_three_or(self):
        selector = _1_() | _1_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _1_() | _0_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _1_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _0_() | _0_()
        self.assertEquals(selector(None), 0)

    def test_composition(self):
        selector = (_1_() & _1_()) & (_1_() & _1_())
        self.failUnless(isinstance(selector, AndSelector))
        self.assertEquals(len(selector.selectors), 4)
        self.assertEquals(selector(None), 4)
        selector = (_1_() & _0_()) | (_1_() & _1_())
        self.failUnless(isinstance(selector, OrSelector))
        self.assertEquals(len(selector.selectors), 2)
        self.assertEquals(selector(None), 2)


if __name__ == '__main__':
    unittest_main()

