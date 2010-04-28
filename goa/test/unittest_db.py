# -*- coding: utf-8 -*-
# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""

"""
from cubicweb.goa.testlib import *

from cubicweb import Binary
from cubicweb.goa.goaconfig import GAEConfiguration
from cubicweb.server.utils import crypt_password

from google.appengine.api.datastore_types import Text, Blob


class Blog(db.Model):
    data = db.BlobProperty()

class DBTest(GAEBasedTC):
    config = GAEConfiguration('toto')
    config.global_set_option('use-google-auth', False)

    MODEL_CLASSES = (Blog,)

    def test_set_none_relation(self):
        eprop = self.add_entity('CWProperty', pkey=u'ui.language', value=u'en')
        self.failUnless('s_for_user' in eprop._dbmodel)
        self.assertEquals(eprop._dbmodel['s_for_user'], None)

    def test_euser_key(self):
        euser = self.add_entity('CWUser', login=u'toto', upassword='toto')
        self.assertEquals(euser.key().name(), 'key_toto')

    def test_egroup_key(self):
        egroup = self.add_entity('CWGroup', name=u'toto')
        self.assertEquals(egroup.key().name(), 'key_toto')

    def test_password_encryption(self):
        euser = self.add_entity('CWUser', login=u'toto', upassword='toto')
        self.failUnless(euser.upassword != 'toto', euser.upassword)
        self.assertEquals(crypt_password('toto', euser.upassword[:2]), euser.upassword)

    def test_long_text(self):
        # datastore string type is limited to 500 bytes
        text = u'e'*501
        entity = self.add_entity('State', name=u'test', description=text)
        self.assertIsInstance(entity.description, unicode)
        self.failIf(isinstance(entity.description, Text))
        self.assertEquals(entity.description, text)

    def test_long_accentued_text(self):
        # datastore string type is limited to 500 bytes
        text = u'é'*500
        entity = self.add_entity('State', name=u'test', description=text)
        self.assertIsInstance(entity.description, unicode)
        self.failIf(isinstance(entity.description, Text))
        self.assertEquals(entity.description, text)

    def test_blob(self):
        data = 'e'*501
        entity = self.add_entity('Blog', data=data)
        self.assertIsInstance(entity.data, Binary)
        value = entity.data.getvalue()
        self.failIf(isinstance(value, Blob))
        self.assertEquals(value, data)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
