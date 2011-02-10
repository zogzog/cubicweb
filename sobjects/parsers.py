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
"""datafeed parser for xml generated by cubicweb"""

import urllib2
import StringIO
import os.path as osp
from cookielib import CookieJar
from datetime import datetime, timedelta

from lxml import etree

from logilab.common.date import todate, totime
from logilab.common.textutils import splitstrip, text_to_dict

from yams.constraints import BASE_CONVERTERS
from yams.schema import role_name as rn

from cubicweb import ValidationError, typed_eid
from cubicweb.server.sources import datafeed

def ensure_str_keys(dict):
    for key in dict:
        dict[str(key)] = dict.pop(key)

# see cubicweb.web.views.xmlrss.SERIALIZERS
DEFAULT_CONVERTERS = BASE_CONVERTERS.copy()
DEFAULT_CONVERTERS['String'] = unicode
DEFAULT_CONVERTERS['Password'] = lambda x: x.encode('utf8')
def convert_date(ustr):
    return todate(datetime.strptime(ustr, '%Y-%m-%d'))
DEFAULT_CONVERTERS['Date'] = convert_date
def convert_datetime(ustr):
    return datetime.strptime(ustr, '%Y-%m-%d %H:%M:%S')
DEFAULT_CONVERTERS['Datetime'] = convert_datetime
def convert_time(ustr):
    return totime(datetime.strptime(ustr, '%H:%M:%S'))
DEFAULT_CONVERTERS['Time'] = convert_time
def convert_interval(ustr):
    return time(seconds=int(ustr))
DEFAULT_CONVERTERS['Interval'] = convert_interval

# use a cookie enabled opener to use session cookie if any
_OPENER = urllib2.build_opener(urllib2.HTTPCookieProcessor(CookieJar()))

def extract_typed_attrs(eschema, stringdict, converters=DEFAULT_CONVERTERS):
    typeddict = {}
    for rschema in eschema.subject_relations():
        if rschema.final and rschema in stringdict:
            if rschema == 'eid':
                continue
            attrtype = eschema.destination(rschema)
            typeddict[rschema.type] = converters[attrtype](stringdict[rschema])
    return typeddict

def _entity_etree(parent):
    for node in list(parent):
        item = {'cwtype': unicode(node.tag),
                'cwuri': node.attrib['cwuri'],
                'eid': typed_eid(node.attrib['eid']),
                }
        rels = {}
        for child in node:
            role = child.get('role')
            if child.get('role'):
                # relation
                related = rels.setdefault(role, {}).setdefault(child.tag, [])
                related += [ritem for ritem, _ in _entity_etree(child)]
            else:
                # attribute
                item[child.tag] = unicode(child.text)
        yield item, rels

def build_search_rql(etype, attrs):
    restrictions = []
    for attr in attrs:
        restrictions.append('X %(attr)s %%(%(attr)s)s' % {'attr': attr})
    return 'Any X WHERE X is %s, %s' % (etype, ','.join(restrictions))

def rtype_role_rql(rtype, role):
    if role == 'object':
        return 'Y %s X WHERE X eid %%(x)s' % rtype
    else:
        return 'X %s Y WHERE X eid %%(x)s' % rtype


def _check_no_option(action, options, eid, _):
    if options:
        msg = _("'%s' action doesn't take any options") % action
        raise ValidationError(eid, {rn('options', 'subject'): msg})

def _check_linkattr_option(action, options, eid, _):
    if not 'linkattr' in options:
        msg = _("'%s' action require 'linkattr' option") % action
        raise ValidationError(eid, {rn('options', 'subject'): msg})


class CWEntityXMLParser(datafeed.DataFeedParser):
    """datafeed parser for the 'xml' entity view"""
    __regid__ = 'cw.entityxml'

    action_options = {
        'copy': _check_no_option,
        'link-or-create': _check_linkattr_option,
        'link': _check_linkattr_option,
        }

    def __init__(self, *args, **kwargs):
        super(CWEntityXMLParser, self).__init__(*args, **kwargs)
        self.action_methods = {
            'copy': self.related_copy,
            'link-or-create': self.related_link_or_create,
            'link': self.related_link,
            }

    # mapping handling #########################################################

    def add_schema_config(self, schemacfg, checkonly=False):
        """added CWSourceSchemaConfig, modify mapping accordingly"""
        _ = self._cw._
        try:
            rtype = schemacfg.schema.rtype.name
        except AttributeError:
            msg = _("entity and relation types can't be mapped, only attributes "
                    "or relations")
            raise ValidationError(schemacfg.eid, {rn('cw_for_schema', 'subject'): msg})
        if schemacfg.options:
            options = text_to_dict(schemacfg.options)
        else:
            options = {}
        try:
            role = options.pop('role')
            if role not in ('subject', 'object'):
                raise KeyError
        except KeyError:
            msg = _('"role=subject" or "role=object" must be specified in options')
            raise ValidationError(schemacfg.eid, {rn('options', 'subject'): msg})
        try:
            action = options.pop('action')
            self.action_options[action](action, options, schemacfg.eid, _)
        except KeyError:
            msg = _('"action" must be specified in options; allowed values are '
                    '%s') % ', '.join(self.action_methods)
            raise ValidationError(schemacfg.eid, {rn('options', 'subject'): msg})
        if not checkonly:
            if role == 'subject':
                etype = schemacfg.schema.stype.name
                ttype = schemacfg.schema.otype.name
            else:
                etype = schemacfg.schema.otype.name
                ttype = schemacfg.schema.stype.name
            etyperules = self.source.mapping.setdefault(etype, {})
            etyperules.setdefault((rtype, role, action), []).append(
                (ttype, options) )
            self.source.mapping_idx[schemacfg.eid] = (
                etype, rtype, role, action, ttype)

    def del_schema_config(self, schemacfg, checkonly=False):
        """deleted CWSourceSchemaConfig, modify mapping accordingly"""
        etype, rtype, role, action, ttype = self.source.mapping_idx[schemacfg.eid]
        rules = self.source.mapping[etype][(rtype, role, action)]
        rules = [x for x in rules if not x[0] == ttype]
        if not rules:
            del self.source.mapping[etype][(rtype, role, action)]

    # import handling ##########################################################

    def process(self, url, partialcommit=True):
        """IDataFeedParser main entry point"""
        # XXX suppression support according to source configuration. If set, get
        # all cwuri of entities from this source, and compare with newly
        # imported ones
        for item, rels in self.parse(url):
            self.process_item(item, rels)
            if partialcommit:
                # commit+set_pool instead of commit(reset_pool=False) to let
                # other a chance to get our pool
                self._cw.commit()
                self._cw.set_pool()

    def parse(self, url):
        if not url.startswith('http'):
            stream = StringIO.StringIO(url)
        else:
            for mappedurl in HOST_MAPPING:
                if url.startswith(mappedurl):
                    url = url.replace(mappedurl, HOST_MAPPING[mappedurl], 1)
                    break
            self.source.info('GET %s', url)
            stream = _OPENER.open(url)
        return _entity_etree(etree.parse(stream).getroot())

    def process_one(self, url):
        # XXX assert len(root.children) == 1
        for item, rels in self.parse(url):
            return self.process_item(item, rels)

    def process_item(self, item, rels):
        entity = self.extid2entity(str(item.pop('cwuri')),
                                   item.pop('cwtype'),
                                   item=item)
        if not (self.created_during_pull(entity)
                or self.updated_during_pull(entity)):
            self.notify_updated(entity)
            item.pop('eid')
            # XXX check modification date
            attrs = extract_typed_attrs(entity.e_schema, item)
            entity.set_attributes(**attrs)
        for (rtype, role, action), rules in self.source.mapping.get(entity.__regid__, {}).iteritems():
            try:
                rel = rels[role][rtype]
            except KeyError:
                self.source.error('relation %s-%s doesn\'t seem exported in %s xml',
                                  rtype, role, entity.__regid__)
                continue
            try:
                actionmethod = self.action_methods[action]
            except KeyError:
                raise Exception('Unknown action %s' % action)
            actionmethod(entity, rtype, role, rel, rules)
        return entity

    def before_entity_copy(self, entity, sourceparams):
        """IDataFeedParser callback"""
        attrs = extract_typed_attrs(entity.e_schema, sourceparams['item'])
        entity.cw_edited.update(attrs)

    def related_copy(self, entity, rtype, role, value, rules):
        """implementation of 'copy' action

        Takes no option.
        """
        assert not any(x[1] for x in rules), "'copy' action takes no option"
        ttypes = set([x[0] for x in rules])
        value = [item for item in value if item['cwtype'] in ttypes]
        eids = [] # local eids
        if not value:
            self._clear_relation(entity, rtype, role, ttypes)
            return
        for item in value:
            eids.append(self.process_one(self._complete_url(item)).eid)
        self._set_relation(entity, rtype, role, eids)

    def related_link(self, entity, rtype, role, value, rules):
        """implementation of 'link' action

        requires an options to control search of the linked entity.
        """
        for ttype, options in rules:
            assert 'linkattr' in options, (
                "'link-or-create' action require a list of attributes used to "
                "search if the entity already exists")
            self._related_link(entity, rtype, role, ttype, value, [options['linkattr']],
                               self._log_not_found)

    def related_link_or_create(self, entity, rtype, role, value, rules):
        """implementation of 'link-or-create' action

        requires an options to control search of the linked entity.
        """
        for ttype, options in rules:
            assert 'linkattr' in options, (
                "'link-or-create' action require a list of attributes used to "
                "search if the entity already exists")
            self._related_link(entity, rtype, role, ttype, value, [options['linkattr']],
                               self._create_not_found)

    def _log_not_found(self, entity, rtype, role, ritem, searchvalues):
        self.source.error('can find %s entity with attributes %s',
                          ritem['cwtype'], searchvalues)

    def _create_not_found(self, entity, rtype, role, ritem, searchvalues):
        ensure_str_keys(searchvalues) # XXX necessary with python < 2.6
        return self._cw.create_entity(ritem['cwtype'], **searchvalues).eid

    def _related_link(self, entity, rtype, role, ttype, value, searchattrs,
                      notfound_callback):
        eids = [] # local eids
        for item in value:
            if item['cwtype'] != ttype:
                continue
            if not all(attr in item for attr in searchattrs):
                # need to fetch related entity's xml
                ritems = list(self.parse(self._complete_url(item, False)))
                assert len(ritems) == 1, 'unexpected xml'
                ritem = ritems[0][0] # list of 2-uples
                assert all(attr in ritem for attr in searchattrs), \
                       'missing attribute, got %s expected keys %s' % (item, searchattrs)
            else:
                ritem = item
            kwargs = dict((attr, ritem[attr]) for attr in searchattrs)
            rql = build_search_rql(item['cwtype'], kwargs)
            rset = self._cw.execute(rql, kwargs)
            if rset:
                assert len(rset) == 1
                eids.append(rset[0][0])
            else:
                eid = notfound_callback(entity, rtype, role, ritem, kwargs)
                if eid is not None:
                    eids.append(eid)
        if not eids:
            self._clear_relation(entity, rtype, role, (ttype,))
        else:
            self._set_relation(entity, rtype, role, eids)

    def _complete_url(self, item, add_relations=True):
        itemurl = item['cwuri'] + '?vid=xml'
        for rtype, role, _ in self.source.mapping.get(item['cwtype'], ()):
            itemurl += '&relation=%s_%s' % (rtype, role)
        return itemurl

    def _clear_relation(self, entity, rtype, role, ttypes):
        if entity.eid not in self.stats['created']:
            if len(ttypes) > 1:
                typerestr = ', Y is IN(%s)' % ','.join(ttypes)
            else:
                typerestr = ', Y is %s' % ','.join(ttypes)
            self._cw.execute('DELETE ' + rtype_role_rql(rtype, role) + typerestr,
                             {'x': entity.eid})

    def _set_relation(self, entity, rtype, role, eids):
        eidstr = ','.join(str(eid) for eid in eids)
        rql = rtype_role_rql(rtype, role)
        self._cw.execute('DELETE %s, NOT Y eid IN (%s)' % (rql, eidstr),
                         {'x': entity.eid})
        if role == 'object':
            rql = 'SET %s, Y eid IN (%s), NOT Y %s X' % (rql, eidstr, rtype)
        else:
            rql = 'SET %s, Y eid IN (%s), NOT X %s Y' % (rql, eidstr, rtype)
        self._cw.execute(rql, {'x': entity.eid})

def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__)
    global HOST_MAPPING
    HOST_MAPPING = {}
    if vreg.config.apphome:
        host_mapping_file = osp.join(vreg.config.apphome, 'hostmapping.py')
        if osp.exists(host_mapping_file):
            HOST_MAPPING = eval(file(host_mapping_file).read())
            vreg.info('using host mapping %s from %s', HOST_MAPPING, host_mapping_file)
