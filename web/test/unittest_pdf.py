from unittest import TestCase
import os.path as osp
from xml.etree.cElementTree import ElementTree, fromstring, tostring, dump

from tempfile import NamedTemporaryFile
from subprocess import Popen as sub

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
        pdftmp.seek(0) # a bit superstitious
        reference = open(osp.join(DATADIR, 'sample1.pdf'), 'r').read()
        output = pdftmp.read()
        # XXX almost equals due to ID, creation date, so it seems to fail
        self.assertTextEquals(output, reference)
