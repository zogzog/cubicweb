# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

from cubicweb.devtools.testlib import CubicWebTC


class BreadCrumbsTC(CubicWebTC):

    def test_base(self):
        with self.admin_access.web_request() as req:
            f1 = req.create_entity('Folder', name=u'par&ent')
            f2 = req.create_entity('Folder', name=u'chi&ld')
            req.cnx.execute('SET F2 filed_under F1 WHERE F1 eid %(f1)s, F2 eid %(f2)s',
                            {'f1' : f1.eid, 'f2' : f2.eid})
            req.cnx.commit()
            self.assertEqual(f2.view('breadcrumbs'),
                             '<a href="http://testing.fr/cubicweb/folder/%s" title="">'
                             'chi&amp;ld</a>' % f2.eid)
            childrset = f2.as_rset()
            ibc = self.vreg['ctxcomponents'].select('breadcrumbs', req, rset=childrset)
            l = []
            ibc.render(l.append)
            self.assertMultiLineEqual('<span id="breadcrumbs" class="pathbar">&#160;&gt;&#160;'
                                      '<a href="http://testing.fr/cubicweb/Folder">Folder_plural</a>'
                                      '&#160;&gt;&#160;<a href="http://testing.fr/cubicweb/folder/%s" '
                                      'title="">par&amp;ent</a>&#160;&gt;&#160;\n'
                                      '<a href="http://testing.fr/cubicweb/folder/%s" title="">'
                                      'chi&amp;ld</a></span>' % (f1.eid, f2.eid),
                                      ''.join(l))

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
