"""csv export views

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.schema import display_name
from cubicweb.uilib import UnicodeCSVWriter
from cubicweb.view import EntityView, AnyRsetView

class CSVMixIn(object):
    """mixin class for CSV views"""
    templatable = False
    content_type = "text/comma-separated-values"
    binary = True # avoid unicode assertion
    csv_params = {'dialect': 'excel',
                  'quotechar': '"',
                  'delimiter': ';',
                  'lineterminator': '\n'}

    def set_request_content_type(self):
        """overriden to set a .csv filename"""
        self._cw.set_content_type(self.content_type, filename='cubicwebexport.csv')

    def csvwriter(self, **kwargs):
        params = self.csv_params.copy()
        params.update(kwargs)
        return UnicodeCSVWriter(self.w, self._cw.encoding, **params)


class CSVRsetView(CSVMixIn, AnyRsetView):
    """dumps raw result set in CSV"""
    __regid__ = 'csvexport'
    title = _('csv export')

    def call(self):
        writer = self.csvwriter()
        writer.writerow(self.columns_labels())
        rset, descr = self.cw_rset, self.cw_rset.description
        eschema = self._cw.schema.eschema
        for rowindex, row in enumerate(rset):
            csvrow = []
            for colindex, val in enumerate(row):
                etype = descr[rowindex][colindex]
                if val is not None and not eschema(etype).final:
                    # csvrow.append(val) # val is eid in that case
                    content = self._cw.view('textincontext', rset,
                                            row=rowindex, col=colindex)
                else:
                    content = self._cw.view('final', rset,
                                            format='text/plain',
                                            row=rowindex, col=colindex)
                csvrow.append(content)
            writer.writerow(csvrow)


class CSVEntityView(CSVMixIn, EntityView):
    """dumps rset's entities (with full set of attributes) in CSV

    the generated CSV file will have a table per entity type found in the
    resultset. ('table' here only means empty lines separation between table
    contents)
    """
    __regid__ = 'ecsvexport'
    title = _('csv entities export')

    def call(self):
        req = self._cw
        rows_by_type = {}
        writer = self.csvwriter()
        rowdef_by_type = {}
        for index in xrange(len(self.cw_rset)):
            entity = self.cw_rset.complete_entity(index)
            if entity.e_schema not in rows_by_type:
                rowdef_by_type[entity.e_schema] = [rs for rs, at in entity.e_schema.attribute_definitions()
                                                   if at != 'Bytes']
                rows_by_type[entity.e_schema] = [[display_name(req, rschema.type)
                                                  for rschema in rowdef_by_type[entity.e_schema]]]
            rows = rows_by_type[entity.e_schema]
            rows.append([entity.printable_value(rs.type, format='text/plain')
                         for rs in rowdef_by_type[entity.e_schema]])
        for rows in rows_by_type.itervalues():
            writer.writerows(rows)
            # use two empty lines as separator
            writer.writerows([[], []])

