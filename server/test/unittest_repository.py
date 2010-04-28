# -*- coding: iso-8859-1 -*-
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
"""unit tests for module cubicweb.server.repository

"""
from __future__ import with_statement

from __future__ import with_statement

import os
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime

from logilab.common.testlib import TestCase, unittest_main

from yams.constraints import UniqueConstraint

from cubicweb import (BadConnectionId, RepositoryError, ValidationError,
                      UnknownEid, AuthenticationError)
from cubicweb.selectors import implements
from cubicweb.schema import CubicWebSchema, RQLConstraint
from cubicweb.dbapi import connect, multiple_connections_unfix
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.repotest import tuplify
from cubicweb.server import repository, hook
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.hook import Hook
from cubicweb.server.sources import native

# start name server anyway, process will fail if already running
os.system('pyro-ns >/dev/null 2>/dev/null &')


class RepositoryTC(CubicWebTC):
    """ singleton providing access to a persistent storage for entities
    and relation
    """

    def test_fill_schema(self):
        origshema = self.repo.schema
        try:
            self.repo.schema = CubicWebSchema(self.repo.config.appid)
            self.repo.config._cubes = None # avoid assertion error
            self.repo.config.repairing = True # avoid versions checking
            self.repo.fill_schema()
            table = SQL_PREFIX + 'CWEType'
            namecol = SQL_PREFIX + 'name'
            finalcol = SQL_PREFIX + 'final'
            self.session.set_pool()
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
            self.repo.set_schema(origshema)

    def test_schema_has_owner(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.failIf(repo.execute(cnxid, 'CWEType X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWRType X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWAttribute X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWRelation X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWConstraint X WHERE NOT X owned_by U'))
        self.failIf(repo.execute(cnxid, 'CWConstraintType X WHERE NOT X owned_by U'))

    def test_connect(self):
        self.assert_(self.repo.connect(self.admlogin, password=self.admpassword))
        self.assertRaises(AuthenticationError,
                          self.repo.connect, self.admlogin, password='nimportnawak')
        self.assertRaises(AuthenticationError,
                          self.repo.connect, self.admlogin, password=None)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, None, password=None)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, self.admlogin)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, None)

    def test_execute(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        repo.execute(cnxid, 'Any X')
        repo.execute(cnxid, 'Any X where X is Personne')
        repo.execute(cnxid, 'Any X where X is Personne, X nom ~= "to"')
        repo.execute(cnxid, 'Any X WHERE X has_text %(text)s', {'text': u'\xe7a'})
        repo.close(cnxid)

    def test_login_upassword_accent(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        repo.execute(cnxid, 'INSERT CWUser X: X login %(login)s, X upassword %(passwd)s, X in_group G WHERE G name "users"',
                     {'login': u"barnabé", 'passwd': u"héhéhé".encode('UTF8')})
        repo.commit(cnxid)
        repo.close(cnxid)
        self.assert_(repo.connect(u"barnabé", password=u"héhéhé".encode('UTF8')))

    def test_invalid_entity_rollback(self):
        cnxid = self.repo.connect(self.admlogin, password=self.admpassword)
        # no group
        self.repo.execute(cnxid,
                          'INSERT CWUser X: X login %(login)s, X upassword %(passwd)s',
                          {'login': u"tutetute", 'passwd': 'tutetute'})
        self.assertRaises(ValidationError, self.repo.commit, cnxid)
        self.failIf(self.repo.execute(cnxid, 'CWUser X WHERE X login "tutetute"'))

    def test_close(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.assert_(cnxid)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.execute, cnxid, 'Any X')

    def test_invalid_cnxid(self):
        self.assertRaises(BadConnectionId, self.repo.execute, 0, 'Any X')
        self.assertRaises(BadConnectionId, self.repo.close, None)

    def test_shared_data(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        repo.set_shared_data(cnxid, 'data', 4)
        cnxid2 = repo.connect(self.admlogin, password=self.admpassword)
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
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.assertEquals(repo.check_session(cnxid), None)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.check_session, cnxid)

    def test_transaction_base(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
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
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        # rollback relation insertion
        repo.execute(cnxid, "SET U in_group G WHERE U login 'admin', G name 'guests'")
        result = repo.execute(cnxid, "Any U WHERE U in_group G, U login 'admin', G name 'guests'")
        self.assertEquals(result.rowcount, 1)
        repo.rollback(cnxid)
        result = repo.execute(cnxid, "Any U WHERE U in_group G, U login 'admin', G name 'guests'")
        self.assertEquals(result.rowcount, 0, result.rows)

    def test_transaction_base3(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        # rollback state change which trigger TrInfo insertion
        session = repo._get_session(cnxid)
        session.set_pool()
        user = session.user
        user.fire_transition('deactivate')
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': user.eid})
        self.assertEquals(len(rset), 1)
        repo.rollback(cnxid)
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': user.eid})
        self.assertEquals(len(rset), 0)

    def test_transaction_interleaved(self):
        self.skip('implement me')

    def test_close_wait_processing_request(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
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
                                                 'owned_by', 'created_by',
                                                 'update_permission', 'read_permission')],
                              ['relation_type',
                               'from_entity', 'to_entity',
                               'in_basket', 'constrained_by', 
                               'cardinality', 'ordernum',
                               'indexed', 'fulltextindexed', 'internationalizable',
                               'defaultval', 'description', 'description_format'])

        self.assertEquals(schema.eschema('CWEType').main_attribute(), 'name')
        self.assertEquals(schema.eschema('State').main_attribute(), 'name')

        constraints = schema.rschema('name').rdef('CWEType', 'String').constraints
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

        constraints = schema.rschema('relation_type').rdef('CWAttribute', 'CWRType').constraints
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
            from logilab.common import pyro_ext
            pyro_ext._DAEMONS.clear()


    def _pyro_client(self, done):
        cnx = connect(self.repo.config.appid, u'admin', password='gingkow',
                      initlog=False) # don't reset logging configuration
        try:
            # check we can get the schema
            schema = cnx.get_schema()
            self.assertEquals(schema.__hashmode__, None)
            cu = cnx.cursor()
            rset = cu.execute('Any U,G WHERE U in_group G')
            cnx.close()
            done.append(True)
        finally:
            # connect monkey patch some method by default, remove them
            multiple_connections_unfix()

    def test_internal_api(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
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
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.assertEquals(repo.user_info(cnxid), (5, 'admin', set([u'managers']), {}))
        self.assertEquals(repo.describe(cnxid, 1), (u'CWGroup', u'system', None))
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.user_info, cnxid)
        self.assertRaises(BadConnectionId, repo.describe, cnxid, 1)

    def test_shared_data_api(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
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

    def test_delete_if_singlecard1(self):
        note = self.request().create_entity('Affaire')
        p1 = self.request().create_entity('Personne', nom=u'toto')
        self.execute('SET A todo_by P WHERE A eid %(x)s, P eid %(p)s',
                     {'x': note.eid, 'p': p1.eid})
        rset = self.execute('Any P WHERE A todo_by P, A eid %(x)s',
                            {'x': note.eid})
        self.assertEquals(len(rset), 1)
        p2 = self.request().create_entity('Personne', nom=u'tutu')
        self.execute('SET A todo_by P WHERE A eid %(x)s, P eid %(p)s',
                     {'x': note.eid, 'p': p2.eid})
        rset = self.execute('Any P WHERE A todo_by P, A eid %(x)s',
                            {'x': note.eid})
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.rows[0][0], p2.eid)


    def test_set_attributes_in_before_update(self):
        # local hook
        class DummyBeforeHook(Hook):
            __regid__ = 'dummy-before-hook'
            __select__ = Hook.__select__ & implements('EmailAddress')
            events = ('before_update_entity',)
            def __call__(self):
                # safety belt: avoid potential infinite recursion if the test
                #              fails (i.e. RuntimeError not raised)
                pendings = self._cw.transaction_data.setdefault('pending', set())
                if self.entity.eid not in pendings:
                    pendings.add(self.entity.eid)
                    self.entity.set_attributes(alias=u'foo')
        with self.temporary_appobjects(DummyBeforeHook):
            req = self.request()
            addr = req.create_entity('EmailAddress', address=u'a@b.fr')
            addr.set_attributes(address=u'a@b.com')
            rset = self.execute('Any A,AA WHERE X eid %(x)s, X address A, X alias AA',
                                {'x': addr.eid})
            self.assertEquals(rset.rows, [[u'a@b.com', u'foo']])

    def test_set_attributes_in_before_add(self):
        # local hook
        class DummyBeforeHook(Hook):
            __regid__ = 'dummy-before-hook'
            __select__ = Hook.__select__ & implements('EmailAddress')
            events = ('before_add_entity',)
            def __call__(self):
                # set_attributes is forbidden within before_add_entity()
                self.entity.set_attributes(alias=u'foo')
        with self.temporary_appobjects(DummyBeforeHook):
            req = self.request()
            # XXX will fail with python -O
            self.assertRaises(AssertionError, req.create_entity,
                              'EmailAddress', address=u'a@b.fr')

    def test_multiple_edit_set_attributes(self):
        """make sure edited_attributes doesn't get cluttered
        by previous entities on multiple set
        """
        # local hook
        class DummyBeforeHook(Hook):
            _test = self # keep reference to test instance
            __regid__ = 'dummy-before-hook'
            __select__ = Hook.__select__ & implements('Affaire')
            events = ('before_update_entity',)
            def __call__(self):
                # invoiced attribute shouldn't be considered "edited" before the hook
                self._test.failIf('invoiced' in self.entity.edited_attributes,
                                  'edited_attributes cluttered by previous update')
                self.entity['invoiced'] = 10
        with self.temporary_appobjects(DummyBeforeHook):
            req = self.request()
            req.create_entity('Affaire', ref=u'AFF01')
            req.create_entity('Affaire', ref=u'AFF02')
            req.execute('SET A duration 10 WHERE A is Affaire')


class DataHelpersTC(CubicWebTC):

    def test_create_eid(self):
        self.session.set_pool()
        self.assert_(self.repo.system_source.create_eid(self.session))

    def test_source_from_eid(self):
        self.session.set_pool()
        self.assertEquals(self.repo.source_from_eid(1, self.session),
                          self.repo.sources_by_uri['system'])

    def test_source_from_eid_raise(self):
        self.session.set_pool()
        self.assertRaises(UnknownEid, self.repo.source_from_eid, -2, self.session)

    def test_type_from_eid(self):
        self.session.set_pool()
        self.assertEquals(self.repo.type_from_eid(1, self.session), 'CWGroup')

    def test_type_from_eid_raise(self):
        self.session.set_pool()
        self.assertRaises(UnknownEid, self.repo.type_from_eid, -2, self.session)

    def test_add_delete_info(self):
        entity = self.repo.vreg['etypes'].etype_class('Personne')(self.session)
        entity.eid = -1
        entity.complete = lambda x: None
        self.session.set_pool()
        self.repo.add_info(self.session, entity, self.repo.system_source)
        cu = self.session.system_sql('SELECT * FROM entities WHERE eid = -1')
        data = cu.fetchall()
        self.assertIsInstance(data[0][3], datetime)
        data[0] = list(data[0])
        data[0][3] = None
        self.assertEquals(tuplify(data), [(-1, 'Personne', 'system', None, None)])
        self.repo.delete_info(self.session, entity, 'system', None)
        #self.repo.commit()
        cu = self.session.system_sql('SELECT * FROM entities WHERE eid = -1')
        data = cu.fetchall()
        self.assertEquals(data, [])


class FTITC(CubicWebTC):

    def test_reindex_and_modified_since(self):
        self.repo.system_source.multisources_etypes.add('Personne')
        eidp = self.execute('INSERT Personne X: X nom "toto", X prenom "tutu"')[0][0]
        self.commit()
        ts = datetime.now()
        self.assertEquals(len(self.execute('Personne X WHERE X has_text "tutu"')), 1)
        self.session.set_pool()
        cu = self.session.system_sql('SELECT mtime, eid FROM entities WHERE eid = %s' % eidp)
        omtime = cu.fetchone()[0]
        # our sqlite datetime adapter is ignore seconds fraction, so we have to
        # ensure update is done the next seconds
        time.sleep(1 - (ts.second - int(ts.second)))
        self.execute('SET X nom "tata" WHERE X eid %(x)s', {'x': eidp})
        self.commit()
        self.assertEquals(len(self.execute('Personne X WHERE X has_text "tutu"')), 1)
        self.session.set_pool()
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

    def test_fulltext_container_entity(self):
        assert self.schema.rschema('use_email').fulltext_container == 'subject'
        req = self.request()
        toto = req.create_entity('EmailAddress', address=u'toto@logilab.fr')
        self.commit()
        rset = req.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
        self.assertEquals(rset.rows, [])
        req.user.set_relations(use_email=toto)
        self.commit()
        rset = req.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
        self.assertEquals(rset.rows, [[req.user.eid]])
        req.execute('DELETE X use_email Y WHERE X login "admin", Y eid %(y)s',
                    {'y': toto.eid})
        self.commit()
        rset = req.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
        self.assertEquals(rset.rows, [])
        tutu = req.create_entity('EmailAddress', address=u'tutu@logilab.fr')
        req.user.set_relations(use_email=tutu)
        self.commit()
        rset = req.execute('Any X WHERE X has_text %(t)s', {'t': 'tutu'})
        self.assertEquals(rset.rows, [[req.user.eid]])
        tutu.set_attributes(address=u'hip@logilab.fr')
        self.commit()
        rset = req.execute('Any X WHERE X has_text %(t)s', {'t': 'tutu'})
        self.assertEquals(rset.rows, [])
        rset = req.execute('Any X WHERE X has_text %(t)s', {'t': 'hip'})
        self.assertEquals(rset.rows, [[req.user.eid]])

    def test_no_uncessary_ftiindex_op(self):
        req = self.request()
        req.create_entity('Workflow', name=u'dummy workflow', description=u'huuuuu')
        self.failIf(any(x for x in self.session.pending_operations
                        if isinstance(x, native.FTIndexEntityOp)))


class DBInitTC(CubicWebTC):

    def test_versions_inserted(self):
        inserted = [r[0] for r in self.execute('Any K ORDERBY K WHERE P pkey K, P pkey ~= "system.version.%"')]
        self.assertEquals(inserted,
                          [u'system.version.basket', u'system.version.card', u'system.version.comment',
                           u'system.version.cubicweb', u'system.version.email',
                           u'system.version.file', u'system.version.folder',
                           u'system.version.tag'])

CALLED = []

class InlineRelHooksTC(CubicWebTC):
    """test relation hooks are called for inlined relations
    """
    def setUp(self):
        CubicWebTC.setUp(self)
        CALLED[:] = ()

    def _after_relation_hook(self, pool, fromeid, rtype, toeid):
        self.called.append((fromeid, rtype, toeid))

    def test_inline_relation(self):
        """make sure <event>_relation hooks are called for inlined relation"""
        class EcritParHook(hook.Hook):
            __regid__ = 'inlinedrelhook'
            __select__ = hook.Hook.__select__ & hook.match_rtype('ecrit_par')
            events = ('before_add_relation', 'after_add_relation',
                      'before_delete_relation', 'after_delete_relation')
            def __call__(self):
                CALLED.append((self.event, self.eidfrom, self.rtype, self.eidto))

        with self.temporary_appobjects(EcritParHook):
            eidp = self.execute('INSERT Personne X: X nom "toto"')[0][0]
            eidn = self.execute('INSERT Note X: X type "T"')[0][0]
            self.execute('SET N ecrit_par Y WHERE N type "T", Y nom "toto"')
            self.assertEquals(CALLED, [('before_add_relation', eidn, 'ecrit_par', eidp),
                                       ('after_add_relation', eidn, 'ecrit_par', eidp)])
            CALLED[:] = ()
            self.execute('DELETE N ecrit_par Y WHERE N type "T", Y nom "toto"')
            self.assertEquals(CALLED, [('before_delete_relation', eidn, 'ecrit_par', eidp),
                                       ('after_delete_relation', eidn, 'ecrit_par', eidp)])
            CALLED[:] = ()
            eidn = self.execute('INSERT Note N: N ecrit_par P WHERE P nom "toto"')[0][0]
            self.assertEquals(CALLED, [('before_add_relation', eidn, 'ecrit_par', eidp),
                                       ('after_add_relation', eidn, 'ecrit_par', eidp)])


if __name__ == '__main__':
    unittest_main()
