# copyright 2010-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from io import BytesIO
from os.path import exists
from datetime import datetime, timedelta
from functools import partial

from six import text_type
from six.moves.urllib.parse import urlparse
from six.moves.urllib.request import Request, build_opener, HTTPCookieProcessor
from six.moves.urllib.error import HTTPError
from six.moves.http_cookiejar import CookieJar

from pytz import utc
from lxml import etree

from logilab.common.deprecation import deprecated

from cubicweb import RegistryNotFound, ObjectNotFound, ValidationError, UnknownEid, SourceException
from cubicweb.server.repository import preprocess_inlined_relations
from cubicweb.server.sources import AbstractSource
from cubicweb.appobject import AppObject


class DataFeedSource(AbstractSource):
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
          'default': False,
          'help': ('Should already imported entities not found anymore on the '
                   'external source be deleted?'),
          'group': 'datafeed-source', 'level': 2,
          }),
        ('logs-lifetime',
         {'type': 'time',
          'default': '10d',
          'help': ('Time before logs from datafeed imports are deleted.'),
          'group': 'datafeed-source', 'level': 2,
          }),
        ('http-timeout',
         {'type': 'time',
          'default': '1min',
          'help': ('Timeout of HTTP GET requests, when synchronizing a source.'),
          'group': 'datafeed-source', 'level': 2,
          }),
        ('use-cwuri-as-url',
         {'type': 'yn',
          'default': None, # explicitly unset
          'help': ('Use cwuri (i.e. external URL) for link to the entity '
                   'instead of its local URL.'),
          'group': 'datafeed-source', 'level': 1,
          }),
        )

    def check_config(self, source_entity):
        """check configuration of source entity"""
        typed_config = super(DataFeedSource, self).check_config(source_entity)
        if typed_config['synchronization-interval'] < 60:
            _ = source_entity._cw._
            msg = _('synchronization-interval must be greater than 1 minute')
            raise ValidationError(source_entity.eid, {'config': msg})
        return typed_config

    def _entity_update(self, source_entity):
        super(DataFeedSource, self)._entity_update(source_entity)
        self.parser_id = source_entity.parser
        self.latest_retrieval = source_entity.latest_retrieval

    def update_config(self, source_entity, typed_config):
        """update configuration from source entity. `typed_config` is config
        properly typed with defaults set
        """
        super(DataFeedSource, self).update_config(source_entity, typed_config)
        self.synchro_interval = timedelta(seconds=typed_config['synchronization-interval'])
        self.max_lock_lifetime = timedelta(seconds=typed_config['max-lock-lifetime'])
        self.http_timeout = typed_config['http-timeout']
        # if typed_config['use-cwuri-as-url'] is set, we have to update
        # use_cwuri_as_url attribute and public configuration dictionary
        # accordingly
        if typed_config['use-cwuri-as-url'] is not None:
            self.use_cwuri_as_url = typed_config['use-cwuri-as-url']
            self.public_config['use-cwuri-as-url'] = self.use_cwuri_as_url

    def init(self, activated, source_entity):
        super(DataFeedSource, self).init(activated, source_entity)
        self.parser_id = source_entity.parser
        self.load_mapping(source_entity._cw)

    def _get_parser(self, cnx, **kwargs):
        if self.parser_id is None:
            self.warning('No parser defined on source %r', self)
            raise ObjectNotFound()
        return self.repo.vreg['parsers'].select(
            self.parser_id, cnx, source=self, **kwargs)

    def load_mapping(self, cnx):
        self.mapping = {}
        self.mapping_idx = {}
        try:
            parser = self._get_parser(cnx)
        except (RegistryNotFound, ObjectNotFound):
            return # no parser yet, don't go further
        self._load_mapping(cnx, parser=parser)

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
        return datetime.now(tz=utc) < (self.latest_retrieval + self.synchro_interval)

    def update_latest_retrieval(self, cnx):
        self.latest_retrieval = datetime.now(tz=utc)
        cnx.execute('SET X latest_retrieval %(date)s WHERE X eid %(x)s',
                    {'x': self.eid, 'date': self.latest_retrieval})
        cnx.commit()

    def acquire_synchronization_lock(self, cnx):
        # XXX race condition until WHERE of SET queries is executed using
        # 'SELECT FOR UPDATE'
        now = datetime.now(tz=utc)
        maxdt = now - self.max_lock_lifetime
        if not cnx.execute(
                'SET X in_synchronization %(now)s WHERE X eid %(x)s, '
                'X in_synchronization NULL OR X in_synchronization < %(maxdt)s',
                {'x': self.eid, 'now': now, 'maxdt': maxdt}):
            cnx.commit()
            raise SourceException("a concurrent synchronization is already running")
        cnx.commit()

    def release_synchronization_lock(self, cnx):
        cnx.execute('SET X in_synchronization NULL WHERE X eid %(x)s',
                    {'x': self.eid})
        cnx.commit()

    def pull_data(self, cnx, force=False, raise_on_error=False, async=False):
        """Launch synchronization of the source if needed.

        If `async` is true, the method return immediatly a dictionnary containing the import log's
        eid, and the actual synchronization is done asynchronously. If `async` is false, return some
        imports statistics (e.g. number of created and updated entities).

        This method is responsible to handle commit/rollback on the given connection.
        """
        if not force and self.fresh():
            return {}
        try:
            self.acquire_synchronization_lock(cnx)
        except SourceException as exc:
            if force:
                raise
            self.error(str(exc))
            return {}
        try:
            if async:
                return self._async_pull_data(cnx, force, raise_on_error)
            else:
                return self._pull_data(cnx, force, raise_on_error)
        finally:
            cnx.rollback()  # rollback first in case there is some dirty transaction remaining
            self.release_synchronization_lock(cnx)

    def _async_pull_data(self, cnx, force, raise_on_error):
        import_log = cnx.create_entity('CWDataImport', cw_import_of=self)
        cnx.commit()  # commit the import log creation before starting the synchronize task

        def _synchronize_source(repo, source_eid, import_log_eid):
            with repo.internal_cnx() as cnx:
                source = repo.sources_by_eid[source_eid]
                source._pull_data(cnx, force, raise_on_error, import_log_eid=import_log_eid)

        sync = partial(_synchronize_source, cnx.repo, self.eid, import_log.eid)
        cnx.repo.threaded_task(sync)
        return {'import_log_eid': import_log.eid}

    def _pull_data(self, cnx, force=False, raise_on_error=False, import_log_eid=None):
        importlog = self.init_import_log(cnx, import_log_eid)
        source_uris = self.source_uris(cnx)
        try:
            parser = self._get_parser(cnx, import_log=importlog,
                                      source_uris=source_uris,
                                      moved_uris=self.moved_uris(cnx))
        except ObjectNotFound:
            return {}
        if parser.process_urls(self.urls, raise_on_error):
            self.warning("some error occurred, don't attempt to delete entities")
        else:
            parser.handle_deletion(self.config, cnx, source_uris)
        self.update_latest_retrieval(cnx)
        stats = parser.stats
        if stats.get('created'):
            importlog.record_info('added %s entities' % len(stats['created']))
        if stats.get('updated'):
            importlog.record_info('updated %s entities' % len(stats['updated']))
        importlog.write_log(cnx, end_timestamp=self.latest_retrieval)
        cnx.commit()
        return stats

    @deprecated('[3.21] use the new store API')
    def before_entity_insertion(self, cnx, lid, etype, eid, sourceparams):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.

        This method must return the an Entity instance representation of this
        entity.
        """
        entity = super(DataFeedSource, self).before_entity_insertion(
            cnx, lid, etype, eid, sourceparams)
        entity.cw_edited['cwuri'] = lid.decode('utf-8')
        entity.cw_edited.set_defaults()
        sourceparams['parser'].before_entity_copy(entity, sourceparams)
        return entity

    @deprecated('[3.21] use the new store API')
    def after_entity_insertion(self, cnx, lid, entity, sourceparams):
        """called by the repository after an entity stored here has been
        inserted in the system table.
        """
        relations = preprocess_inlined_relations(cnx, entity)
        if cnx.is_hook_category_activated('integrity'):
            entity.cw_edited.check(creation=True)
        self.repo.system_source.add_entity(cnx, entity)
        entity.cw_edited.saved = entity._cw_is_saved = True
        sourceparams['parser'].after_entity_copy(entity, sourceparams)
        # call hooks for inlined relations
        call_hooks = self.repo.hm.call_hooks
        if self.should_call_hooks:
            for attr, value in relations:
                call_hooks('before_add_relation', cnx,
                           eidfrom=entity.eid, rtype=attr, eidto=value)
                call_hooks('after_add_relation', cnx,
                           eidfrom=entity.eid, rtype=attr, eidto=value)

    def source_uris(self, cnx):
        sql = 'SELECT extid, eid, type FROM entities WHERE asource=%(source)s'
        return dict((self.decode_extid(uri), (eid, type))
                    for uri, eid, type in cnx.system_sql(sql, {'source': self.uri}).fetchall())

    def moved_uris(self, cnx):
        sql = 'SELECT extid FROM moved_entities'
        return set(self.decode_extid(uri) for uri, in cnx.system_sql(sql).fetchall())

    def init_import_log(self, cnx, import_log_eid=None, **kwargs):
        if import_log_eid is None:
            import_log = cnx.create_entity('CWDataImport', cw_import_of=self,
                                           start_timestamp=datetime.now(tz=utc),
                                           **kwargs)
        else:
            import_log = cnx.entity_from_eid(import_log_eid)
            import_log.cw_set(start_timestamp=datetime.now(tz=utc), **kwargs)
        cnx.commit()  # make changes visible
        import_log.init()
        return import_log


class DataFeedParser(AppObject):
    __registry__ = 'parsers'

    def __init__(self, cnx, source, import_log=None, source_uris=None, moved_uris=None):
        super(DataFeedParser, self).__init__(cnx)
        self.source = source
        self.import_log = import_log
        if source_uris is None:
            source_uris = {}
        self.source_uris = source_uris
        if moved_uris is None:
            moved_uris = ()
        self.moved_uris = moved_uris
        self.stats = {'created': set(), 'updated': set(), 'checked': set()}

    def normalize_url(self, url):
        """Normalize an url by looking if there is a replacement for it in
        `cubicweb.sobjects.URL_MAPPING`.

        This dictionary allow to redirect from one host to another, which may be
        useful for example in case of test instance using production data, while
        you don't want to load the external source nor to hack your `/etc/hosts`
        file.
        """
        # local import mandatory, it's available after registration
        from cubicweb.sobjects import URL_MAPPING
        for mappedurl in URL_MAPPING:
            if url.startswith(mappedurl):
                return url.replace(mappedurl, URL_MAPPING[mappedurl], 1)
        return url

    def retrieve_url(self, url):
        """Return stream linked by the given url:
        * HTTP urls will be normalized (see :meth:`normalize_url`)
        * handle file:// URL
        * other will be considered as plain content, useful for testing purpose

        For http URLs, it will try to find a cwclientlib config entry
        (if available) and use it as requester.
        """
        purl = urlparse(url)
        if purl.scheme == 'file':
            return URLLibResponseAdapter(open(url[7:]), url)

        url = self.normalize_url(url)

        # first, try to use cwclientlib if it's available and if the
        # url matches a configuration entry in ~/.config/cwclientlibrc
        try:
            from cwclientlib import cwproxy_for
            # parse url again since it has been normalized
            cnx = cwproxy_for(url)
            cnx.timeout = self.source.http_timeout
            self.source.info('Using cwclientlib for %s' % url)
            resp = cnx.get(url)
            resp.raise_for_status()
            return URLLibResponseAdapter(BytesIO(resp.content), url)
        except (ImportError, ValueError, EnvironmentError) as exc:
            # ImportError: not available
            # ValueError: no config entry found
            # EnvironmentError: no cwclientlib config file found
            self.source.debug(str(exc))

        # no chance with cwclientlib, fall back to former implementation
        if purl.scheme in ('http', 'https'):
            self.source.info('GET %s', url)
            req = Request(url)
            return _OPENER.open(req, timeout=self.source.http_timeout)

        # url is probably plain content
        return URLLibResponseAdapter(BytesIO(url.encode('ascii')), url)

    def add_schema_config(self, schemacfg, checkonly=False):
        """added CWSourceSchemaConfig, modify mapping accordingly"""
        msg = schemacfg._cw._("this parser doesn't use a mapping")
        raise ValidationError(schemacfg.eid, {None: msg})

    def del_schema_config(self, schemacfg, checkonly=False):
        """deleted CWSourceSchemaConfig, modify mapping accordingly"""
        msg = schemacfg._cw._("this parser doesn't use a mapping")
        raise ValidationError(schemacfg.eid, {None: msg})

    @deprecated('[3.21] use the new store API')
    def extid2entity(self, uri, etype, **sourceparams):
        """Return an entity for the given uri. May return None if it should be
        skipped.

        If a `raise_on_error` keyword parameter is passed, a ValidationError
        exception may be raised.
        """
        raise_on_error = sourceparams.pop('raise_on_error', False)
        cnx = self._cw
        # if cwsource is specified and repository has a source with the same
        # name, call extid2eid on that source so entity will be properly seen as
        # coming from this source
        source_uri = sourceparams.pop('cwsource', None)
        if source_uri is not None and source_uri != 'system':
            source = cnx.repo.sources_by_uri.get(source_uri, self.source)
        else:
            source = self.source
        sourceparams['parser'] = self
        if isinstance(uri, text_type):
            uri = uri.encode('utf-8')
        try:
            eid = cnx.repo.extid2eid(source, uri, etype, cnx,
                                     sourceparams=sourceparams)
        except ValidationError as ex:
            if raise_on_error:
                raise
            self.source.critical('error while creating %s: %s', etype, ex)
            self.import_log.record_error('error while creating %s: %s'
                                         % (etype, ex))
            return None
        if eid < 0:
            # entity has been moved away from its original source
            #
            # Don't give etype to entity_from_eid so we get UnknownEid if the
            # entity has been removed
            try:
                entity = cnx.entity_from_eid(-eid)
            except UnknownEid:
                return None
            self.notify_updated(entity)  # avoid later update from the source's data
            return entity
        if self.source_uris is not None:
            self.source_uris.pop(str(uri), None)
        return cnx.entity_from_eid(eid, etype)

    def process_urls(self, urls, raise_on_error=False):
        error = False
        for url in urls:
            self.info('pulling data from %s', url)
            try:
                if self.process(url, raise_on_error):
                    error = True
            except IOError as exc:
                if raise_on_error:
                    raise
                self.import_log.record_error(
                    'could not pull data while processing %s: %s'
                    % (url, exc))
                error = True
            except Exception as exc:
                if raise_on_error:
                    raise
                self.import_log.record_error(str(exc))
                self.exception('error while processing %s: %s',
                               url, exc)
                error = True
        return error

    def process(self, url, raise_on_error=False):
        """main callback: process the url"""
        raise NotImplementedError

    @deprecated('[3.21] use the new store API')
    def before_entity_copy(self, entity, sourceparams):
        raise NotImplementedError

    @deprecated('[3.21] use the new store API')
    def after_entity_copy(self, entity, sourceparams):
        self.stats['created'].add(entity.eid)

    def created_during_pull(self, entity):
        return entity.eid in self.stats['created']

    def updated_during_pull(self, entity):
        return entity.eid in self.stats['updated']

    def notify_updated(self, entity):
        return self.stats['updated'].add(entity.eid)

    def notify_checked(self, entity):
        return self.stats['checked'].add(entity.eid)

    def is_deleted(self, extid, etype, eid):
        """return True if the entity of given external id, entity type and eid
        is actually deleted. Always return True by default, put more sensible
        stuff in sub-classes.
        """
        return True

    def handle_deletion(self, config, cnx, source_uris):
        if config['delete-entities'] and source_uris:
            byetype = {}
            for extid, (eid, etype) in source_uris.items():
                if self.is_deleted(extid, etype, eid):
                    byetype.setdefault(etype, []).append(str(eid))
            for etype, eids in byetype.items():
                self.warning('delete %s %s entities', len(eids), etype)
                cnx.execute('DELETE %s X WHERE X eid IN (%s)'
                            % (etype, ','.join(eids)))
            cnx.commit()

    def update_if_necessary(self, entity, attrs):
        entity.complete(tuple(attrs))
        # check modification date and compare attribute values to only update
        # what's actually needed
        self.notify_checked(entity)
        mdate = attrs.get('modification_date')
        if not mdate or mdate > entity.modification_date:
            attrs = dict( (k, v) for k, v in attrs.items()
                          if v != getattr(entity, k))
            if attrs:
                entity.cw_set(**attrs)
                self.notify_updated(entity)


class DataFeedXMLParser(DataFeedParser):

    @deprecated()
    def process(self, url, raise_on_error=False):
        """IDataFeedParser main entry point"""
        try:
            parsed = self.parse(url)
        except Exception as ex:
            if raise_on_error:
                raise
            self.import_log.record_error(str(ex))
            return True
        for args in parsed:
            self.process_item(*args, raise_on_error=raise_on_error)
        return False

    def parse(self, url):
        stream = self.retrieve_url(url)
        return self.parse_etree(etree.parse(stream).getroot())

    def parse_etree(self, document):
        return [(document,)]

    def process_item(self, *args, **kwargs):
        raise NotImplementedError

    def is_deleted(self, extid, etype, eid):
        if extid.startswith('file://'):
            return exists(extid[7:])

        url = self.normalize_url(extid)
        # first, try to use cwclientlib if it's available and if the
        # url matches a configuration entry in ~/.config/cwclientlibrc
        try:
            from cwclientlib import cwproxy_for
            # parse url again since it has been normalized
            cnx = cwproxy_for(url)
            cnx.timeout = self.source.http_timeout
            self.source.info('Using cwclientlib for checking %s' % url)
            return cnx.get(url).status_code == 404
        except (ImportError, ValueError, EnvironmentError) as exc:
            # ImportError: not available
            # ValueError: no config entry found
            # EnvironmentError: no cwclientlib config file found
            self.source.debug(str(exc))

        # no chance with cwclientlib, fall back to former implementation
        if urlparse(url).scheme in ('http', 'https'):
            try:
                _OPENER.open(url, timeout=self.source.http_timeout)
            except HTTPError as ex:
                if ex.code == 404:
                    return True
        return False


class URLLibResponseAdapter(object):
    """Thin wrapper to be used to fake a value returned by urllib2.urlopen"""
    def __init__(self, stream, url, code=200):
        self._stream = stream
        self._url = url
        self.code = code

    def read(self, *args):
        return self._stream.read(*args)

    def geturl(self):
        return self._url

    def getcode(self):
        return self.code


# use a cookie enabled opener to use session cookie if any
_OPENER = build_opener()
try:
    from logilab.common import urllib2ext
    _OPENER.add_handler(urllib2ext.HTTPGssapiAuthHandler())
except ImportError: # python-kerberos not available
    pass
_OPENER.add_handler(HTTPCookieProcessor(CookieJar()))
