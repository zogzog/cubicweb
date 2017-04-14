# copyright 2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common import tempattr

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sources import datafeed


class SynchronizeSourceTC(CubicWebTC):

    def test_synchronize_view(self):
        with self.admin_access.web_request(vid='cw.source-sync') as req:

            class AParser(datafeed.DataFeedParser):
                __regid__ = 'testparser'

                def process(self, url, raise_on_error=False):
                    pass

            with self.temporary_appobjects(AParser):
                source = req.create_entity('CWSource', name=u'ext', type=u'datafeed',
                                           parser=u'cw.entityxml', url=u'whatever')
                req.cnx.commit()

            self.threads = 0

            def threaded_task(func):
                self.threads += 1

            with tempattr(req.cnx.repo, 'threaded_task', threaded_task):
                path, args = self.expect_redirect_handle_request(
                    req, path=source.rest_path())
                self.assertEqual(self.threads, 1)
                self.assertTrue(path.startswith('cwdataimport/'))


if __name__ == '__main__':
    import unittest
    unittest.main()
