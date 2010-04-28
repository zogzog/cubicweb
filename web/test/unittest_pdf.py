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
import os.path as osp
from tempfile import NamedTemporaryFile
from subprocess import Popen as sub
from xml.etree.cElementTree import ElementTree, fromstring, tostring, dump

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.utils import can_do_pdf_conversion
from cubicweb.ext.xhtml2fo import ReportTransformer

DATADIR = osp.join(osp.dirname(__file__), 'data')

class PDFTC(TestCase):

    def test_xhtml_to_fop_to_pdf(self):
        if not can_do_pdf_conversion():
            self.skip('dependencies not available : check pysixt and fop')
        xmltree = ElementTree()
        xmltree.parse(osp.join(DATADIR, 'sample1.xml'))
        foptree = ReportTransformer(u'contentmain').transform(xmltree)
        # next
        foptmp = NamedTemporaryFile()
        foptree.write(foptmp)
        foptmp.flush()
        pdftmp = NamedTemporaryFile()
        fopproc = sub(['/usr/bin/fop', foptmp.name, pdftmp.name])
        fopproc.wait()
        del foptmp
        if fopproc.returncode:
            self.skip('fop returned status %s' % fopproc.returncode)
        pdftmp.seek(0) # a bit superstitious
        reference = open(osp.join(DATADIR, 'sample1.pdf'), 'r').read()
        output = pdftmp.read()
        # XXX almost equals due to ID, creation date, so it seems to fail
        self.assertEquals( len(output), len(reference) )
        # cut begin & end 'cause they contain variyng data
        self.assertTextEquals(output[150:1500], reference[150:1500])

if __name__ == '__main__':
    unittest_main()

