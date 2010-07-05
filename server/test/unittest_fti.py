from __future__ import with_statement

from cubicweb.devtools import ApptestConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.selectors import is_instance
from cubicweb.entities.adapters import IFTIndexableAdapter

class PostgresFTITC(CubicWebTC):
    config = ApptestConfiguration('data', sourcefile='sources_fti')

    def test_occurence_count(self):
        req = self.request()
        c1 = req.create_entity('Card', title=u'c1',
                               content=u'cubicweb cubicweb cubicweb')
        c2 = req.create_entity('Card', title=u'c3',
                               content=u'cubicweb')
        c3 = req.create_entity('Card', title=u'c2',
                               content=u'cubicweb cubicweb')
        self.commit()
        self.assertEquals(req.execute('Card X ORDERBY FTIRANK(X) DESC WHERE X has_text "cubicweb"').rows,
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
            self.assertEquals(req.execute('Card X ORDERBY FTIRANK(X) DESC WHERE X has_text "cubicweb"').rows,
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
            self.assertEquals(req.execute('Any X ORDERBY FTIRANK(X) DESC WHERE X has_text "cubicweb"').rows,
                              [[c1.eid], [c3.eid], [c2.eid]])
