# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""html calendar views"""

__docformat__ = "restructuredtext en"
from cubicweb import _

import copy
from datetime import timedelta

from logilab.mtconverter import xml_escape
from logilab.common.date import todatetime

from cubicweb.utils import json_dumps, make_uid
from cubicweb.predicates import adaptable
from cubicweb.view import EntityView, EntityAdapter

# useful constants & functions ################################################

ONEDAY = timedelta(1)

WEEKDAYS = (_("monday"), _("tuesday"), _("wednesday"), _("thursday"),
            _("friday"), _("saturday"), _("sunday"))
MONTHNAMES = ( _('january'), _('february'), _('march'), _('april'), _('may'),
               _('june'), _('july'), _('august'), _('september'), _('october'),
               _('november'), _('december')
               )


class ICalendarableAdapter(EntityAdapter):
    __needs_bw_compat__ = True
    __regid__ = 'ICalendarable'
    __abstract__ = True

    @property
    def start(self):
        """return start date"""
        raise NotImplementedError

    @property
    def stop(self):
        """return stop date"""
        raise NotImplementedError


# Calendar views ##############################################################

try:
    from vobject import iCalendar

    class iCalView(EntityView):
        """A calendar view that generates a iCalendar file (RFC 2445)

        Does apply to ICalendarable compatible entities
        """
        __select__ = adaptable('ICalendarable')
        paginable = False
        content_type = 'text/calendar'
        title = _('iCalendar')
        templatable = False
        __regid__ = 'ical'

        def call(self):
            ical = iCalendar()
            for i in range(len(self.cw_rset.rows)):
                task = self.cw_rset.complete_entity(i, 0)
                event = ical.add('vevent')
                event.add('summary').value = task.dc_title()
                event.add('description').value = task.dc_description()
                icalendarable = task.cw_adapt_to('ICalendarable')
                if icalendarable.start:
                    event.add('dtstart').value = icalendarable.start
                if icalendarable.stop:
                    event.add('dtend').value = icalendarable.stop

            buff = ical.serialize()
            if not isinstance(buff, unicode):
                buff = unicode(buff, self._cw.encoding)
            self.w(buff)

except ImportError:
    pass

class hCalView(EntityView):
    """A calendar view that generates a hCalendar file

    Does apply to ICalendarable compatible entities
    """
    __regid__ = 'hcal'
    __select__ = adaptable('ICalendarable')
    paginable = False
    title = _('hCalendar')
    #templatable = False

    def call(self):
        self.w(u'<div class="hcalendar">')
        for i in range(len(self.cw_rset.rows)):
            task = self.cw_rset.complete_entity(i, 0)
            self.w(u'<div class="vevent">')
            self.w(u'<h3 class="summary">%s</h3>' % xml_escape(task.dc_title()))
            self.w(u'<div class="description">%s</div>'
                   % task.dc_description(format='text/html'))
            icalendarable = task.cw_adapt_to('ICalendarable')
            if icalendarable.start:
                self.w(u'<abbr class="dtstart" title="%s">%s</abbr>'
                       % (icalendarable.start.isoformat(),
                          self._cw.format_date(icalendarable.start)))
            if icalendarable.stop:
                self.w(u'<abbr class="dtstop" title="%s">%s</abbr>'
                       % (icalendarable.stop.isoformat(),
                          self._cw.format_date(icalendarable.stop)))
            self.w(u'</div>')
        self.w(u'</div>')


class CalendarItemView(EntityView):
    __regid__ = 'calendaritem'

    def cell_call(self, row, col, dates=False):
        task = self.cw_rset.complete_entity(row, 0)
        task.view('oneline', w=self.w)
        if dates:
            icalendarable = task.cw_adapt_to('ICalendarable')
            if icalendarable.start and icalendarable.stop:
                self.w('<br/> %s' % self._cw._('from %(date)s')
                       % {'date': self._cw.format_date(icalendarable.start)})
                self.w('<br/> %s' % self._cw._('to %(date)s')
                       % {'date': self._cw.format_date(icalendarable.stop)})
            else:
                self.w('<br/>%s'%self._cw.format_date(icalendarable.start
                                                      or icalendarable.stop))


class _TaskEntry(object):
    def __init__(self, task, color, index=0):
        self.task = task
        self.color = color
        self.index = index
        self.length = 1
        icalendarable = task.cw_adapt_to('ICalendarable')
        self.start = icalendarable.start
        self.stop = icalendarable.stop

    def in_working_hours(self):
        """predicate returning True is the task is in working hours"""
        if todatetime(self.start).hour > 7 and todatetime(self.stop).hour < 20:
            return True
        return False

    def is_one_day_task(self):
        return self.start and self.stop and self.start.isocalendar() == self.stop.isocalendar()


class CalendarView(EntityView):
    __regid__ = 'calendar'
    __select__ = adaptable('ICalendarable')

    paginable = False
    title = _('calendar')

    fullcalendar_options = {
        'firstDay': 1,
        'firstHour': 8,
        'defaultView': 'month',
        'editable': True,
        'header': {'left': 'prev,next today',
                   'center': 'title',
                   'right': 'month,agendaWeek,agendaDay',
                   },
        }

    def call(self, cssclass=""):
        self._cw.add_css(('fullcalendar.css', 'cubicweb.calendar.css'))
        self._cw.add_js(('jquery.ui.js', 'fullcalendar.min.js', 'jquery.qtip.min.js', 'fullcalendar.locale.js'))
        self.calendar_id = 'cal' + make_uid('uid')
        self.add_onload()
        # write calendar div to load jquery fullcalendar object
        if cssclass:
            self.w(u'<div class="%s" id="%s"></div>' % (cssclass, self.calendar_id))
        else:
            self.w(u'<div id="%s"></div>' % self.calendar_id)

    def add_onload(self):
        fullcalendar_options = self.fullcalendar_options.copy()
        fullcalendar_options['events'] = self.get_events()
        # i18n
        # js callback to add a tooltip and to put html in event's title
        js = """
        var options = $.fullCalendar.regional('%s', %s);
        options.eventRender = function(event, $element) {
          // add a tooltip for each event
          var div = '<div class="tooltip">'+ event.description+ '</div>';
          $element.append(div);
          // allow to have html tags in event's title
          $element.find('span.fc-event-title').html($element.find('span.fc-event-title').text());
        };
        $("#%s").fullCalendar(options);
        """ #"
        self._cw.add_onload(js % (self._cw.lang, json_dumps(fullcalendar_options), self.calendar_id))

    def get_events(self):
        events = []
        for entity in self.cw_rset.entities():
            icalendarable = entity.cw_adapt_to('ICalendarable')
            if not (icalendarable.start and icalendarable.stop):
                continue
            start_date = icalendarable.start or  icalendarable.stop
            event = {'eid': entity.eid,
                     'title': entity.view('calendaritem'),
                     'url': xml_escape(entity.absolute_url()),
                     'className': 'calevent',
                     'description': entity.view('tooltip'),
                     }
            event['start'] = start_date.strftime('%Y-%m-%dT%H:%M')
            event['allDay'] = True
            if icalendarable.stop:
                event['end'] = icalendarable.stop.strftime('%Y-%m-%dT%H:%M')
                event['allDay'] = False
            events.append(event)
        return events

class OneMonthCal(CalendarView):
    __regid__ = 'onemonthcal'

    title = _('one month')

class OneWeekCal(CalendarView):
    __regid__ = 'oneweekcal'

    title = _('one week')
    fullcalendar_options = CalendarView.fullcalendar_options.copy()
    fullcalendar_options['defaultView'] = 'agendaWeek'
