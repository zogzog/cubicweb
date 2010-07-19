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
"""Specific views for entities implementing IProgress

"""
__docformat__ = "restructuredtext en"
_ = unicode

from math import floor

from logilab.mtconverter import xml_escape

from cubicweb.utils import make_uid
from cubicweb.selectors import implements
from cubicweb.interfaces import IProgress, IMileStone
from cubicweb.schema import display_name
from cubicweb.view import EntityView
from cubicweb.web.views.tableview import EntityAttributesTableView

class ProgressTableView(EntityAttributesTableView):
    """The progress table view is able to display progress information
    of any object implement IMileStone.

    The default layout is composoed of 7 columns : parent task,
    milestone, state, estimated date, cost, progressbar, and todo_by

    The view accepts an optional ``columns`` paramater that lets you
    remove or reorder some of those columns.

    To add new columns, you should extend this class, define a new
    ``columns`` class attribute and implement corresponding
    build_COLNAME_cell methods

    header_for_COLNAME methods allow to customize header's label
    """

    __regid__ = 'progress_table_view'
    title = _('task progression')
    __select__ = implements(IMileStone)
    table_css = "progress"
    css_files = ('cubicweb.iprogress.css',)

    # default columns of the table
    columns = (_('project'), _('milestone'), _('state'), _('eta_date'),
               _('cost'), _('progress'), _('todo_by'))

    def cell_call(self, row, col):
        _ = self._cw._
        entity = self.cw_rset.get_entity(row, col)
        infos = {}
        for col in self.columns:
            meth = getattr(self, 'build_%s_cell' % col, None)
            # find the build method or try to find matching attribute
            if meth:
                content = meth(entity)
            else:
                content = entity.printable_value(col)
            infos[col] = content
        if hasattr(entity, 'progress_class'):
            cssclass = entity.progress_class()
        else:
            cssclass = u''
        self.w(u"""<tr class="%s" onmouseover="addElementClass(this, 'highlighted');"
            onmouseout="removeElementClass(this, 'highlighted')">""" % cssclass)
        line = u''.join(u'<td>%%(%s)s</td>' % col for col in self.columns)
        self.w(line % infos)
        self.w(u'</tr>\n')

    ## header management ######################################################

    def header_for_project(self, ecls):
        """use entity's parent type as label"""
        return display_name(self._cw, ecls.parent_type)

    def header_for_milestone(self, ecls):
        """use entity's type as label"""
        return display_name(self._cw, ecls.__regid__)

    ## cell management ########################################################
    def build_project_cell(self, entity):
        """``project`` column cell renderer"""
        project = entity.get_main_task()
        if project:
            return project.view('incontext')
        return self._cw._('no related project')

    def build_milestone_cell(self, entity):
        """``milestone`` column cell renderer"""
        return entity.view('incontext')

    def build_state_cell(self, entity):
        """``state`` column cell renderer"""
        return xml_escape(self._cw._(entity.state))

    def build_eta_date_cell(self, entity):
        """``eta_date`` column cell renderer"""
        if entity.finished():
            return self._cw.format_date(entity.completion_date())
        formated_date = self._cw.format_date(entity.initial_prevision_date())
        if entity.in_progress():
            eta_date = self._cw.format_date(entity.eta_date())
            _ = self._cw._
            if formated_date:
                formated_date += u' (%s %s)' % (_('expected:'), eta_date)
            else:
                formated_date = u'%s %s' % (_('expected:'), eta_date)
        return formated_date

    def build_todo_by_cell(self, entity):
        """``todo_by`` column cell renderer"""
        return u', '.join(p.view('outofcontext') for p in entity.contractors())

    def build_cost_cell(self, entity):
        """``cost`` column cell renderer"""
        _ = self._cw._
        pinfo = entity.progress_info()
        totalcost = pinfo.get('estimatedcorrected', pinfo['estimated'])
        missing = pinfo.get('notestimatedcorrected', pinfo.get('notestimated', 0))
        costdescr = []
        if missing:
            # XXX: link to unestimated entities
            costdescr.append(_('%s not estimated') % missing)
        estimated = pinfo['estimated']
        if estimated and estimated != totalcost:
            costdescr.append(_('initial estimation %s') % estimated)
        if costdescr:
            return u'%s (%s)' % (totalcost, ', '.join(costdescr))
        return unicode(totalcost)

    def build_progress_cell(self, entity):
        """``progress`` column cell renderer"""
        return entity.view('progressbar')


class InContextProgressTableView(ProgressTableView):
    """this views redirects to ``progress_table_view`` but removes
    the ``project`` column
    """
    __regid__ = 'ic_progress_table_view'

    def call(self, columns=None):
        view = self._cw.vreg['views'].select('progress_table_view', self._cw,
                                         rset=self.cw_rset)
        columns = list(columns or view.columns)
        try:
            columns.remove('project')
        except ValueError:
            self.info('[ic_progress_table_view] could not remove project from columns')
        view.render(w=self.w, columns=columns)


class ProgressBarView(EntityView):
    """displays a progress bar"""
    __regid__ = 'progressbar'
    title = _('progress bar')
    __select__ = implements(IProgress)

    precision = 0.1
    red_threshold = 1.1
    orange_threshold = 1.05
    yellow_threshold = 1

    @classmethod
    def overrun(cls, entity):
        """overrun = done + todo - """
        if entity.done + entity.todo > entity.revised_cost:
            overrun = entity.done + entity.todo - entity.revised_cost
        else:
            overrun = 0
        if overrun < cls.precision:
            overrun = 0
        return overrun

    @classmethod
    def overrun_percentage(cls, entity):
        """pourcentage overrun = overrun / budget"""
        if entity.revised_cost == 0:
            return 0
        else:
            return cls.overrun(entity) * 100. / entity.revised_cost

    def cell_call(self, row, col):
        self._cw.add_css('cubicweb.iprogress.css')
        self._cw.add_js('cubicweb.iprogress.js')
        entity = self.cw_rset.get_entity(row, col)
        done = entity.done
        todo = entity.todo
        budget = entity.revised_cost
        if budget == 0:
            pourcent = 100
        else:
            pourcent = done*100./budget
        if pourcent > 100.1:
            color = 'red'
        elif todo+done > self.red_threshold*budget:
            color = 'red'
        elif todo+done > self.orange_threshold*budget:
            color = 'orange'
        elif todo+done > self.yellow_threshold*budget:
            color = 'yellow'
        else:
            color = 'green'
        if pourcent < 0:
            pourcent = 0

        if floor(done) == done or done>100:
            done_str = '%i' % done
        else:
            done_str = '%.1f' % done
        if floor(budget) == budget or budget>100:
            budget_str = '%i' % budget
        else:
            budget_str = '%.1f' % budget

        title = u'%s/%s = %i%%' % (done_str, budget_str, pourcent)
        short_title = title
        if self.overrun_percentage(entity):
            title += u' overrun +%sj (+%i%%)' % (self.overrun(entity),
                                                 self.overrun_percentage(entity))
            overrun = self.overrun(entity)
            if floor(overrun) == overrun or overrun>100:
                overrun_str = '%i' % overrun
            else:
                overrun_str = '%.1f' % overrun
            short_title += u' +%s' % overrun_str
        # write bars
        maxi = max(done+todo, budget)
        if maxi == 0:
            maxi = 1

        cid = make_uid('progress_bar')
        self._cw.html_headers.add_onload('draw_progressbar("canvas%s", %i, %i, %i, "%s");' %
                                         (cid,
                                          int(100.*done/maxi), int(100.*(done+todo)/maxi),
                                          int(100.*budget/maxi), color))
        self.w(u'%s<br/>'
               u'<canvas class="progressbar" id="canvas%s" width="100" height="10"></canvas>'
               % (xml_escape(short_title), cid))
