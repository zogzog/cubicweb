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

def datetime2ticks(date):
    return time.mktime(date.timetuple()) * 1000

class FlotPlotWidget(object):
    """PlotRenderer widget using Flot"""
    onload = u'''
%(plotdefs)s
jQuery.plot(jQuery("#%(figid)s"), [%(plotdata)s],
    {points: {show: true},
     lines: {show: true},
     grid: {hoverable: true},
     xaxis: {mode: %(mode)s}});
jQuery('#%(figid)s').bind('plothover', onPlotHover);
'''
    
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
    
    def render(self, req, width=500, height=400, w=None):
        # XXX IE requires excanvas.js
        req.add_js( ('jquery.flot.js', 'cubicweb.flot.js') )
        figid = u'figure%s' % make_uid('foo')
        plotdefs = []
        plotdata = []
        w(u'<div id="%s" style="width: %spx; height: %spx;"></div>' %
          (figid, width, height))
        for idx, (label, plot) in enumerate(zip(self.labels, self.plots)):
            plotid = '%s_%s' % (figid, idx)
            plotdefs.append('var %s = %s;' % (plotid, self.dump_plot(plot)))
            plotdata.append("{label: '%s', data: %s}" % (label, plotid))
        req.html_headers.add_onload(self.onload %
                                    {'plotdefs': '\n'.join(plotdefs),
                                     'figid': figid,
                                     'plotdata': ','.join(plotdata),
                                     'mode': self.timemode and "'time'" or 'null'})
    

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
            plots.append(filterout_nulls(abscissa, plot))
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
