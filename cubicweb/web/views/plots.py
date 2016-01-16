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

__docformat__ = "restructuredtext en"
from cubicweb import _

from six import add_metaclass
from six.moves import range

from logilab.common.date import datetime2ticks
from logilab.common.deprecation import class_deprecated
from logilab.common.registry import objectify_predicate
from logilab.mtconverter import xml_escape

from cubicweb.utils import UStringIO, json_dumps
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


@add_metaclass(class_deprecated)
class FlotPlotWidget(PlotWidget):
    """PlotRenderer widget using Flot"""
    __deprecation_warning__ = '[3.14] cubicweb.web.views.plots module is deprecated, use the jqplot cube instead'
    onload = u"""
var fig = jQuery('#%(figid)s');
if (fig.attr('cubicweb:type') != 'prepared-plot') {
    %(plotdefs)s
    jQuery.plot(jQuery('#%(figid)s'), [%(plotdata)s],
        {points: {show: true},
         lines: {show: true},
         grid: {hoverable: true},
         /*yaxis : {tickFormatter : suffixFormatter},*/
         xaxis: {mode: %(mode)s}});
    jQuery('#%(figid)s').data({mode: %(mode)s, dateformat: %(dateformat)s});
    jQuery('#%(figid)s').bind('plothover', onPlotHover);
    fig.attr('cubicweb:type','prepared-plot');
}
"""

    def __init__(self, labels, plots, timemode=False):
        self.labels = labels
        self.plots = plots # list of list of couples
        self.timemode = timemode

    def dump_plot(self, plot):
        if self.timemode:
            plot = [(datetime2ticks(x), y) for x, y in plot]
        return json_dumps(plot)

    def _render(self, req, width=500, height=400):
        if req.ie_browser():
            req.add_js('excanvas.js')
        req.add_js(('jquery.flot.js', 'cubicweb.flot.js'))
        figid = u'figure%s' % next(req.varmaker)
        plotdefs = []
        plotdata = []
        self.w(u'<div id="%s" style="width: %spx; height: %spx;"></div>' %
               (figid, width, height))
        for idx, (label, plot) in enumerate(zip(self.labels, self.plots)):
            plotid = '%s_%s' % (figid, idx)
            plotdefs.append('var %s = %s;' % (plotid, self.dump_plot(plot)))
            # XXX ugly but required in order to not crash my demo
            plotdata.append("{label: '%s', data: %s}" % (label.replace(u'&', u''), plotid))
        fmt = req.property_value('ui.date-format') # XXX datetime-format
        # XXX TODO make plot options customizable
        req.html_headers.add_onload(self.onload %
                                    {'plotdefs': '\n'.join(plotdefs),
                                     'figid': figid,
                                     'plotdata': ','.join(plotdata),
                                     'mode': self.timemode and "'time'" or 'null',
                                     'dateformat': '"%s"' % fmt})


@add_metaclass(class_deprecated)
class PlotView(baseviews.AnyRsetView):
    __deprecation_warning__ = '[3.14] cubicweb.web.views.plots module is deprecated, use the jqplot cube instead'
    __regid__ = 'plot'
    title = _('generic plot')
    __select__ = multi_columns_rset() & all_columns_are_numbers()
    timemode = False
    paginable = False

    def call(self, width=500, height=400):
        # prepare data
        rqlst = self.cw_rset.syntax_tree()
        # XXX try to make it work with unions
        varnames = [var.name for var in rqlst.children[0].get_selected_variables()][1:]
        abscissa = [row[0] for row in self.cw_rset]
        plots = []
        nbcols = len(self.cw_rset.rows[0])
        for col in range(1, nbcols):
            data = [row[col] for row in self.cw_rset]
            plots.append(filterout_nulls(abscissa, data))
        plotwidget = FlotPlotWidget(varnames, plots, timemode=self.timemode)
        plotwidget.render(self._cw, width, height, w=self.w)


class TimeSeriePlotView(PlotView):
    __select__ = multi_columns_rset() & columns_are_date_then_numbers()
    timemode = True


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
