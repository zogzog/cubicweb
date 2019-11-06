# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from time import time
from logging import getLogger

from logilab.common import configuration
from logilab.common.textutils import unormalize

from yams.schema import role_name

from cubicweb import ValidationError, set_log_methods, server, _
from cubicweb.server import SOURCE_TYPES
from cubicweb.misc.source_highlight import highlight_terminal


def dbg_st_search(uri, union, args, cachekey=None, prefix='rql for'):
    if server.DEBUG & server.DBG_RQL:
        global t
        print(" ", prefix, uri, "source:", highlight_terminal(repr(union.as_string())[1:-1], 'RQL'))
        t = time()
        if server.DEBUG & server.DBG_MORE:
            print('    args', repr(args))
            print('    cache key', cachekey)
            print('    solutions', ','.join(str(s.solutions)
                                            for s in union.children))
    # return true so it can be used as assertion (and so be killed by python -O)
    return True


def dbg_results(results):
    if server.DEBUG & server.DBG_RQL:
        if len(results) > 10:
            print('  -->', results[:10], '...', len(results), end=' ')
        else:
            print('  -->', results, end=' ')
        print('time: ', time() - t)
    # return true so it can be used as assertion (and so be killed by python -O)
    return True


class AbstractSource(object):
    """an abstract class for sources"""

    # boolean telling if the repository should connect to this source during
    # migration
    connect_for_migration = True

    # a global identifier for this source, which has to be set by the source
    # instance
    uri = None
    # a reference to the system information helper
    repo = None
    # a reference to the instance'schema (may differs from the source'schema)
    schema = None

    # force deactivation (configuration error for instance)
    disabled = False

    # boolean telling if cwuri of entities from this source is the url that
    # should be used as entity's absolute url
    use_cwuri_as_url = False

    # source configuration options
    options = ()

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg, *a, **kw: None

    def __init__(self, repo, source_config, eid=None):
        self.repo = repo
        self.set_schema(repo.schema)
        self.eid = eid
        self.public_config = source_config.copy()
        self.public_config['use-cwuri-as-url'] = self.use_cwuri_as_url
        self.remove_sensitive_information(self.public_config)
        self.uri = source_config.pop('uri')
        # unormalize to avoid non-ascii characters in logger's name, this will cause decoding error
        # on logging
        set_log_methods(self, getLogger('cubicweb.sources.' + unormalize(self.uri)))
        source_config.pop('type')
        self.config = self._check_config_dict(
            eid, source_config, raise_on_error=False)

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

    def __ne__(self, other):
        return not (self == other)

    def backup(self, backupfile, confirm, format='native'):
        """method called to create a backup of source's data"""
        pass

    def restore(self, backupfile, confirm, drop, format='native'):
        """method called to restore a backup of source's data"""
        pass

    def _check_config_dict(self, eid, confdict, raise_on_error=True):
        """Check configuration of source entity and return config dict properly
        typed with defaults set.

        If `raise_on_error` is True (the default), a ValidationError will be
        raised if some error is encountered, else the problem will be ignored.
        """
        processed = {}
        for optname, optdict in self.options:
            value = confdict.pop(optname, optdict.get('default'))
            if value is configuration.REQUIRED:
                if not raise_on_error:
                    continue
                msg = _('specifying %s is mandatory')
                msgargs = optname
                raise ValidationError(eid, {role_name('config', 'subject'): msg}, msgargs)
            elif value is not None:
                # type check
                try:
                    value = configuration._validate(value, optdict, optname)
                except Exception as ex:
                    if not raise_on_error:
                        continue
                    msg = str(ex)
                    raise ValidationError(eid, {role_name('config', 'subject'): msg})
            processed[optname] = value
        # cw < 3.10 bw compat
        try:
            processed['adapter'] = confdict['adapter']
        except KeyError:
            pass
        # check for unknown options
        if confdict and tuple(confdict) != ('adapter',):
            if raise_on_error:
                msg = _('unknown options %s')
                msgargs = ', '.join(confdict)
                raise ValidationError(eid, {role_name('config', 'subject'): msg}, msgargs)
            else:
                self.warning('unknown options %s', ', '.join(confdict))
                # add options to processed, they may be necessary during migration
                processed.update(confdict)
        return processed

    def check_config(self, source_entity):
        """Check configuration of source entity, raise ValidationError if some
        errors are detected.
        """
        return self._check_config_dict(source_entity.eid, source_entity.dictconfig)

    def check_urls(self, source_entity):
        """Check URL of source entity: `urls` is a string that may contain one
        URL per line), and return a list of at least one validated URL.
        """
        urls = source_entity.url if source_entity.url else ''
        urls = [url.strip() for url in urls.splitlines() if url.strip()]
        if not urls:
            msg = _('specifying an URL is mandatory')
            raise ValidationError(source_entity.eid, {role_name('url', 'subject'): msg})
        return urls

    # source initialization / finalization #####################################

    def set_schema(self, schema):
        """set the instance'schema"""
        self.schema = schema

    def init_creating(self):
        """method called by the repository once ready to create a new instance"""
        pass

    def init(self, source_entity):
        """method called by the repository once ready to handle request.
        `activated` is a boolean flag telling if the source is activated or not.
        """
        source_entity.complete()
        if source_entity.url:
            self.urls = self.check_urls(source_entity)
        else:
            self.urls = []

    PUBLIC_KEYS = ('type', 'uri', 'use-cwuri-as-url')

    def remove_sensitive_information(self, sourcedef):
        """remove sensitive information such as login / password from source
        definition
        """
        for key in list(sourcedef):
            if key not in self.PUBLIC_KEYS:
                sourcedef.pop(key)

    # connections handling #####################################################

    def get_connection(self):
        """open and return a connection to the source"""
        raise NotImplementedError(self)

    def close_source_connections(self):
        for cnxset in self.repo.cnxsets:
            cnxset.cu = None
            cnxset.cnx.close()

    def open_source_connections(self):
        for cnxset in self.repo.cnxsets:
            cnxset.cnx = self.get_connection()
            cnxset.cu = cnxset.cnx.cursor()

    # user authentication api ##################################################

    def authenticate(self, cnx, login, **kwargs):
        """if the source support CWUser entity type, it should implement
        this method which should return CWUser eid for the given login/password
        if this account is defined in this source and valid login / password is
        given. Else raise `AuthenticationError`
        """
        raise NotImplementedError(self)

    # RQL query api ############################################################

    def syntax_tree_search(self, cnx, union,
                           args=None, cachekey=None, debug=0):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        raise NotImplementedError(self)

    # write modification api ###################################################
    # read-only sources don't have to implement methods below

    def add_entity(self, cnx, entity):
        """add a new entity to the source"""
        raise NotImplementedError(self)

    def update_entity(self, cnx, entity):
        """update an entity in the source"""
        raise NotImplementedError(self)

    def delete_entities(self, cnx, entities):
        """delete several entities from the source"""
        for entity in entities:
            self.delete_entity(cnx, entity)

    def delete_entity(self, cnx, entity):
        """delete an entity from the source"""
        raise NotImplementedError(self)

    def add_relation(self, cnx, subject, rtype, object):
        """add a relation to the source"""
        raise NotImplementedError(self)

    def add_relations(self, cnx, rtype, subj_obj_list):
        """add a relations to the source"""
        # override in derived classes if you feel you can
        # optimize
        for subject, object in subj_obj_list:
            self.add_relation(cnx, subject, rtype, object)

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        raise NotImplementedError(self)

    # system source interface #################################################

    def eid_type(self, cnx, eid):
        """Return the type of entity `eid`."""
        raise NotImplementedError(self)

    def create_eid(self, cnx):
        raise NotImplementedError(self)

    def add_info(self, cnx, entity, source):
        """add type and source info for an eid into the system table"""
        raise NotImplementedError(self)

    def update_info(self, cnx, entity, need_fti_update):
        """mark entity as being modified, fulltext reindex if needed"""
        raise NotImplementedError(self)

    def index_entity(self, cnx, entity):
        """create an operation to [re]index textual content of the given entity
        on commit
        """
        raise NotImplementedError(self)

    def fti_unindex_entities(self, cnx, entities):
        """remove text content for entities from the full text index
        """
        raise NotImplementedError(self)

    def fti_index_entities(self, cnx, entities):
        """add text content of created/modified entities to the full text index
        """
        raise NotImplementedError(self)

    # sql system source interface #############################################

    def sqlexec(self, cnx, sql, args=None):
        """execute the query and return its result"""
        raise NotImplementedError(self)

    def create_index(self, cnx, table, column, unique=False):
        raise NotImplementedError(self)

    def drop_index(self, cnx, table, column, unique=False):
        raise NotImplementedError(self)


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
