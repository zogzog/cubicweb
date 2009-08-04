"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.goa.testlib import *

from cubicweb.interfaces import ICalendarable


class Blog(db.Model):
    diem = db.DateProperty(required=True, auto_now_add=True)
    title = db.StringProperty(required=True)
    content = db.TextProperty()

    __implements__ = (ICalendarable,)

    @property
    def start(self):
        return self.diem

    @property
    def stop(self):
        return self.diem

    def matching_dates(self, begin, end):
        """calendar views interface"""
        mydate = self.diem
        if mydate:
            return [mydate]
        return []


class SomeViewsTC(GAEBasedTC):
    MODEL_CLASSES = (Blog, )
    from cubicweb.web.views import basecontrollers, baseviews, navigation, boxes, calendar
    from data import views
    LOAD_APP_MODULES = (basecontrollers, baseviews, navigation, boxes, calendar, views)

    def setUp(self):
        GAEBasedTC.setUp(self)
        self.req = self.request()
        self.blog = Blog(title=u'a blog', content=u'hop')
        self.blog.put(self.req)

    def test_hcal(self):
        self.vreg['views'].render('hcal', self.req, rset=self.blog.rset)

    def test_django_index(self):
        self.vreg'views'].render('index', self.req, rset=None)

for vid in ('primary', 'oneline', 'incontext', 'outofcontext', 'text'):
    setattr(SomeViewsTC, 'test_%s'%vid, lambda self, vid=vid: self.blog.view(vid))

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
