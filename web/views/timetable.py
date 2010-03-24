"""html calendar views

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.mtconverter import xml_escape
from logilab.common.date import date_range, todatetime

from cubicweb.interfaces import ITimetableViews
from cubicweb.selectors import implements
from cubicweb.view import AnyRsetView


class _TaskEntry(object):
    def __init__(self, task, color, column):
        self.task = task
        self.color = color
        self.column = column
        self.lines = 1

MIN_COLS = 3  # minimum number of task columns for a single user
ALL_USERS = object()

class TimeTableView(AnyRsetView):
    __regid__ = 'timetable'
    title = _('timetable')
    __select__ = implements(ITimetableViews)
    paginable = False

    def call(self, title=None):
        """Dumps a timetable from a resultset composed of a note (anything
        with start/stop) and a user (anything)"""
        self._cw.add_css('cubicweb.timetable.css')
        dates = {}
        users = []
        users_max = {}
        # XXX: try refactoring with calendar.py:OneMonthCal
        for row in xrange(self.cw_rset.rowcount):
            task = self.cw_rset.get_entity(row, 0)
            if len(self.cw_rset[row]) > 1:
                user = self.cw_rset.get_entity(row, 1)
            else:
                user = ALL_USERS
            the_dates = []
            if task.start and task.stop:
                if task.start.toordinal() == task.stop.toordinal():
                    the_dates.append(task.start)
                else:
                    the_dates += date_range( task.start, task.stop )
            elif task.start:
                the_dates.append(task.start)
            elif task.stop:
                the_dates.append(task.stop)
            for d in the_dates:
                d = todatetime(d)
                d_users = dates.setdefault(d, {})
                u_tasks = d_users.setdefault(user, set())
                u_tasks.add( task )
                task_max = users_max.setdefault(user, 0)
                if len(u_tasks)>task_max:
                    users_max[user] = len(u_tasks)
            if user not in users:
                # keep original ordering
                users.append(user)
        if not dates:
            return
        date_min = min(dates)
        date_max = max(dates)
        #users = list(sorted(users, key=lambda u:u.login))

        rows = []
        # colors here are class names defined in cubicweb.css
        colors = ["col%x" % i for i in xrange(12)]
        next_color_index = 0

        visited_tasks = {} # holds a description of a task for a user
        task_colors = {}   # remember a color assigned to a task
        for date in date_range(date_min, date_max):
            columns = [date]
            d_users = dates.get(date, {})
            for user in users:
                # every user has its column "splitted" in at least MIN_COLS
                # sub-columns (for overlapping tasks)
                user_columns = [None] * max(MIN_COLS, users_max[user])
                # every task that is "visited" for the first time
                # require a special treatment, so we put them in
                # 'postpone'
                postpone = []
                for task in d_users.get(user, []):
                    key = (task, user)
                    if key in visited_tasks:
                        task_descr = visited_tasks[ key ]
                        user_columns[task_descr.column] = task_descr, False
                        task_descr.lines += 1
                    else:
                        postpone.append(key)
                for key in postpone:
                    # to every 'new' task we must affect a color
                    # (which must be the same for every user concerned
                    # by the task)
                    task, user = key
                    for i, t in enumerate(user_columns):
                        if t is None:
                            if task in task_colors:
                                color = task_colors[task]
                            else:
                                color = colors[next_color_index]
                                next_color_index = (next_color_index+1)%len(colors)
                                task_colors[task] = color
                            task_descr = _TaskEntry(task, color, i)
                            user_columns[i] = task_descr, True
                            visited_tasks[key] = task_descr
                            break
                    else:
                        raise RuntimeError("is it possible we got it wrong?")

                columns.append( user_columns )
            rows.append( columns )

        widths = [ len(col) for col in rows[0][1:] ]
        self.w(u'<div class="section">')
        if title:
            self.w(u'<h4>%s</h4>\n' % title)
        self.w(u'<table class="listing timetable">')
        self.render_col_headers(users, widths)
        self.render_rows(rows)
        self.w(u'</table>')
        self.w(u'</div>\n')

    def render_col_headers(self, users, widths):
        """ render column headers """
        self.w(u'<tr class="header">\n')

        self.w(u'<th class="ttdate">&#160;</th>\n')
        columns = []
        for user, width in zip(users, widths):
            self.w(u'<th colspan="%s">' % max(MIN_COLS, width))
            if user is ALL_USERS:
                self.w(u'*')
            else:
                user.view('oneline', w=self.w)
            self.w(u'</th>')
        self.w(u'</tr>\n')
        return columns

    def render_rows(self, rows):
        """ render table content (row headers and central content) """
        odd = False
        previous_is_empty = False
        for row in rows:
            date = row[0]
            empty_line = True
            for group in row[1:]:
                for value in group:
                    if value:
                        empty_line = False
                        break
                else:
                    continue
                break
            if empty_line and previous_is_empty:
                continue
            previous_is_empty = False

            klass = "even"
            if date.weekday() in (5, 6) and not empty_line:
                klass = "odd"
            self.w(u'<tr class="%s">' % klass)
            odd = not odd

            if not empty_line:
                self.w(u'<th class="ttdate">%s</th>' % self._cw.format_date(date) )
            else:
                self.w(u'<th>...</th>'  )
                previous_is_empty = True

            empty_klasses = [ "ttle", "ttme", "ttre" ]
            filled_klasses = [ "ttlf", "ttmf", "ttrf" ]
            kj = 0 # 0: left, 1: mid, 2: right
            for uid, group in enumerate(row[1:]):
                for i, value in enumerate(group):
                    if i == 0:
                        kj = 0
                    elif i == len(group):
                        kj = 2
                    else:
                        kj = 1
                    if value:
                        task_descr, first_row = value
                        if first_row:
                            url = xml_escape(task_descr.task.absolute_url(vid="edition"))
                            self.w(u'<td rowspan="%d" class="%s %s" onclick="document.location=\'%s\'">&#160;<div>' % (
                                task_descr.lines, task_descr.color, filled_klasses[kj], url))
                            task_descr.task.view('tooltip', w=self.w)
                            self.w(u'</div></td>')
                    else:
                        if empty_line:
                            self.w(u'<td class="ttempty">&#160;</td>')
                        else:
                            self.w(u'<td class="%s">&#160;</td>' % empty_klasses[kj] )
            self.w(u'</tr>\n')
