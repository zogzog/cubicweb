# copyright 2010-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Specific views for data sources and related entities (eg CWSource,
CWSourceHostConfig, CWSourceSchemaConfig).
"""

__docformat__ = "restructuredtext en"
_ = unicode

import logging
from itertools import repeat
from logilab.mtconverter import xml_escape
from logilab.common.decorators import cachedproperty

from cubicweb import Unauthorized, tags
from cubicweb.utils import make_uid
from cubicweb.predicates import (is_instance, score_entity, has_related_entities,
                                match_user_groups, match_kwargs, match_view)
from cubicweb.view import EntityView, StartupView
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, display_name
from cubicweb.web import formwidgets as wdgs, facet
from cubicweb.web.views import add_etype_button
from cubicweb.web.views import (uicfg, tabs, actions, ibreadcrumbs, navigation,
                                tableview, pyviews)


_abaa = uicfg.actionbox_appearsin_addmenu
# there are explicit 'add' buttons for those
_abaa.tag_object_of(('CWSourceSchemaConfig', 'cw_schema', '*'), False)
_abaa.tag_object_of(('CWSourceSchemaConfig', 'cw_for_source', '*'), False)
_abaa.tag_object_of(('CWSourceSchemaConfig', 'cw_host_config_of', '*'), False)
_abaa.tag_object_of(('CWDataImport', 'cw_import_of', '*'), False)

_afs = uicfg.autoform_section
_afs.tag_attribute(('CWSource', 'latest_retrieval'), 'main', 'hidden')
_afs.tag_attribute(('CWSource', 'in_synchronization'), 'main', 'hidden')
_afs.tag_object_of(('*', 'cw_for_source', 'CWSource'), 'main', 'hidden')

_affk = uicfg.autoform_field_kwargs
_affk.tag_attribute(('CWSource', 'parser'), {'widget': wdgs.TextInput})

# source primary views #########################################################

_pvs = uicfg.primaryview_section
_pvs.tag_attribute(('CWSource', 'name'), 'hidden')
_pvs.tag_object_of(('*', 'cw_for_source', 'CWSource'), 'hidden')
_pvs.tag_object_of(('*', 'cw_host_config_of', 'CWSource'), 'hidden')

_pvdc = uicfg.primaryview_display_ctrl
_pvdc.tag_attribute(('CWSource', 'type'), {'vid': 'attribute'})# disable reledit

_rc = uicfg.reledit_ctrl
_rc.tag_attribute(('CWSource', 'config'), {'rvid': 'verbatimattr'})
_rc.tag_attribute(('CWSourceHostConfig', 'config'), {'rvid': 'verbatimattr'})
_rc.tag_attribute(('CWSourceSchemaConfig', 'options'), {'rvid': 'verbatimattr'})


class CWSourcePrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWSource')
    tabs = [_('cwsource-main'), _('cwsource-mapping'), _('cwsource-imports')]
    default_tab = 'cwsource-main'


class CWSourceMainTab(tabs.PrimaryTab):
    __regid__ = 'cwsource-main'
    __select__ = is_instance('CWSource')

    def render_entity_attributes(self, entity):
        super(CWSourceMainTab, self).render_entity_attributes(entity)
        self.w(add_etype_button(self._cw, 'CWSourceHostConfig',
                                __linkto='cw_host_config_of:%s:subject' % entity.eid,
                                __redirectpath=entity.rest_path()))
        try:
            hostconfig = self._cw.execute(
                'Any X, XC, XH WHERE X cw_host_config_of S, S eid %(s)s, '
                'X config XC, X match_host XH', {'s': entity.eid})
        except Unauthorized:
            pass
        else:
            if hostconfig:
                self.w(u'<h3>%s</h3>' % self._cw._('CWSourceHostConfig_plural'))
                self._cw.view('table', hostconfig, w=self.w,
                              displaycols=range(2),
                              cellvids={1: 'editable-final'})


MAPPED_SOURCE_TYPES = set( ('datafeed',) )

class CWSourceMappingTab(EntityView):
    __regid__ = 'cwsource-mapping'
    __select__ = (is_instance('CWSource')
                  & match_user_groups('managers')
                  & score_entity(lambda x:x.type in MAPPED_SOURCE_TYPES))

    def entity_call(self, entity):
        _ = self._cw._
        self.w('<h3>%s</h3>' % _('Entity and relation supported by this source'))
        self.w(add_etype_button(self._cw, 'CWSourceSchemaConfig',
                                __linkto='cw_for_source:%s:subject' % entity.eid))
        self.w(u'<div class="clear"></div>')
        rset = self._cw.execute(
            'Any X, SCH, XO ORDERBY ET WHERE X options XO, X cw_for_source S, S eid %(s)s, '
            'X cw_schema SCH, SCH is ET', {'s': entity.eid})
        self.wview('table', rset, 'noresult')
        checker = MappingChecker(entity)
        checker.check()
        if (checker.errors or checker.warnings or checker.infos):
            self.w('<h2>%s</h2>' % _('Detected problems'))
            errors = zip(repeat(_('error')), checker.errors)
            warnings = zip(repeat(_('warning')), checker.warnings)
            infos = zip(repeat(_('warning')), checker.infos)
            self.wview('pyvaltable', pyvalue=errors + warnings + infos)


class MappingChecker(object):
    def __init__(self, cwsource):
        self.cwsource = cwsource
        self.errors = []
        self.warnings = []
        self.infos = []
        self.schema = cwsource._cw.vreg.schema

    def init(self):
        # supported entity types
        self.sentities = set()
        # supported relations
        self.srelations = {}
        # avoid duplicated messages
        self.seen = set()
        # first get mapping as dict/sets
        for schemacfg in self.cwsource.reverse_cw_for_source:
            self.init_schemacfg(schemacfg)

    def init_schemacfg(self, schemacfg):
        cwerschema = schemacfg.schema
        if cwerschema.__regid__ == 'CWEType':
            self.sentities.add(cwerschema.name)
        elif cwerschema.__regid__ == 'CWRType':
            assert not cwerschema.name in self.srelations
            self.srelations[cwerschema.name] = None
        else: # CWAttribute/CWRelation
            self.srelations.setdefault(cwerschema.rtype.name, []).append(
                (cwerschema.stype.name, cwerschema.otype.name) )
            self.sentities.add(cwerschema.stype.name)
            self.sentities.add(cwerschema.otype.name)

    def check(self):
        self.init()
        error = self.errors.append
        warning = self.warnings.append
        info = self.infos.append
        for etype in self.sentities:
            eschema = self.schema[etype]
            for rschema, ttypes, role in eschema.relation_definitions():
                if rschema in META_RTYPES:
                    continue
                ttypes = [ttype for ttype in ttypes if ttype in self.sentities]
                if not rschema in self.srelations:
                    for ttype in ttypes:
                        rdef = rschema.role_rdef(etype, ttype, role)
                        self.seen.add(rdef)
                        if rdef.role_cardinality(role) in '1+':
                            error(_('relation %(type)s with %(etype)s as %(role)s '
                                    'and target type %(target)s is mandatory but '
                                    'not supported') %
                                  {'rtype': rschema, 'etype': etype, 'role': role,
                                   'target': ttype})
                        elif ttype in self.sentities:
                            warning(_('%s could be supported') % rdef)
                elif not ttypes:
                    warning(_('relation %(rtype)s with %(etype)s as %(role)s is '
                              'supported but no target type supported') %
                            {'rtype': rschema, 'role': role, 'etype': etype})
        for rtype, rdefs in self.srelations.iteritems():
            if rdefs is None:
                rschema = self.schema[rtype]
                for subj, obj in rschema.rdefs:
                    if subj in self.sentities and obj in self.sentities:
                        break
                else:
                    error(_('relation %s is supported but none of its definitions '
                            'matches supported entities') % rtype)
        self.custom_check()

    def custom_check(self):
        pass



class CWSourceImportsTab(EntityView):
    __regid__ = 'cwsource-imports'
    __select__ = (is_instance('CWSource')
                  & has_related_entities('cw_import_of', 'object'))

    def entity_call(self, entity):
        rset = self._cw.execute('Any X, XST, XET, XS ORDERBY XST DESC WHERE '
                                'X cw_import_of S, S eid %(s)s, X status XS, '
                                'X start_timestamp XST, X end_timestamp XET',
                                {'s': entity.eid})
        self._cw.view('cw.imports-table', rset, w=self.w)


class CWImportsTable(tableview.EntityTableView):
    __regid__ = 'cw.imports-table'
    __select__ = is_instance('CWDataImport')
    columns = ['import', 'start_timestamp', 'end_timestamp']
    column_renderers = {'import': tableview.MainEntityColRenderer()}
    layout_args = {'display_filter': 'top'}




# sources management view ######################################################

class ManageSourcesAction(actions.ManagersAction):
    __regid__ = 'cwsource'
    title = _('data sources')
    category = 'manage'


class CWSourcesManagementView(StartupView):
    __regid__ = 'cw.sources-management'
    rql = ('Any S,ST,SP,SD,SN ORDERBY SN WHERE S is CWSource, S name SN, S type ST, '
           'S latest_retrieval SD, S parser SP')
    title = _('data sources management')

    def call(self, **kwargs):
        self.w('<h1>%s</h1>' % self._cw._(self.title))
        self.w(add_etype_button(self._cw, 'CWSource'))
        self.w(u'<div class="clear"></div>')
        self.wview('cw.sources-table', self._cw.execute(self.rql))


class CWSourcesTable(tableview.EntityTableView):
    __regid__ = 'cw.sources-table'
    __select__ = is_instance('CWSource')
    columns = ['source', 'type', 'parser', 'latest_retrieval', 'latest_import']

    class LatestImportColRenderer(tableview.EntityTableColRenderer):
        def render_cell(self, w, rownum):
            entity = self.entity(rownum)
            rset = self._cw.execute('Any X,XS,XST ORDERBY XST DESC LIMIT 1 WHERE '
                                    'X cw_import_of S, S eid %(s)s, X status XS, '
                                    'X start_timestamp XST', {'s': entity.eid})
            if rset:
                self._cw.view('incontext', rset, row=0, w=w)
            else:
                w(self.empty_cell_content)

    column_renderers = {
        'source': tableview.MainEntityColRenderer(),
        'latest_import': LatestImportColRenderer(header=_('latest import'),
                                                 sortable=False)
        }

# datafeed source import #######################################################

REVERSE_SEVERITIES = {
    logging.DEBUG :   _('DEBUG'),
    logging.INFO :    _('INFO'),
    logging.WARNING : _('WARNING'),
    logging.ERROR :   _('ERROR'),
    logging.FATAL :   _('FATAL')
}


def log_to_table(req, rawdata):
    data = []
    for msg_idx, msg in enumerate(rawdata.split('<br/>')):
        record = msg.strip()
        if not record:
            continue
        try:
            severity, url, line, msg = record.split('\t', 3)
        except ValueError:
            req.warning('badly formated log %s' % record)
            url = line = u''
            severity = logging.DEBUG
            msg = record
        data.append( (severity, url, line, msg) )
    return data


class LogTableLayout(tableview.TableLayout):
    __select__ = match_view('cw.log.table')
    needs_js = tableview.TableLayout.needs_js + ('cubicweb.log.js',)
    needs_css = tableview.TableLayout.needs_css + ('cubicweb.log.css',)
    columns_css = {
        0: 'logSeverity',
        1: 'logPath',
        2: 'logLine',
        3: 'logMsg',
        }

    def render_table(self, w, actions, paginate):
        default_level = self.view.cw_extra_kwargs['default_level']
        if default_level != 'Debug':
            self._cw.add_onload('$("select.logFilter").val("%s").change();'
                           % self._cw.form.get('logLevel', default_level))
        w(u'\n<form action="#"><fieldset>')
        w(u'<label>%s</label>' % self._cw._(u'Message threshold'))
        w(u'<select class="log_filter" onchange="filterLog(\'%s\', this.options[this.selectedIndex].value)">'
          % self.view.domid)
        for level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'FATAL'):
            w('<option value="%s">%s</option>' % (level.capitalize(),
                                                  self._cw._(level)))
        w(u'</select>')
        w(u'</fieldset></form>')
        super(LogTableLayout, self).render_table(w, actions, paginate)

    def table_attributes(self):
        attrs = super(LogTableLayout, self).table_attributes()
        attrs['id'] = 'table'+self.view.domid
        return attrs

    def row_attributes(self, rownum):
        attrs = super(LogTableLayout, self).row_attributes(rownum)
        attrs['id'] = 'log_msg_%i' % rownum
        severityname = REVERSE_SEVERITIES[int(self.view.pyvalue[rownum][0])]
        attrs['class'] = 'log%s' % severityname.capitalize()
        return attrs

    def cell_attributes(self, rownum, colnum, colid):
        attrs = super(LogTableLayout, self).cell_attributes(rownum, colnum, colid)
        attrs['class'] = self.columns_css[colnum]
        return attrs


class LogTable(pyviews.PyValTableView):
    __regid__ = 'cw.log.table'
    headers = [_('severity'), _('url'), _('line'), _('message')]

    @cachedproperty
    def domid(self):
        return make_uid('logTable')

    class SeverityRenderer(pyviews.PyValTableColRenderer):
        def render_cell(self, w, rownum):
            severity = self.data[rownum][0]
            w(u'<a class="internallink" href="javascript:;" title="%(title)s" '
              u'''onclick="document.location.hash='%(msg_id)s';">&#182;</a>'''
              u'&#160;%(severity)s' % {
                'severity': self._cw._(REVERSE_SEVERITIES[int(severity)]),
                'title': self._cw._('permalink to this message'),
                'msg_id': 'log_msg_%i' % rownum,
            })
        def sortvalue(self, rownum):
            return int(self.data[rownum][0])

    class URLRenderer(pyviews.PyValTableColRenderer):
        def render_cell(self, w, rownum):
            url = self.data[rownum][1]
            if url and url.startswith('http'):
                url = tags.a(url, href=url)
            w(url or u'&#160;')

    class LineRenderer(pyviews.PyValTableColRenderer):
        def render_cell(self, w, rownum):
            line = self.data[rownum][2]
            w(line or u'&#160;')

    class MessageRenderer(pyviews.PyValTableColRenderer):
        snip_over = 7
        def render_cell(self, w, rownum):
            msg = self.data[rownum][3]
            lines = msg.splitlines()
            if len(lines) <= self.snip_over:
                w(u'<pre class="rawtext">%s</pre>' % msg)
            else:
                # The make_uid argument has no specific meaning here.
                div_snip_id = make_uid(u'log_snip_')
                div_full_id = make_uid(u'log_full_')
                divs_id = (div_snip_id, div_full_id)
                snip = u'\n'.join((lines[0], lines[1],
                                   u'  ...',
                                   u'    %i more lines [double click to expand]' % (len(lines)-4),
                                   u'  ...',
                                   lines[-2], lines[-1]))
                divs = (
                        (div_snip_id, snip, u'expand', "class='collapsed'"),
                        (div_full_id, msg,  u'collapse', "class='hidden'")
                )
                for div_id, content, button, h_class in divs:
                    text = self._cw._(button)
                    js = u"toggleVisibility('%s'); toggleVisibility('%s');" % divs_id
                    w(u'<div id="%s" %s>' % (div_id, h_class))
                    w(u'<pre class="raw_test" ondblclick="javascript: %s" '
                      u'title="%s" style="display: block;">' % (js, text))
                    w(content)
                    w(u'</pre>')
                    w(u'</div>')

    column_renderers = {0: SeverityRenderer(),
                        1: URLRenderer(sortable=False),
                        2: LineRenderer(sortable=False),
                        3: MessageRenderer(sortable=False),
                        }


class DataFeedSourceDataImport(EntityView):
    __select__ = EntityView.__select__ & match_kwargs('rtype')
    __regid__ = 'cw.formated_log'

    def cell_call(self, row, col, rtype, loglevel='Info', **kwargs):
        if 'dispctrl' in self.cw_extra_kwargs:
            loglevel = self.cw_extra_kwargs['dispctrl'].get('loglevel', loglevel)
        entity = self.cw_rset.get_entity(row, col)
        value = getattr(entity, rtype)
        if value:
            self._cw.view('cw.log.table', pyvalue=log_to_table(self._cw, value),
                          default_level=loglevel, w=self.w)
        else:
            self.w(self._cw._('no log to display'))


_pvs.tag_attribute(('CWDataImport', 'log'), 'relations')
_pvdc.tag_attribute(('CWDataImport', 'log'), {'vid': 'cw.formated_log'})
_pvs.tag_subject_of(('CWDataImport', 'cw_import_of', '*'), 'hidden') # in breadcrumbs
_pvs.tag_object_of(('*', 'cw_import_of', 'CWSource'), 'hidden') # in dedicated tab


class CWDataImportIPrevNextAdapter(navigation.IPrevNextAdapter):
    __select__ = is_instance('CWDataImport')

    def next_entity(self):
        if self.entity.start_timestamp is not None:
            # add NOT X eid %(e)s because > may not be enough
            rset = self._cw.execute(
                'Any X,XSTS ORDERBY 2 LIMIT 1 WHERE X is CWDataImport, '
                'X cw_import_of S, S eid %(s)s, NOT X eid %(e)s, '
                'X start_timestamp XSTS, X start_timestamp > %(sts)s',
                {'sts': self.entity.start_timestamp,
                 'e': self.entity.eid,
                 's': self.entity.cwsource.eid})
            if rset:
                return rset.get_entity(0, 0)

    def previous_entity(self):
        if self.entity.start_timestamp is not None:
            # add NOT X eid %(e)s because < may not be enough
            rset = self._cw.execute(
                'Any X,XSTS ORDERBY 2 DESC LIMIT 1 WHERE X is CWDataImport, '
                'X cw_import_of S, S eid %(s)s, NOT X eid %(e)s, '
                'X start_timestamp XSTS, X start_timestamp < %(sts)s',
                {'sts': self.entity.start_timestamp,
                 'e': self.entity.eid,
                 's': self.entity.cwsource.eid})
            if rset:
                return rset.get_entity(0, 0)

class CWDataImportStatusFacet(facet.AttributeFacet):
    __regid__ = 'datafeed.dataimport.status'
    __select__ = is_instance('CWDataImport')
    rtype = 'status'


# breadcrumbs configuration ####################################################

class CWsourceConfigIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('CWSourceHostConfig', 'CWSourceSchemaConfig')
    def parent_entity(self):
        return self.entity.cwsource

class CWDataImportIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('CWDataImport')
    def parent_entity(self):
        return self.entity.cw_import_of[0]
