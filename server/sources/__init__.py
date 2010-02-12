"""cubicweb server sources support

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from os.path import join, splitext
from datetime import datetime, timedelta
from logging import getLogger

from cubicweb import set_log_methods, server
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.server.sqlutils import SQL_PREFIX


def dbg_st_search(uri, union, varmap, args, cachekey=None, prefix='rql for'):
    if server.DEBUG & server.DBG_RQL:
        print '  %s %s source: %s' % (prefix, uri, union.as_string())
        if varmap:
            print '    using varmap', varmap
        if server.DEBUG & server.DBG_MORE:
            print '    args', args
            print '    cache key', cachekey
            print '    solutions', ','.join(str(s.solutions)
                                            for s in union.children)
    # return true so it can be used as assertion (and so be killed by python -O)
    return True

def dbg_results(results):
    if server.DEBUG & server.DBG_RQL:
        if len(results) > 10:
            print '  -->', results[:10], '...', len(results)
        else:
            print '  -->', results
    # return true so it can be used as assertion (and so be killed by python -O)
    return True

class TimedCache(dict):
    def __init__(self, ttlm, ttls=0):
        # time to live in minutes
        self.ttl = timedelta(0, ttlm*60 + ttls, 0)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, (datetime.now(), value))

    def __getitem__(self, key):
        return dict.__getitem__(self, key)[1]

    def clear_expired(self):
        now_ = datetime.now()
        ttl = self.ttl
        for key, (timestamp, value) in self.items():
            if now_ - timestamp > ttl:
                del self[key]


class AbstractSource(object):
    """an abstract class for sources"""

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


    def __init__(self, repo, appschema, source_config, *args, **kwargs):
        self.repo = repo
        self.uri = source_config['uri']
        set_log_methods(self, getLogger('cubicweb.sources.'+self.uri))
        self.set_schema(appschema)
        self.support_relations['identity'] = False

    def init_creating(self):
        """method called by the repository once ready to create a new instance"""
        pass

    def init(self):
        """method called by the repository once ready to handle request"""
        pass

    def backup(self, backupfile):
        """method called to create a backup of source's data"""
        pass

    def restore(self, backupfile, confirm, drop):
        """method called to restore a backup of source's data"""
        pass

    def close_pool_connections(self):
        for pool in self.repo.pools:
            pool._cursors.pop(self.uri, None)
            pool.source_cnxs[self.uri][1].close()

    def open_pool_connections(self):
        for pool in self.repo.pools:
            pool.source_cnxs[self.uri] = (self, self.get_connection())

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        pass

    def clear_eid_cache(self, eid, etype):
        """clear potential caches for the given eid"""
        pass

    def __repr__(self):
        return '<%s source @%#x>' % (self.uri, id(self))

    def __cmp__(self, other):
        """simple comparison function to get predictable source order, with the
        system source at last
        """
        if self.uri == other.uri:
            return 0
        if self.uri == 'system':
            return 1
        if other.uri == 'system':
            return -1
        return cmp(self.uri, other.uri)

    def set_schema(self, schema):
        """set the instance'schema"""
        self.schema = schema

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
            if not rschema.final or rschema == 'has_text':
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
        #     card 1 relation ? ...)
        if self.support_relation(rtype):
            return rtype in self.cross_relations
        return rtype not in self.dont_cross_relations

    def eid2extid(self, eid, session=None):
        return self.repo.eid2extid(self, eid, session)

    def extid2eid(self, value, etype, session=None, **kwargs):
        return self.repo.extid2eid(self, value, etype, session, **kwargs)

    PUBLIC_KEYS = ('adapter', 'uri')
    def remove_sensitive_information(self, sourcedef):
        """remove sensitive information such as login / password from source
        definition
        """
        for key in sourcedef.keys():
            if not key in self.PUBLIC_KEYS:
                sourcedef.pop(key)

    def _cleanup_system_relations(self, session):
        """remove relation in the system source referencing entities coming from
        this source
        """
        cu = session.system_sql('SELECT eid FROM entities WHERE source=%(uri)s',
                                {'uri': self.uri})
        myeids = ','.join(str(r[0]) for r in cu.fetchall())
        if not myeids:
            return
        # delete relations referencing one of those eids
        eidcolum = SQL_PREFIX + 'eid'
        for rschema in self.schema.relations():
            if rschema.final or rschema.type in VIRTUAL_RTYPES:
                continue
            if rschema.inlined:
                column = SQL_PREFIX + rschema.type
                for subjtype in rschema.subjects():
                    table = SQL_PREFIX + str(subjtype)
                    for objtype in rschema.objects(subjtype):
                        if self.support_entity(objtype):
                            sql = 'UPDATE %s SET %s=NULL WHERE %s IN (%s);' % (
                                table, column, eidcolum, myeids)
                            session.system_sql(sql)
                            break
                continue
            for etype in rschema.subjects():
                if self.support_entity(etype):
                    sql = 'DELETE FROM %s_relation WHERE eid_from IN (%s);' % (
                        rschema.type, myeids)
                    session.system_sql(sql)
                    break
            for etype in rschema.objects():
                if self.support_entity(etype):
                    sql = 'DELETE FROM %s_relation WHERE eid_to IN (%s);' % (
                        rschema.type, myeids)
                    session.system_sql(sql)
                    break

    def cleanup_entities_info(self, session):
        """cleanup system tables from information for entities coming from
        this source. This should be called when a source is removed to
        properly cleanup the database
        """
        self._cleanup_system_relations(session)
        # fti / entities tables cleanup
        # sqlite doesn't support DELETE FROM xxx USING yyy
        dbhelper = session.pool.source('system').dbhelper
        session.system_sql('DELETE FROM %s WHERE %s.%s IN (SELECT eid FROM '
                           'entities WHERE entities.source=%%(uri)s)'
                           % (dbhelper.fti_table, dbhelper.fti_table,
                              dbhelper.fti_uid_attr),
                           {'uri': self.uri})
        session.system_sql('DELETE FROM entities WHERE source=%(uri)s',
                           {'uri': self.uri})

    # abstract methods to override (at least) in concrete source classes #######

    def get_connection(self):
        """open and return a connection to the source"""
        raise NotImplementedError()

    def check_connection(self, cnx):
        """check connection validity, return None if the connection is still valid
        else a new connection (called when the pool using the given connection is
        being attached to a session)

        do nothing by default
        """
        pass

    def pool_reset(self, cnx):
        """the pool using the given connection is being reseted from its current
        attached session

        do nothing by default
        """
        pass

    def authenticate(self, session, login, **kwargs):
        """if the source support CWUser entity type, it should implements
        this method which should return CWUser eid for the given login/password
        if this account is defined in this source and valid login / password is
        given. Else raise `AuthenticationError`
        """
        raise NotImplementedError()

    def syntax_tree_search(self, session, union,
                           args=None, cachekey=None, varmap=None, debug=0):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        raise NotImplementedError()

    def flying_insert(self, table, session, union, args=None, varmap=None):
        """similar as .syntax_tree_search, but inserts data in the temporary
        table (on-the-fly if possible, eg for the system source whose the given
        cursor come from). If not possible, inserts all data by calling
        .executemany().
        """
        res = self.syntax_tree_search(session, union, args, varmap=varmap)
        session.pool.source('system').manual_insert(res, table, session)

    # system source don't have to implement the two methods below

    def before_entity_insertion(self, session, lid, etype, eid):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.

        This method must return the an Entity instance representation of this
        entity.
        """
        entity = self.repo.vreg['etypes'].etype_class(etype)(session)
        entity.set_eid(eid)
        return entity

    def after_entity_insertion(self, session, lid, entity):
        """called by the repository after an entity stored here has been
        inserted in the system table.
        """
        pass

    # read-only sources don't have to implement methods below

    def get_extid(self, entity):
        """return the external id for the given newly inserted entity"""
        raise NotImplementedError()

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        raise NotImplementedError()

    def update_entity(self, session, entity):
        """update an entity in the source"""
        raise NotImplementedError()

    def delete_entity(self, session, etype, eid):
        """delete an entity from the source"""
        raise NotImplementedError()

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        raise NotImplementedError()

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        raise NotImplementedError()

    # system source interface #################################################

    def eid_type_source(self, session, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        raise NotImplementedError()

    def create_eid(self, session):
        raise NotImplementedError()

    def add_info(self, session, entity, source, extid=None):
        """add type and source info for an eid into the system table"""
        raise NotImplementedError()

    def delete_info(self, session, eid, etype, uri, extid):
        """delete system information on deletion of an entity by transfering
        record from the entities table to the deleted_entities table
        """
        raise NotImplementedError()

    def fti_unindex_entity(self, session, eid):
        """remove text content for entity with the given eid from the full text
        index
        """
        raise NotImplementedError()

    def fti_index_entity(self, session, entity):
        """add text content of a created/modified entity to the full text index
        """
        raise NotImplementedError()

    def modified_entities(self, session, etypes, mtime):
        """return a 2-uple:
        * list of (etype, eid) of entities of the given types which have been
          modified since the given timestamp (actually entities whose full text
          index content has changed)
        * list of (etype, eid) of entities of the given types which have been
          deleted since the given timestamp
        """
        raise NotImplementedError()

    # sql system source interface #############################################

    def sqlexec(self, session, sql, args=None):
        """execute the query and return its result"""
        raise NotImplementedError()

    def temp_table_def(self, selection, solution, table, basemap):
        raise NotImplementedError()

    def create_index(self, session, table, column, unique=False):
        raise NotImplementedError()

    def drop_index(self, session, table, column, unique=False):
        raise NotImplementedError()

    def create_temp_table(self, session, table, schema):
        raise NotImplementedError()

    def clean_temp_data(self, session, temptables):
        """remove temporary data, usually associated to temporary tables"""
        pass


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

from cubicweb.server import SOURCE_TYPES

def source_adapter(source_config):
    adapter_type = source_config['adapter'].lower()
    try:
        return SOURCE_TYPES[adapter_type]
    except KeyError:
        raise RuntimeError('Unknown adapter %r' % adapter_type)

def get_source(source_config, global_schema, repo):
    """return a source adapter according to the adapter field in the
    source's configuration
    """
    return source_adapter(source_config)(repo, global_schema, source_config)
