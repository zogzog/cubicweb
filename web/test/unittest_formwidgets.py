# copyright 2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unittests for cw.web.formwidgets"""

from logilab.common.testlib import TestCase, unittest_main, mock_object as mock

from cubicweb.devtools import TestServerConfiguration, fake
from cubicweb.web import uicfg, formwidgets, formfields

from cubes.file.entities import File

def setUpModule(*args):
    global schema
    config = TestServerConfiguration('data', apphome=WidgetsTC.datadir)
    config.bootstrap_cubes()
    schema = config.load_schema()

class WidgetsTC(TestCase):

    def test_state_fields(self):
        field = formfields.guess_field(schema['Bookmark'], schema['path'])
        widget = formwidgets.EditableURLWidget()
        req = fake.FakeRequest(form={'path-subjectfqs:A': 'param=value&vid=view'})
        form = mock(_cw=req, formvalues={}, edited_entity=mock(eid='A'))
        self.assertEqual(widget.process_field_data(form, field),
                         '?param=value%26vid%3Dview')

if __name__ == '__main__':
    unittest_main()
