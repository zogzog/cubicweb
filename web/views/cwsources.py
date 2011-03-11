# copyright 2010-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from itertools import repeat, chain

from cubicweb.selectors import is_instance, score_entity, match_user_groups
from cubicweb.view import EntityView, StartupView
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, display_name
from cubicweb.web import uicfg
from cubicweb.web.views import tabs, actions


_abaa = uicfg.actionbox_appearsin_addmenu
_abaa.tag_object_of(('CWSourceSchemaConfig', 'cw_schema', '*'), False)
_abaa.tag_object_of(('CWSourceSchemaConfig', 'cw_for_source', '*'), False)

# source primary views #########################################################

_pvs = uicfg.primaryview_section
_pvs.tag_object_of(('*', 'cw_for_source', 'CWSource'), 'hidden')


class CWSourcePrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWSource')
    tabs = [_('cwsource-main'), _('cwsource-mapping')]
    default_tab = 'cwsource-main'


class CWSourceMainTab(tabs.PrimaryTab):
    __regid__ = 'cwsource-main'
    __select__ = tabs.PrimaryTab.__select__ & is_instance('CWSource')


MAPPED_SOURCE_TYPES = set( ('pyrorql', 'datafeed') )

class CWSourceMappingTab(EntityView):
    __regid__ = 'cwsource-mapping'
    __select__ = (tabs.PrimaryTab.__select__ & is_instance('CWSource')
                  & match_user_groups('managers')
                  & score_entity(lambda x:x.type in MAPPED_SOURCE_TYPES))

    def entity_call(self, entity):
        _ = self._cw._
        self.w('<h3>%s</h3>' % _('Entity and relation supported by this source'))
        eschema = self._cw.vreg.schema.eschema('CWSourceSchemaConfig')
        if eschema.has_perm(self._cw, 'add'):
            self.w(u'<a href="%s" class="addButton right">%s</a>' % (
                self._cw.build_url('add/%s' % eschema),
                self._cw._('add a CWSourceSchemaConfig')))
            self.w(u'<div class="clear"></div>')
        rset = self._cw.execute(
            'Any X, SCH, XO ORDERBY ET WHERE X options XO, X cw_for_source S, S eid %(s)s, '
            'X cw_schema SCH, SCH is ET', {'s': entity.eid})
        self.wview('table', rset, 'noresult')
        # self.w('<h3>%s</h3>' % _('Relations that should not be crossed'))
        # self.w('<p>%s</p>' % _(
        #     'By default, when a relation is not supported by a source, it is '
        #     'supposed that a local relation may point to an entity from the '
        #     'external source. Relations listed here won\'t have this '
        #     '"crossing" behaviour.'))
        # self.wview('list', entity.related('cw_dont_cross'), 'noresult')
        # self.w('<h3>%s</h3>' % _('Relations that can be crossed'))
        # self.w('<p>%s</p>' % _(
        #     'By default, when a relation is supported by a source, it is '
        #     'supposed that a local relation can\'t point to an entity from the '
        #     'external source. Relations listed here may have this '
        #     '"crossing" behaviour anyway.'))
        # self.wview('list', entity.related('cw_may_cross'), 'noresult')
        checker = MAPPING_CHECKERS.get(entity.type, MappingChecker)(entity)
        checker.check()
        if (checker.errors or checker.warnings or checker.infos):
                self.w('<h2>%s</h2>' % _('Detected problems'))
                errors = zip(repeat(_('error')), checker.errors)
                warnings = zip(repeat(_('warning')), checker.warnings)
                infos = zip(repeat(_('warning')), checker.infos)
                self.wview('pyvaltable', pyvalue=chain(errors, warnings, infos))


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
        for rtype in self.srelations:
            rschema = self.schema[rtype]
            for subj, obj in rschema.rdefs:
                if subj in self.sentities and obj in self.sentities:
                    break
            else:
                error(_('relation %s is supported but none if its definitions '
                        'matches supported entities') % rtype)
        self.custom_check()

    def custom_check(self):
        pass


class PyroRQLMappingChecker(MappingChecker):
    """pyrorql source mapping checker"""

    def init(self):
        self.dontcross = set()
        self.maycross = set()
        super(PyroRQLMappingChecker, self).init()

    def init_schemacfg(self, schemacfg):
        options = schemacfg.options or ()
        if 'dontcross' in options:
            self.dontcross.add(schemacfg.schema.name)
        else:
            super(PyroRQLMappingChecker, self).init_schemacfg(schemacfg)
            if 'maycross' in options:
                self.maycross.add(schemacfg.schema.name)

    def custom_check(self):
        error = self.errors.append
        info = self.infos.append
        for etype in self.sentities:
            eschema = self.schema[etype]
            for rschema, ttypes, role in eschema.relation_definitions():
                if rschema in META_RTYPES:
                    continue
                if not rschema in self.srelations:
                    if rschema not in self.dontcross:
                        if role == 'subject' and rschema.inlined:
                            error(_('inlined relation %(rtype)s of %(etype)s '
                                    'should be supported') %
                                  {'rtype': rschema, 'etype': etype})
                        elif (rschema not in self.seen and rschema not in self.maycross):
                            info(_('you may want to specify something for %s') %
                                 rschema)
                            self.seen.add(rschema)
                elif rschema in self.maycross and rschema.inlined:
                    error(_('you should un-inline relation %s which is '
                            'supported and may be crossed ') % rschema)

MAPPING_CHECKERS = {
    'pyrorql': PyroRQLMappingChecker,
    }

# sources management view ######################################################

class ManageSourcesAction(actions.ManagersAction):
    __regid__ = 'cwsource'
    title = _('data sources')
    category = 'manage'

class CWSourceManagementView(StartupView):
    __regid__ = 'cw.source-management'
    rql = ('Any S, ST, SN ORDERBY SN WHERE S is CWSource, S name SN, S type ST')
    title = _('data sources management')

    def call(self, **kwargs):
        self.w('<h1>%s</h1>' % self._cw._(self.title))
        eschema = self._cw.vreg.schema.eschema('CWSource')
        if eschema.has_perm(self._cw, 'add'):
            self.w(u'<a href="%s" class="addButton right">%s</a>' % (
                self._cw.build_url('add/%s' % eschema),
                self._cw._('add a CWSource')))
            self.w(u'<div class="clear"></div>')
        self.wview('table', self._cw.execute(self.rql), displaycols=range(2))
