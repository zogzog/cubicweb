from cubicweb.devtools.testlib import CubicWebTC

class BreadCrumbsTC(CubicWebTC):

    def test_base(self):
        req = self.request()
        f1 = req.create_entity('Folder', name=u'par&ent')
        f2 = req.create_entity('Folder', name=u'chi&ld')
        self.execute('SET F2 filed_under F1 WHERE F1 eid %(f1)s, F2 eid %(f2)s',
                     {'f1' : f1.eid, 'f2' : f2.eid})
        self.commit()
        self.assertEquals(f2.view('breadcrumbs'),
                          '<a href="http://testing.fr/cubicweb/folder/%s" title="">chi&amp;ld</a>' % f2.eid)
        childrset = f2.as_rset()
        ibc = self.vreg['components'].select('breadcrumbs', self.request(), rset=childrset)
        self.assertEquals(ibc.render(),
                          """<span id="breadcrumbs" class="pathbar">&#160;&gt;&#160;<a href="http://testing.fr/cubicweb/Folder">folder_plural</a>&#160;&gt;&#160;<a href="http://testing.fr/cubicweb/folder/%s" title="">par&amp;ent</a>&#160;&gt;&#160;
chi&amp;ld</span>""" % f1.eid)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
