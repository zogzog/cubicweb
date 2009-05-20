"""basic plot views

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import os
import time

from simplejson import dumps

from logilab.common import flatten
from logilab.mtconverter import html_escape

from cubicweb.utils import make_uid
from cubicweb.vregistry import objectify_selector
from cubicweb.web.views import baseviews

@objectify_selector
def at_least_two_columns(cls, req, rset, *args, **kwargs):
    if not rset:
        return 0
    return len(rset.rows[0]) >= 2

@objectify_selector
def all_columns_are_numbers(cls, req, rset, *args, **kwargs):
    """accept result set with at least one line and two columns of result
    all columns after second must be of numerical types"""
    for etype in rset.description[0]:
        if etype not in ('Int', 'Float'):
            return 0
    return 1

@objectify_selector
def second_column_is_number(cls, req, rset, *args, **kwargs):
    etype = rset.description[0][1]
    if etype not  in ('Int', 'Float'):
        return 0
    return 1

@objectify_selector
def columns_are_date_then_numbers(cls, req, rset, *args, **kwargs):
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

class PlotView(baseviews.AnyRsetView):
    id = 'plot'
    title = _('generic plot')
    __select__ = at_least_two_columns() & all_columns_are_numbers()
    mode = 'null' # null or time, meant for jquery.flot.js

    def _build_abscissa(self):
        return [row[0] for row in self.rset]

    def _build_data(self, abscissa, plot):
        return filterout_nulls(abscissa, plot)

    def call(self, width=500, height=400):
        # XXX add excanvas.js if IE
        self.req.add_js( ('jquery.flot.js', 'cubicweb.flot.js') )
        # prepare data
        abscissa = self._build_abscissa()
        plots = []
        nbcols = len(self.rset.rows[0])
        for col in xrange(1, nbcols):
            plots.append([row[col] for row in self.rset])
        # plot data
        plotuid = 'plot%s' % make_uid('foo')
        self.w(u'<div id="%s" style="width: %spx; height: %spx;"></div>' %
               (plotuid, width, height))
        rqlst = self.rset.syntax_tree()
        # XXX try to make it work with unions
        varnames = [var.name for var in rqlst.children[0].get_selected_variables()][1:]
        plotdefs = []
        plotdata = []
        for idx, (varname, plot) in enumerate(zip(varnames, plots)):
            plotid = '%s_%s' % (plotuid, idx)
            data = self._build_data(abscissa, plot)
            plotdefs.append('var %s = %s;' % (plotid, dumps(data)))
            plotdata.append("{label: '%s', data: %s}" % (varname, plotid))
        self.req.html_headers.add_onload('''
%(plotdefs)s
jQuery.plot(jQuery("#%(plotuid)s"), [%(plotdata)s],
    {points: {show: true},
     lines: {show: true},
     grid: {hoverable: true},
     xaxis: {mode: %(mode)s}});
jQuery('#%(plotuid)s').bind('plothover', onPlotHover);
''' % {'plotdefs': '\n'.join(plotdefs),
       'plotuid': plotuid,
       'plotdata': ','.join(plotdata),
       'mode': self.mode})


class TimeSeriePlotView(PlotView):
    id = 'plot'
    title = _('generic plot')
    __select__ = at_least_two_columns() & columns_are_date_then_numbers()
    mode = '"time"'

    def _build_abscissa(self):
        abscissa = [time.mktime(row[0].timetuple()) * 1000
                    for row in self.rset]
        return abscissa

    def _build_data(self, abscissa, plot):
        data = []
        # XXX find a way to get rid of the 3rd column and find 'mode' in JS
        for x, y in filterout_nulls(abscissa, plot):
            data.append( (x, y, x) )
        return data

try:
    from GChartWrapper import Pie, Pie3D
except ImportError:
    pass
else:
    class PieChartView(baseviews.AnyRsetView):
        id = 'piechart'
        pieclass = Pie
        __select__ = at_least_two_columns() & second_column_is_number()

        def call(self, title=None, width=None, height=None):
            piechart = self.pieclass([(row[1] or 0) for row in self.rset])
            labels = ['%s: %s' % (row[0].encode(self.req.encoding), row[1])
                      for row in self.rset]
            piechart.label(*labels)
            if width is not None:
                height = height or width
                piechart.size(width, height)
            if title:
                piechart.title(title)
            self.w(u'<img src="%s" />' % html_escape(piechart.url))


    class PieChart3DView(PieChartView):
        id = 'piechart3D'
        pieclass = Pie3D
