# -*- coding: utf-8 -*-
# copyright 2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from functools import partial

from logilab.common.testlib import unittest_main

from cubicweb.devtools.testlib import CubicWebTC, real_error_handling
from cubicweb import view
from cubicweb.predicates import is_instance

class IDownloadableUser(view.EntityAdapter):
    __regid__ = 'IDownloadable'
    __select__ = is_instance('CWUser')

    def download_content_type(self):
        """return MIME type of the downloadable content"""
        return 'text/plain'

    def download_encoding(self):
        """return encoding of the downloadable content"""
        return 'ascii'

    def download_file_name(self):
        """return file name of the downloadable content"""
        return  self.entity.name() + '.txt'

    def download_data(self):
        return 'Babar is not dead!'


class BrokenIDownloadableGroup(IDownloadableUser):
    __regid__ = 'IDownloadable'
    __select__ = is_instance('CWGroup')

    def download_file_name(self):
        return  self.entity.name + '.txt'

    def download_data(self):
        raise IOError()

class IDownloadableTC(CubicWebTC):

    def setUp(self):
        super(IDownloadableTC, self).setUp()
        self.vreg.register(IDownloadableUser)
        self.addCleanup(partial(self.vreg.unregister, IDownloadableUser))

    def test_header_simple_case(self):
        with self.admin_access.web_request() as req:
            req.form['vid'] = 'download'
            req.form['eid'] = str(req.user.eid)
            data = self.ctrl_publish(req, 'view')
            get = req.headers_out.getRawHeaders
            self.assertEqual(['attachment;filename="admin.txt"'],
                             get('content-disposition'))
            self.assertEqual(['text/plain;charset=ascii'],
                             get('content-type'))
            self.assertEqual('Babar is not dead!', data)

    def test_header_with_space(self):
        with self.admin_access.web_request() as req:
            self.create_user(req, login=u'c c l a', password='babar')
            req.cnx.commit()
        with self.new_access(u'c c l a').web_request() as req:
            req.form['vid'] = 'download'
            req.form['eid'] = str(req.user.eid)
            data = self.ctrl_publish(req,'view')
            get = req.headers_out.getRawHeaders
            self.assertEqual(['attachment;filename="c c l a.txt"'],
                             get('content-disposition'))
            self.assertEqual(['text/plain;charset=ascii'],
                             get('content-type'))
            self.assertEqual('Babar is not dead!', data)

    def test_header_with_space_and_comma(self):
        with self.admin_access.web_request() as req:
            self.create_user(req, login=ur'c " l\ a', password='babar')
            req.cnx.commit()
        with self.new_access(ur'c " l\ a').web_request() as req:
            req.form['vid'] = 'download'
            req.form['eid'] = str(req.user.eid)
            data = self.ctrl_publish(req,'view')
            get = req.headers_out.getRawHeaders
            self.assertEqual([r'attachment;filename="c \" l\\ a.txt"'],
                             get('content-disposition'))
            self.assertEqual(['text/plain;charset=ascii'],
                             get('content-type'))
            self.assertEqual('Babar is not dead!', data)

    def test_header_unicode_filename(self):
        with self.admin_access.web_request() as req:
            self.create_user(req, login=u'cécilia', password='babar')
            req.cnx.commit()
        with self.new_access(u'cécilia').web_request() as req:
            req.form['vid'] = 'download'
            req.form['eid'] = str(req.user.eid)
            self.ctrl_publish(req,'view')
            get = req.headers_out.getRawHeaders
            self.assertEqual(['''attachment;filename="ccilia.txt";filename*=utf-8''c%C3%A9cilia.txt'''],
                             get('content-disposition'))

    def test_header_unicode_long_filename(self):
        name = u'Bèrte_hô_grand_nôm_ça_va_totallement_déborder_de_la_limite_là'
        with self.admin_access.web_request() as req:
            self.create_user(req, login=name, password='babar')
            req.cnx.commit()
        with self.new_access(name).web_request() as req:
            req.form['vid'] = 'download'
            req.form['eid'] = str(req.user.eid)
            self.ctrl_publish(req,'view')
            get = req.headers_out.getRawHeaders
            self.assertEqual(["""attachment;filename="Brte_h_grand_nm_a_va_totallement_dborder_de_la_limite_l.txt";filename*=utf-8''B%C3%A8rte_h%C3%B4_grand_n%C3%B4m_%C3%A7a_va_totallement_d%C3%A9border_de_la_limite_l%C3%A0.txt"""],
                             get('content-disposition'))


    def test_download_data_error(self):
        self.vreg.register(BrokenIDownloadableGroup)
        self.addCleanup(partial(self.vreg.unregister, BrokenIDownloadableGroup))
        with self.admin_access.web_request() as req:
            req.form['vid'] = 'download'
            req.form['eid'] = str(req.execute('CWGroup X WHERE X name "managers"')[0][0])
            with real_error_handling(self.app):
                data = self.app_handle_request(req)
            get = req.headers_out.getRawHeaders
            self.assertEqual(['text/html;charset=UTF-8'],
                             get('content-type'))
            self.assertEqual(None,
                             get('content-disposition'))
            self.assertEqual(req.status_out, 500)

if __name__ == '__main__':
    unittest_main()
