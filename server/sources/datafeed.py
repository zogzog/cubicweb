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
from datetime import datetime, timedelta
from base64 import b64decode

from cubicweb import RegistryNotFound, ObjectNotFound, ValidationError
from cubicweb.server.sources import AbstractSource
from cubicweb.appobject import AppObject

class DataFeedSource(AbstractSource):
    copy_based_source = True

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
        self.update_config(None, self.check_conf_dict(eid, source_config))

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
        self.parser = source_entity.parser
        self.latest_retrieval = source_entity.latest_retrieval
        self.urls = [url.strip() for url in source_entity.url.splitlines()
                     if url.strip()]

    def update_config(self, source_entity, typedconfig):
        """update configuration from source entity. `typedconfig` is config
        properly typed with defaults set
        """
        self.synchro_interval = timedelta(seconds=typedconfig['synchronization-interval'])
        if source_entity is not None:
            self._entity_update(source_entity)
        self.config = typedconfig

    def init(self, activated, source_entity):
        if activated:
            self._entity_update(source_entity)
        self.parser = source_entity.parser
        self.load_mapping(source_entity._cw)

    def _get_parser(self, session, **kwargs):
        return self.repo.vreg['parsers'].select(
            self.parser, session, source=self, **kwargs)

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
        return datetime.now() < (self.latest_retrieval + self.synchro_interval)

    def pull_data(self, session, force=False):
        if not force and self.fresh():
            return {}
        if self.config['delete-entities']:
            myuris = self.source_cwuris(session)
        else:
            myuris = None
        parser = self._get_parser(session, sourceuris=myuris)
        error = False
        self.info('pulling data for source %s', self.uri)
        for url in self.urls:
            try:
                if parser.process(url):
                    error = True
            except IOError, exc:
                self.error('could not pull data while processing %s: %s',
                           url, exc)
                error = True
        if error:
            self.warning("some error occured, don't attempt to delete entities")
        elif self.config['delete-entities'] and myuris:
            byetype = {}
            for eid, etype in myuris.values():
                byetype.setdefault(etype, []).append(str(eid))
            self.error('delete %s entities %s', self.uri, byetype)
            for etype, eids in byetype.iteritems():
                session.execute('DELETE %s X WHERE X eid IN (%s)'
                                % (etype, ','.join(eids)))
        self.latest_retrieval = datetime.now()
        session.execute('SET X latest_retrieval %(date)s WHERE X eid %(x)s',
                        {'x': self.eid, 'date': self.latest_retrieval})
        return parser.stats

    def before_entity_insertion(self, session, lid, etype, eid, sourceparams):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.

        This method must return the an Entity instance representation of this
        entity.
        """
        entity = super(DataFeedSource, self).before_entity_insertion(
            session, lid, etype, eid, sourceparams)
        entity.cw_edited['cwuri'] = unicode(lid)
        entity.cw_edited.set_defaults()
        sourceparams['parser'].before_entity_copy(entity, sourceparams)
        # avoid query to search full-text indexed attributes
        for attr in entity.e_schema.indexable_attributes():
            entity.cw_edited.setdefault(attr, u'')
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

    def __init__(self, session, source, sourceuris=None):
        self._cw = session
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
        sourceparams['parser'] = self
        eid = self.source.extid2eid(str(uri), etype, self._cw,
                                    sourceparams=sourceparams)
        if self.sourceuris is not None:
            self.sourceuris.pop(str(uri), None)
        return self._cw.entity_from_eid(eid, etype)

    def process(self, url):
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
