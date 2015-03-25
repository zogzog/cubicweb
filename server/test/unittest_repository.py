# -*- coding: iso-8859-1 -*-
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for module cubicweb.server.repository"""

import threading
import time
import logging

from yams.constraints import UniqueConstraint
from yams import register_base_type, unregister_base_type

from logilab.database import get_db_helper

from cubicweb import (BadConnectionId, ValidationError,
                      UnknownEid, AuthenticationError, Unauthorized, QueryError)
from cubicweb.predicates import is_instance
from cubicweb.schema import RQLConstraint
from cubicweb.dbapi import connect, multiple_connections_unfix
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.repotest import tuplify
from cubicweb.server import repository, hook
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.hook import Hook
from cubicweb.server.sources import native
from cubicweb.server.session import SessionClosedError


class RepositoryTC(CubicWebTC):
    """ singleton providing access to a persistent storage for entities
    and relation
    """

    def test_unique_together_constraint(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('INSERT Societe S: S nom "Logilab", S type "SSLL", S cp "75013"')
            with self.assertRaises(ValidationError) as wraperr:
                cnx.execute('INSERT Societe S: S nom "Logilab", S type "SSLL", S cp "75013"')
            self.assertEqual(
                {'cp': u'%(KEY-rtype)s is part of violated unicity constraint',
                 'nom': u'%(KEY-rtype)s is part of violated unicity constraint',
                 'type': u'%(KEY-rtype)s is part of violated unicity constraint',
                 '': u'some relations violate a unicity constraint'},
                wraperr.exception.args[1])

    def test_unique_together_schema(self):
        person = self.repo.schema.eschema('Personne')
        self.assertEqual(len(person._unique_together), 1)
        self.assertItemsEqual(person._unique_together[0],
                                           ('nom', 'prenom', 'inline2'))

    def test_all_entities_have_owner(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertFalse(cnx.execute('Any X WHERE NOT X owned_by U'))

    def test_all_entities_have_is(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertFalse(cnx.execute('Any X WHERE NOT X is ET'))

    def test_all_entities_have_cw_source(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertFalse(cnx.execute('Any X WHERE NOT X cw_source S'))

    def test_connect(self):
        cnxid = self.repo.connect(self.admlogin, password=self.admpassword)
        self.assert_(cnxid)
        self.repo.close(cnxid)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, self.admlogin, password='nimportnawak')
        self.assertRaises(AuthenticationError,
                          self.repo.connect, self.admlogin, password='')
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
        cnxid = repo.connect(u"barnabé", password=u"héhéhé".encode('UTF8'))
        self.assert_(cnxid)
        repo.close(cnxid)

    def test_rollback_on_commit_error(self):
        cnxid = self.repo.connect(self.admlogin, password=self.admpassword)
        self.repo.execute(cnxid,
                          'INSERT CWUser X: X login %(login)s, X upassword %(passwd)s',
                          {'login': u"tutetute", 'passwd': 'tutetute'})
        self.assertRaises(ValidationError, self.repo.commit, cnxid)
        self.assertFalse(self.repo.execute(cnxid, 'CWUser X WHERE X login "tutetute"'))
        self.repo.close(cnxid)

    def test_rollback_on_execute_validation_error(self):
        class ValidationErrorAfterHook(Hook):
            __regid__ = 'valerror-after-hook'
            __select__ = Hook.__select__ & is_instance('CWGroup')
            events = ('after_update_entity',)
            def __call__(self):
                raise ValidationError(self.entity.eid, {})

        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(ValidationErrorAfterHook):
                self.assertRaises(ValidationError,
                                  cnx.execute, 'SET X name "toto" WHERE X is CWGroup, X name "guests"')
                self.assertTrue(cnx.execute('Any X WHERE X is CWGroup, X name "toto"'))
                with self.assertRaises(QueryError) as cm:
                    cnx.commit()
                self.assertEqual(str(cm.exception), 'transaction must be rolled back')
                cnx.rollback()
                self.assertFalse(cnx.execute('Any X WHERE X is CWGroup, X name "toto"'))

    def test_rollback_on_execute_unauthorized(self):
        class UnauthorizedAfterHook(Hook):
            __regid__ = 'unauthorized-after-hook'
            __select__ = Hook.__select__ & is_instance('CWGroup')
            events = ('after_update_entity',)
            def __call__(self):
                raise Unauthorized()

        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(UnauthorizedAfterHook):
                self.assertRaises(Unauthorized,
                                  cnx.execute, 'SET X name "toto" WHERE X is CWGroup, X name "guests"')
                self.assertTrue(cnx.execute('Any X WHERE X is CWGroup, X name "toto"'))
                with self.assertRaises(QueryError) as cm:
                    cnx.commit()
                self.assertEqual(str(cm.exception), 'transaction must be rolled back')
                cnx.rollback()
                self.assertFalse(cnx.execute('Any X WHERE X is CWGroup, X name "toto"'))


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
        self.assertEqual(repo.get_shared_data(cnxid, 'data'), 4)
        self.assertEqual(repo.get_shared_data(cnxid2, 'data'), None)
        repo.set_shared_data(cnxid2, 'data', 5)
        self.assertEqual(repo.get_shared_data(cnxid, 'data'), 4)
        self.assertEqual(repo.get_shared_data(cnxid2, 'data'), 5)
        repo.get_shared_data(cnxid2, 'data', pop=True)
        self.assertEqual(repo.get_shared_data(cnxid, 'data'), 4)
        self.assertEqual(repo.get_shared_data(cnxid2, 'data'), None)
        repo.close(cnxid)
        repo.close(cnxid2)
        self.assertRaises(BadConnectionId, repo.get_shared_data, cnxid, 'data')
        self.assertRaises(BadConnectionId, repo.get_shared_data, cnxid2, 'data')
        self.assertRaises(BadConnectionId, repo.set_shared_data, cnxid, 'data', 1)
        self.assertRaises(BadConnectionId, repo.set_shared_data, cnxid2, 'data', 1)

    def test_check_session(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.assertIsInstance(repo.check_session(cnxid), float)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.check_session, cnxid)

    def test_transaction_base(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        # check db state
        result = repo.execute(cnxid, 'Personne X')
        self.assertEqual(result.rowcount, 0)
        # rollback entity insertion
        repo.execute(cnxid, "INSERT Personne X: X nom 'bidule'")
        result = repo.execute(cnxid, 'Personne X')
        self.assertEqual(result.rowcount, 1)
        repo.rollback(cnxid)
        result = repo.execute(cnxid, 'Personne X')
        self.assertEqual(result.rowcount, 0, result.rows)
        # commit
        repo.execute(cnxid, "INSERT Personne X: X nom 'bidule'")
        repo.commit(cnxid)
        result = repo.execute(cnxid, 'Personne X')
        self.assertEqual(result.rowcount, 1)
        repo.close(cnxid)

    def test_transaction_base2(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        # rollback relation insertion
        repo.execute(cnxid, "SET U in_group G WHERE U login 'admin', G name 'guests'")
        result = repo.execute(cnxid, "Any U WHERE U in_group G, U login 'admin', G name 'guests'")
        self.assertEqual(result.rowcount, 1)
        repo.rollback(cnxid)
        result = repo.execute(cnxid, "Any U WHERE U in_group G, U login 'admin', G name 'guests'")
        self.assertEqual(result.rowcount, 0, result.rows)
        repo.close(cnxid)

    def test_transaction_base3(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        # rollback state change which trigger TrInfo insertion
        session = repo._get_session(cnxid)
        user = session.user
        user.cw_adapt_to('IWorkflowable').fire_transition('deactivate')
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': user.eid})
        self.assertEqual(len(rset), 1)
        repo.rollback(cnxid)
        rset = repo.execute(cnxid, 'TrInfo T WHERE T wf_info_for X, X eid %(x)s', {'x': user.eid})
        self.assertEqual(len(rset), 0)
        repo.close(cnxid)

    def test_close_kill_processing_request(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        repo.execute(cnxid, 'INSERT CWUser X: X login "toto", X upassword "tutu", X in_group G WHERE G name "users"')
        repo.commit(cnxid)
        lock = threading.Lock()
        lock.acquire()
        # close has to be in the thread due to sqlite limitations
        def close_in_a_few_moment():
            lock.acquire()
            repo.close(cnxid)
        t = threading.Thread(target=close_in_a_few_moment)
        t.start()
        def run_transaction():
            lock.release()
            repo.execute(cnxid, 'DELETE CWUser X WHERE X login "toto"')
            repo.commit(cnxid)
        try:
            with self.assertRaises(SessionClosedError) as cm:
                run_transaction()
            self.assertEqual(str(cm.exception), 'try to access connections set on a closed session %s' % cnxid)
        finally:
            t.join()

    def test_initial_schema(self):
        schema = self.repo.schema
        # check order of attributes is respected
        notin = set(('eid', 'is', 'is_instance_of', 'identity',
                     'creation_date', 'modification_date', 'cwuri',
                     'owned_by', 'created_by', 'cw_source',
                     'update_permission', 'read_permission',
                     'add_permission', 'in_basket'))
        self.assertListEqual(['relation_type',
                              'from_entity', 'to_entity',
                              'constrained_by',
                              'cardinality', 'ordernum', 'formula',
                              'indexed', 'fulltextindexed', 'internationalizable',
                              'defaultval', 'extra_props',
                              'description', 'description_format'],
                             [r.type
                              for r in schema.eschema('CWAttribute').ordered_relations()
                              if r.type not in notin])

        self.assertEqual(schema.eschema('CWEType').main_attribute(), 'name')
        self.assertEqual(schema.eschema('State').main_attribute(), 'name')

        constraints = schema.rschema('name').rdef('CWEType', 'String').constraints
        self.assertEqual(len(constraints), 2)
        for cstr in constraints[:]:
            if isinstance(cstr, UniqueConstraint):
                constraints.remove(cstr)
                break
        else:
            self.fail('unique constraint not found')
        sizeconstraint = constraints[0]
        self.assertEqual(sizeconstraint.min, None)
        self.assertEqual(sizeconstraint.max, 64)

        constraints = schema.rschema('relation_type').rdef('CWAttribute', 'CWRType').constraints
        self.assertEqual(len(constraints), 1)
        cstr = constraints[0]
        self.assert_(isinstance(cstr, RQLConstraint))
        self.assertEqual(cstr.expression, 'O final TRUE')

        ownedby = schema.rschema('owned_by')
        self.assertEqual(ownedby.objects('CWEType'), ('CWUser',))

    def test_pyro(self):
        import Pyro
        Pyro.config.PYRO_MULTITHREADED = 0
        done = []
        self.repo.config.global_set_option('pyro-ns-host', 'NO_PYRONS')
        daemon = self.repo.pyro_register()
        try:
            uri = self.repo.pyro_uri.replace('PYRO', 'pyroloc')
            # the client part has to be in the thread due to sqlite limitations
            t = threading.Thread(target=self._pyro_client, args=(uri, done))
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


    def _pyro_client(self, uri, done):
        cnx = connect(uri,
                      u'admin', password='gingkow',
                      initlog=False) # don't reset logging configuration
        try:
            cnx.load_appobjects(subpath=('entities',))
            # check we can get the schema
            schema = cnx.get_schema()
            self.assertTrue(cnx.vreg)
            self.assertTrue('etypes'in cnx.vreg)
            cu = cnx.cursor()
            rset = cu.execute('Any U,G WHERE U in_group G')
            user = iter(rset.entities()).next()
            self.assertTrue(user._cw)
            self.assertTrue(user._cw.vreg)
            from cubicweb.entities import authobjs
            self.assertIsInstance(user._cw.user, authobjs.CWUser)
            # make sure the tcp connection is closed properly; yes, it's disgusting.
            adapter = cnx._repo.adapter
            cnx.close()
            adapter.release()
            done.append(True)
        finally:
            # connect monkey patch some method by default, remove them
            multiple_connections_unfix()


    def test_zmq(self):
        try:
            import zmq
        except ImportError:
            self.skipTest("zmq in not available")
        done = []
        from cubicweb.devtools import TestServerConfiguration as ServerConfiguration
        from cubicweb.server.cwzmq import ZMQRepositoryServer
        # the client part has to be in a thread due to sqlite limitations
        t = threading.Thread(target=self._zmq_client, args=(done,))
        t.start()

        zmq_server = ZMQRepositoryServer(self.repo)
        zmq_server.connect('zmqpickle-tcp://127.0.0.1:41415')

        t2 = threading.Thread(target=self._zmq_quit, args=(done, zmq_server,))
        t2.start()

        zmq_server.run()

        t2.join(1)
        t.join(1)

        if t.isAlive():
            self.fail('something went wrong, thread still alive')

    def _zmq_quit(self, done, srv):
        while not done:
            time.sleep(0.1)
        srv.quit()

    def _zmq_client(self, done):
        try:
            cnx = connect('zmqpickle-tcp://127.0.0.1:41415', u'admin', password=u'gingkow',
                          initlog=False) # don't reset logging configuration
            try:
                cnx.load_appobjects(subpath=('entities',))
                # check we can get the schema
                schema = cnx.get_schema()
                self.assertTrue(cnx.vreg)
                self.assertTrue('etypes'in cnx.vreg)
                cu = cnx.cursor()
                rset = cu.execute('Any U,G WHERE U in_group G')
                user = iter(rset.entities()).next()
                self.assertTrue(user._cw)
                self.assertTrue(user._cw.vreg)
                from cubicweb.entities import authobjs
                self.assertIsInstance(user._cw.user, authobjs.CWUser)
                cnx.close()
                done.append(True)
            finally:
                # connect monkey patch some method by default, remove them
                multiple_connections_unfix()
        finally:
            done.append(False)

    def test_internal_api(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        session = repo._get_session(cnxid, setcnxset=True)
        self.assertEqual(repo.type_and_source_from_eid(2, session),
                         ('CWGroup', None, 'system'))
        self.assertEqual(repo.type_from_eid(2, session), 'CWGroup')
        repo.close(cnxid)

    def test_public_api(self):
        self.assertEqual(self.repo.get_schema(), self.repo.schema)
        self.assertEqual(self.repo.source_defs(), {'system': {'type': 'native',
                                                              'uri': 'system',
                                                              'use-cwuri-as-url': False}
                                                  })
        # .properties() return a result set
        self.assertEqual(self.repo.properties().rql, 'Any K,V WHERE P is CWProperty,P pkey K, P value V, NOT P for_user U')

    def test_session_api(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.assertEqual(repo.user_info(cnxid), (6, 'admin', set([u'managers']), {}))
        self.assertEqual({'type': u'CWGroup', 'extid': None, 'source': 'system'},
                         repo.entity_metas(cnxid, 2))
        self.assertEqual(repo.describe(cnxid, 2), (u'CWGroup', 'system', None, 'system'))
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.user_info, cnxid)
        self.assertRaises(BadConnectionId, repo.describe, cnxid, 1)

    def test_shared_data_api(self):
        repo = self.repo
        cnxid = repo.connect(self.admlogin, password=self.admpassword)
        self.assertEqual(repo.get_shared_data(cnxid, 'data'), None)
        repo.set_shared_data(cnxid, 'data', 4)
        self.assertEqual(repo.get_shared_data(cnxid, 'data'), 4)
        repo.get_shared_data(cnxid, 'data', pop=True)
        repo.get_shared_data(cnxid, 'whatever', pop=True)
        self.assertEqual(repo.get_shared_data(cnxid, 'data'), None)
        repo.close(cnxid)
        self.assertRaises(BadConnectionId, repo.set_shared_data, cnxid, 'data', 0)
        self.assertRaises(BadConnectionId, repo.get_shared_data, cnxid, 'data')

    def test_schema_is_relation(self):
        with self.admin_access.repo_cnx() as cnx:
            no_is_rset = cnx.execute('Any X WHERE NOT X is ET')
            self.assertFalse(no_is_rset, no_is_rset.description)

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
        with self.admin_access.repo_cnx() as cnx:
            note = cnx.create_entity('Affaire')
            p1 = cnx.create_entity('Personne', nom=u'toto')
            cnx.execute('SET A todo_by P WHERE A eid %(x)s, P eid %(p)s',
                        {'x': note.eid, 'p': p1.eid})
            rset = cnx.execute('Any P WHERE A todo_by P, A eid %(x)s',
                               {'x': note.eid})
            self.assertEqual(len(rset), 1)
            p2 = cnx.create_entity('Personne', nom=u'tutu')
            cnx.execute('SET A todo_by P WHERE A eid %(x)s, P eid %(p)s',
                        {'x': note.eid, 'p': p2.eid})
            rset = cnx.execute('Any P WHERE A todo_by P, A eid %(x)s',
                                {'x': note.eid})
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.rows[0][0], p2.eid)

    def test_delete_if_object_inlined_singlecard(self):
        with self.admin_access.repo_cnx() as cnx:
            c = cnx.create_entity('Card', title=u'Carte')
            cnx.create_entity('Personne', nom=u'Vincent', fiche=c)
            cnx.create_entity('Personne', nom=u'Florent', fiche=c)
            cnx.commit()
            self.assertEqual(len(c.reverse_fiche), 1)

    def test_delete_computed_relation_nonregr(self):
        with self.admin_access.repo_cnx() as cnx:
            c = cnx.create_entity('Personne', nom=u'Adam', login_user=cnx.user.eid)
            cnx.commit()
            c.cw_delete()
            cnx.commit()

    def test_cw_set_in_before_update(self):
        # local hook
        class DummyBeforeHook(Hook):
            __regid__ = 'dummy-before-hook'
            __select__ = Hook.__select__ & is_instance('EmailAddress')
            events = ('before_update_entity',)
            def __call__(self):
                # safety belt: avoid potential infinite recursion if the test
                #              fails (i.e. RuntimeError not raised)
                pendings = self._cw.transaction_data.setdefault('pending', set())
                if self.entity.eid not in pendings:
                    pendings.add(self.entity.eid)
                    self.entity.cw_set(alias=u'foo')

        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(DummyBeforeHook):
                addr = cnx.create_entity('EmailAddress', address=u'a@b.fr')
                addr.cw_set(address=u'a@b.com')
                rset = cnx.execute('Any A,AA WHERE X eid %(x)s, X address A, X alias AA',
                                   {'x': addr.eid})
                self.assertEqual(rset.rows, [[u'a@b.com', u'foo']])

    def test_cw_set_in_before_add(self):
        # local hook
        class DummyBeforeHook(Hook):
            __regid__ = 'dummy-before-hook'
            __select__ = Hook.__select__ & is_instance('EmailAddress')
            events = ('before_add_entity',)
            def __call__(self):
                # cw_set is forbidden within before_add_entity()
                self.entity.cw_set(alias=u'foo')

        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(DummyBeforeHook):
                # XXX will fail with python -O
                self.assertRaises(AssertionError, cnx.create_entity,
                                  'EmailAddress', address=u'a@b.fr')

    def test_multiple_edit_cw_set(self):
        """make sure cw_edited doesn't get cluttered
        by previous entities on multiple set
        """
        # local hook
        class DummyBeforeHook(Hook):
            _test = self # keep reference to test instance
            __regid__ = 'dummy-before-hook'
            __select__ = Hook.__select__ & is_instance('Affaire')
            events = ('before_update_entity',)
            def __call__(self):
                # invoiced attribute shouldn't be considered "edited" before the hook
                self._test.assertFalse('invoiced' in self.entity.cw_edited,
                                  'cw_edited cluttered by previous update')
                self.entity.cw_edited['invoiced'] = 10

        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(DummyBeforeHook):
                cnx.create_entity('Affaire', ref=u'AFF01')
                cnx.create_entity('Affaire', ref=u'AFF02')
                cnx.execute('SET A duration 10 WHERE A is Affaire')


    def test_user_friendly_error(self):
        from cubicweb.entities.adapters import IUserFriendlyUniqueTogether
        class MyIUserFriendlyUniqueTogether(IUserFriendlyUniqueTogether):
            __select__ = IUserFriendlyUniqueTogether.__select__ & is_instance('Societe')
            def raise_user_exception(self):
                raise ValidationError(self.entity.eid, {'hip': 'hop'})

        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(MyIUserFriendlyUniqueTogether):
                s = cnx.create_entity('Societe', nom=u'Logilab', type=u'ssll', cp=u'75013')
                cnx.commit()
                with self.assertRaises(ValidationError) as cm:
                    cnx.create_entity('Societe', nom=u'Logilab', type=u'ssll', cp=u'75013')
                self.assertEqual(cm.exception.errors, {'hip': 'hop'})
                cnx.rollback()
                cnx.create_entity('Societe', nom=u'Logilab', type=u'ssll', cp=u'31400')
                with self.assertRaises(ValidationError) as cm:
                    s.cw_set(cp=u'31400')
                self.assertEqual(cm.exception.entity, s.eid)
                self.assertEqual(cm.exception.errors, {'hip': 'hop'})
                cnx.rollback()


class SchemaDeserialTC(CubicWebTC):

    appid = 'data-schemaserial'

    @classmethod
    def setUpClass(cls):
        register_base_type('BabarTestType', ('jungle_speed',))
        helper = get_db_helper('sqlite')
        helper.TYPE_MAPPING['BabarTestType'] = 'TEXT'
        helper.TYPE_CONVERTERS['BabarTestType'] = lambda x: '"%s"' % x
        super(SchemaDeserialTC, cls).setUpClass()


    @classmethod
    def tearDownClass(cls):
        unregister_base_type('BabarTestType')
        helper = get_db_helper('sqlite')
        helper.TYPE_MAPPING.pop('BabarTestType', None)
        helper.TYPE_CONVERTERS.pop('BabarTestType', None)
        super(SchemaDeserialTC, cls).tearDownClass()

    def test_deserialization_base(self):
        """Check the following deserialization

        * all CWEtype has name
        * Final type
        * CWUniqueTogetherConstraint
        * _unique_together__ content"""
        origshema = self.repo.schema
        try:
            self.repo.config.repairing = True # avoid versions checking
            self.repo.set_schema(self.repo.deserialize_schema())
            table = SQL_PREFIX + 'CWEType'
            namecol = SQL_PREFIX + 'name'
            finalcol = SQL_PREFIX + 'final'
            with self.admin_access.repo_cnx() as cnx:
                with cnx.ensure_cnx_set:
                    cu = cnx.system_sql('SELECT %s FROM %s WHERE %s is NULL'
                                        % (namecol, table, finalcol))
                    self.assertEqual(cu.fetchall(), [])
                    cu = cnx.system_sql('SELECT %s FROM %s '
                                        'WHERE %s=%%(final)s ORDER BY %s'
                                        % (namecol, table, finalcol, namecol),
                                        {'final': True})
                    self.assertEqual(cu.fetchall(),
                                     [(u'BabarTestType',),
                                      (u'BigInt',), (u'Boolean',), (u'Bytes',),
                                      (u'Date',), (u'Datetime',),
                                      (u'Decimal',),(u'Float',),
                                      (u'Int',),
                                      (u'Interval',), (u'Password',),
                                      (u'String',),
                                      (u'TZDatetime',), (u'TZTime',), (u'Time',)])
                    sql = ("SELECT etype.cw_eid, etype.cw_name, cstr.cw_eid, rel.eid_to "
                           "FROM cw_CWUniqueTogetherConstraint as cstr, "
                           "     relations_relation as rel, "
                           "     cw_CWEType as etype "
                           "WHERE cstr.cw_eid = rel.eid_from "
                           "  AND cstr.cw_constraint_of = etype.cw_eid "
                           "  AND etype.cw_name = 'Personne' "
                           ";")
                    cu = cnx.system_sql(sql)
                    rows = cu.fetchall()
                    self.assertEqual(len(rows), 3)
                    person = self.repo.schema.eschema('Personne')
                    self.assertEqual(len(person._unique_together), 1)
                    self.assertItemsEqual(person._unique_together[0],
                                          ('nom', 'prenom', 'inline2'))

        finally:
            self.repo.set_schema(origshema)

    def test_custom_attribute_param(self):
        origshema = self.repo.schema
        try:
            self.repo.config.repairing = True # avoid versions checking
            self.repo.set_schema(self.repo.deserialize_schema())
            pes = self.repo.schema['Personne']
            attr = pes.rdef('custom_field_of_jungle')
            self.assertIn('jungle_speed', vars(attr))
            self.assertEqual(42, attr.jungle_speed)
        finally:
            self.repo.set_schema(origshema)



class DataHelpersTC(CubicWebTC):

    def test_type_from_eid(self):
        with self.admin_access.repo_cnx() as cnx:
            with cnx.ensure_cnx_set:
                self.assertEqual(self.repo.type_from_eid(2, cnx), 'CWGroup')

    def test_type_from_eid_raise(self):
        with self.admin_access.repo_cnx() as cnx:
            with cnx.ensure_cnx_set:
                self.assertRaises(UnknownEid, self.repo.type_from_eid, -2, cnx)

    def test_add_delete_info(self):
        with self.admin_access.repo_cnx() as cnx:
            with cnx.ensure_cnx_set:
                cnx.mode = 'write'
                entity = self.repo.vreg['etypes'].etype_class('Personne')(cnx)
                entity.eid = -1
                entity.complete = lambda x: None
                self.repo.add_info(cnx, entity, self.repo.system_source)
                cu = cnx.system_sql('SELECT * FROM entities WHERE eid = -1')
                data = cu.fetchall()
                self.assertEqual(tuplify(data), [(-1, 'Personne', 'system', None)])
                self.repo.delete_info(cnx, entity, 'system')
                #self.repo.commit()
                cu = cnx.system_sql('SELECT * FROM entities WHERE eid = -1')
                data = cu.fetchall()
                self.assertEqual(data, [])


class FTITC(CubicWebTC):

    def test_fulltext_container_entity(self):
        with self.admin_access.repo_cnx() as cnx:
            assert self.schema.rschema('use_email').fulltext_container == 'subject'
            toto = cnx.create_entity('EmailAddress', address=u'toto@logilab.fr')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
            self.assertEqual(rset.rows, [])
            cnx.user.cw_set(use_email=toto)
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
            self.assertEqual(rset.rows, [[cnx.user.eid]])
            cnx.execute('DELETE X use_email Y WHERE X login "admin", Y eid %(y)s',
                        {'y': toto.eid})
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text %(t)s', {'t': 'toto'})
            self.assertEqual(rset.rows, [])
            tutu = cnx.create_entity('EmailAddress', address=u'tutu@logilab.fr')
            cnx.user.cw_set(use_email=tutu)
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text %(t)s', {'t': 'tutu'})
            self.assertEqual(rset.rows, [[cnx.user.eid]])
            tutu.cw_set(address=u'hip@logilab.fr')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text %(t)s', {'t': 'tutu'})
            self.assertEqual(rset.rows, [])
            rset = cnx.execute('Any X WHERE X has_text %(t)s', {'t': 'hip'})
            self.assertEqual(rset.rows, [[cnx.user.eid]])

    def test_no_uncessary_ftiindex_op(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('Workflow',
                              name=u'dummy workflow',
                              description=u'huuuuu')
            self.assertFalse(any(x for x in cnx.pending_operations
                                 if isinstance(x, native.FTIndexEntityOp)))


class DBInitTC(CubicWebTC):

    def test_versions_inserted(self):
        with self.admin_access.repo_cnx() as cnx:
            inserted = [r[0]
                        for r in cnx.execute('Any K ORDERBY K '
                                             'WHERE P pkey K, P pkey ~= "system.version.%"')]
            self.assertEqual(inserted,
                             [u'system.version.basket',
                              u'system.version.card',
                              u'system.version.comment',
                              u'system.version.cubicweb',
                              u'system.version.email',
                              u'system.version.file',
                              u'system.version.folder',
                              u'system.version.localperms',
                              u'system.version.tag'])

CALLED = []

class InlineRelHooksTC(CubicWebTC):
    """test relation hooks are called for inlined relations
    """
    def setUp(self):
        CubicWebTC.setUp(self)
        CALLED[:] = ()

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
            with self.admin_access.repo_cnx() as cnx:
                eidp = cnx.execute('INSERT Personne X: X nom "toto"')[0][0]
                eidn = cnx.execute('INSERT Note X: X type "T"')[0][0]
                cnx.execute('SET N ecrit_par Y WHERE N type "T", Y nom "toto"')
                self.assertEqual(CALLED, [('before_add_relation', eidn, 'ecrit_par', eidp),
                                          ('after_add_relation', eidn, 'ecrit_par', eidp)])
                CALLED[:] = ()
                cnx.execute('DELETE N ecrit_par Y WHERE N type "T", Y nom "toto"')
                self.assertEqual(CALLED, [('before_delete_relation', eidn, 'ecrit_par', eidp),
                                          ('after_delete_relation', eidn, 'ecrit_par', eidp)])
                CALLED[:] = ()
                eidn = cnx.execute('INSERT Note N: N ecrit_par P WHERE P nom "toto"')[0][0]
                self.assertEqual(CALLED, [('before_add_relation', eidn, 'ecrit_par', eidp),
                                          ('after_add_relation', eidn, 'ecrit_par', eidp)])

    def test_unique_contraint(self):
        with self.admin_access.repo_cnx() as cnx:
            toto = cnx.create_entity('Personne', nom=u'toto')
            a01 = cnx.create_entity('Affaire', ref=u'A01', todo_by=toto)
            cnx.commit()
            cnx.create_entity('Note', type=u'todo', inline1=a01)
            cnx.commit()
            cnx.create_entity('Note', type=u'todo', inline1=a01)
            with self.assertRaises(ValidationError) as cm:
                cnx.commit()
            self.assertEqual(cm.exception.errors,
                             {'inline1-subject': u'RQLUniqueConstraint S type T, S inline1 A1, '
                              'A1 todo_by C, Y type T, Y inline1 A2, A2 todo_by C failed'})

    def test_add_relations_at_creation_with_del_existing_rel(self):
        with self.admin_access.repo_cnx() as cnx:
            person = cnx.create_entity('Personne',
                                       nom=u'Toto',
                                       prenom=u'Lanturlu',
                                       sexe=u'M')
            users_rql = 'Any U WHERE U is CWGroup, U name "users"'
            users = cnx.execute(users_rql).get_entity(0, 0)
            cnx.create_entity('CWUser',
                              login=u'Toto',
                              upassword=u'firstname',
                              firstname=u'firstname',
                              surname=u'surname',
                              reverse_login_user=person,
                              in_group=users)
            cnx.commit()


class PerformanceTest(CubicWebTC):
    def setUp(self):
        super(PerformanceTest, self).setUp()
        logger = logging.getLogger('cubicweb.session')
        #logger.handlers = [logging.StreamHandler(sys.stdout)]
        logger.setLevel(logging.INFO)
        self.info = logger.info

    def tearDown(self):
        super(PerformanceTest, self).tearDown()
        logger = logging.getLogger('cubicweb.session')
        logger.setLevel(logging.CRITICAL)

    def test_composite_deletion(self):
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            t0 = time.time()
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M')
            for j in xrange(0, 2000, 100):
                abraham.cw_set(personne_composite=personnes[j:j+100])
            t1 = time.time()
            self.info('creation: %.2gs', (t1 - t0))
            cnx.commit()
            t2 = time.time()
            self.info('commit creation: %.2gs', (t2 - t1))
            cnx.execute('DELETE Personne P WHERE P eid %(eid)s', {'eid': abraham.eid})
            t3 = time.time()
            self.info('deletion: %.2gs', (t3 - t2))
            cnx.commit()
            t4 = time.time()
            self.info("commit deletion: %2gs", (t4 - t3))

    def test_add_relation_non_inlined(self):
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            cnx.commit()
            t0 = time.time()
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M',
                                        personne_composite=personnes[:100])
            t1 = time.time()
            self.info('creation: %.2gs', (t1 - t0))
            for j in xrange(100, 2000, 100):
                abraham.cw_set(personne_composite=personnes[j:j+100])
            t2 = time.time()
            self.info('more relations: %.2gs', (t2-t1))
            cnx.commit()
            t3 = time.time()
            self.info('commit creation: %.2gs', (t3 - t2))

    def test_add_relation_inlined(self):
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            cnx.commit()
            t0 = time.time()
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M',
                                        personne_inlined=personnes[:100])
            t1 = time.time()
            self.info('creation: %.2gs', (t1 - t0))
            for j in xrange(100, 2000, 100):
                abraham.cw_set(personne_inlined=personnes[j:j+100])
            t2 = time.time()
            self.info('more relations: %.2gs', (t2-t1))
            cnx.commit()
            t3 = time.time()
            self.info('commit creation: %.2gs', (t3 - t2))


    def test_session_add_relation(self):
        """ to be compared with test_session_add_relations"""
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M')
            cnx.commit()
            t0 = time.time()
            add_relation = cnx.add_relation
            for p in personnes:
                add_relation(abraham.eid, 'personne_composite', p.eid)
            cnx.commit()
            t1 = time.time()
            self.info('add relation: %.2gs', t1-t0)

    def test_session_add_relations (self):
        """ to be compared with test_session_add_relation"""
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M')
            cnx.commit()
            t0 = time.time()
            add_relations = cnx.add_relations
            relations = [('personne_composite', [(abraham.eid, p.eid) for p in personnes])]
            add_relations(relations)
            cnx.commit()
            t1 = time.time()
            self.info('add relations: %.2gs', t1-t0)

    def test_session_add_relation_inlined(self):
        """ to be compared with test_session_add_relations"""
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M')
            cnx.commit()
            t0 = time.time()
            add_relation = cnx.add_relation
            for p in personnes:
                add_relation(abraham.eid, 'personne_inlined', p.eid)
            cnx.commit()
            t1 = time.time()
            self.info('add relation (inlined): %.2gs', t1-t0)

    def test_session_add_relations_inlined (self):
        """ to be compared with test_session_add_relation"""
        with self.admin_access.repo_cnx() as cnx:
            personnes = []
            for i in xrange(2000):
                p = cnx.create_entity('Personne', nom=u'Doe%03d'%i, prenom=u'John', sexe=u'M')
                personnes.append(p)
            abraham = cnx.create_entity('Personne', nom=u'Abraham', prenom=u'John', sexe=u'M')
            cnx.commit()
            t0 = time.time()
            add_relations = cnx.add_relations
            relations = [('personne_inlined', [(abraham.eid, p.eid) for p in personnes])]
            add_relations(relations)
            cnx.commit()
            t1 = time.time()
            self.info('add relations (inlined): %.2gs', t1-t0)

    def test_optional_relation_reset_1(self):
        with self.admin_access.repo_cnx() as cnx:
            p1 = cnx.create_entity('Personne', nom=u'Vincent')
            p2 = cnx.create_entity('Personne', nom=u'Florent')
            w = cnx.create_entity('Affaire', ref=u'wc')
            w.cw_set(todo_by=[p1,p2])
            w.cw_clear_all_caches()
            cnx.commit()
            self.assertEqual(len(w.todo_by), 1)
            self.assertEqual(w.todo_by[0].eid, p2.eid)

    def test_optional_relation_reset_2(self):
        with self.admin_access.repo_cnx() as cnx:
            p1 = cnx.create_entity('Personne', nom=u'Vincent')
            p2 = cnx.create_entity('Personne', nom=u'Florent')
            w = cnx.create_entity('Affaire', ref=u'wc')
            w.cw_set(todo_by=p1)
            cnx.commit()
            w.cw_set(todo_by=p2)
            w.cw_clear_all_caches()
            cnx.commit()
            self.assertEqual(len(w.todo_by), 1)
            self.assertEqual(w.todo_by[0].eid, p2.eid)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
