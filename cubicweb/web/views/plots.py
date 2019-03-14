# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""basic plot views"""

from logilab.common.registry import objectify_predicate
from logilab.mtconverter import xml_escape

from cubicweb.utils import UStringIO
from cubicweb.predicates import multi_columns_rset
from cubicweb.web.views import baseviews

@objectify_predicate
def all_columns_are_numbers(cls, req, rset=None, *args, **kwargs):
    """accept result set with at least one line and two columns of result
    all columns after second must be of numerical types"""
    for etype in rset.description[0]:
        if etype not in ('Int', 'BigInt', 'Float'):
            return 0
    return 1

@objectify_predicate
def second_column_is_number(cls, req, rset=None, *args, **kwargs):
    etype = rset.description[0][1]
    if etype not  in ('Int', 'BigInt', 'Float'):
        return 0
    return 1

@objectify_predicate
def columns_are_date_then_numbers(cls, req, rset=None, *args, **kwargs):
    etypes = rset.description[0]
    if etypes[0] not in ('Date', 'Datetime', 'TZDatetime'):
        return 0
    for etype in etypes[1:]:
        if etype not in ('Int', 'BigInt', 'Float'):
            return 0
    return 1


def filterout_nulls(abscissa, plot):
    filtered = []
    for x, y in zip(abscissa, plot):
        if x is None or y is None:
            continue
        filtered.append( (x, y) )
    return sorted(filtered)

class PlotWidget(object):
    # XXX refactor with cubicweb.web.views.htmlwidgets.HtmlWidget
    def _initialize_stream(self, w=None):
        if w:
            self.w = w
        else:
            self._stream = UStringIO()
            self.w = self._stream.write

    def render(self, *args, **kwargs):
        w = kwargs.pop('w', None)
        self._initialize_stream(w)
        self._render(*args, **kwargs)
        if w is None:
            return self._stream.getvalue()

    def _render(self, *args, **kwargs):
        raise NotImplementedError


try:
    from GChartWrapper import Pie, Pie3D
except ImportError:
    pass
else:

    class PieChartWidget(PlotWidget):
        def __init__(self, labels, values, pieclass=Pie, title=None):
            self.labels = labels
            self.values = values
            self.pieclass = pieclass
            self.title = title

        def _render(self, width=None, height=None):
            piechart = self.pieclass(self.values)
            piechart.label(*self.labels)
            if width is not None:
                height = height or width
                piechart.size(width, height)
            if self.title:
                piechart.title(self.title)
            self.w(u'<img src="%s" />' % xml_escape(piechart.url))

    class PieChartView(baseviews.AnyRsetView):
        __regid__ = 'piechart'
        pieclass = Pie
        paginable = False

        __select__ = multi_columns_rset() & second_column_is_number()

        def _guess_vid(self, row):
            etype = self.cw_rset.description[row][0]
            if self._cw.vreg.schema.eschema(etype).final:
                return 'final'
            return 'textincontext'

        def call(self, title=None, width=None, height=None):
            labels = []
            values = []
            for rowidx, (_, value) in enumerate(self.cw_rset):
                if value is not None:
                    vid = self._guess_vid(rowidx)
                    label = '%s: %s' % (self._cw.view(vid, self.cw_rset, row=rowidx, col=0),
                                        value)
                    labels.append(label.encode(self._cw.encoding))
                    values.append(value)
            pie = PieChartWidget(labels, values, pieclass=self.pieclass,
                                 title=title)
            if width is not None:
                height = height or width
            pie.render(width, height, w=self.w)


    class PieChart3DView(PieChartView):
        __regid__ = 'piechart3D'
        pieclass = Pie3D
