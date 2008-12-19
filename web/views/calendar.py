"""html calendar views

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from mx.DateTime import DateTime, RelativeDateTime, today, ISO
from datetime import datetime

from vobject import iCalendar, icalendar

from logilab.mtconverter import html_escape

from cubicweb.interfaces import ICalendarable
from cubicweb.common.utils import date_range
from cubicweb.common.uilib import ajax_replace_url
from cubicweb.common.selectors import interface_selector
from cubicweb.common.registerers import priority_registerer
from cubicweb.common.view import EntityView


# For backward compatibility
from cubicweb.interfaces import ICalendarViews, ITimetableViews
try:
    from cubicweb.web.views.old_calendar import _CalendarView, AMPMWeekCalendarView
except ImportError:
    import logging
    logger = logging.getLogger('cubicweb.registry')
    logger.info("old calendar views could not be found and won't be registered")

_ = unicode

# useful constants & functions
def mkdt(mxdate):
    """
    Build a stdlib datetime date from a mx.datetime 
    """
    d = mxdate
    return datetime(d.year, d.month, d.day, d.hour, d.minute,
                    tzinfo=icalendar.utc)
def iso(mxdate):
    """
    Format a ms datetime in ISO 8601 string 
    """
    # XXX What about timezone?
    return ISO.str(mxdate)

# mx.DateTime and ustrftime could be used to build WEEKDAYS
WEEKDAYS = (_("monday"), _("tuesday"), _("wednesday"), _("thursday"),
            _("friday"), _("saturday"), _("sunday"))

# used by i18n tools
MONTHNAMES = ( _('january'), _('february'), _('march'), _('april'), _('may'),
               _('june'), _('july'), _('august'), _('september'), _('october'),
               _('november'), _('december')
               )

#################
# In calendar views (views used as calendar cell item) 


class CalendarItemView(EntityView):
    id = 'calendaritem'

    def cell_call(self, row, col, dates=False):
        task = self.complete_entity(row)
        task.view('oneline', w=self.w)
        if dates:
            if task.start and task.stop:
                self.w('<br/>from %s'%self.format_date(task.start))
                self.w('<br/>to %s'%self.format_date(task.stop))
                
class CalendarLargeItemView(CalendarItemView):
    id = 'calendarlargeitem'
        
#################
# Calendar views

class iCalView(EntityView):
    """A calendar view that generates a iCalendar file (RFC 2445)

    Does apply to ICalendarable compatible entities
    """
    __registerer__ = priority_registerer
    __selectors__ = (interface_selector,)
    accepts_interfaces = (ICalendarable,)
    need_navigation = False
    content_type = 'text/calendar'
    title = _('iCalendar')
    templatable = False
    id = 'ical'

    def call(self):
        ical = iCalendar()
        for i in range(len(self.rset.rows)):
            task = self.complete_entity(i)
            event = ical.add('vevent')
            event.add('summary').value = task.dc_title()
            event.add('description').value = task.dc_description()
            if task.start:
                event.add('dtstart').value = mkdt(task.start)
            if task.stop:
                event.add('dtend').value = mkdt(task.stop)

        buff = ical.serialize()
        if not isinstance(buff, unicode):
            buff = unicode(buff, self.req.encoding)
        self.w(buff)

class hCalView(EntityView):
    """A calendar view that generates a hCalendar file

    Does apply to ICalendarable compatible entities
    """
    __registerer__ = priority_registerer
    __selectors__ = (interface_selector,)
    accepts_interfaces = (ICalendarable,)
    need_navigation = False
    title = _('hCalendar')
    templatable = False
    id = 'hcal'

    def call(self):
        self.w(u'<div class="hcalendar">')
        for i in range(len(self.rset.rows)):
            task = self.complete_entity(i)
            self.w(u'<div class="vevent">')
            self.w(u'<h3 class="summary">%s</h3>' % html_escape(task.dc_title()))
            self.w(u'<div class="description">%s</div>' % html_escape(task.dc_description()))
            if task.start:
                self.w(u'<abbr class="dtstart" title="%s">%s</abbr>' % (iso(task.start), self.format_date(task.start)))
            if task.stop:
                self.w(u'<abbr class="dtstop" title="%s">%s</abbr>' % (iso(task.stop), self.format_date(task.stop)))
            self.w(u'</div>')
        self.w(u'</div>')

    
class _TaskEntry(object):
    def __init__(self, task, color, index=0):
        self.task = task
        self.color = color
        self.index = index
        self.length = 1

class OneMonthCal(EntityView):
    """At some point, this view will probably replace ampm calendars"""
    __registerer__ = priority_registerer
    __selectors__ = (interface_selector, )
    accepts_interfaces = (ICalendarable,)
    need_navigation = False
    id = 'onemonthcal'
    title = _('one month')

    def call(self):
        self.req.add_js('cubicweb.ajax.js')
        self.req.add_css('cubicweb.calendar.css')
        # XXX: restrict courses directy with RQL
        _today =  today()

        if 'year' in self.req.form:
            year = int(self.req.form['year'])
        else:
            year = _today.year
        if 'month' in self.req.form:
            month = int(self.req.form['month'])
        else:
            month = _today.month

        first_day_of_month = DateTime(year, month, 1)
        lastday = first_day_of_month + RelativeDateTime(months=1,weekday=(6,1))
        firstday= first_day_of_month + RelativeDateTime(months=-1,weekday=(0,-1))
        month_dates = list(date_range(firstday, lastday))
        dates = {}
        users = []
        task_max = 0
        for row in xrange(self.rset.rowcount):
            task = self.rset.get_entity(row,0)
            if len(self.rset[row]) > 1 and self.rset.description[row][1] == 'EUser':
                user = self.rset.get_entity(row,1)
            else:
                user = None
            the_dates = []
            if task.start:
                if task.start > lastday:
                    continue
                the_dates = [task.start]
            if task.stop:
                if task.stop < firstday:
                    continue
                the_dates = [task.stop]
            if task.start and task.stop:
                if task.start.absdate == task.stop.absdate:
                    date = task.start
                    if firstday<= date <= lastday:
                        the_dates = [date]
                else:
                    the_dates = date_range(max(task.start,firstday),
                                           min(task.stop,lastday))
            if not the_dates:
                continue
            
            for d in the_dates:
                d_tasks = dates.setdefault((d.year, d.month, d.day), {})
                t_users = d_tasks.setdefault(task,set())
                t_users.add( user )
                if len(d_tasks)>task_max:
                    task_max = len(d_tasks)

        days = []
        nrows = max(3,task_max)
        # colors here are class names defined in cubicweb.css
        colors = [ "col%x"%i for i in range(12) ]
        next_color_index = 0

        visited_tasks = {} # holds a description of a task
        task_colors = {}   # remember a color assigned to a task
        for date in month_dates:
            d_tasks = dates.get((date.year, date.month, date.day), {})
            rows = [None] * nrows
            # every task that is "visited" for the first time
            # require a special treatment, so we put them in
            # 'postpone'
            postpone = []
            for task in d_tasks:
                if task in visited_tasks:
                    task_descr = visited_tasks[ task ]
                    rows[task_descr.index] = task_descr
                else:
                    postpone.append(task)
            for task in postpone:
                # to every 'new' task we must affect a color
                # (which must be the same for every user concerned
                # by the task)
                for i,t in enumerate(rows):
                    if t is None:
                        if task in task_colors:
                            color = task_colors[task]
                        else:
                            color = colors[next_color_index]
                            next_color_index = (next_color_index+1)%len(colors)
                            task_colors[task] = color
                        task_descr = _TaskEntry(task, color, i)
                        rows[i] = task_descr
                        visited_tasks[task] = task_descr
                        break
                else:
                    raise RuntimeError("is it possible we got it wrong?")

            days.append( rows )

        curdate = first_day_of_month
        self.w(u'<div id="onemonthcalid">')
        # build schedule
        self.w(u'<table class="omcalendar">')
        prevlink, nextlink = self._prevnext_links(curdate)  # XXX
        self.w(u'<tr><th><a href="%s">&lt;&lt;</a></th><th colspan="5">%s %s</th>'
               u'<th><a href="%s">&gt;&gt;</a></th></tr>' %
               (html_escape(prevlink), self.req._(curdate.strftime('%B').lower()),
                curdate.year, html_escape(nextlink)))

        # output header
        self.w(u'<tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>' %
               tuple(self.req._(day) for day in WEEKDAYS))
        
        # build calendar
        for date, task_rows in zip(month_dates, days):
            if date.day_of_week == 0:
                self.w(u'<tr>')
            self._build_calendar_cell(date, task_rows, curdate)
            if date.day_of_week == 6:
                self.w(u'</tr>')
        self.w(u'</table></div>')

    def _prevnext_links(self, curdate):
        prevdate = curdate - RelativeDateTime(months=1)
        nextdate = curdate + RelativeDateTime(months=1)
        rql = self.rset.rql
        prevlink = ajax_replace_url('onemonthcalid', rql, 'onemonthcal',
                                    year=prevdate.year, month=prevdate.month)
        nextlink = ajax_replace_url('onemonthcalid', rql, 'onemonthcal',
                                    year=nextdate.year, month=nextdate.month)
        return prevlink, nextlink

    def _build_calendar_cell(self, date, rows, curdate):
        curmonth = curdate.month
        classes = ""
        if date.month != curmonth:
            classes += " outOfRange"
        if date == today():
            classes += " today"
        self.w(u'<td class="cell%s">' % classes)
        self.w(u'<div class="calCellTitle%s">' % classes)
        self.w(u'<div class="day">%s</div>' % date.day)
        
        if len(self.rset.column_types(0)) == 1:
            etype = list(self.rset.column_types(0))[0]
            url = self.build_url(vid='creation', etype=etype,
                                 schedule=True,
                                 start=self.format_date(date), stop=self.format_date(date),
                                 __redirectrql=self.rset.rql,
                                 __redirectparams=self.req.build_url_params(year=curdate.year, month=curmonth),
                                 __redirectvid=self.id
                                 )
            self.w(u'<div class="cmd"><a href="%s">%s</a></div>' % (html_escape(url), self.req._(u'add')))
            self.w(u'&nbsp;')
        self.w(u'</div>')
        self.w(u'<div class="cellContent">')
        for task_descr in rows:
            if task_descr:
                task = task_descr.task
                self.w(u'<div class="task %s">' % task_descr.color)
                task.view('calendaritem', w=self.w )
                url = task.absolute_url(vid='edition',
                                        __redirectrql=self.rset.rql,
                                        __redirectparams=self.req.build_url_params(year=curdate.year, month=curmonth),
                                        __redirectvid=self.id
                                        )

                self.w(u'<div class="tooltip" ondblclick="stopPropagation(event); window.location.assign(\'%s\'); return false;">' % html_escape(url))
                task.view('tooltip', w=self.w )
                self.w(u'</div>')
            else:
                self.w(u'<div class="task">')
                self.w(u"&nbsp;")
            self.w(u'</div>')
        self.w(u'</div>')
        self.w(u'</td>')


class OneWeekCal(EntityView):
    """At some point, this view will probably replace ampm calendars"""
    __registerer__ = priority_registerer
    __selectors__ = (interface_selector, )
    accepts_interfaces = (ICalendarable,)
    need_navigation = False
    id = 'oneweekcal'
    title = _('one week')
    
    def call(self):
        self.req.add_js( ('cubicweb.ajax.js', 'cubicweb.calendar.js') )
        self.req.add_css('cubicweb.calendar.css')
        # XXX: restrict courses directy with RQL
        _today =  today()

        if 'year' in self.req.form:
            year = int(self.req.form['year'])
        else:
            year = _today.year
        if 'week' in self.req.form:
            week = int(self.req.form['week'])
        else:
            week = _today.iso_week[1]        

        first_day_of_week = ISO.ParseWeek("%s-W%s-1"%(year, week))
        lastday = first_day_of_week + RelativeDateTime(days=6)
        firstday= first_day_of_week
        dates = [[] for i in range(7)]
        task_max = 0
        task_colors = {}   # remember a color assigned to a task
        # colors here are class names defined in cubicweb.css
        colors = [ "col%x"%i for i in range(12) ]
        next_color_index = 0
        done_tasks = []
        for row in xrange(self.rset.rowcount):
            task = self.rset.get_entity(row,0)
            if task in done_tasks:
                continue
            done_tasks.append(task)
            the_dates = []
            if task.start:
                if task.start > lastday:
                    continue
                the_dates = [task.start]
            if task.stop:
                if task.stop < firstday:
                    continue
                the_dates = [task.stop]
            if task.start and task.stop:
                the_dates = date_range(max(task.start,firstday),
                                       min(task.stop,lastday))
            if not the_dates:
                continue
                
            if task not in task_colors:
                task_colors[task] = colors[next_color_index]
                next_color_index = (next_color_index+1)%len(colors)
            
            for d in the_dates:
                day = d.day_of_week
                task_descr = _TaskEntry(task, task_colors[task])  
                dates[day].append(task_descr)
            
        self.w(u'<div id="oneweekcalid">')
        # build schedule
        self.w(u'<table class="omcalendar" id="week">')
        prevlink, nextlink = self._prevnext_links(first_day_of_week)  # XXX
        self.w(u'<tr><th class="transparent"></th>')
        self.w(u'<th><a href="%s">&lt;&lt;</a></th><th colspan="5">%s %s %s</th>'
               u'<th><a href="%s">&gt;&gt;</a></th></tr>' %
               (html_escape(prevlink), first_day_of_week.year,
                self.req._(u'week'), first_day_of_week.iso_week[1],
                html_escape(nextlink)))

        # output header
        self.w(u'<tr>')
        self.w(u'<th class="transparent"></th>') # column for hours
        _today = today()
        for i, day in enumerate(WEEKDAYS):
            date = first_day_of_week + i
            if date.absdate == _today.absdate:
                self.w(u'<th class="today">%s<br/>%s</th>' % (self.req._(day), self.format_date(date)))
            else:
                self.w(u'<th>%s<br/>%s</th>' % (self.req._(day), self.format_date(date)))
        self.w(u'</tr>')

        
        # build week calendar
        self.w(u'<tr>')
        self.w(u'<td style="width:5em;">') # column for hours
        extra = ""
        for h in range(8, 20):
            self.w(u'<div class="hour" %s>'%extra)
            self.w(u'%02d:00'%h)
            self.w(u'</div>')            
        self.w(u'</td>')
        
        for i, day in enumerate(WEEKDAYS):
            date = first_day_of_week + i
            classes = ""
            if date.absdate == _today.absdate:
                classes = " today"
            self.w(u'<td class="column %s" id="%s">'%(classes, day))
            if len(self.rset.column_types(0)) == 1:
                etype = list(self.rset.column_types(0))[0]
                url = self.build_url(vid='creation', etype=etype,
                                     schedule=True,
                                     __redirectrql=self.rset.rql,
                                     __redirectparams=self.req.build_url_params(year=year, week=week),
                                     __redirectvid=self.id
                                     )
                extra = ' ondblclick="addCalendarItem(event, hmin=%s, hmax=%s, year=%s, month=%s, day=%s, duration=%s, baseurl=\'%s\')"' % (8,20,date.year, date.month, date.day, 2, html_escape(url))
            else:
                extra = ""
            self.w(u'<div class="columndiv"%s>'% extra)
            for h in range(8, 20):
                self.w(u'<div class="hourline" style="top:%sex;">'%((h-7)*8))
                self.w(u'</div>')            
            if dates[i]:
                self._build_calendar_cell(date, dates[i])
            self.w(u'</div>')
            self.w(u'</td>')
        self.w(u'</tr>')
        self.w(u'</table></div>')
        self.w(u'<div id="coord"></div>')
        self.w(u'<div id="debug">&nbsp;</div>')
 
    def _one_day_task(self, task):
        """
        Return true if the task is a "one day" task; ie it have a start and a stop the same day
        """
        if task.start and task.stop:
            if task.start.absdate ==  task.stop.absdate:
                return True
        return False
        
    def _build_calendar_cell(self, date, task_descrs):
        inday_tasks = [t for t in task_descrs if self._one_day_task(t.task) and  t.task.start.hour<20 and t.task.stop.hour>7]
        wholeday_tasks = [t for t in task_descrs if not self._one_day_task(t.task)]

        inday_tasks.sort(key=lambda t:t.task.start)
        sorted_tasks = []
        for i, t in enumerate(wholeday_tasks):
            t.index = i
        ncols = len(wholeday_tasks)
        while inday_tasks:
            t = inday_tasks.pop(0)
            for i, c in enumerate(sorted_tasks):
                if not c or c[-1].task.stop <= t.task.start:
                    c.append(t)
                    t.index = i+ncols
                    break
            else:
                t.index = len(sorted_tasks) + ncols
                sorted_tasks.append([t])
        ncols += len(sorted_tasks)
        if ncols == 0:
            return

        inday_tasks = []
        for tasklist in sorted_tasks:
            inday_tasks += tasklist
        width = 100.0/ncols
        for task_desc in wholeday_tasks + inday_tasks:
            task = task_desc.task
            start_hour = 8
            start_min = 0
            stop_hour = 20
            stop_min = 0
            if task.start:
                if date < task.start < date + 1:
                    start_hour = max(8, task.start.hour)
                    start_min = task.start.minute
            if task.stop:
                if date < task.stop < date + 1:
                    stop_hour = min(20, task.stop.hour)
                    if stop_hour < 20:
                        stop_min = task.stop.minute
                    
            height = 100.0*(stop_hour+stop_min/60.0-start_hour-start_min/60.0)/(20-8)
            top = 100.0*(start_hour+start_min/60.0-8)/(20-8)
            left = width*task_desc.index
            style = "height: %s%%; width: %s%%; top: %s%%; left: %s%%; " % \
                (height, width, top, left)
            self.w(u'<div class="task %s" style="%s">' % \
                       (task_desc.color, style))
            task.view('calendaritem', dates=False, w=self.w)
            url = task.absolute_url(vid='edition',
                                    __redirectrql=self.rset.rql,
                                    __redirectparams=self.req.build_url_params(year=date.year, week=date.iso_week[1]),
                                    __redirectvid=self.id
                                 )

            self.w(u'<div class="tooltip" ondblclick="stopPropagation(event); window.location.assign(\'%s\'); return false;">' % html_escape(url))
            task.view('tooltip', w=self.w)
            self.w(u'</div>')
            if task.start is None:
                self.w(u'<div class="bottommarker">')
                self.w(u'<div class="bottommarkerline" style="margin: 0px 3px 0px 3px; height: 1px;">')
                self.w(u'</div>')
                self.w(u'<div class="bottommarkerline" style="margin: 0px 2px 0px 2px; height: 1px;">')
                self.w(u'</div>')
                self.w(u'<div class="bottommarkerline" style="margin: 0px 1px 0px 1px; height: 3ex; color: white; font-size: x-small; vertical-align: center; text-align: center;">')
                self.w(u'end')
                self.w(u'</div>')
                self.w(u'</div>')
            self.w(u'</div>')

            
    def _prevnext_links(self, curdate):
        prevdate = curdate - RelativeDateTime(days=7)
        nextdate = curdate + RelativeDateTime(days=7)
        rql = self.rset.rql
        prevlink = ajax_replace_url('oneweekcalid', rql, 'oneweekcal',
                                    year=prevdate.year, week=prevdate.iso_week[1])
        nextlink = ajax_replace_url('oneweekcalid', rql, 'oneweekcal',
                                    year=nextdate.year, week=nextdate.iso_week[1])
        return prevlink, nextlink

