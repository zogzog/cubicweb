"""html calendar views

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from datetime import datetime, date, timedelta

from logilab.mtconverter import xml_escape

from cubicweb.interfaces import ICalendarable
from cubicweb.selectors import implements
from cubicweb.utils import strptime, date_range, todate, todatetime
from cubicweb.view import EntityView


# useful constants & functions ################################################

ONEDAY = timedelta(1)

WEEKDAYS = (_("monday"), _("tuesday"), _("wednesday"), _("thursday"),
            _("friday"), _("saturday"), _("sunday"))
MONTHNAMES = ( _('january'), _('february'), _('march'), _('april'), _('may'),
               _('june'), _('july'), _('august'), _('september'), _('october'),
               _('november'), _('december')
               )

# Calendar views ##############################################################

try:
    from vobject import iCalendar

    class iCalView(EntityView):
        """A calendar view that generates a iCalendar file (RFC 2445)

        Does apply to ICalendarable compatible entities
        """
        __select__ = implements(ICalendarable)
        need_navigation = False
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
                if task.start:
                    event.add('dtstart').value = task.start
                if task.stop:
                    event.add('dtend').value = task.stop

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
    __select__ = implements(ICalendarable)
    need_navigation = False
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
            if task.start:
                self.w(u'<abbr class="dtstart" title="%s">%s</abbr>' % (task.start.isoformat(), self._cw.format_date(task.start)))
            if task.stop:
                self.w(u'<abbr class="dtstop" title="%s">%s</abbr>' % (task.stop.isoformat(), self._cw.format_date(task.stop)))
            self.w(u'</div>')
        self.w(u'</div>')


class CalendarItemView(EntityView):
    __regid__ = 'calendaritem'

    def cell_call(self, row, col, dates=False):
        task = self.cw_rset.complete_entity(row, 0)
        task.view('oneline', w=self.w)
        if dates:
            if task.start and task.stop:
                self.w('<br/>' % self._cw._('from %(date)s' % {'date': self._cw.format_date(task.start)}))
                self.w('<br/>' % self._cw._('to %(date)s' % {'date': self._cw.format_date(task.stop)}))
                self.w('<br/>to %s'%self._cw.format_date(task.stop))

class CalendarLargeItemView(CalendarItemView):
    __regid__ = 'calendarlargeitem'


class _TaskEntry(object):
    def __init__(self, task, color, index=0):
        self.task = task
        self.color = color
        self.index = index
        self.length = 1

    def in_working_hours(self):
        """predicate returning True is the task is in working hours"""
        if todatetime(self.task.start).hour > 7 and todatetime(self.task.stop).hour < 20:
            return True
        return False

    def is_one_day_task(self):
        task = self.task
        return task.start and task.stop and task.start.isocalendar() ==  task.stop.isocalendar()


class OneMonthCal(EntityView):
    """At some point, this view will probably replace ampm calendars"""
    __regid__ = 'onemonthcal'
    __select__ = implements(ICalendarable)
    need_navigation = False
    title = _('one month')

    def call(self):
        self._cw.add_js('cubicweb.ajax.js')
        self._cw.add_css('cubicweb.calendar.css')
        # XXX: restrict courses directy with RQL
        _today =  datetime.today()

        if 'year' in self._cw.form:
            year = int(self._cw.form['year'])
        else:
            year = _today.year
        if 'month' in self._cw.form:
            month = int(self._cw.form['month'])
        else:
            month = _today.month

        first_day_of_month = date(year, month, 1)
        firstday = first_day_of_month - timedelta(first_day_of_month.weekday())
        if month >= 12:
            last_day_of_month = date(year + 1, 1, 1) - timedelta(1)
        else:
            last_day_of_month = date(year, month + 1, 1) - timedelta(1)
        lastday = last_day_of_month + timedelta(6 - last_day_of_month.weekday())
        month_dates = list(date_range(firstday, lastday))
        dates = {}
        task_max = 0
        for row in xrange(self.cw_rset.rowcount):
            task = self.cw_rset.get_entity(row, 0)
            if len(self.cw_rset[row]) > 1 and self.cw_rset.description[row][1] == 'CWUser':
                user = self.cw_rset.get_entity(row, 1)
            else:
                user = None
            the_dates = []
            tstart = task.start
            if tstart:
                tstart = todate(task.start)
                if tstart > lastday:
                    continue
                the_dates = [tstart]
            tstop = task.stop
            if tstop:
                tstop = todate(tstop)
                if tstop < firstday:
                    continue
                the_dates = [tstop]
            if tstart and tstop:
                if tstart.isocalendar() == tstop.isocalendar():
                    if firstday <= tstart <= lastday:
                        the_dates = [tstart]
                else:
                    the_dates = date_range(max(tstart, firstday),
                                           min(tstop, lastday))
            if not the_dates:
                continue

            for d in the_dates:
                d_tasks = dates.setdefault((d.year, d.month, d.day), {})
                t_users = d_tasks.setdefault(task, set())
                t_users.add( user )
                if len(d_tasks) > task_max:
                    task_max = len(d_tasks)

        days = []
        nrows = max(3, task_max)
        # colors here are class names defined in cubicweb.css
        colors = [ "col%x" % i for i in range(12) ]
        next_color_index = 0

        visited_tasks = {} # holds a description of a task
        task_colors = {}   # remember a color assigned to a task
        for mdate in month_dates:
            d_tasks = dates.get((mdate.year, mdate.month, mdate.day), {})
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
                for i, t in enumerate(rows):
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
               (xml_escape(prevlink), self._cw._(curdate.strftime('%B').lower()),
                curdate.year, xml_escape(nextlink)))

        # output header
        self.w(u'<tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>' %
               tuple(self._cw._(day) for day in WEEKDAYS))

        # build calendar
        for mdate, task_rows in zip(month_dates, days):
            if mdate.weekday() == 0:
                self.w(u'<tr>')
            self._build_calendar_cell(mdate, task_rows, curdate)
            if mdate.weekday() == 6:
                self.w(u'</tr>')
        self.w(u'</table></div>')

    def _prevnext_links(self, curdate):
        prevdate = curdate - timedelta(31)
        nextdate = curdate + timedelta(31)
        rql = self.cw_rset.printable_rql()
        prevlink = self._cw.build_ajax_replace_url('onemonthcalid', rql, 'onemonthcal',
                                                   year=prevdate.year,
                                                   month=prevdate.month)
        nextlink = self._cw.build_ajax_replace_url('onemonthcalid', rql, 'onemonthcal',
                                                   year=nextdate.year,
                                                   month=nextdate.month)
        return prevlink, nextlink

    def _build_calendar_cell(self, celldate, rows, curdate):
        curmonth = curdate.month
        classes = ""
        if celldate.month != curmonth:
            classes += " outOfRange"
        if celldate == date.today():
            classes += " today"
        self.w(u'<td class="cell%s">' % classes)
        self.w(u'<div class="calCellTitle%s">' % classes)
        self.w(u'<div class="day">%s</div>' % celldate.day)

        if len(self.cw_rset.column_types(0)) == 1:
            etype = list(self.cw_rset.column_types(0))[0]
            url = self._cw.build_url(vid='creation', etype=etype,
                                     schedule=True,
                                     start=self._cw.format_date(celldate), stop=self._cw.format_date(celldate),
                                     __redirectrql=self.cw_rset.printable_rql(),
                                     __redirectparams=self._cw.build_url_params(year=curdate.year, month=curmonth),
                                     __redirectvid=self.__regid__
                                     )
            self.w(u'<div class="cmd"><a href="%s">%s</a></div>' % (xml_escape(url), self._cw._(u'add')))
            self.w(u'&#160;')
        self.w(u'</div>')
        self.w(u'<div class="cellContent">')
        for task_descr in rows:
            if task_descr:
                task = task_descr.task
                self.w(u'<div class="task %s">' % task_descr.color)
                task.view('calendaritem', w=self.w )
                url = task.absolute_url(vid='edition',
                                        __redirectrql=self.cw_rset.printable_rql(),
                                        __redirectparams=self._cw.build_url_params(year=curdate.year, month=curmonth),
                                        __redirectvid=self.__regid__
                                        )

                self.w(u'<div class="tooltip" ondblclick="stopPropagation(event); window.location.assign(\'%s\'); return false;">' % xml_escape(url))
                task.view('tooltip', w=self.w )
                self.w(u'</div>')
            else:
                self.w(u'<div class="task">')
                self.w(u"&#160;")
            self.w(u'</div>')
        self.w(u'</div>')
        self.w(u'</td>')


class OneWeekCal(EntityView):
    """At some point, this view will probably replace ampm calendars"""
    __regid__ = 'oneweekcal'
    __select__ = implements(ICalendarable)
    need_navigation = False
    title = _('one week')

    def call(self):
        self._cw.add_js( ('cubicweb.ajax.js', 'cubicweb.calendar.js') )
        self._cw.add_css('cubicweb.calendar.css')
        # XXX: restrict directly with RQL
        _today =  datetime.today()
        if 'year' in self._cw.form:
            year = int(self._cw.form['year'])
        else:
            year = _today.year
        if 'week' in self._cw.form:
            week = int(self._cw.form['week'])
        else:
            week = _today.isocalendar()[1]
        # week - 1 since we get week number > 0 while we want it to start from 0
        first_day_of_week = todate(strptime('%s-%s-1' % (year, week - 1), '%Y-%U-%w'))
        lastday = first_day_of_week + timedelta(6)
        firstday = first_day_of_week
        dates = [[] for i in range(7)]
        task_colors = {}   # remember a color assigned to a task
        # colors here are class names defined in cubicweb.css
        colors = [ "col%x" % i for i in range(12) ]
        next_color_index = 0
        done_tasks = []
        for row in xrange(self.cw_rset.rowcount):
            task = self.cw_rset.get_entity(row, 0)
            if task in done_tasks:
                continue
            done_tasks.append(task)
            the_dates = []
            tstart = task.start
            tstop = task.stop
            if tstart:
                tstart = todate(tstart)
                if tstart > lastday:
                    continue
                the_dates = [tstart]
            if tstop:
                tstop = todate(tstop)
                if tstop < firstday:
                    continue
                the_dates = [tstop]
            if tstart and tstop:
                the_dates = date_range(max(tstart, firstday),
                                       min(tstop, lastday))
            if not the_dates:
                continue

            if task not in task_colors:
                task_colors[task] = colors[next_color_index]
                next_color_index = (next_color_index+1) % len(colors)

            for d in the_dates:
                day = d.weekday()
                task_descr = _TaskEntry(task, task_colors[task])
                dates[day].append(task_descr)

        self.w(u'<div id="oneweekcalid">')
        # build schedule
        self.w(u'<table class="omcalendar" id="week">')
        prevlink, nextlink = self._prevnext_links(first_day_of_week)  # XXX
        self.w(u'<tr><th class="transparent"></th>')
        self.w(u'<th><a href="%s">&lt;&lt;</a></th><th colspan="5">%s %s %s</th>'
               u'<th><a href="%s">&gt;&gt;</a></th></tr>' %
               (xml_escape(prevlink), first_day_of_week.year,
                self._cw._(u'week'), first_day_of_week.isocalendar()[1],
                xml_escape(nextlink)))

        # output header
        self.w(u'<tr>')
        self.w(u'<th class="transparent"></th>') # column for hours
        _today = date.today()
        for i, day in enumerate(WEEKDAYS):
            wdate = first_day_of_week + timedelta(i)
            if wdate.isocalendar() == _today.isocalendar():
                self.w(u'<th class="today">%s<br/>%s</th>' % (self._cw._(day), self._cw.format_date(wdate)))
            else:
                self.w(u'<th>%s<br/>%s</th>' % (self._cw._(day), self._cw.format_date(wdate)))
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
            wdate = first_day_of_week + timedelta(i)
            classes = ""
            if wdate.isocalendar() == _today.isocalendar():
                classes = " today"
            self.w(u'<td class="column %s" id="%s">' % (classes, day))
            if len(self.cw_rset.column_types(0)) == 1:
                etype = list(self.cw_rset.column_types(0))[0]
                url = self._cw.build_url(vid='creation', etype=etype,
                                         schedule=True,
                                         __redirectrql=self.cw_rset.printable_rql(),
                                         __redirectparams=self._cw.build_url_params(year=year, week=week),
                                         __redirectvid=self.__regid__
                                         )
                extra = ' ondblclick="addCalendarItem(event, hmin=8, hmax=20, year=%s, month=%s, day=%s, duration=2, baseurl=\'%s\')"' % (
                    wdate.year, wdate.month, wdate.day, xml_escape(url))
            else:
                extra = ""
            self.w(u'<div class="columndiv"%s>'% extra)
            for h in range(8, 20):
                self.w(u'<div class="hourline" style="top:%sex;">'%((h-7)*8))
                self.w(u'</div>')
            if dates[i]:
                self._build_calendar_cell(wdate, dates[i])
            self.w(u'</div>')
            self.w(u'</td>')
        self.w(u'</tr>')
        self.w(u'</table></div>')
        self.w(u'<div id="coord"></div>')
        self.w(u'<div id="debug">&#160;</div>')

    def _build_calendar_cell(self, date, task_descrs):
        inday_tasks = [t for t in task_descrs if t.is_one_day_task() and  t.in_working_hours()]
        wholeday_tasks = [t for t in task_descrs if not t.is_one_day_task()]
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
                if date < todate(task.start) < date + ONEDAY:
                    start_hour = max(8, task.start.hour)
                    start_min = task.start.minute
            if task.stop:
                if date < todate(task.stop) < date + ONEDAY:
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
                                    __redirectrql=self.cw_rset.printable_rql(),
                                    __redirectparams=self._cw.build_url_params(year=date.year, week=date.isocalendar()[1]),
                                    __redirectvid=self.__regid__
                                 )

            self.w(u'<div class="tooltip" ondblclick="stopPropagation(event); window.location.assign(\'%s\'); return false;">' % xml_escape(url))
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
        prevdate = curdate - timedelta(7)
        nextdate = curdate + timedelta(7)
        rql = self.cw_rset.printable_rql()
        prevlink = self._cw.build_ajax_replace_url('oneweekcalid', rql, 'oneweekcal',
                                                   year=prevdate.year,
                                                   week=prevdate.isocalendar()[1])
        nextlink = self._cw.build_ajax_replace_url('oneweekcalid', rql, 'oneweekcal',
                                                   year=nextdate.year,
                                                   week=nextdate.isocalendar()[1])
        return prevlink, nextlink
