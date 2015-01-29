# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common.testlib import unittest_main
from logilab.mtconverter import html_unescape

from cubicweb.devtools.htmlparser import XMLValidator
from cubicweb.devtools.testlib import CubicWebTC


class TreeViewTC(CubicWebTC):

    def test_treeview(self):
        with self.admin_access.repo_cnx() as cnx:
            ce = cnx.create_entity
            root = ce('TreeNode', name=u'root')
            node = ce('TreeNode', name=u'node1', parent=root)
            ce('TreeNode', name=u'leaf1a', parent=node)
            ce('TreeNode', name=u'leaf1b', parent=node)
            node = ce('TreeNode', name=u'node2', parent=root)
            ce('TreeNode', name=u'leaf2a', parent=node)
            ce('TreeNode', name=u'leaf2b', parent=node)
            root_eid = root.eid
            cnx.commit()

        with self.admin_access.web_request() as req:
            root = req.entity_from_eid(root_eid)
            valid = self.content_type_validators.get('text/html', XMLValidator)()
            page = valid.parse_string(root.view('tree', klass='oh-my-class'))
            uls = page.find_tag('ul', gettext=False)
            for _, attrib in uls:
                self.assertEqual(attrib['class'], 'oh-my-class')


if __name__ == '__main__':
    unittest_main()
