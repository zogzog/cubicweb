# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Adapter for google appengine source.

"""
__docformat__ = "restructuredtext en"

from cubicweb import AuthenticationError, UnknownEid
from cubicweb.server.sources import AbstractSource, ConnectionWrapper
from cubicweb.server.pool import SingleOperation
from cubicweb.server.utils import crypt_password
from cubicweb.goa.dbinit import set_user_groups
from cubicweb.goa.rqlinterpreter import RQLInterpreter

from google.appengine.api.datastore import Key, Entity, Put, Delete
from google.appengine.api import datastore_errors, users

def _init_groups(guser, euser):
    # set default groups
    if guser is None:
        groups = ['guests']
    else:
        groups = ['users']
        if users.is_current_user_admin():
            groups.append('managers')
    set_user_groups(euser, groups)

def _clear_related_cache(session, gaesubject, rtype, gaeobject):
    subject, object = str(gaesubject.key()), str(gaeobject.key())
    for eid, role in ((subject, 'subject'), (object, 'object')):
        # clear related cache if necessary
        try:
            entity = session.entity_cache(eid)
        except KeyError:
            pass
        else:
            entity.clear_related_cache(rtype, role)
    if gaesubject.kind() == 'CWUser':
        for asession in session.repo._sessions.itervalues():
            if asession.user.eid == subject:
                asession.user.clear_related_cache(rtype, 'subject')
    if gaeobject.kind() == 'CWUser':
        for asession in session.repo._sessions.itervalues():
            if asession.user.eid == object:
                asession.user.clear_related_cache(rtype, 'object')

def _mark_modified(session, gaeentity):
    modified = session.transaction_data.setdefault('modifiedentities', {})
    modified[str(gaeentity.key())] = gaeentity
    DatastorePutOp(session)

def _rinfo(session, subject, rtype, object):
    gaesubj = session.datastore_get(subject)
    gaeobj = session.datastore_get(object)
    rschema = session.vreg.schema.rschema(rtype)
    cards = rschema.rproperty(gaesubj.kind(), gaeobj.kind(), 'cardinality')
    return gaesubj, gaeobj, cards

def _radd(session, gaeentity, targetkey, relation, card):
    if card in '?1':
        gaeentity[relation] = targetkey
    else:
        try:
            related = gaeentity[relation]
        except KeyError:
            related = []
        else:
            if related is None:
                related = []
        related.append(targetkey)
        gaeentity[relation] = related
    _mark_modified(session, gaeentity)

def _rdel(session, gaeentity, targetkey, relation, card):
    if card in '?1':
        gaeentity[relation] = None
    else:
        related = gaeentity[relation]
        if related is not None:
            related = [key for key in related if not key == targetkey]
            gaeentity[relation] = related or None
    _mark_modified(session, gaeentity)


class DatastorePutOp(SingleOperation):
    """delayed put of entities to have less datastore write api calls

    * save all modified entities at precommit (should be the first operation
      processed, hence the 0 returned by insert_index())

    * in case others precommit operations modify some entities, resave modified
      entities at commit. This suppose that no db changes will occurs during
      commit event but it should be the case.
    """
    def insert_index(self):
        return 0

    def _put_entities(self):
        pending = self.session.transaction_data.get('pendingeids', ())
        modified = self.session.transaction_data.get('modifiedentities', {})
        for eid, gaeentity in modified.iteritems():
            assert not eid in pending
            Put(gaeentity)
        modified.clear()

    def commit_event(self):
        self._put_entities()

    def precommit_event(self):
        self._put_entities()


class GAESource(AbstractSource):
    """adapter for a system source on top of google appengine datastore"""

    passwd_rql = "Any P WHERE X is CWUser, X login %(login)s, X upassword P"
    auth_rql = "Any X WHERE X is CWUser, X login %(login)s, X upassword %(pwd)s"
    _sols = ({'X': 'CWUser', 'P': 'Password'},)

    options = ()

    def __init__(self, repo, appschema, source_config, *args, **kwargs):
        AbstractSource.__init__(self, repo, appschema, source_config,
                                *args, **kwargs)
        if repo.config['use-google-auth']:
            self.info('using google authentication service')
            self.authenticate = self.authenticate_gauth
        else:
            self.authenticate = self.authenticate_local

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        pass

    def init_creating(self):
        pass

    def init(self):
        # XXX unregister unsupported hooks
        from cubicweb.server.hooks import sync_owner_after_add_composite_relation
        self.repo.hm.unregister_hook(sync_owner_after_add_composite_relation,
                                     'after_add_relation', '')

    def get_connection(self):
        return ConnectionWrapper()

    # ISource interface #######################################################

    def compile_rql(self, rql):
        rqlst = self.repo.vreg.parse(rql)
        rqlst.restricted_vars = ()
        rqlst.children[0].solutions = self._sols
        return rqlst

    def set_schema(self, schema):
        """set the instance'schema"""
        self.interpreter = RQLInterpreter(schema)
        self.schema = schema
        if 'CWUser' in schema and not self.repo.config['use-google-auth']:
            # rql syntax trees used to authenticate users
            self._passwd_rqlst = self.compile_rql(self.passwd_rql)
            self._auth_rqlst = self.compile_rql(self.auth_rql)

    def support_entity(self, etype, write=False):
        """return true if the given entity's type is handled by this adapter
        if write is true, return true only if it's a RW support
        """
        return True

    def support_relation(self, rtype, write=False):
        """return true if the given relation's type is handled by this adapter
        if write is true, return true only if it's a RW support
        """
        return True

    def authenticate_gauth(self, session, login, password):
        guser = users.get_current_user()
        # allowing or not anonymous connection should be done in the app.yaml
        # file, suppose it's authorized if we are there
        if guser is None:
            login = u'anonymous'
        else:
            login = unicode(guser.nickname())
        # XXX http://code.google.com/appengine/docs/users/userobjects.html
        # use a reference property to automatically work with email address
        # changes after the propagation feature is implemented
        key = Key.from_path('CWUser', 'key_' + login, parent=None)
        try:
            euser = session.datastore_get(key)
            # XXX fix user. Required until we find a better way to fix broken records
            if not euser.get('s_in_group'):
                _init_groups(guser, euser)
                Put(euser)
            return str(key)
        except datastore_errors.EntityNotFoundError:
            # create a record for this user
            euser = Entity('CWUser', name='key_' + login)
            euser['s_login'] = login
            _init_groups(guser, euser)
            Put(euser)
            return str(euser.key())

    def authenticate_local(self, session, login, password):
        """return CWUser eid for the given login/password if this account is
        defined in this source, else raise `AuthenticationError`

        two queries are needed since passwords are stored crypted, so we have
        to fetch the salt first
        """
        args = {'login': login, 'pwd' : password}
        if password is not None:
            rset = self.syntax_tree_search(session, self._passwd_rqlst, args)
            try:
                pwd = rset[0][0]
            except IndexError:
                raise AuthenticationError('bad login')
            # passwords are stored using the bytea type, so we get a StringIO
            if pwd is not None:
                args['pwd'] = crypt_password(password, pwd[:2])
        # get eid from login and (crypted) password
        rset = self.syntax_tree_search(session, self._auth_rqlst, args)
        try:
            return rset[0][0]
        except IndexError:
            raise AuthenticationError('bad password')

    def syntax_tree_search(self, session, union, args=None, cachekey=None,
                           varmap=None):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        results, description = self.interpreter.interpret(union, args,
                                                          session.datastore_get)
        return results # XXX description

    def flying_insert(self, table, session, union, args=None, varmap=None):
        raise NotImplementedError

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        # do not delay add_entity as other modifications, new created entity
        # needs an eid
        entity.put()

    def update_entity(self, session, entity):
        """replace an entity in the source"""
        gaeentity = entity.to_gae_model()
        _mark_modified(session, entity.to_gae_model())
        if gaeentity.kind() == 'CWUser':
            for asession in self.repo._sessions.itervalues():
                if asession.user.eid == entity.eid:
                    asession.user.update(dict(gaeentity))

    def delete_entity(self, session, entity):
        """delete an entity from the source"""
        # do not delay delete_entity as other modifications to ensure
        # consistency
        eid = entity.eid
        key = Key(eid)
        Delete(key)
        session.clear_datastore_cache(key)
        session.drop_entity_cache(eid)
        session.transaction_data.get('modifiedentities', {}).pop(eid, None)

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        gaesubj, gaeobj, cards = _rinfo(session, subject, rtype, object)
        _radd(session, gaesubj, gaeobj.key(), 's_' + rtype, cards[0])
        _radd(session, gaeobj, gaesubj.key(), 'o_' + rtype, cards[1])
        _clear_related_cache(session, gaesubj, rtype, gaeobj)

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        gaesubj, gaeobj, cards = _rinfo(session, subject, rtype, object)
        pending = session.transaction_data.setdefault('pendingeids', set())
        if not subject in pending:
            _rdel(session, gaesubj, gaeobj.key(), 's_' + rtype, cards[0])
        if not object in pending:
            _rdel(session, gaeobj, gaesubj.key(), 'o_' + rtype, cards[1])
        _clear_related_cache(session, gaesubj, rtype, gaeobj)

    # system source interface #################################################

    def eid_type_source(self, session, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        try:
            key = Key(eid)
        except datastore_errors.BadKeyError:
            raise UnknownEid(eid)
        return key.kind(), 'system', None

    def create_eid(self, session):
        return None # let the datastore generating key

    def add_info(self, session, entity, source, extid=None):
        """add type and source info for an eid into the system table"""
        pass

    def delete_info(self, session, eid, etype, uri, extid):
        """delete system information on deletion of an entity by transfering
        record from the entities table to the deleted_entities table
        """
        pass

    def fti_unindex_entity(self, session, eid):
        """remove text content for entity with the given eid from the full text
        index
        """
        pass

    def fti_index_entity(self, session, entity):
        """add text content of a created/modified entity to the full text index
        """
        pass
