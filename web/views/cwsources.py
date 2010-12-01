# copyright 2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Specific views for data sources"""

__docformat__ = "restructuredtext en"
_ = unicode

from itertools import repeat, chain

from cubicweb.selectors import is_instance, score_entity
from cubicweb.view import EntityView
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, display_name
from cubicweb.web import uicfg
from cubicweb.web.views import tabs

for rtype in ('cw_support', 'cw_may_cross', 'cw_dont_cross'):
    uicfg.primaryview_section.tag_subject_of(('CWSource', rtype, '*'),
                                             'hidden')

class CWSourcePrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWSource')
    tabs = [_('cwsource-main'), _('cwsource-mapping')]
    default_tab = 'cwsource-main'


class CWSourceMainTab(tabs.PrimaryTab):
    __regid__ = 'cwsource-main'
    __select__ = tabs.PrimaryTab.__select__ & is_instance('CWSource')


class CWSourceMappingTab(EntityView):
    __regid__ = 'cwsource-mapping'
    __select__ = (tabs.PrimaryTab.__select__ & is_instance('CWSource')
                  & score_entity(lambda x:x.type == 'pyrorql'))

    def entity_call(self, entity):
        _ = self._cw._
        self.w('<h3>%s</h3>' % _('Entity and relation types supported by this source'))
        self.wview('list', entity.related('cw_support'), 'noresult')
        self.w('<h3>%s</h3>' % _('Relations that should not be crossed'))
        self.w('<p>%s</p>' % _(
            'By default, when a relation is not supported by a source, it is '
            'supposed that a local relation may point to an entity from the '
            'external source. Relations listed here won\'t have this '
            '"crossing" behaviour.'))
        self.wview('list', entity.related('cw_dont_cross'), 'noresult')
        self.w('<h3>%s</h3>' % _('Relations that can be crossed'))
        self.w('<p>%s</p>' % _(
            'By default, when a relation is supported by a source, it is '
            'supposed that a local relation can\'t point to an entity from the '
            'external source. Relations listed here may have this '
            '"crossing" behaviour anyway.'))
        self.wview('list', entity.related('cw_may_cross'), 'noresult')
        if self._cw.user.is_in_group('managers'):
            errors, warnings, infos = check_mapping(entity)
            if (errors or warnings or infos):
                self.w('<h2>%s</h2>' % _('Detected problems'))
                errors = zip(repeat(_('error'), errors))
                warnings = zip(repeat(_('warning'), warnings))
                infos = zip(repeat(_('warning'), infos))
                self.wview('pyvaltable', pyvalue=chain(errors, warnings, infos))

def check_mapping(cwsource):
    req = cwsource._cw
    _ = req._
    errors = []
    error = errors.append
    warnings = []
    warning = warnings.append
    infos = []
    info = infos.append
    srelations = set()
    sentities = set()
    maycross = set()
    dontcross = set()
    # first check supported stuff / meta & virtual types and get mapping as sets
    for cwertype in cwsource.cw_support:
        if cwertype.name in META_RTYPES:
            error(_('meta relation %s can not be supported') % cwertype.name)
        else:
            if cwertype.__regid__ == 'CWEType':
                sentities.add(cwertype.name)
            else:
                srelations.add(cwertype.name)
    for attr, attrset in (('cw_may_cross', maycross),
                          ('cw_dont_cross', dontcross)):
        for cwrtype in getattr(cwsource, attr):
            if cwrtype.name in VIRTUAL_RTYPES:
                error(_('virtual relation %(rtype)s can not be referenced by '
                        'the "%(srel)s" relation') %
                      {'rtype': cwrtype.name,
                       'srel': display_name(req, attr, context='CWSource')})
            else:
                attrset.add(cwrtype.name)
    # check relation in dont_cross_relations aren't in support_relations
    for rtype in dontcross & maycross:
        info(_('relation %(rtype)s is supported but in %(dontcross)s') %
             {'rtype': rtype,
              'dontcross': display_name(req, 'cw_dont_cross',
                                        context='CWSource')})
    # check relation in cross_relations are in support_relations
    for rtype in maycross & srelations:
        info(_('relation %(rtype)s isn\'t supported but in %(maycross)s') %
             {'rtype': rtype,
              'dontcross': display_name(req, 'cw_may_cross',
                                        context='CWSource')})
    # now check for more handy things
    seen = set()
    for etype in sentities:
        eschema = req.vreg.schema[etype]
        for rschema, ttypes, role in eschema.relation_definitions():
            if rschema in META_RTYPES:
                continue
            ttypes = [ttype for ttype in ttypes if ttype in sentities]
            if not rschema in srelations:
                somethingprinted = False
                for ttype in ttypes:
                    rdef = rschema.role_rdef(etype, ttype, role)
                    seen.add(rdef)
                    if rdef.role_cardinality(role) in '1+':
                        error(_('relation %(type)s with %(etype)s as %(role)s '
                                'and target type %(target)s is mandatory but '
                                'not supported') %
                              {'rtype': rschema, 'etype': etype, 'role': role,
                               'target': ttype})
                        somethingprinted = True
                    elif ttype in sentities:
                        if rdef not in seen:
                            warning(_('%s could be supported') % rdef)
                        somethingprinted = True
                if rschema not in dontcross:
                    if role == 'subject' and rschema.inlined:
                        error(_('inlined relation %(rtype)s of %(etype)s '
                                'should be supported') %
                              {'rtype': rschema, 'etype': etype})
                    elif (not somethingprinted and rschema not in seen
                          and rschema not in maycross):
                        info(_('you may want to specify something for %s') %
                             rschema)
                        seen.add(rschema)
            else:
                if not ttypes:
                    warning(_('relation %(rtype)s with %(etype)s as %(role)s '
                              'is supported but no target type supported') %
                            {'rtype': rschema, 'role': role, 'etype': etype})
                if rschema in maycross and rschema.inlined:
                    error(_('you should un-inline relation %s which is '
                            'supported and may be crossed ') % rschema)
    for rschema in srelations:
        for subj, obj in rschema.rdefs:
            if subj in sentities and obj in sentities:
                break
        else:
            error(_('relation %s is supported but none if its definitions '
                    'matches supported entities') % rschema)
    return errors, warnings, infos
