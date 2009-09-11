from cubicweb.devtools.testlib import WebTest

class BreadCrumbsTC(WebTest):

    def test_base(self):
        f1 = self.add_entity('Folder', name=u'par&ent')
        f2 = self.add_entity('Folder', name=u'chi&ld')
        self.execute('SET F2 filed_under F1 WHERE F1 eid %(f1)s, F2 eid %(f2)s',
                     {'f1' : f1.eid, 'f2' : f2.eid})
        self.commit()
        childrset = self.execute('Folder F WHERE F eid %s' % f2.eid)
        self.assertEquals(childrset.get_entity(0,0).view('breadcrumbs'),
                          '<a href="http://testing.fr/cubicweb/folder/%s" title="">chi&amp;ld</a>' % f1.eid)
        ibc = self.vreg['components'].select('breadcrumbs', self.request(), rset=childrset)
        self.assertEquals(ibc.render(),
                          """<span id="breadcrumbs" class="pathbar">&#160;&gt;&#160;<a href="http://testing.fr/cubicweb/Folder">folder_plural</a>&#160;&gt;&#160;<a href="http://testing.fr/cubicweb/folder/%s" title="">par&amp;ent</a>&#160;&gt;&#160;
chi&amp;ld</span>""" % f2.eid)
