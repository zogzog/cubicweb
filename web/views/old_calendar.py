"""html calendar views

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from mx.DateTime import DateTime, RelativeDateTime, Date, Time, today, Sunday

from logilab.mtconverter import html_escape

from cubicweb.interfaces import ICalendarViews
from cubicweb.common.utils import date_range
from cubicweb.selectors import implements
from cubicweb.common.registerers import priority_registerer
from cubicweb.common.view import EntityView

# Define some useful constants
ONE_MONTH = RelativeDateTime(months=1)
TODAY = today()
THIS_MONTH = TODAY.month
THIS_YEAR = TODAY.year
# mx.DateTime and ustrftime could be used to build WEEKDAYS
WEEKDAYS = [_("monday"), _("tuesday"), _("wednesday"), _("thursday"),
            _("friday"), _("saturday"), _("sunday")]

# used by i18n tools
MONTHNAMES = [ _('january'), _('february'), _('march'), _('april'), _('may'),
               _('june'), _('july'), _('august'), _('september'), _('october'),
               _('november'), _('december')
               ]

class _CalendarView(EntityView):
    """base calendar view containing helpful methods to build calendar views"""
    __registerer__ = priority_registerer
    __selectors__ = implements(ICalendarViews)
    need_navigation = False

    # Navigation building methods / views ####################################

    PREV = u'<a href="%s">&lt;&lt;</a>&nbsp;&nbsp;<a href="%s">&lt;</a>'
    NEXT = u'<a href="%s">&gt;</a>&nbsp;&nbsp;<a href="%s">&gt;&gt;</a>'
    NAV_HEADER = u"""<table class="calendarPageHeader">
<tr><td class="prev">%s</td><td class="next">%s</td></tr>
</table>
""" % (PREV, NEXT)
    
    def nav_header(self, date, smallshift=3, bigshift=9):
        """prints shortcut links to go to previous/next steps (month|week)"""
        prev1 = date - RelativeDateTime(months=smallshift)
        prev2 = date - RelativeDateTime(months=bigshift)
        next1 = date + RelativeDateTime(months=smallshift)
        next2 = date + RelativeDateTime(months=bigshift)
        rql, vid = self.rset.printable_rql(), self.id
        return self.NAV_HEADER % (
            html_escape(self.build_url(rql=rql, vid=vid, year=prev2.year, month=prev2.month)),
            html_escape(self.build_url(rql=rql, vid=vid, year=prev1.year, month=prev1.month)),
            html_escape(self.build_url(rql=rql, vid=vid, year=next1.year, month=next1.month)),
            html_escape(self.build_url(rql=rql, vid=vid, year=next2.year, month=next2.month)))
        
    
    # Calendar building methods ##############################################
    
    def build_calendars(self, schedule, begin, end):
        """build several HTML calendars at once, one for each month
        between begin and end
        """
        return [self.build_calendar(schedule, date)
                for date in date_range(begin, end, incr=ONE_MONTH)]
    
    def build_calendar(self, schedule, first_day):
        """method responsible for building *one* HTML calendar"""
        # FIXME  iterates between [first_day-first_day.day_of_week ;
        #                          last_day+6-last_day.day_of_week]
        umonth = self.format_date(first_day, '%B %Y') # localized month name
        rows = []
        current_row = [NO_CELL] * first_day.day_of_week
        for daynum in xrange(0, first_day.days_in_month):
            # build cell day
            day = first_day + daynum
            events = schedule.get(day)
            if events:
                events = [u'\n'.join(event) for event in events.values()]
                current_row.append(CELL % (daynum+1, '\n'.join(events)))
            else:
                current_row.append(EMPTY_CELL % (daynum+1))
            # store & reset current row on Sundays
            if day.day_of_week == Sunday:
                rows.append(u'<tr>%s%s</tr>' % (WEEKNUM_CELL % day.iso_week[1], ''.join(current_row)))
                current_row = []
        current_row.extend([NO_CELL] * (Sunday-day.day_of_week))
        rql = self.rset.printable_rql()
        if day.day_of_week != Sunday:
            rows.append(u'<tr>%s%s</tr>' % (WEEKNUM_CELL % day.iso_week[1], ''.join(current_row)))
        url = self.build_url(rql=rql, vid='calendarmonth',
                             year=first_day.year, month=first_day.month)
        monthlink = u'<a href="%s">%s</a>' % (html_escape(url), umonth)
        return CALENDAR(self.req) % (monthlink, '\n'.join(rows))

    def _mk_schedule(self, begin, end, itemvid='calendaritem'):
        """private method that gathers information from resultset
        and builds calendars according to it

        :param begin: begin of date range
        :param end: end of date rangs
        :param itemvid: which view to call to render elements in cells

        returns { day1 : { hour : [views] },
                  day2 : { hour : [views] } ... }
        """
        # put this here since all sub views are calling this method        
        self.req.add_css('cubicweb.calendar.css') 
        schedule = {}
        for row in xrange(len(self.rset.rows)):
            entity = self.entity(row)
            infos = u'<div class="event">'
            infos += self.view(itemvid, self.rset, row=row)
            infos += u'</div>'
            for date in entity.matching_dates(begin, end):
                day = Date(date.year, date.month, date.day)
                time = Time(date.hour, date.minute, date.second) 
                schedule.setdefault(day, {})
                schedule[day].setdefault(time, []).append(infos)
        return schedule
        

    @staticmethod
    def get_date_range(day=TODAY, shift=4):
        """returns a couple (begin, end)

        <begin> is the first day of current_month - shift
        <end> is the last day of current_month + (shift+1)
        """
        first_day_in_month = DateTime(day.year, day.month, 1)
        begin = first_day_in_month - RelativeDateTime(months=shift)
        end = (first_day_in_month + RelativeDateTime(months=shift+1)) - 1
        return begin, end


    def _build_ampm_cells(self, daynum, events):
        """create a view without any hourly details.

        :param daynum: day of the built cell
        :param events: dictionnary with all events classified by hours"""
        # split events according am/pm
        am_events = [event for e_time, e_list in events.iteritems()
                     if 0 <= e_time.hour < 12
                     for event in e_list]
        pm_events = [event for e_time, e_list in events.iteritems()
                     if 12 <= e_time.hour < 24
                     for event in e_list]
        # format each am/pm cell
        if am_events:
            am_content = AMPM_CONTENT % ("amCell", "am", '\n'.join(am_events))
        else:
            am_content = AMPM_EMPTY % ("amCell", "am")
        if pm_events:
            pm_content = AMPM_CONTENT % ("pmCell", "pm", '\n'.join(pm_events))
        else:
            pm_content = AMPM_EMPTY % ("pmCell", "pm")
        return am_content, pm_content



class YearCalendarView(_CalendarView):
    id = 'calendaryear'
    title = _('calendar (year)')

    def call(self, year=THIS_YEAR, month=THIS_MONTH):
        """this view renders a 3x3 calendars' table"""
        year = int(self.req.form.get('year', year))
        month = int(self.req.form.get('month', month))
        center_date = DateTime(year, month)
        begin, end = self.get_date_range(day=center_date)
        schedule = self._mk_schedule(begin, end)
        self.w(self.nav_header(center_date))
        calendars = tuple(self.build_calendars(schedule, begin, end))
        self.w(SMALL_CALENDARS_PAGE % calendars)


class SemesterCalendarView(_CalendarView):
    """this view renders three semesters as three rows of six columns,
    one column per month
    """
    id = 'calendarsemester'
    title = _('calendar (semester)')

    def call(self, year=THIS_YEAR, month=THIS_MONTH):
        year = int(self.req.form.get('year', year))
        month = int(self.req.form.get('month', month))
        begin = DateTime(year, month) - RelativeDateTime(months=2)
        end = DateTime(year, month) + RelativeDateTime(months=3)
        schedule = self._mk_schedule(begin, end)
        self.w(self.nav_header(DateTime(year, month), 1, 6))
        self.w(u'<table class="semesterCalendar">')
        self.build_calendars(schedule, begin, end)
        self.w(u'</table>')
        self.w(self.nav_header(DateTime(year, month), 1, 6))

    def build_calendars(self, schedule, begin, end):
        self.w(u'<tr>')
        rql = self.rset.printable_rql()
        for cur_month in date_range(begin, end, incr=ONE_MONTH):
            umonth = u'%s&nbsp;%s' % (self.format_date(cur_month, '%B'), cur_month.year)
            url = self.build_url(rql=rql, vid=self.id,
                                 year=cur_month.year, month=cur_month.month)
            self.w(u'<th colspan="2"><a href="%s">%s</a></th>' % (html_escape(url),
                                                                  umonth))
        self.w(u'</tr>')
        _ = self.req._
        for day_num in xrange(31):
            self.w(u'<tr>')
            for cur_month in date_range(begin, end, incr=ONE_MONTH):
                if day_num >= cur_month.days_in_month:
                    self.w(u'%s%s' % (NO_CELL, NO_CELL))
                else:
                    day = DateTime(cur_month.year, cur_month.month, day_num+1)
                    events = schedule.get(day)
                    self.w(u'<td>%s&nbsp;%s</td>\n' % (_(WEEKDAYS[day.day_of_week])[0].upper(), day_num+1))
                    self.format_day_events(day, events)
            self.w(u'</tr>')
            
    def format_day_events(self, day, events):
        if events:
            events = ['\n'.join(event) for event in events.values()]
            self.w(WEEK_CELL % '\n'.join(events))
        else:
            self.w(WEEK_EMPTY_CELL)
        

class MonthCalendarView(_CalendarView):
    """this view renders a 3x1 calendars' table"""
    id = 'calendarmonth'
    title = _('calendar (month)')
    
    def call(self, year=THIS_YEAR, month=THIS_MONTH):
        year = int(self.req.form.get('year', year))
        month = int(self.req.form.get('month', month))
        center_date = DateTime(year, month)
        begin, end = self.get_date_range(day=center_date, shift=1)
        schedule = self._mk_schedule(begin, end)
        calendars = self.build_calendars(schedule, begin, end)
        self.w(self.nav_header(center_date, 1, 3))
        self.w(BIG_CALENDARS_PAGE % tuple(calendars))
        self.w(self.nav_header(center_date, 1, 3))

        
class WeekCalendarView(_CalendarView):
    """this view renders a calendar for week events"""
    id = 'calendarweek'
    title = _('calendar (week)')
    
    def call(self, year=THIS_YEAR, week=TODAY.iso_week[1]):
        year = int(self.req.form.get('year', year))
        week = int(self.req.form.get('week', week))
        day0 = DateTime(year)
        first_day_of_week = (day0-day0.day_of_week) + 7*week
        begin, end = first_day_of_week-7, first_day_of_week+14
        schedule = self._mk_schedule(begin, end, itemvid='calendarlargeitem')
        self.w(self.nav_header(first_day_of_week))
        self.w(u'<table class="weekCalendar">')
        _weeks = [(first_day_of_week-7, first_day_of_week-1),
                  (first_day_of_week, first_day_of_week+6),
                  (first_day_of_week+7, first_day_of_week+13)]
        self.build_calendar(schedule, _weeks)
        self.w(u'</table>')
        self.w(self.nav_header(first_day_of_week))
 
    def build_calendar(self, schedule, weeks):
        rql = self.rset.printable_rql()
        _ = self.req._
        for monday, sunday in weeks:            
            umonth = self.format_date(monday, '%B %Y')
            url = self.build_url(rql=rql, vid='calendarmonth',
                                 year=monday.year, month=monday.month)
            monthlink = '<a href="%s">%s</a>' % (html_escape(url), umonth)
            self.w(u'<tr><th colspan="3">%s %s (%s)</th></tr>' \
                  % (_('week'), monday.iso_week[1], monthlink))
            for day in date_range(monday, sunday):
                self.w(u'<tr>')
                self.w(u'<td>%s</td>' % _(WEEKDAYS[day.day_of_week]))
                self.w(u'<td>%s</td>' % (day.strftime('%Y-%m-%d')))
                events = schedule.get(day)
                if events:
                    events = ['\n'.join(event) for event in events.values()]
                    self.w(WEEK_CELL % '\n'.join(events))
                else:
                    self.w(WEEK_EMPTY_CELL)
                self.w(u'</tr>')
        
    def nav_header(self, date, smallshift=1, bigshift=3):
        """prints shortcut links to go to previous/next steps (month|week)"""
        prev1 = date - RelativeDateTime(weeks=smallshift)
        prev2 = date - RelativeDateTime(weeks=bigshift)
        next1 = date + RelativeDateTime(weeks=smallshift)
        next2 = date + RelativeDateTime(weeks=bigshift)
        rql, vid = self.rset.printable_rql(), self.id
        return self.NAV_HEADER % (
            html_escape(self.build_url(rql=rql, vid=vid, year=prev2.year, week=prev2.iso_week[1])),
            html_escape(self.build_url(rql=rql, vid=vid, year=prev1.year, week=prev1.iso_week[1])),
            html_escape(self.build_url(rql=rql, vid=vid, year=next1.year, week=next1.iso_week[1])),
            html_escape(self.build_url(rql=rql, vid=vid, year=next2.year, week=next2.iso_week[1])))


        
class AMPMYearCalendarView(YearCalendarView):
    id = 'ampmcalendaryear'
    title = _('am/pm calendar (year)')
    
    def build_calendar(self, schedule, first_day):
        """method responsible for building *one* HTML calendar"""
        umonth = self.format_date(first_day, '%B %Y') # localized month name
        rows = [] # each row is: (am,pm), (am,pm) ... week_title
        current_row = [(NO_CELL, NO_CELL, NO_CELL)] * first_day.day_of_week
        rql = self.rset.printable_rql()
        for daynum in xrange(0, first_day.days_in_month):
            # build cells day
            day = first_day + daynum
            events = schedule.get(day)
            if events:
                current_row.append((AMPM_DAY % (daynum+1),) + self._build_ampm_cells(daynum, events))
            else:
                current_row.append((AMPM_DAY % (daynum+1),
                                    AMPM_EMPTY % ("amCell", "am"),
                                    AMPM_EMPTY % ("pmCell", "pm")))
            # store & reset current row on Sundays
            if day.day_of_week == Sunday:
                url = self.build_url(rql=rql, vid='ampmcalendarweek',
                                     year=day.year, week=day.iso_week[1])
                weeklink = '<a href="%s">%s</a>' % (html_escape(url),
                                                    day.iso_week[1])
                current_row.append(WEEKNUM_CELL % weeklink)
                rows.append(current_row)
                current_row = []
        current_row.extend([(NO_CELL, NO_CELL, NO_CELL)] * (Sunday-day.day_of_week))
        url = self.build_url(rql=rql, vid='ampmcalendarweek',
                             year=day.year, week=day.iso_week[1])
        weeklink = '<a href="%s">%s</a>' % (html_escape(url), day.iso_week[1])
        current_row.append(WEEKNUM_CELL % weeklink)
        rows.append(current_row)
        # build two rows for each week: am & pm
        formatted_rows = []
        for row in rows:
            week_title = row.pop()
            day_row = [day for day, am, pm in row]
            am_row = [am for day, am, pm in row]
            pm_row = [pm for day, am, pm in row]
            formatted_rows.append('<tr>%s%s</tr>'% (week_title, '\n'.join(day_row)))
            formatted_rows.append('<tr class="amRow"><td>&nbsp;</td>%s</tr>'% '\n'.join(am_row))
            formatted_rows.append('<tr class="pmRow"><td>&nbsp;</td>%s</tr>'% '\n'.join(pm_row))
        # tigh everything together
        url = self.build_url(rql=rql, vid='ampmcalendarmonth',
                             year=first_day.year, month=first_day.month)
        monthlink = '<a href="%s">%s</a>' % (html_escape(url), umonth)
        return CALENDAR(self.req) % (monthlink, '\n'.join(formatted_rows))
        


class AMPMSemesterCalendarView(SemesterCalendarView):
    """this view renders a 3x1 calendars' table"""
    id = 'ampmcalendarsemester'
    title = _('am/pm calendar (semester)')

    def build_calendars(self, schedule, begin, end):
        self.w(u'<tr>')
        rql = self.rset.printable_rql()
        for cur_month in date_range(begin, end, incr=ONE_MONTH):
            umonth = u'%s&nbsp;%s' % (self.format_date(cur_month, '%B'), cur_month.year)
            url = self.build_url(rql=rql, vid=self.id,
                                 year=cur_month.year, month=cur_month.month)
            self.w(u'<th colspan="3"><a href="%s">%s</a></th>' % (html_escape(url),
                                                                  umonth))
        self.w(u'</tr>')
        _ = self.req._
        for day_num in xrange(31):
            self.w(u'<tr>')
            for cur_month in date_range(begin, end, incr=ONE_MONTH):
                if day_num >= cur_month.days_in_month:
                    self.w(u'%s%s%s' % (NO_CELL, NO_CELL, NO_CELL))
                else:
                    day = DateTime(cur_month.year, cur_month.month, day_num+1)
                    events = schedule.get(day)
                    self.w(u'<td>%s&nbsp;%s</td>\n' % (_(WEEKDAYS[day.day_of_week])[0].upper(),
                                                       day_num+1))
                    self.format_day_events(day, events)
            self.w(u'</tr>')
    
    def format_day_events(self, day, events):
        if events:
            self.w(u'\n'.join(self._build_ampm_cells(day, events)))
        else:
            self.w(u'%s %s'% (AMPM_EMPTY % ("amCell", "am"), 
                              AMPM_EMPTY % ("pmCell", "pm")))


class AMPMMonthCalendarView(MonthCalendarView):
    """this view renders a 3x1 calendars' table"""
    id = 'ampmcalendarmonth'
    title = _('am/pm calendar (month)')

    def build_calendar(self, schedule, first_day):
        """method responsible for building *one* HTML calendar"""
        umonth = self.format_date(first_day, '%B %Y') # localized month name
        rows = [] # each row is: (am,pm), (am,pm) ... week_title
        current_row = [(NO_CELL, NO_CELL, NO_CELL)] * first_day.day_of_week
        rql = self.rset.printable_rql()
        for daynum in xrange(0, first_day.days_in_month):
            # build cells day
            day = first_day + daynum
            events = schedule.get(day)
            if events:
                current_row.append((AMPM_DAY % (daynum+1),) + self._build_ampm_cells(daynum, events))
            else:
                current_row.append((AMPM_DAY % (daynum+1),
                                    AMPM_EMPTY % ("amCell", "am"),
                                    AMPM_EMPTY % ("pmCell", "pm")))
            # store & reset current row on Sundays
            if day.day_of_week == Sunday:
                url = self.build_url(rql=rql, vid='ampmcalendarweek',
                                     year=day.year, week=day.iso_week[1])
                weeklink = '<a href="%s">%s</a>' % (html_escape(url),
                                                    day.iso_week[1])
                current_row.append(WEEKNUM_CELL % weeklink)
                rows.append(current_row)
                current_row = []
        current_row.extend([(NO_CELL, NO_CELL, NO_CELL)] * (Sunday-day.day_of_week))
        url = self.build_url(rql=rql, vid='ampmcalendarweek',
                             year=day.year, week=day.iso_week[1])
        weeklink = '<a href="%s">%s</a>' % (html_escape(url),
                                            day.iso_week[1])
        current_row.append(WEEKNUM_CELL % weeklink)
        rows.append(current_row)
        # build two rows for each week: am & pm
        formatted_rows = []
        for row in rows:
            week_title = row.pop()
            day_row = [day for day, am, pm in row]
            am_row = [am for day, am, pm in row]
            pm_row = [pm for day, am, pm in row]
            formatted_rows.append('<tr>%s%s</tr>'% (week_title, '\n'.join(day_row)))
            formatted_rows.append('<tr class="amRow"><td>&nbsp;</td>%s</tr>'% '\n'.join(am_row))
            formatted_rows.append('<tr class="pmRow"><td>&nbsp;</td>%s</tr>'% '\n'.join(pm_row))
        # tigh everything together
        url = self.build_url(rql=rql, vid='ampmcalendarmonth',
                             year=first_day.year, month=first_day.month)
        monthlink = '<a href="%s">%s</a>' % (html_escape(url),
                                             umonth)
        return CALENDAR(self.req) % (monthlink, '\n'.join(formatted_rows))      
    

    
class AMPMWeekCalendarView(WeekCalendarView):
    """this view renders a 3x1 calendars' table"""
    id = 'ampmcalendarweek'
    title = _('am/pm calendar (week)')

    def build_calendar(self, schedule, weeks):
        rql = self.rset.printable_rql()
        w = self.w
        _ = self.req._
        for monday, sunday in weeks:
            umonth = self.format_date(monday, '%B %Y')
            url = self.build_url(rql=rql, vid='ampmcalendarmonth',
                                 year=monday.year, month=monday.month)
            monthlink = '<a href="%s">%s</a>' % (html_escape(url), umonth)
            w(u'<tr>%s</tr>' % (
                WEEK_TITLE % (_('week'), monday.iso_week[1], monthlink)))
            w(u'<tr><th>%s</th><th>&nbsp;</th></tr>'% _(u'Date'))
            for day in date_range(monday, sunday):
                events = schedule.get(day)
                style = day.day_of_week % 2 and "even" or "odd"
                w(u'<tr class="%s">' % style)
                if events:
                    hours = events.keys()
                    hours.sort()
                    w(AMPM_DAYWEEK % (
                        len(hours), _(WEEKDAYS[day.day_of_week]),
                        self.format_date(day)))
                    w(AMPM_WEEK_CELL % (
                        hours[0].hour, hours[0].minute,
                        '\n'.join(events[hours[0]])))
                    w(u'</tr>')
                    for hour in hours[1:]:
                        w(u'<tr class="%s">%s</tr>'% (
                            style, AMPM_WEEK_CELL % (hour.hour, hour.minute,
                                                     '\n'.join(events[hour]))))
                else:
                    w(AMPM_DAYWEEK_EMPTY % (
                        _(WEEKDAYS[day.day_of_week]),
                        self.format_date(day)))
                    w(WEEK_EMPTY_CELL)
                    w(u'</tr>')


SMALL_CALENDARS_PAGE = u"""<table class="smallCalendars">
<tr><td class="calendar">%s</td><td class="calendar">%s</td><td class="calendar">%s</td></tr>
<tr><td class="calendar">%s</td><td class="calendar">%s</td><td class="calendar">%s</td></tr>
<tr><td class="calendar">%s</td><td class="calendar">%s</td><td class="calendar">%s</td></tr>
</table>
"""

BIG_CALENDARS_PAGE = u"""<table class="bigCalendars">
<tr><td class="calendar">%s</td></tr>
<tr><td class="calendar">%s</td></tr>
<tr><td class="calendar">%s</td></tr>
</table>
"""

WEEKNUM_CELL = u'<td class="weeknum">%s</td>'

def CALENDAR(req):
    _ = req._
    WEEKNUM_HEADER = u'<th class="weeknum">%s</th>' % _('week')
    CAL_HEADER = WEEKNUM_HEADER + u' \n'.join([u'<th class="weekday">%s</th>' % _(day)[0].upper()
                                               for day in WEEKDAYS])
    return u"""<table>
<tr><th class="month" colspan="8">%%s</th></tr>
<tr>
  %s
</tr>
%%s
</table>
""" % (CAL_HEADER,)


DAY_TEMPLATE = """<tr><td class="weekday">%(daylabel)s</td><td>%(dmydate)s</td><td>%(dayschedule)s</td>
"""

NO_CELL = u'<td class="noday"></td>'
EMPTY_CELL = u'<td class="cellEmpty"><span class="cellTitle">%s</span></td>'
CELL = u'<td class="cell"><span class="cellTitle">%s</span><div class="cellContent">%s</div></td>'

AMPM_DAY = u'<td class="cellDay">%d</td>'
AMPM_EMPTY = u'<td class="%sEmpty"><span class="cellTitle">%s</span></td>'
AMPM_CONTENT = u'<td class="%s"><span class="cellTitle">%s</span><div class="cellContent">%s</div></td>'

WEEK_TITLE = u'<th class="weekTitle" colspan="2">%s %s (%s)</th>'
WEEK_EMPTY_CELL = u'<td class="weekEmptyCell">&nbsp;</td>'
WEEK_CELL = u'<td class="weekCell"><div class="cellContent">%s</div></td>'

AMPM_DAYWEEK_EMPTY = u'<td>%s&nbsp;%s</td>'
AMPM_DAYWEEK = u'<td rowspan="%d">%s&nbsp;%s</td>'
AMPM_WEEK_CELL = u'<td class="ampmWeekCell"><div class="cellContent">%02d:%02d - %s</div></td>'
