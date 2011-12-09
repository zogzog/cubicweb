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
"""datafeed sources: copy data from an external data stream into the system
database
"""
from __future__ import with_statement

import urllib2
import StringIO
from datetime import datetime, timedelta
from base64 import b64decode
from cookielib import CookieJar

from lxml import etree

from cubicweb import RegistryNotFound, ObjectNotFound, ValidationError, UnknownEid
from cubicweb.server.sources import AbstractSource
from cubicweb.appobject import AppObject


class DataFeedSource(AbstractSource):
    copy_based_source = True
    use_cwuri_as_url = True

    options = (
        ('synchronize',
         {'type' : 'yn',
          'default': True,
          'help': ('Is the repository responsible to automatically import '
                   'content from this source? '
                   'You should say yes unless you don\'t want this behaviour '
                   'or if you use a multiple repositories setup, in which '
                   'case you should say yes on one repository, no on others.'),
          'group': 'datafeed-source', 'level': 2,
          }),
        ('synchronization-interval',
         {'type' : 'time',
          'default': '5min',
          'help': ('Interval in seconds between synchronization with the '
                   'external source (default to 5 minutes, must be >= 1 min).'),
          'group': 'datafeed-source', 'level': 2,
          }),
        ('max-lock-lifetime',
         {'type' : 'time',
          'default': '1h',
          'help': ('Maximum time allowed for a synchronization to be run. '
                   'Exceeded that time, the synchronization will be considered '
                   'as having failed and not properly released the lock, hence '
                   'it won\'t be considered'),
          'group': 'datafeed-source', 'level': 2,
          }),
        ('delete-entities',
         {'type' : 'yn',
          'default': True,
          'help': ('Should already imported entities not found anymore on the '
                   'external source be deleted?'),
          'group': 'datafeed-source', 'level': 2,
          }),

        )
    def __init__(self, repo, source_config, eid=None):
        AbstractSource.__init__(self, repo, source_config, eid)
        self.update_config(None, self.check_conf_dict(eid, source_config,
                                                      fail_if_unknown=False))

    def check_config(self, source_entity):
        """check configuration of source entity"""
        typedconfig = super(DataFeedSource, self).check_config(source_entity)
        if typedconfig['synchronization-interval'] < 60:
            _ = source_entity._cw._
            msg = _('synchronization-interval must be greater than 1 minute')
            raise ValidationError(source_entity.eid, {'config': msg})
        return typedconfig

    def _entity_update(self, source_entity):
        source_entity.complete()
        self.parser_id = source_entity.parser
        self.latest_retrieval = source_entity.latest_retrieval
        self.urls = [url.strip() for url in source_entity.url.splitlines()
                     if url.strip()]

    def update_config(self, source_entity, typedconfig):
        """update configuration from source entity. `typedconfig` is config
        properly typed with defaults set
        """
        self.synchro_interval = timedelta(seconds=typedconfig['synchronization-interval'])
        self.max_lock_lifetime = timedelta(seconds=typedconfig['max-lock-lifetime'])
        if source_entity is not None:
            self._entity_update(source_entity)
        self.config = typedconfig

    def init(self, activated, source_entity):
        if activated:
            self._entity_update(source_entity)
        self.parser_id = source_entity.parser
        self.load_mapping(source_entity._cw)

    def _get_parser(self, session, **kwargs):
        return self.repo.vreg['parsers'].select(
            self.parser_id, session, source=self, **kwargs)

    def load_mapping(self, session):
        self.mapping = {}
        self.mapping_idx = {}
        try:
            parser = self._get_parser(session)
        except (RegistryNotFound, ObjectNotFound):
            return # no parser yet, don't go further
        self._load_mapping(session, parser=parser)

    def add_schema_config(self, schemacfg, checkonly=False, parser=None):
        """added CWSourceSchemaConfig, modify mapping accordingly"""
        if parser is None:
            parser = self._get_parser(schemacfg._cw)
        parser.add_schema_config(schemacfg, checkonly)

    def del_schema_config(self, schemacfg, checkonly=False, parser=None):
        """deleted CWSourceSchemaConfig, modify mapping accordingly"""
        if parser is None:
            parser = self._get_parser(schemacfg._cw)
        parser.del_schema_config(schemacfg, checkonly)

    def fresh(self):
        if self.latest_retrieval is None:
            return False
        return datetime.utcnow() < (self.latest_retrieval + self.synchro_interval)

    def update_latest_retrieval(self, session):
        self.latest_retrieval = datetime.utcnow()
        session.execute('SET X latest_retrieval %(date)s WHERE X eid %(x)s',
                        {'x': self.eid, 'date': self.latest_retrieval})

    def acquire_synchronization_lock(self, session):
        # XXX race condition until WHERE of SET queries is executed using
        # 'SELECT FOR UPDATE'
        now = datetime.utcnow()
        if not session.execute(
            'SET X in_synchronization %(now)s WHERE X eid %(x)s, '
            'X in_synchronization NULL OR X in_synchronization < %(maxdt)s',
            {'x': self.eid, 'now': now, 'maxdt': now - self.max_lock_lifetime}):
            self.error('concurrent synchronization detected, skip pull')
            session.commit(free_cnxset=False)
            return False
        session.commit(free_cnxset=False)
        return True

    def release_synchronization_lock(self, session):
        session.set_cnxset()
        session.execute('SET X in_synchronization NULL WHERE X eid %(x)s',
                        {'x': self.eid})
        session.commit()

    def pull_data(self, session, force=False, raise_on_error=False):
        """Launch synchronization of the source if needed.

        This method is responsible to handle commit/rollback on the given
        session.
        """
        if not force and self.fresh():
            return {}
        if not self.acquire_synchronization_lock(session):
            return {}
        try:
            with session.transaction(free_cnxset=False):
                return self._pull_data(session, force, raise_on_error)
        finally:
            self.release_synchronization_lock(session)

    def _pull_data(self, session, force=False, raise_on_error=False):
        if self.config['delete-entities']:
            myuris = self.source_cwuris(session)
        else:
            myuris = None
        parser = self._get_parser(session, sourceuris=myuris)
        if self.process_urls(parser, self.urls, raise_on_error):
            self.warning("some error occured, don't attempt to delete entities")
        elif self.config['delete-entities'] and myuris:
            byetype = {}
            for eid, etype in myuris.values():
                byetype.setdefault(etype, []).append(str(eid))
            self.error('delete %s entities %s', self.uri, byetype)
            for etype, eids in byetype.iteritems():
                session.execute('DELETE %s X WHERE X eid IN (%s)'
                                % (etype, ','.join(eids)))
        self.update_latest_retrieval(session)
        return parser.stats

    def process_urls(self, parser, urls, raise_on_error=False):
        error = False
        for url in urls:
            self.info('pulling data from %s', url)
            try:
                if parser.process(url, raise_on_error):
                    error = True
            except IOError, exc:
                if raise_on_error:
                    raise
                self.error('could not pull data while processing %s: %s',
                           url, exc)
                error = True
            except Exception, exc:
                if raise_on_error:
                    raise
                self.exception('error while processing %s: %s',
                               url, exc)
                error = True
        return error

    def before_entity_insertion(self, session, lid, etype, eid, sourceparams):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.

        This method must return the an Entity instance representation of this
        entity.
        """
        entity = super(DataFeedSource, self).before_entity_insertion(
            session, lid, etype, eid, sourceparams)
        entity.cw_edited['cwuri'] = lid.decode('utf-8')
        entity.cw_edited.set_defaults()
        sourceparams['parser'].before_entity_copy(entity, sourceparams)
        return entity

    def after_entity_insertion(self, session, lid, entity, sourceparams):
        """called by the repository after an entity stored here has been
        inserted in the system table.
        """
        if session.is_hook_category_activated('integrity'):
            entity.cw_edited.check(creation=True)
        self.repo.system_source.add_entity(session, entity)
        entity.cw_edited.saved = entity._cw_is_saved = True
        sourceparams['parser'].after_entity_copy(entity, sourceparams)

    def source_cwuris(self, session):
        sql = ('SELECT extid, eid, type FROM entities, cw_source_relation '
               'WHERE entities.eid=cw_source_relation.eid_from '
               'AND cw_source_relation.eid_to=%s' % self.eid)
        return dict((b64decode(uri), (eid, type))
                    for uri, eid, type in session.system_sql(sql))


class DataFeedParser(AppObject):
    __registry__ = 'parsers'

    def __init__(self, session, source, sourceuris=None, **kwargs):
        super(DataFeedParser, self).__init__(session, **kwargs)
        self.source = source
        self.sourceuris = sourceuris
        self.stats = {'created': set(),
                      'updated': set()}

    def add_schema_config(self, schemacfg, checkonly=False):
        """added CWSourceSchemaConfig, modify mapping accordingly"""
        msg = schemacfg._cw._("this parser doesn't use a mapping")
        raise ValidationError(schemacfg.eid, {None: msg})

    def del_schema_config(self, schemacfg, checkonly=False):
        """deleted CWSourceSchemaConfig, modify mapping accordingly"""
        msg = schemacfg._cw._("this parser doesn't use a mapping")
        raise ValidationError(schemacfg.eid, {None: msg})

    def extid2entity(self, uri, etype, **sourceparams):
        """return an entity for the given uri. May return None if it should be
        skipped
        """
        session = self._cw
        # if cwsource is specified and repository has a source with the same
        # name, call extid2eid on that source so entity will be properly seen as
        # coming from this source
        source_uri = sourceparams.pop('cwsource', None)
        if source_uri is not None and source_uri != 'system':
            source = session.repo.sources_by_uri.get(source_uri, self.source)
        else:
            source = self.source
        sourceparams['parser'] = self
        if isinstance(uri, unicode):
            uri = uri.encode('utf-8')
        try:
            eid = session.repo.extid2eid(source, str(uri), etype, session,
                                         complete=False, commit=False,
                                         sourceparams=sourceparams)
        except ValidationError, ex:
            self.source.error('error while creating %s: %s', etype, ex)
            return None
        if eid < 0:
            # entity has been moved away from its original source
            #
            # Don't give etype to entity_from_eid so we get UnknownEid if the
            # entity has been removed
            try:
                entity = session.entity_from_eid(-eid)
            except UnknownEid:
                return None
            self.notify_updated(entity) # avoid later update from the source's data
            return entity
        if self.sourceuris is not None:
            self.sourceuris.pop(str(uri), None)
        return session.entity_from_eid(eid, etype)

    def process(self, url, partialcommit=True):
        """main callback: process the url"""
        raise NotImplementedError

    def before_entity_copy(self, entity, sourceparams):
        raise NotImplementedError

    def after_entity_copy(self, entity, sourceparams):
        self.stats['created'].add(entity.eid)

    def created_during_pull(self, entity):
        return entity.eid in self.stats['created']

    def updated_during_pull(self, entity):
        return entity.eid in self.stats['updated']

    def notify_updated(self, entity):
        return self.stats['updated'].add(entity.eid)


class DataFeedXMLParser(DataFeedParser):

    def process(self, url, raise_on_error=False, partialcommit=True):
        """IDataFeedParser main entry point"""
        try:
            parsed = self.parse(url)
        except Exception, ex:
            if raise_on_error:
                raise
            self.source.error(str(ex))
            return True
        error = False
        for args in parsed:
            try:
                self.process_item(*args)
                if partialcommit:
                    # commit+set_cnxset instead of commit(free_cnxset=False) to let
                    # other a chance to get our connections set
                    self._cw.commit()
                    self._cw.set_cnxset()
            except ValidationError, exc:
                if raise_on_error:
                    raise
                if partialcommit:
                    self.source.error('Skipping %s because of validation error %s' % (args, exc))
                    self._cw.rollback()
                    self._cw.set_cnxset()
                    error = True
                else:
                    raise
        return error

    def parse(self, url):
        if url.startswith('http'):
            from cubicweb.sobjects.parsers import URL_MAPPING
            for mappedurl in URL_MAPPING:
                if url.startswith(mappedurl):
                    url = url.replace(mappedurl, URL_MAPPING[mappedurl], 1)
                    break
            self.source.info('GET %s', url)
            stream = _OPENER.open(url)
        elif url.startswith('file://'):
            stream = open(url[7:])
        else:
            stream = StringIO.StringIO(url)
        return self.parse_etree(etree.parse(stream).getroot())

    def parse_etree(self, document):
        return [(document,)]

    def process_item(self, *args):
        raise NotImplementedError

# use a cookie enabled opener to use session cookie if any
_OPENER = urllib2.build_opener()
try:
    from logilab.common import urllib2ext
    _OPENER.add_handler(urllib2ext.HTTPGssapiAuthHandler())
except ImportError: # python-kerberos not available
    pass
_OPENER.add_handler(urllib2.HTTPCookieProcessor(CookieJar()))
