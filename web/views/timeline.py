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
"""basic support for SIMILE's timline widgets

cf. http://code.google.com/p/simile-widgets/

"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb.interfaces import ICalendarable
from cubicweb.selectors import implements
from cubicweb.view import EntityView, StartupView
from cubicweb.web import json

_ = unicode

class TimelineJsonView(EntityView):
    """generates a json file to feed Timeline.loadJSON()
    NOTE: work in progress (image_url, bubbleUrl and so on
    should be properties of entity classes or subviews)
    """
    __regid__ = 'timeline-json'
    binary = True
    templatable = False
    content_type = 'application/json'

    __select__ = implements(ICalendarable)
    date_fmt = '%Y/%m/%d'

    def call(self):
        events = []
        for entity in self.cw_rset.entities():
            event = self.build_event(entity)
            if event is not None:
                events.append(event)
        timeline_data = {'dateTimeFormat': self.date_fmt,
                         'events': events}
        self.w(json.dumps(timeline_data))

    # FIXME: those properties should be defined by the entity class
    def onclick_url(self, entity):
        return entity.absolute_url()

    def onclick(self, entity):
        url = self.onclick_url(entity)
        if url:
            return u"javascript: document.location.href='%s'" % url
        return None

    def build_event(self, entity):
        """converts `entity` into a JSON object
        {'start': '1891',
        'end': '1915',
        'title': 'Portrait of Horace Brodsky',
        'description': 'by Henri Gaudier-Brzeska, French Sculptor, 1891-1915',
        'image': 'http://imagecache2.allposters.com/images/BRGPOD/102770_b.jpg',
        'link': 'http://www.allposters.com/-sp/Portrait-of-Horace-Brodsky-Posters_i1584413_.htm'
        }
        """
        start = entity.start
        stop = entity.stop
        start = start or stop
        if start is None and stop is None:
            return None
        event_data = {'start': start.strftime(self.date_fmt),
                      'title': xml_escape(entity.dc_title()),
                      'description': entity.dc_description(format='text/html'),
                      'link': entity.absolute_url(),
                      }
        onclick = self.onclick(entity)
        if onclick:
            event_data['onclick'] = onclick
        if stop:
            event_data['end'] = stop.strftime(self.date_fmt)
        return event_data


class TimelineViewMixIn(object):
    widget_class = 'TimelineWidget'
    jsfiles = ('cubicweb.timeline-bundle.js', 'cubicweb.widgets.js',
               'cubicweb.timeline-ext.js', 'cubicweb.ajax.js')

    def render_url(self, loadurl, tlunit=None):
        tlunit = tlunit or self._cw.form.get('tlunit')
        self._cw.add_js(self.jsfiles)
        self._cw.add_css('timeline-bundle.css')
        if tlunit:
            additional = u' cubicweb:tlunit="%s"' % tlunit
        else:
            additional = u''
        self.w(u'<div class="widget" cubicweb:wdgtype="%s" '
               u'cubicweb:loadtype="auto" cubicweb:loadurl="%s" %s >' %
               (self.widget_class, xml_escape(loadurl),
                additional))
        self.w(u'</div>')


class TimelineView(TimelineViewMixIn, EntityView):
    """builds a cubicweb timeline widget node"""
    __regid__ = 'timeline'
    title = _('timeline')
    __select__ = implements(ICalendarable)
    paginable = False
    def call(self, tlunit=None):
        self._cw.html_headers.define_var('Timeline_urlPrefix', self._cw.datadir_url)
        rql = self.cw_rset.printable_rql()
        loadurl = self._cw.build_url(rql=rql, vid='timeline-json')
        self.render_url(loadurl, tlunit)


class StaticTimelineView(TimelineViewMixIn, StartupView):
    """similar to `TimelineView` but loads data from a static
    JSON file instead of one after a RQL query.
    """
    __regid__ = 'static-timeline'

    def call(self, loadurl, tlunit=None, wdgclass=None):
        self.widget_class = wdgclass or self.widget_class
        self.render_url(loadurl, tlunit)
