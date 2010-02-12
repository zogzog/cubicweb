"""Specific views for entities implementing IProgress

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape

from cubicweb.selectors import implements
from cubicweb.interfaces import IProgress, IMileStone
from cubicweb.schema import display_name
from cubicweb.view import EntityView
from cubicweb.web.htmlwidgets import ProgressBarWidget


class ProgressTableView(EntityView):
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

    # default columns of the table
    columns = (_('project'), _('milestone'), _('state'), _('eta_date'),
               _('cost'), _('progress'), _('todo_by'))


    def call(self, columns=None):
        """displays all versions in a table"""
        self._cw.add_css('cubicweb.iprogress.css')
        _ = self._cw._
        self.columns = columns or self.columns
        ecls = self._cw.vreg['etypes'].etype_class(self.cw_rset.description[0][0])
        self.w(u'<table class="progress">')
        self.table_header(ecls)
        self.w(u'<tbody>')
        for row in xrange(self.cw_rset.rowcount):
            self.cell_call(row=row, col=0)
        self.w(u'</tbody>')
        self.w(u'</table>')

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

    def table_header(self, ecls):
        """builds the table's header"""
        self.w(u'<thead><tr>')
        _ = self._cw._
        for column in self.columns:
            meth = getattr(self, 'header_for_%s' % column, None)
            if meth:
                colname = meth(ecls)
            else:
                colname = _(column)
            self.w(u'<th>%s</th>' % xml_escape(colname))
        self.w(u'</tr></thead>\n')


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

    def cell_call(self, row, col):
        self._cw.add_css('cubicweb.iprogress.css')
        self._cw.add_js('cubicweb.iprogress.js')
        entity = self.cw_rset.get_entity(row, col)
        widget = ProgressBarWidget(entity.done, entity.todo,
                                   entity.revised_cost)
        self.w(widget.render())

