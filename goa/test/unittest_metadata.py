"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.goa.testlib import *

import time
from mx.DateTime import DateTimeType
from datetime import datetime
from cubicweb.goa import db

from google.appengine.api import datastore

class Article(db.Model):
    content = db.TextProperty()
    synopsis = db.StringProperty(default='hello')

class Blog(db.Model):
    diem = db.DateProperty(required=True, auto_now_add=True)
    title = db.StringProperty(required=True)
    content = db.TextProperty()
    talks_about = db.ReferenceProperty(Article)
    cites = db.SelfReferenceProperty()


class MetaDataTC(GAEBasedTC):
    MODEL_CLASSES = (Article, Blog)

    def setUp(self):
        GAEBasedTC.setUp(self)
        self.req = self.request()
        self.a = self.add_entity('Article')
        self.p = self.add_entity('CWProperty', pkey=u'ui.language', value=u'en')
        self.session.commit()

    def _test_timestamp(self, entity, attr, sleep=0.1):
        timestamp = getattr(entity, attr)
        self.failUnless(timestamp)
        self.assertIsInstance(timestamp, DateTimeType)
        self.assertIsInstance(entity.to_gae_model()['s_'+attr], datetime)
        time.sleep(sleep)
        if entity.id == 'Article':
            entity.set_attributes(content=u'zou')
        else:
            entity.set_attributes(value=u'en')
        self.session.commit()
        return timestamp

    def test_creation_date_dbmodel(self):
        cdate = self._test_timestamp(self.a, 'creation_date')
        self.assertEquals(cdate, self.a.creation_date)

    def test_creation_date_yams(self):
        cdate = self._test_timestamp(self.p, 'creation_date')
        self.assertEquals(cdate, self.p.creation_date)

    def test_modification_date_dbmodel(self):
        mdate = self._test_timestamp(self.a, 'modification_date', sleep=1)
        a = self.execute('Any X WHERE X eid %(x)s', {'x': self.a.eid}, 'x').get_entity(0, 0)
        self.failUnless(mdate < a.modification_date, (mdate, a.modification_date))

    def test_modification_date_yams(self):
        mdate = self._test_timestamp(self.p, 'modification_date', sleep=1)
        p = self.execute('Any X WHERE X eid %(x)s', {'x': self.p.eid}, 'x').get_entity(0, 0)
        self.failUnless(mdate < p.modification_date, (mdate, p.modification_date))

    def _test_owned_by(self, entity):
        self.assertEquals(len(entity.owned_by), 1)
        owner = entity.owned_by[0]
        self.assertIsInstance(owner, db.Model)
        dbmodel = entity.to_gae_model()
        self.assertEquals(len(dbmodel['s_owned_by']), 1)
        self.assertIsInstance(dbmodel['s_owned_by'][0], datastore.Key)

    def test_owned_by_dbmodel(self):
        self._test_owned_by(self.a)

    def test_owned_by_yams(self):
        self._test_owned_by(self.p)

    def _test_created_by(self, entity):
        self.assertEquals(len(entity.created_by), 1)
        creator = entity.created_by[0]
        self.assertIsInstance(creator, db.Model)
        self.assertIsInstance(entity.to_gae_model()['s_created_by'], datastore.Key)

    def test_created_by_dbmodel(self):
        self._test_created_by(self.a)

    def test_created_by_dbmodel(self):
        self._test_created_by(self.p)

    def test_user_owns_dbmodel(self):
        self.failUnless(self.req.user.owns(self.a.eid))

    def test_user_owns_yams(self):
        self.failUnless(self.req.user.owns(self.p.eid))

    def test_is_relation(self):
        en = self.execute('Any EN WHERE E name EN, X is E, X eid %(x)s', {'x': self.a.eid}, 'x')[0][0]
        self.assertEquals(en, 'Article')
        en = self.execute('Any EN WHERE E name EN, X is E, X eid %(x)s', {'x': self.p.eid}, 'x')[0][0]
        self.assertEquals(en, 'CWProperty')
        en = self.execute('Any EN WHERE E name EN, X is E, X eid %(x)s', {'x': self.req.user.eid}, 'x')[0][0]
        self.assertEquals(en, 'CWUser')


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
