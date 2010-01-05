"""basic plot views

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
import time

from simplejson import dumps

from logilab.common import flatten
from logilab.mtconverter import xml_escape

from cubicweb.utils import make_uid, UStringIO, datetime2ticks
from cubicweb.appobject import objectify_selector
from cubicweb.web.views import baseviews

@objectify_selector
def at_least_two_columns(cls, req, rset=None, *args, **kwargs):
    if not rset:
        return 0
    return len(rset.rows[0]) >= 2

@objectify_selector
def all_columns_are_numbers(cls, req, rset=None, *args, **kwargs):
    """accept result set with at least one line and two columns of result
    all columns after second must be of numerical types"""
    for etype in rset.description[0]:
        if etype not in ('Int', 'Float'):
            return 0
    return 1

@objectify_selector
def second_column_is_number(cls, req, rset=None, *args, **kwargs):
    etype = rset.description[0][1]
    if etype not  in ('Int', 'Float'):
        return 0
    return 1

@objectify_selector
def columns_are_date_then_numbers(cls, req, rset=None, *args, **kwargs):
    etypes = rset.description[0]
    if etypes[0] not in ('Date', 'Datetime'):
        return 0
    for etype in etypes[1:]:
        if etype not in ('Int', 'Float'):
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

class FlotPlotWidget(PlotWidget):
    """PlotRenderer widget using Flot"""
    onload = u"""
var fig = jQuery("#%(figid)s");
if (fig.attr('cubicweb:type') != 'prepared-plot') {
    %(plotdefs)s
    jQuery.plot(jQuery("#%(figid)s"), [%(plotdata)s],
        {points: {show: true},
         lines: {show: true},
         grid: {hoverable: true},
         xaxis: {mode: %(mode)s}});
    jQuery("#%(figid)s").bind("plothover", onPlotHover);
    fig.attr('cubicweb:type','prepared-plot');
}
"""

    def __init__(self, labels, plots, timemode=False):
        self.labels = labels
        self.plots = plots # list of list of couples
        self.timemode = timemode

    def dump_plot(self, plot):
        # XXX for now, the only way that we have to customize properly
        #     datetime labels on tooltips is to insert an additional column
        #     cf. function onPlotHover in cubicweb.flot.js
        if self.timemode:
            plot = [(datetime2ticks(x), y, datetime2ticks(x)) for x,y in plot]
        return dumps(plot)

    def _render(self, req, width=500, height=400):
        if req.ie_browser():
            req.add_js('excanvas.js')
        req.add_js(('jquery.flot.js', 'cubicweb.flot.js'))
        figid = u'figure%s' % req.varmaker.next()
        plotdefs = []
        plotdata = []
        self.w(u'<div id="%s" style="width: %spx; height: %spx;"></div>' %
               (figid, width, height))
        for idx, (label, plot) in enumerate(zip(self.labels, self.plots)):
            plotid = '%s_%s' % (figid, idx)
            plotdefs.append('var %s = %s;' % (plotid, self.dump_plot(plot)))
            # XXX ugly but required in order to not crash my demo
            plotdata.append("{label: '%s', data: %s}" % (label.replace(u'&', u''), plotid))
        req.html_headers.add_onload(self.onload %
                                    {'plotdefs': '\n'.join(plotdefs),
                                     'figid': figid,
                                     'plotdata': ','.join(plotdata),
                                     'mode': self.timemode and "'time'" or 'null'},
                                    jsoncall=req.form.get('jsoncall', False))


class PlotView(baseviews.AnyRsetView):
    id = 'plot'
    title = _('generic plot')
    __select__ = at_least_two_columns() & all_columns_are_numbers()
    timemode = False

    def call(self, width=500, height=400):
        # prepare data
        rqlst = self.rset.syntax_tree()
        # XXX try to make it work with unions
        varnames = [var.name for var in rqlst.children[0].get_selected_variables()][1:]
        abscissa = [row[0] for row in self.rset]
        plots = []
        nbcols = len(self.rset.rows[0])
        for col in xrange(1, nbcols):
            data = [row[col] for row in self.rset]
            plots.append(filterout_nulls(abscissa, data))
        plotwidget = FlotPlotWidget(varnames, plots, timemode=self.timemode)
        plotwidget.render(self.req, width, height, w=self.w)


class TimeSeriePlotView(PlotView):
    __select__ = at_least_two_columns() & columns_are_date_then_numbers()
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
        id = 'piechart'
        pieclass = Pie

        __select__ = at_least_two_columns() & second_column_is_number()

        def _guess_vid(self, row):
            etype = self.rset.description[row][0]
            if self.schema.eschema(etype).final:
                return 'final'
            return 'textincontext'

        def call(self, title=None, width=None, height=None):
            labels = []
            values = []
            for rowidx, (_, value) in enumerate(self.rset):
                if value is not None:
                    vid = self._guess_vid(rowidx)
                    label = '%s: %s' % (self.view(vid, self.rset, row=rowidx, col=0),
                                        value)
                    labels.append(label.encode(self.req.encoding))
                    values.append(value)
            pie = PieChartWidget(labels, values, pieclass=self.pieclass,
                                 title=title)
            if width is not None:
                height = height or width
            pie.render(width, height, w=self.w)


    class PieChart3DView(PieChartView):
        id = 'piechart3D'
        pieclass = Pie3D
