# -*- coding: iso-8859-1 -*-
"""unit tests for module cubicweb.server.repository

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import os
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime

from logilab.common.testlib import TestCase, unittest_main

from yams.constraints import UniqueConstraint

from cubicweb import BadConnectionId, RepositoryError, ValidationError, UnknownEid, AuthenticationError
from cubicweb.schema import CubicWebSchema, RQLConstraint
from cubicweb.dbapi import connect, repo_connect
from cubicweb.devtools.apptest import RepositoryBasedTC
from cubicweb.devtools.repotest import tuplify
from cubicweb.server import repository
from cubicweb.server.sqlutils import SQL_PREFIX


# start name server anyway, process will fail if already running
os.system('pyro-ns >/dev/null 2>/dev/null &')


class RepositoryTC(RepositoryBasedTC):
    """ singleton providing access to a persistent storage for entities
    and relation
    """

#     def setUp(self):
#         pass

#     def tearDown(self):
#         self.repo.config.db_perms = True
#         cnxid = self.repo.connect(*self.default_user_password())
#         for etype in ('Affaire', 'Note', 'Societe', 'Personne'):
#             self.repo.execute(cnxid, 'DELETE %s X' % etype)
#             self.repo.commit(cnxid)
#         self.repo.close(cnxid)

    def test_fill_schema(self):
        self.repo.schema = CubicWebSchema(self.repo.config.appid)
        self.repo.config._cubes = None # avoid assertion error
        self.repo.fill_schema()
        pool = self.repo._get_pool()
        table = SQL_PREFIX + 'CWEType'
        namecol = SQL_PREFIX + 'name'
        finalcol = SQL_PREFIX + 'final'
        try:
            cu = self.session.system_sql('SELECT %s FROM %s WHERE %s is NULL' % (
                namecol, table, finalcol))
            self.assertEquals(cu.fetchall(), [])
            cu = self.session.system_sql('SELECT %s FROM %s WHERE %s=%%(final)s ORDER BY %s'
                              % (namecol, table, finalcol, namecol), {'final': 'TRUE'})
            self.assertEquals(cu.fetchall(), [(u'Boolean',), (u'Bytes',),
                                                     (u'Date',), (u'Datetime',),
                                                     (u'Decimal',),(u'Float',),
                                                     (u'Int',),
                                                     (u'Interval',), (u'Password',),
                                                     (u'String',), (u'Time',)])
        finally:
            self.repo._free_pool(pool)

    def test_schema_has_owner(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        self.failIf(repo.execute(cnxid, 'CWEType X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWRType X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWAttribute X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWRelation X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWConstraint X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWConstraintType X WHERE NOT X owned_by U'))

    def test_connect(self):
        login, passwd = self.default_user_password()
        self.assert_(self.repo.connect(login, passwd))
        self.assertRaises(AuthenticationError,
                          self.repo.connect, login, 'nimportnawak')
        self.assertRaises(AuthenticationError,
                          self.repo.connect, login, None)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, None, None)

    def test_execute(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        repo.execute(cnxid, 'Any X')
        repo.execute(cnxid, 'Any X where X is Personne')
        repo.execute(cnxid, 'Any X where X is Personne, X nom ~= "to"')
        repo.execute(cnxid, 'Any X WHERE X has_text %(text)s', {'text': u'\xe7a'})
        repo.close(cnxid)

    def test_login_upassword_accent(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        repo.execute(cnxid, 'INSERT CWUser X: X login %(login)s, X upassword %(passwd)s, X in_state S, X in_group G WHERE S name "activated", G name "users"',
                     {'login': u"barnabé", 'passwd': u"héhéhé".encode('UTF8')})
        repo.commit(cnxid)
        repo.close(cnxid)
        self.assert_(repo.connect(u"barnabé", u"héhéhé".encode('UTF8')))

    def test_invalid_entity_rollback(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        # no group
        repo.execute(cnxid, 'INSERT CWUser X: X login %(login)s, X upassword %(passwd)s, X in_state S WHERE S name "activated"',
                     {'login': u"tutetute", 'passwd': 'tutetute'})
        self.assertRaises(ValidationError, repo.commit, cnxid)
        rset = repo.execute(cnxid, 'CWUser X WHERE X login "tutetute"')
        self.assertEquals(rset.rowcount, 0)

    def test_close(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        self.assert_(cnxid)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.execute, cnxid, 'Any X')

    def test_invalid_cnxid(self):
        self.assertRaises(BadConnectionId, self.repo.execute, 0, 'Any X')
        self.assertRaises(BadConnectionId, self.repo.close, None)

    def test_shared_data(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        repo.set_shared_data(cnxid, 'data', 4)
        cnxid2 = repo.connect(*self.default_user_password())
        self.assertEquals(repo.get_shared_data(cnxid, 'data'), 4)
        self.assertEquals(repo.get_shared_data(cnxid2, 'data'), None)
        repo.set_shared_data(cnxid2, 'data', 5)
        self.assertEquals(repo.get_shared_data(cnxid, 'data'), 4)
        self.assertEquals(repo.get_shared_data(cnxid2, 'data'), 5)
        repo.get_shared_data(cnxid2, 'data', pop=True)
        self.assertEquals(repo.get_shared_data(cnxid, 'data'), 4)
        self.assertEquals(repo.get_shared_data(cnxid2, 'data'), None)
        repo.close(cnxid)
        repo.close(cnxid2)
        self.assertRaises(BadConnectionId, repo.get_shared_data, cnxid, 'data')
        self.assertRaises(BadConnectionId, repo.get_shared_data, cnxid2, 'data')
        self.assertRaises(BadConnectionId, repo.set_shared_data, cnxid, 'data', 1)
        self.assertRaises(BadConnectionId, repo.set_shared_data, cnxid2, 'data', 1)

    def test_check_session(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        self.assertEquals(repo.check_session(cnxid), None)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.check_session, cnxid)

    def test_transaction_base(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        # check db state
        result = repo.execute(cnxid, 'Personne X')
        self.assertEquals(result.rowcount, 0)
        # rollback entity insertion
        repo.execute(cnxid, "INSERT Personne X: X nom 'bidule'")
        result = repo.execute(cnxid, 'Personne X')
        self.assertEquals(result.rowcount, 1)
        repo.rollback(cnxid)
        result = repo.execute(cnxid, 'Personne X')
        self.assertEquals(result.rowcount, 0, result.rows)
        # commit
        repo.execute(cnxid, "INSERT Personne X: X nom 'bidule'")
        repo.commit(cnxid)
        result = repo.execute(cnxid, 'Personne X')
        self.assertEquals(result.rowcount, 1)

    def test_transaction_base2(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        # rollback relation insertion
        repo.execute(cnxid, "SET U in_group G WHERE U login 'admin', G name 'guests'")
        result = repo.execute(cnxid, "Any U WHERE U in_group G, U login 'admin', G name 'guests'")
        self.assertEquals(result.rowcount, 1)
        repo.rollback(cnxid)
        result = repo.execute(cnxid, "Any U WHERE U in_group G, U login 'admin', G name 'guests'")
        self.assertEquals(result.rowcount, 0, result.rows)

    def test_transaction_base3(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        # rollback state change which trigger TrInfo insertion
        ueid = repo._get_session(cnxid).user.eid
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': ueid})
        self.assertEquals(len(rset), 1)
        repo.execute(cnxid, 'SET X in_state S WHERE X eid %(x)s, S name "deactivated"',
                     {'x': ueid}, 'x')
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': ueid})
        self.assertEquals(len(rset), 2)
        repo.rollback(cnxid)
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': ueid})
        self.assertEquals(len(rset), 1)

    def test_transaction_interleaved(self):
        self.skip('implement me')

    def test_close_wait_processing_request(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        repo.execute(cnxid, 'INSERT CWUser X: X login "toto", X upassword "tutu", X in_group G WHERE G name "users"')
        repo.commit(cnxid)
        # close has to be in the thread due to sqlite limitations
        def close_in_a_few_moment():
            time.sleep(0.1)
            repo.close(cnxid)
        t = threading.Thread(target=close_in_a_few_moment)
        t.start()
        try:
            repo.execute(cnxid, 'DELETE CWUser X WHERE X login "toto"')
            repo.commit(cnxid)
        finally:
            t.join()

    def test_initial_schema(self):
        schema = self.repo.schema
        # check order of attributes is respected
        self.assertListEquals([r.type for r in schema.eschema('CWAttribute').ordered_relations()
                               if not r.type in ('eid', 'is', 'is_instance_of', 'identity',
                                                 'creation_date', 'modification_date', 'cwuri',
                                                 'owned_by', 'created_by')],
                              ['relation_type', 'from_entity', 'in_basket', 'to_entity', 'constrained_by',
                               'cardinality', 'ordernum',
                               'indexed', 'fulltextindexed', 'internationalizable',
                               'defaultval', 'description', 'description_format'])

        self.assertEquals(schema.eschema('CWEType').main_attribute(), 'name')
        self.assertEquals(schema.eschema('State').main_attribute(), 'name')

        constraints = schema.rschema('name').rproperty('CWEType', 'String', 'constraints')
        self.assertEquals(len(constraints), 2)
        for cstr in constraints[:]:
            if isinstance(cstr, UniqueConstraint):
                constraints.remove(cstr)
                break
        else:
            self.fail('unique constraint not found')
        sizeconstraint = constraints[0]
        self.assertEquals(sizeconstraint.min, None)
        self.assertEquals(sizeconstraint.max, 64)

        constraints = schema.rschema('relation_type').rproperty('CWAttribute', 'CWRType', 'constraints')
        self.assertEquals(len(constraints), 1)
        cstr = constraints[0]
        self.assert_(isinstance(cstr, RQLConstraint))
        self.assertEquals(cstr.restriction, 'O final TRUE')

        ownedby = schema.rschema('owned_by')
        self.assertEquals(ownedby.objects('CWEType'), ('CWUser',))

    def test_pyro(self):
        import Pyro
        Pyro.config.PYRO_MULTITHREADED = 0
        done = []
        # the client part has to be in the thread due to sqlite limitations
        t = threading.Thread(target=self._pyro_client, args=(done,))
        try:
            daemon = self.repo.pyro_register()
            t.start()
            while not done:
                daemon.handleRequests(1.0)
            t.join(1)
            if t.isAlive():
                self.fail('something went wrong, thread still alive')
        finally:
            repository.pyro_unregister(self.repo.config)

    def _pyro_client(self, done):
        cnx = connect(self.repo.config.appid, u'admin', 'gingkow')
        # check we can get the schema
        schema = cnx.get_schema()
        self.assertEquals(schema.__hashmode__, None)
        cu = cnx.cursor()
        rset = cu.execute('Any U,G WHERE U in_group G')
        cnx.close()
        done.append(True)

    def test_internal_api(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        session = repo._get_session(cnxid, setpool=True)
        self.assertEquals(repo.type_and_source_from_eid(1, session),
                          ('CWGroup', 'system', None))
        self.assertEquals(repo.type_from_eid(1, session), 'CWGroup')
        self.assertEquals(repo.source_from_eid(1, session).uri, 'system')
        self.assertEquals(repo.eid2extid(repo.system_source, 1, session), None)
        class dummysource: uri = 'toto'
        self.assertRaises(UnknownEid, repo.eid2extid, dummysource, 1, session)

    def test_public_api(self):
        self.assertEquals(self.repo.get_schema(), self.repo.schema)
        self.assertEquals(self.repo.source_defs(), {'system': {'adapter': 'native', 'uri': 'system'}})
        # .properties() return a result set
        self.assertEquals(self.repo.properties().rql, 'Any K,V WHERE P is CWProperty,P pkey K, P value V, NOT P for_user U')

    def test_session_api(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        self.assertEquals(repo.user_info(cnxid), (5, 'admin', set([u'managers']), {}))
        self.assertEquals(repo.describe(cnxid, 1), (u'CWGroup', u'system', None))
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.user_info, cnxid)
        self.assertRaises(BadConnectionId, repo.describe, cnxid, 1)

    def test_shared_data_api(self):
        repo = self.repo
        cnxid = repo.connect(*self.default_user_password())
        self.assertEquals(repo.get_shared_data(cnxid, 'data'), None)
        repo.set_shared_data(cnxid, 'data', 4)
        self.assertEquals(repo.get_shared_data(cnxid, 'data'), 4)
        repo.get_shared_data(cnxid, 'data', pop=True)
        repo.get_shared_data(cnxid, 'whatever', pop=True)
        self.assertEquals(repo.get_shared_data(cnxid, 'data'), None)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.set_shared_data, cnxid, 'data', 0)
        self.assertRaises(BadConnectionId, repo.get_shared_data, cnxid, 'data')

    def test_schema_is_relation(self):
        no_is_rset = self.execute('Any X WHERE NOT X is ET')
        self.failIf(no_is_rset, no_is_rset.description)

#     def test_perfo(self):
#         self.set_debug(True)
#         from time import time, clock
#         t, c = time(), clock()
#         try:
#             self.create_user('toto')
#         finally:
#             self.set_debug(False)
#         print 'test time: %.3f (time) %.3f (cpu)' % ((time() - t), clock() - c)


class DataHelpersTC(RepositoryBasedTC):

    def setUp(self):
        """ called before each test from this class """
        cnxid = self.repo.connect(*self.default_user_password())
        self.session = self.repo._sessions[cnxid]
        self.session.set_pool()

    def tearDown(self):
        self.session.rollback()

    def test_create_eid(self):
        self.assert_(self.repo.system_source.create_eid(self.session))

    def test_source_from_eid(self):
        self.assertEquals(self.repo.source_from_eid(1, self.session),
                          self.repo.sources_by_uri['system'])

    def test_source_from_eid_raise(self):
        self.assertRaises(UnknownEid, self.repo.source_from_eid, -2, self.session)

    def test_type_from_eid(self):
        self.assertEquals(self.repo.type_from_eid(1, self.session), 'CWGroup')

    def test_type_from_eid_raise(self):
        self.assertRaises(UnknownEid, self.repo.type_from_eid, -2, self.session)

    def test_add_delete_info(self):
        entity = self.repo.vreg.etype_class('Personne')(self.session, None, None)
        entity.eid = -1
        entity.complete = lambda x: None
        self.repo.add_info(self.session, entity, self.repo.sources_by_uri['system'])
        cu = self.session.system_sql('SELECT * FROM entities WHERE eid = -1')
        data = cu.fetchall()
        self.assertIsInstance(data[0][3], datetime)
        data[0] = list(data[0])
        data[0][3] = None
        self.assertEquals(tuplify(data), [(-1, 'Personne', 'system', None, None)])
        self.repo.delete_info(self.session, -1)
        #self.repo.commit()
        cu = self.session.system_sql('SELECT * FROM entities WHERE eid = -1')
        data = cu.fetchall()
        self.assertEquals(data, [])


class FTITC(RepositoryBasedTC):

    def test_reindex_and_modified_since(self):
        eidp = self.execute('INSERT Personne X: X nom "toto", X prenom "tutu"')[0][0]
        self.commit()
        ts = datetime.now()
        self.assertEquals(len(self.execute('Personne X WHERE X has_text "tutu"')), 1)
        cu = self.session.system_sql('SELECT mtime, eid FROM entities WHERE eid = %s' % eidp)
        omtime = cu.fetchone()[0]
        # our sqlite datetime adapter is ignore seconds fraction, so we have to
        # ensure update is done the next seconds
        time.sleep(1 - (ts.second - int(ts.second)))
        self.execute('SET X nom "tata" WHERE X eid %(x)s', {'x': eidp}, 'x')
        self.commit()
        self.assertEquals(len(self.execute('Personne X WHERE X has_text "tutu"')), 1)
        cu = self.session.system_sql('SELECT mtime FROM entities WHERE eid = %s' % eidp)
        mtime = cu.fetchone()[0]
        self.failUnless(omtime < mtime)
        self.commit()
        date, modified, deleted = self.repo.entities_modified_since(('Personne',), omtime)
        self.assertEquals(modified, [('Personne', eidp)])
        self.assertEquals(deleted, [])
        date, modified, deleted = self.repo.entities_modified_since(('Personne',), mtime)
        self.assertEquals(modified, [])
        self.assertEquals(deleted, [])
        self.execute('DELETE Personne X WHERE X eid %(x)s', {'x': eidp})
        self.commit()
        date, modified, deleted = self.repo.entities_modified_since(('Personne',), omtime)
        self.assertEquals(modified, [])
        self.assertEquals(deleted, [('Personne', eidp)])

    def test_composite_entity(self):
        assert self.schema.rschema('use_email').fulltext_container == 'subject'
        eid = self.add_entity('EmailAddress', address=u'toto@logilab.fr').eid
        self.commit()
        rset = self.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
        self.assertEquals(rset.rows, [[eid]])
        self.execute('SET X use_email Y WHERE X login "admin", Y eid %(y)s', {'y': eid})
        self.commit()
        rset = self.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
        self.assertEquals(rset.rows, [[self.session.user.eid]])
        self.execute('DELETE X use_email Y WHERE X login "admin", Y eid %(y)s', {'y': eid})
        self.commit()
        rset = self.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
        self.assertEquals(rset.rows, [])
        eid = self.add_entity('EmailAddress', address=u'tutu@logilab.fr').eid
        self.execute('SET X use_email Y WHERE X login "admin", Y eid %(y)s', {'y': eid})
        self.commit()
        rset = self.execute('Any X WHERE X has_text %(t)s', {'t': 'tutu'})
        self.assertEquals(rset.rows, [[self.session.user.eid]])


class DBInitTC(RepositoryBasedTC):

    def test_versions_inserted(self):
        inserted = [r[0] for r in self.execute('Any K ORDERBY K WHERE P pkey K, P pkey ~= "system.version.%"')]
        self.assertEquals(inserted,
                          [u'system.version.basket', u'system.version.card', u'system.version.comment',
                           u'system.version.cubicweb', u'system.version.email',
                           u'system.version.file', u'system.version.folder',
                           u'system.version.tag'])

class InlineRelHooksTC(RepositoryBasedTC):
    """test relation hooks are called for inlined relations
    """
    def setUp(self):
        RepositoryBasedTC.setUp(self)
        self.hm = self.repo.hm
        self.called = []

    def _before_relation_hook(self, pool, fromeid, rtype, toeid):
        self.called.append((fromeid, rtype, toeid))

    def _after_relation_hook(self, pool, fromeid, rtype, toeid):
        self.called.append((fromeid, rtype, toeid))

    def test_before_add_inline_relation(self):
        """make sure before_<event>_relation hooks are called directly"""
        self.hm.register_hook(self._before_relation_hook,
                             'before_add_relation', 'ecrit_par')
        eidp = self.execute('INSERT Personne X: X nom "toto"')[0][0]
        eidn = self.execute('INSERT Note X: X type "T"')[0][0]
        self.execute('SET N ecrit_par Y WHERE N type "T", Y nom "toto"')
        self.assertEquals(self.called, [(eidn, 'ecrit_par', eidp)])

    def test_after_add_inline_relation(self):
        """make sure after_<event>_relation hooks are deferred"""
        self.hm.register_hook(self._after_relation_hook,
                             'after_add_relation', 'ecrit_par')
        eidp = self.execute('INSERT Personne X: X nom "toto"')[0][0]
        eidn = self.execute('INSERT Note X: X type "T"')[0][0]
        self.assertEquals(self.called, [])
        self.execute('SET N ecrit_par Y WHERE N type "T", Y nom "toto"')
        self.assertEquals(self.called, [(eidn, 'ecrit_par', eidp,)])

    def test_after_add_inline(self):
        """make sure after_<event>_relation hooks are deferred"""
        self.hm.register_hook(self._after_relation_hook,
                             'after_add_relation', 'in_state')
        eidp = self.execute('INSERT CWUser X: X login "toto", X upassword "tutu", X in_state S WHERE S name "activated"')[0][0]
        eids = self.execute('State X WHERE X name "activated"')[0][0]
        self.assertEquals(self.called, [(eidp, 'in_state', eids,)])

    def test_before_delete_inline_relation(self):
        """make sure before_<event>_relation hooks are called directly"""
        self.hm.register_hook(self._before_relation_hook,
                             'before_delete_relation', 'ecrit_par')
        eidp = self.execute('INSERT Personne X: X nom "toto"')[0][0]
        eidn = self.execute('INSERT Note X: X type "T"')[0][0]
        self.execute('SET N ecrit_par Y WHERE N type "T", Y nom "toto"')
        self.execute('DELETE N ecrit_par Y WHERE N type "T", Y nom "toto"')
        self.assertEquals(self.called, [(eidn, 'ecrit_par', eidp)])
        rset = self.execute('Any Y where N ecrit_par Y, N type "T", Y nom "toto"')
        # make sure the relation is really deleted
        self.failUnless(len(rset) == 0, "failed to delete inline relation")

    def test_after_delete_inline_relation(self):
        """make sure after_<event>_relation hooks are deferred"""
        self.hm.register_hook(self._after_relation_hook,
                             'after_delete_relation', 'ecrit_par')
        eidp = self.execute('INSERT Personne X: X nom "toto"')[0][0]
        eidn = self.execute('INSERT Note X: X type "T"')[0][0]
        self.execute('SET N ecrit_par Y WHERE N type "T", Y nom "toto"')
        self.assertEquals(self.called, [])
        self.execute('DELETE N ecrit_par Y WHERE N type "T", Y nom "toto"')
        self.assertEquals(self.called, [(eidn, 'ecrit_par', eidp,)])


if __name__ == '__main__':
    unittest_main()
