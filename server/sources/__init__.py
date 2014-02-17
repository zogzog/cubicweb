# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb server sources support"""

__docformat__ = "restructuredtext en"

import itertools
from os.path import join, splitext
from time import time
from datetime import datetime, timedelta
from logging import getLogger

from logilab.common import configuration
from logilab.common.deprecation import deprecated

from yams.schema import role_name

from cubicweb import ValidationError, set_log_methods, server
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.edition import EditedEntity


def dbg_st_search(uri, union, varmap, args, cachekey=None, prefix='rql for'):
    if server.DEBUG & server.DBG_RQL:
        global t
        print '  %s %s source: %s' % (prefix, uri, repr(union.as_string()))
        t = time()
        if varmap:
            print '    using varmap', varmap
        if server.DEBUG & server.DBG_MORE:
            print '    args', repr(args)
            print '    cache key', cachekey
            print '    solutions', ','.join(str(s.solutions)
                                            for s in union.children)
    # return true so it can be used as assertion (and so be killed by python -O)
    return True

def dbg_results(results):
    if server.DEBUG & server.DBG_RQL:
        if len(results) > 10:
            print '  -->', results[:10], '...', len(results),
        else:
            print '  -->', results,
        print 'time: ', time() - t
    # return true so it can be used as assertion (and so be killed by python -O)
    return True

class TimedCache(dict):
    def __init__(self, ttl):
        # time to live in seconds
        if ttl <= 0:
            raise ValueError('TimedCache initialized with a ttl of %ss' % ttl.seconds)
        self.ttl = timedelta(seconds=ttl)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, (datetime.utcnow(), value))

    def __getitem__(self, key):
        return dict.__getitem__(self, key)[1]

    def clear_expired(self):
        now_ = datetime.utcnow()
        ttl = self.ttl
        for key, (timestamp, value) in self.items():
            if now_ - timestamp > ttl:
                del self[key]


class AbstractSource(object):
    """an abstract class for sources"""
    # does the source copy data into the system source, or is it a *true* source
    # (i.e. entities are not stored physically here)
    copy_based_source = False

    # boolean telling if modification hooks should be called when something is
    # modified in this source
    should_call_hooks = True
    # boolean telling if the repository should connect to this source during
    # migration
    connect_for_migration = True

    # mappings telling which entities and relations are available in the source
    # keys are supported entity/relation types and values are boolean indicating
    # wether the support is read-only (False) or read-write (True)
    support_entities = {}
    support_relations = {}
    # a global identifier for this source, which has to be set by the source
    # instance
    uri = None
    # a reference to the system information helper
    repo = None
    # a reference to the instance'schema (may differs from the source'schema)
    schema = None

    # multi-sources planning control
    dont_cross_relations = ()
    cross_relations = ()

    # force deactivation (configuration error for instance)
    disabled = False

    # boolean telling if cwuri of entities from this source is the url that
    # should be used as entity's absolute url
    use_cwuri_as_url = False

    # source configuration options
    options = ()

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

    def __init__(self, repo, source_config, eid=None):
        self.repo = repo
        self.set_schema(repo.schema)
        self.support_relations['identity'] = False
        self.eid = eid
        self.public_config = source_config.copy()
        self.public_config.setdefault('use-cwuri-as-url', self.use_cwuri_as_url)
        self.remove_sensitive_information(self.public_config)
        self.uri = source_config.pop('uri')
        set_log_methods(self, getLogger('cubicweb.sources.'+self.uri))
        source_config.pop('type')
        self.update_config(None, self.check_conf_dict(eid, source_config,
                                                      fail_if_unknown=False))

    def __repr__(self):
        return '<%s %s source %s @%#x>' % (self.uri, self.__class__.__name__,
                                           self.eid, id(self))

    def __lt__(self, other):
        """simple comparison function to get predictable source order, with the
        system source at last
        """
        if self.uri == other.uri:
            return False
        if self.uri == 'system':
            return False
        if other.uri == 'system':
            return True
        return self.uri < other.uri

    def __eq__(self, other):
        return self.uri == other.uri

    def backup(self, backupfile, confirm, format='native'):
        """method called to create a backup of source's data"""
        pass

    def restore(self, backupfile, confirm, drop, format='native'):
        """method called to restore a backup of source's data"""
        pass

    @classmethod
    def check_conf_dict(cls, eid, confdict, _=unicode, fail_if_unknown=True):
        """check configuration of source entity. Return config dict properly
        typed with defaults set.
        """
        processed = {}
        for optname, optdict in cls.options:
            value = confdict.pop(optname, optdict.get('default'))
            if value is configuration.REQUIRED:
                if not fail_if_unknown:
                    continue
                msg = _('specifying %s is mandatory' % optname)
                raise ValidationError(eid, {role_name('config', 'subject'): msg})
            elif value is not None:
                # type check
                try:
                    value = configuration._validate(value, optdict, optname)
                except Exception as ex:
                    msg = unicode(ex) # XXX internationalization
                    raise ValidationError(eid, {role_name('config', 'subject'): msg})
            processed[optname] = value
        # cw < 3.10 bw compat
        try:
            processed['adapter'] = confdict['adapter']
        except KeyError:
            pass
        # check for unknown options
        if confdict and tuple(confdict) != ('adapter',):
            if fail_if_unknown:
                msg = _('unknown options %s') % ', '.join(confdict)
                raise ValidationError(eid, {role_name('config', 'subject'): msg})
            else:
                logger = getLogger('cubicweb.sources')
                logger.warning('unknown options %s', ', '.join(confdict))
                # add options to processed, they may be necessary during migration
                processed.update(confdict)
        return processed

    @classmethod
    def check_config(cls, source_entity):
        """check configuration of source entity"""
        return cls.check_conf_dict(source_entity.eid, source_entity.host_config,
                                    _=source_entity._cw._)

    def update_config(self, source_entity, typedconfig):
        """update configuration from source entity. `typedconfig` is config
        properly typed with defaults set
        """
        if source_entity is not None:
            self._entity_update(source_entity)
        self.config = typedconfig

    def _entity_update(self, source_entity):
        source_entity.complete()
        if source_entity.url:
            self.urls = [url.strip() for url in source_entity.url.splitlines()
                         if url.strip()]
        else:
            self.urls = []

    # source initialization / finalization #####################################

    def set_schema(self, schema):
        """set the instance'schema"""
        self.schema = schema

    def init_creating(self):
        """method called by the repository once ready to create a new instance"""
        pass

    def init(self, activated, source_entity):
        """method called by the repository once ready to handle request.
        `activated` is a boolean flag telling if the source is activated or not.
        """
        if activated:
            self._entity_update(source_entity)

    PUBLIC_KEYS = ('type', 'uri', 'use-cwuri-as-url')
    def remove_sensitive_information(self, sourcedef):
        """remove sensitive information such as login / password from source
        definition
        """
        for key in list(sourcedef):
            if not key in self.PUBLIC_KEYS:
                sourcedef.pop(key)

    # connections handling #####################################################

    def get_connection(self):
        """open and return a connection to the source"""
        raise NotImplementedError(self)

    def check_connection(self, cnx):
        """Check connection validity, return None if the connection is still
        valid else a new connection (called when the connections set using the
        given connection is being attached to a session). Do nothing by default.
        """
        pass

    def close_source_connections(self):
        for cnxset in self.repo.cnxsets:
            cnxset._cursors.pop(self.uri, None)
            cnxset.source_cnxs[self.uri][1].close()

    def open_source_connections(self):
        for cnxset in self.repo.cnxsets:
            cnxset.source_cnxs[self.uri] = (self, self.get_connection())

    def cnxset_freed(self, cnx):
        """the connections set holding the given connection is being reseted
        from its current attached session.

        do nothing by default
        """
        pass

    # cache handling ###########################################################

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        pass

    def clear_eid_cache(self, eid, etype):
        """clear potential caches for the given eid"""
        pass

    # external source api ######################################################

    def support_entity(self, etype, write=False):
        """return true if the given entity's type is handled by this adapter
        if write is true, return true only if it's a RW support
        """
        try:
            wsupport = self.support_entities[etype]
        except KeyError:
            return False
        if write:
            return wsupport
        return True

    def support_relation(self, rtype, write=False):
        """return true if the given relation's type is handled by this adapter
        if write is true, return true only if it's a RW support

        current implementation return true if the relation is defined into
        `support_relations` or if it is a final relation of a supported entity
        type
        """
        try:
            wsupport = self.support_relations[rtype]
        except KeyError:
            rschema = self.schema.rschema(rtype)
            if not rschema.final or rschema.type == 'has_text':
                return False
            for etype in rschema.subjects():
                try:
                    wsupport = self.support_entities[etype]
                    break
                except KeyError:
                    continue
            else:
                return False
        if write:
            return wsupport
        return True

    def may_cross_relation(self, rtype):
        """return True if the relation may be crossed among sources. Rules are:

        * if this source support the relation, can't be crossed unless explicitly
          specified in .cross_relations

        * if this source doesn't support the relation, can be crossed unless
          explicitly specified in .dont_cross_relations
        """
        # XXX find a way to have relation such as state_of in dont cross
        #     relation (eg composite relation without both end type available?
        #     card 1 relation? ...)
        if self.support_relation(rtype):
            return rtype in self.cross_relations
        return rtype not in self.dont_cross_relations

    def before_entity_insertion(self, session, lid, etype, eid, sourceparams):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.

        This method must return the an Entity instance representation of this
        entity.
        """
        entity = self.repo.vreg['etypes'].etype_class(etype)(session)
        entity.eid = eid
        entity.cw_edited = EditedEntity(entity)
        return entity

    def after_entity_insertion(self, session, lid, entity, sourceparams):
        """called by the repository after an entity stored here has been
        inserted in the system table.
        """
        pass

    def _load_mapping(self, session=None, **kwargs):
        if not 'CWSourceSchemaConfig' in self.schema:
            self.warning('instance is not mapping ready')
            return
        if session is None:
            _session = self.repo.internal_session()
        else:
            _session = session
        try:
            for schemacfg in _session.execute(
                'Any CFG,CFGO,S WHERE '
                'CFG options CFGO, CFG cw_schema S, '
                'CFG cw_for_source X, X eid %(x)s', {'x': self.eid}).entities():
                self.add_schema_config(schemacfg, **kwargs)
        finally:
            if session is None:
                _session.close()

    def add_schema_config(self, schemacfg, checkonly=False):
        """added CWSourceSchemaConfig, modify mapping accordingly"""
        msg = schemacfg._cw._("this source doesn't use a mapping")
        raise ValidationError(schemacfg.eid, {None: msg})

    def del_schema_config(self, schemacfg, checkonly=False):
        """deleted CWSourceSchemaConfig, modify mapping accordingly"""
        msg = schemacfg._cw._("this source doesn't use a mapping")
        raise ValidationError(schemacfg.eid, {None: msg})

    def update_schema_config(self, schemacfg, checkonly=False):
        """updated CWSourceSchemaConfig, modify mapping accordingly"""
        self.del_schema_config(schemacfg, checkonly)
        self.add_schema_config(schemacfg, checkonly)

    # user authentication api ##################################################

    def authenticate(self, session, login, **kwargs):
        """if the source support CWUser entity type, it should implement
        this method which should return CWUser eid for the given login/password
        if this account is defined in this source and valid login / password is
        given. Else raise `AuthenticationError`
        """
        raise NotImplementedError(self)

    # RQL query api ############################################################

    def syntax_tree_search(self, session, union,
                           args=None, cachekey=None, varmap=None, debug=0):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        raise NotImplementedError(self)

    def flying_insert(self, table, session, union, args=None, varmap=None):
        """similar as .syntax_tree_search, but inserts data in the temporary
        table (on-the-fly if possible, eg for the system source whose the given
        cursor come from). If not possible, inserts all data by calling
        .executemany().
        """
        res = self.syntax_tree_search(session, union, args, varmap=varmap)
        session.cnxset.source('system').manual_insert(res, table, session)

    # write modification api ###################################################
    # read-only sources don't have to implement methods below

    def get_extid(self, entity):
        """return the external id for the given newly inserted entity"""
        raise NotImplementedError(self)

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        raise NotImplementedError(self)

    def update_entity(self, session, entity):
        """update an entity in the source"""
        raise NotImplementedError(self)

    def delete_entities(self, session, entities):
        """delete several entities from the source"""
        for entity in entities:
            self.delete_entity(session, entity)

    def delete_entity(self, session, entity):
        """delete an entity from the source"""
        raise NotImplementedError(self)

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        raise NotImplementedError(self)

    def add_relations(self, session,  rtype, subj_obj_list):
        """add a relations to the source"""
        # override in derived classes if you feel you can
        # optimize
        for subject, object in subj_obj_list:
            self.add_relation(session, subject, rtype, object)

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        raise NotImplementedError(self)

    # system source interface #################################################

    def eid_type_source(self, session, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        raise NotImplementedError(self)

    def create_eid(self, session):
        raise NotImplementedError(self)

    def add_info(self, session, entity, source, extid):
        """add type and source info for an eid into the system table"""
        raise NotImplementedError(self)

    def update_info(self, session, entity, need_fti_update):
        """mark entity as being modified, fulltext reindex if needed"""
        raise NotImplementedError(self)

    def delete_info_multi(self, session, entities, uri):
        """delete system information on deletion of a list of entities with the
        same etype and belinging to the same source
        """
        raise NotImplementedError(self)

    def modified_entities(self, session, etypes, mtime):
        """return a 2-uple:
        * list of (etype, eid) of entities of the given types which have been
          modified since the given timestamp (actually entities whose full text
          index content has changed)
        * list of (etype, eid) of entities of the given types which have been
          deleted since the given timestamp
        """
        raise NotImplementedError(self)

    def index_entity(self, session, entity):
        """create an operation to [re]index textual content of the given entity
        on commit
        """
        raise NotImplementedError(self)

    def fti_unindex_entities(self, session, entities):
        """remove text content for entities from the full text index
        """
        raise NotImplementedError(self)

    def fti_index_entities(self, session, entities):
        """add text content of created/modified entities to the full text index
        """
        raise NotImplementedError(self)

    # sql system source interface #############################################

    def sqlexec(self, session, sql, args=None):
        """execute the query and return its result"""
        raise NotImplementedError(self)

    def temp_table_def(self, selection, solution, table, basemap):
        raise NotImplementedError(self)

    def create_index(self, session, table, column, unique=False):
        raise NotImplementedError(self)

    def drop_index(self, session, table, column, unique=False):
        raise NotImplementedError(self)

    def create_temp_table(self, session, table, schema):
        raise NotImplementedError(self)

    def clean_temp_data(self, session, temptables):
        """remove temporary data, usually associated to temporary tables"""
        pass


    @deprecated('[3.13] use repo.eid2extid(source, eid, session)')
    def eid2extid(self, eid, session=None):
        return self.repo.eid2extid(self, eid, session)

    @deprecated('[3.13] use extid2eid(source, value, etype, session, **kwargs)')
    def extid2eid(self, value, etype, session=None, **kwargs):
        return self.repo.extid2eid(self, value, etype, session, **kwargs)


class TrFunc(object):
    """lower, upper"""
    def __init__(self, trname, index, attrname=None):
        self._tr = trname.lower()
        self.index = index
        self.attrname = attrname

    def apply(self, resdict):
        value = resdict.get(self.attrname)
        if value is not None:
            return getattr(value, self._tr)()
        return None


class GlobTrFunc(TrFunc):
    """count, sum, max, min, avg"""
    funcs = {
        'count': len,
        'sum': sum,
        'max': max,
        'min': min,
        # XXX avg
        }
    def apply(self, result):
        """have to 'groupby' manually. For instance, if we 'count' for index 1:
        >>> self.apply([(1, 2), (3, 4), (1, 5)])
        [(1, 7), (3, 4)]
        """
        keys, values = [], {}
        for row in result:
            key = tuple(v for i, v in enumerate(row) if i != self.index)
            value = row[self.index]
            try:
                values[key].append(value)
            except KeyError:
                keys.append(key)
                values[key] = [value]
        result = []
        trfunc = self.funcs[self._tr]
        for key in keys:
            row = list(key)
            row.insert(self.index, trfunc(values[key]))
            result.append(row)
        return result


class ConnectionWrapper(object):
    def __init__(self, cnx=None):
        self.cnx = cnx
    def commit(self):
        pass
    def rollback(self):
        pass
    def cursor(self):
        return None # no actual cursor support
    def close(self):
        if hasattr(self.cnx, 'close'):
            self.cnx.close()

from cubicweb.server import SOURCE_TYPES

def source_adapter(source_type):
    try:
        return SOURCE_TYPES[source_type]
    except KeyError:
        raise RuntimeError('Unknown source type %r' % source_type)

def get_source(type, source_config, repo, eid):
    """return a source adapter according to the adapter field in the source's
    configuration
    """
    return source_adapter(type)(repo, source_config, eid)
