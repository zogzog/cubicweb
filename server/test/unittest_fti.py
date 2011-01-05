from __future__ import with_statement

import socket

from cubicweb.devtools import ApptestConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.selectors import is_instance
from cubicweb.entities.adapters import IFTIndexableAdapter

AT_LOGILAB = socket.gethostname().endswith('.logilab.fr')

from logilab.common.testlib import SkipTest


class PostgresFTITC(CubicWebTC):
    config = ApptestConfiguration('data', sourcefile='sources_fti')

    @classmethod
    def setUpClass(cls):
        if not AT_LOGILAB:
            raise SkipTest('XXX %s: require logilab configuration' % cls.__name__)

    def test_occurence_count(self):
        req = self.request()
        c1 = req.create_entity('Card', title=u'c1',
                               content=u'cubicweb cubicweb cubicweb')
        c2 = req.create_entity('Card', title=u'c3',
                               content=u'cubicweb')
        c3 = req.create_entity('Card', title=u'c2',
                               content=u'cubicweb cubicweb')
        self.commit()
        self.assertEqual(req.execute('Card X ORDERBY FTIRANK(X) DESC WHERE X has_text "cubicweb"').rows,
                          [[c1.eid], [c3.eid], [c2.eid]])


    def test_attr_weight(self):
        class CardIFTIndexableAdapter(IFTIndexableAdapter):
            __select__ = is_instance('Card')
            attr_weight = {'title': 'A'}
        with self.temporary_appobjects(CardIFTIndexableAdapter):
            req = self.request()
            c1 = req.create_entity('Card', title=u'c1',
                                   content=u'cubicweb cubicweb cubicweb')
            c2 = req.create_entity('Card', title=u'c2',
                                   content=u'cubicweb cubicweb')
            c3 = req.create_entity('Card', title=u'cubicweb',
                                   content=u'autre chose')
            self.commit()
            self.assertEqual(req.execute('Card X ORDERBY FTIRANK(X) DESC WHERE X has_text "cubicweb"').rows,
                              [[c3.eid], [c1.eid], [c2.eid]])

    def test_entity_weight(self):
        class PersonneIFTIndexableAdapter(IFTIndexableAdapter):
            __select__ = is_instance('Personne')
            entity_weight = 2.0
        with self.temporary_appobjects(PersonneIFTIndexableAdapter):
            req = self.request()
            c1 = req.create_entity('Personne', nom=u'c1', prenom=u'cubicweb')
            c2 = req.create_entity('Comment', content=u'cubicweb cubicweb', comments=c1)
            c3 = req.create_entity('Comment', content=u'cubicweb cubicweb cubicweb', comments=c1)
            self.commit()
            self.assertEqual(req.execute('Any X ORDERBY FTIRANK(X) DESC WHERE X has_text "cubicweb"').rows,
                              [[c1.eid], [c3.eid], [c2.eid]])


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
