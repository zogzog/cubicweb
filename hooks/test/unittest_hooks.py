# -*- coding: utf-8 -*-
"""functional tests for core hooks

note: most schemahooks.py hooks are actually tested in unittest_migrations.py
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

from datetime import datetime

from cubicweb import (ConnectionError, ValidationError, AuthenticationError,
                      BadConnectionId)
from cubicweb.devtools.testlib import CubicWebTC, get_versions

from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.repository import Repository

orig_get_versions = Repository.get_versions

def setup_module(*args):
    Repository.get_versions = get_versions

def teardown_module(*args):
    Repository.get_versions = orig_get_versions



class CoreHooksTC(CubicWebTC):

    def test_delete_internal_entities(self):
        self.assertRaises(ValidationError, self.execute,
                          'DELETE CWEType X WHERE X name "CWEType"')
        self.assertRaises(ValidationError, self.execute,
                          'DELETE CWRType X WHERE X name "relation_type"')
        self.assertRaises(ValidationError, self.execute,
                          'DELETE CWGroup X WHERE X name "owners"')

    def test_delete_required_relations_subject(self):
        self.execute('INSERT CWUser X: X login "toto", X upassword "hop", X in_group Y '
                     'WHERE Y name "users"')
        self.commit()
        self.execute('DELETE X in_group Y WHERE X login "toto", Y name "users"')
        self.assertRaises(ValidationError, self.commit)
        self.execute('DELETE X in_group Y WHERE X login "toto"')
        self.execute('SET X in_group Y WHERE X login "toto", Y name "guests"')
        self.commit()

    def test_delete_required_relations_object(self):
        self.skip('no sample in the schema ! YAGNI ? Kermaat ?')

    def test_static_vocabulary_check(self):
        self.assertRaises(ValidationError,
                          self.execute,
                          'SET X composite "whatever" WHERE X from_entity FE, FE name "CWUser", X relation_type RT, RT name "in_group"')

    def test_missing_required_relations_subject_inline(self):
        # missing in_group relation
        self.execute('INSERT CWUser X: X login "toto", X upassword "hop"')
        self.assertRaises(ValidationError,
                          self.commit)

    def test_inlined(self):
        self.assertEquals(self.repo.schema['sender'].inlined, True)
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        eeid = self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                            'WHERE Y is EmailAddress, P is EmailPart')[0][0]
        self.execute('SET X sender Y WHERE X is Email, Y is EmailAddress')
        rset = self.execute('Any S WHERE X sender S, X eid %s' % eeid)
        self.assertEquals(len(rset), 1)

    def test_composite_1(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.failUnless(self.execute('Email X WHERE X sender Y'))
        self.commit()
        self.execute('DELETE Email X')
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEquals(len(rset), 1)
        self.commit()
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEquals(len(rset), 0)

    def test_composite_2(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.commit()
        self.execute('DELETE Email X')
        self.execute('DELETE EmailPart X')
        self.commit()
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEquals(len(rset), 0)

    def test_composite_redirection(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.execute('INSERT Email X: X messageid "<2345>", X subject "test2", X sender Y, X recipients Y '
                     'WHERE Y is EmailAddress')
        self.commit()
        self.execute('DELETE X parts Y WHERE X messageid "<1234>"')
        self.execute('SET X parts Y WHERE X messageid "<2345>"')
        self.commit()
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.get_entity(0, 0).reverse_parts[0].messageid, '<2345>')

    def test_unsatisfied_constraints(self):
        releid = self.execute('INSERT CWRelation X: X from_entity FE, X relation_type RT, X to_entity TE '
                              'WHERE FE name "CWUser", RT name "in_group", TE name "String"')[0][0]
        self.execute('SET X read_permission Y WHERE X eid %(x)s, Y name "managers"',
                     {'x': releid}, 'x')
        ex = self.assertRaises(ValidationError,
                               self.commit)
        self.assertEquals(ex.errors, {'to_entity': 'RQLConstraint O final FALSE failed'})

    def test_html_tidy_hook(self):
        req = self.request()
        entity = req.create_entity('Workflow', name=u'wf1', description_format=u'text/html',
                                 description=u'yo')
        self.assertEquals(entity.description, u'yo')
        entity = req.create_entity('Workflow', name=u'wf2', description_format=u'text/html',
                                 description=u'<b>yo')
        self.assertEquals(entity.description, u'<b>yo</b>')
        entity = req.create_entity('Workflow', name=u'wf3', description_format=u'text/html',
                                 description=u'<b>yo</b>')
        self.assertEquals(entity.description, u'<b>yo</b>')
        entity = req.create_entity('Workflow', name=u'wf4', description_format=u'text/html',
                                 description=u'<b>R&D</b>')
        self.assertEquals(entity.description, u'<b>R&amp;D</b>')
        entity = req.create_entity('Workflow', name=u'wf5', description_format=u'text/html',
                                 description=u"<div>c&apos;est <b>l'ét&eacute;")
        self.assertEquals(entity.description, u"<div>c'est <b>l'été</b></div>")

    def test_nonregr_html_tidy_hook_no_update(self):
        entity = self.request().create_entity('Workflow', name=u'wf1', description_format=u'text/html',
                                 description=u'yo')
        entity.set_attributes(name=u'wf2')
        self.assertEquals(entity.description, u'yo')
        entity.set_attributes(description=u'R&D<p>yo')
        entity.pop('description')
        self.assertEquals(entity.description, u'R&amp;D<p>yo</p>')


    def test_metadata_cwuri(self):
        entity = self.request().create_entity('Workflow', name=u'wf1')
        self.assertEquals(entity.cwuri, self.repo.config['base-url'] + 'eid/%s' % entity.eid)

    def test_metadata_creation_modification_date(self):
        _now = datetime.now()
        entity = self.request().create_entity('Workflow', name=u'wf1')
        self.assertEquals((entity.creation_date - _now).seconds, 0)
        self.assertEquals((entity.modification_date - _now).seconds, 0)

    def test_metadata_created_by(self):
        entity = self.request().create_entity('Bookmark', title=u'wf1', path=u'/view')
        self.commit() # fire operations
        self.assertEquals(len(entity.created_by), 1) # make sure we have only one creator
        self.assertEquals(entity.created_by[0].eid, self.session.user.eid)

    def test_metadata_owned_by(self):
        entity = self.request().create_entity('Bookmark', title=u'wf1', path=u'/view')
        self.commit() # fire operations
        self.assertEquals(len(entity.owned_by), 1) # make sure we have only one owner
        self.assertEquals(entity.owned_by[0].eid, self.session.user.eid)

    def test_user_login_stripped(self):
        u = self.create_user('  joe  ')
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEquals(tname, 'joe')
        self.execute('SET X login " jijoe " WHERE X eid %(x)s', {'x': u.eid})
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEquals(tname, 'jijoe')



class UserGroupHooksTC(CubicWebTC):

    def test_user_synchronization(self):
        self.create_user('toto', password='hop', commit=False)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, u'toto', password='hop')
        self.commit()
        cnxid = self.repo.connect(u'toto', password='hop')
        self.failIfEqual(cnxid, self.session.id)
        self.execute('DELETE CWUser X WHERE X login "toto"')
        self.repo.execute(cnxid, 'State X')
        self.commit()
        self.assertRaises(BadConnectionId,
                          self.repo.execute, cnxid, 'State X')

    def test_user_group_synchronization(self):
        user = self.session.user
        self.assertEquals(user.groups, set(('managers',)))
        self.execute('SET X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        self.assertEquals(user.groups, set(('managers',)))
        self.commit()
        self.assertEquals(user.groups, set(('managers', 'guests')))
        self.execute('DELETE X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        self.assertEquals(user.groups, set(('managers', 'guests')))
        self.commit()
        self.assertEquals(user.groups, set(('managers',)))

    def test_user_composite_owner(self):
        ueid = self.create_user('toto').eid
        # composite of euser should be owned by the euser regardless of who created it
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", U use_email X '
                     'WHERE U login "toto"')
        self.commit()
        self.assertEquals(self.execute('Any A WHERE X owned_by U, U use_email X,'
                                       'U login "toto", X address A')[0][0],
                          'toto@logilab.fr')

    def test_no_created_by_on_deleted_entity(self):
        eid = self.execute('INSERT EmailAddress X: X address "toto@logilab.fr"')[0][0]
        self.execute('DELETE EmailAddress X WHERE X eid %s' % eid)
        self.commit()
        self.failIf(self.execute('Any X WHERE X created_by Y, X eid >= %(x)s', {'x': eid}))


class CWPropertyHooksTC(CubicWebTC):

    def test_unexistant_eproperty(self):
        ex = self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWProperty X: X pkey "bla.bla", X value "hop", X for_user U')
        self.assertEquals(ex.errors, {'pkey': 'unknown property key'})
        ex = self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWProperty X: X pkey "bla.bla", X value "hop"')
        self.assertEquals(ex.errors, {'pkey': 'unknown property key'})

    def test_site_wide_eproperty(self):
        ex = self.assertRaises(ValidationError,
                               self.execute, 'INSERT CWProperty X: X pkey "ui.site-title", X value "hop", X for_user U')
        self.assertEquals(ex.errors, {'for_user': "site-wide property can't be set for user"})

    def test_bad_type_eproperty(self):
        ex = self.assertRaises(ValidationError,
                               self.execute, 'INSERT CWProperty X: X pkey "ui.language", X value "hop", X for_user U')
        self.assertEquals(ex.errors, {'value': u'unauthorized value'})
        ex = self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWProperty X: X pkey "ui.language", X value "hop"')
        self.assertEquals(ex.errors, {'value': u'unauthorized value'})


class SchemaHooksTC(CubicWebTC):

    def test_duplicate_etype_error(self):
        # check we can't add a CWEType or CWRType entity if it already exists one
        # with the same name
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWEType X: X name "CWUser"')
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWRType X: X name "in_group"')

    def test_validation_unique_constraint(self):
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWUser X: X login "admin"')
        try:
            self.execute('INSERT CWUser X: X login "admin"')
        except ValidationError, ex:
            self.assertIsInstance(ex.entity, int)
            self.assertEquals(ex.errors, {'login': 'the value "admin" is already used, use another one'})


class SchemaModificationHooksTC(CubicWebTC):

    @classmethod
    def init_config(cls, config):
        super(SchemaModificationHooksTC, cls).init_config(config)
        config._cubes = None
        cls.repo.fill_schema()

    def index_exists(self, etype, attr, unique=False):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        return dbhelper.index_exists(sqlcursor, SQL_PREFIX + etype, SQL_PREFIX + attr, unique=unique)

    def _set_perms(self, eid):
        self.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                     {'x': eid}, 'x')
        self.execute('SET X add_permission G WHERE X eid %(x)s, G is CWGroup, G name "managers"',
                     {'x': eid}, 'x')
        self.execute('SET X delete_permission G WHERE X eid %(x)s, G is CWGroup, G name "owners"',
                     {'x': eid}, 'x')

    def test_base(self):
        schema = self.repo.schema
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        # schema should be update on insertion (after commit)
        eeid = self.execute('INSERT CWEType X: X name "Societe2", X description "", X final FALSE')[0][0]
        self._set_perms(eeid)
        self.execute('INSERT CWRType X: X name "concerne2", X description "", X final FALSE, X symetric FALSE')
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        # have to commit before adding definition relations
        self.commit()
        self.failUnless(schema.has_entity('Societe2'))
        self.failUnless(schema.has_relation('concerne2'))
        attreid = self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval "noname", '
                               '   X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                               'WHERE RT name "name", E name "Societe2", F name "String"')[0][0]
        self._set_perms(attreid)
        concerne2_rdef_eid = self.execute(
            'INSERT CWRelation X: X cardinality "**", X relation_type RT, X from_entity E, X to_entity E '
            'WHERE RT name "concerne2", E name "Societe2"')[0][0]
        self._set_perms(concerne2_rdef_eid)
        self.failIf('name' in schema['Societe2'].subject_relations())
        self.failIf('concerne2' in schema['Societe2'].subject_relations())
        self.failIf(self.index_exists('Societe2', 'name'))
        self.commit()
        self.failUnless('name' in schema['Societe2'].subject_relations())
        self.failUnless('concerne2' in schema['Societe2'].subject_relations())
        self.failUnless(self.index_exists('Societe2', 'name'))
        # now we should be able to insert and query Societe2
        s2eid = self.execute('INSERT Societe2 X: X name "logilab"')[0][0]
        self.execute('Societe2 X WHERE X name "logilab"')
        self.execute('SET X concerne2 X WHERE X name "logilab"')
        rset = self.execute('Any X WHERE X concerne2 Y')
        self.assertEquals(rset.rows, [[s2eid]])
        # check that when a relation definition is deleted, existing relations are deleted
        rdefeid = self.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                               '   X from_entity E, X to_entity E '
                               'WHERE RT name "concerne2", E name "CWUser"')[0][0]
        self._set_perms(rdefeid)
        self.commit()
        self.execute('DELETE CWRelation X WHERE X eid %(x)s', {'x': concerne2_rdef_eid}, 'x')
        self.commit()
        self.failUnless('concerne2' in schema['CWUser'].subject_relations())
        self.failIf('concerne2' in schema['Societe2'].subject_relations())
        self.failIf(self.execute('Any X WHERE X concerne2 Y'))
        # schema should be cleaned on delete (after commit)
        self.execute('DELETE CWEType X WHERE X name "Societe2"')
        self.execute('DELETE CWRType X WHERE X name "concerne2"')
        self.failUnless(self.index_exists('Societe2', 'name'))
        self.failUnless(schema.has_entity('Societe2'))
        self.failUnless(schema.has_relation('concerne2'))
        self.commit()
        self.failIf(self.index_exists('Societe2', 'name'))
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        self.failIf('concerne2' in schema['CWUser'].subject_relations())

    def test_is_instance_of_insertions(self):
        seid = self.execute('INSERT Transition T: T name "subdiv"')[0][0]
        is_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is ET, ET name ETN' % seid)]
        self.assertEquals(is_etypes, ['Transition'])
        instanceof_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is_instance_of ET, ET name ETN' % seid)]
        self.assertEquals(sorted(instanceof_etypes), ['BaseTransition', 'Transition'])
        snames = [name for name, in self.execute('Any N WHERE S is BaseTransition, S name N')]
        self.failIf('subdiv' in snames)
        snames = [name for name, in self.execute('Any N WHERE S is_instance_of BaseTransition, S name N')]
        self.failUnless('subdiv' in snames)


    def test_perms_synchronization_1(self):
        schema = self.repo.schema
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', 'users')))
        self.failUnless(self.execute('Any X, Y WHERE X is CWEType, X name "CWUser", Y is CWGroup, Y name "users"')[0])
        self.execute('DELETE X read_permission Y WHERE X is CWEType, X name "CWUser", Y name "users"')
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', 'users', )))
        self.commit()
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', )))
        self.execute('SET X read_permission Y WHERE X is CWEType, X name "CWUser", Y name "users"')
        self.commit()
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', 'users',)))

    def test_perms_synchronization_2(self):
        schema = self.repo.schema['in_group']
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users', 'guests')))
        self.execute('DELETE X read_permission Y WHERE X is CWRType, X name "in_group", Y name "guests"')
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users', 'guests')))
        self.commit()
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users')))
        self.execute('SET X read_permission Y WHERE X is CWRType, X name "in_group", Y name "guests"')
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users')))
        self.commit()
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users', 'guests')))

    def test_nonregr_user_edit_itself(self):
        ueid = self.session.user.eid
        groupeids = [eid for eid, in self.execute('CWGroup G WHERE G name in ("managers", "users")')]
        self.execute('DELETE X in_group Y WHERE X eid %s' % ueid)
        self.execute('SET X surname "toto" WHERE X eid %s' % ueid)
        self.execute('SET X in_group Y WHERE X eid %s, Y name "managers"' % ueid)
        self.commit()
        eeid = self.execute('Any X WHERE X is CWEType, X name "CWEType"')[0][0]
        self.execute('DELETE X read_permission Y WHERE X eid %s' % eeid)
        self.execute('SET X final FALSE WHERE X eid %s' % eeid)
        self.execute('SET X read_permission Y WHERE X eid %s, Y eid in (%s, %s)'
                     % (eeid, groupeids[0], groupeids[1]))
        self.commit()
        self.execute('Any X WHERE X is CWEType, X name "CWEType"')

    # schema modification hooks tests #########################################

    def test_uninline_relation(self):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        self.failUnless(self.schema['state_of'].inlined)
        try:
            self.execute('SET X inlined FALSE WHERE X name "state_of"')
            self.failUnless(self.schema['state_of'].inlined)
            self.commit()
            self.failIf(self.schema['state_of'].inlined)
            self.failIf(self.index_exists('State', 'state_of'))
            rset = self.execute('Any X, Y WHERE X state_of Y')
            self.assertEquals(len(rset), 2) # user states
        finally:
            self.execute('SET X inlined TRUE WHERE X name "state_of"')
            self.failIf(self.schema['state_of'].inlined)
            self.commit()
            self.failUnless(self.schema['state_of'].inlined)
            self.failUnless(self.index_exists('State', 'state_of'))
            rset = self.execute('Any X, Y WHERE X state_of Y')
            self.assertEquals(len(rset), 2)

    def test_indexed_change(self):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        try:
            self.execute('SET X indexed FALSE WHERE X relation_type R, R name "name"')
            self.failUnless(self.schema['name'].rproperty('Workflow', 'String', 'indexed'))
            self.failUnless(self.index_exists('Workflow', 'name'))
            self.commit()
            self.failIf(self.schema['name'].rproperty('Workflow', 'String', 'indexed'))
            self.failIf(self.index_exists('Workflow', 'name'))
        finally:
            self.execute('SET X indexed TRUE WHERE X relation_type R, R name "name"')
            self.failIf(self.schema['name'].rproperty('Workflow', 'String', 'indexed'))
            self.failIf(self.index_exists('Workflow', 'name'))
            self.commit()
            self.failUnless(self.schema['name'].rproperty('Workflow', 'String', 'indexed'))
            self.failUnless(self.index_exists('Workflow', 'name'))

    def test_unique_change(self):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        try:
            self.execute('INSERT CWConstraint X: X cstrtype CT, DEF constrained_by X '
                         'WHERE CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                         'RT name "name", E name "Workflow"')
            self.failIf(self.schema['Workflow'].has_unique_values('name'))
            self.failIf(self.index_exists('Workflow', 'name', unique=True))
            self.commit()
            self.failUnless(self.schema['Workflow'].has_unique_values('name'))
            self.failUnless(self.index_exists('Workflow', 'name', unique=True))
        finally:
            self.execute('DELETE DEF constrained_by X WHERE X cstrtype CT, '
                         'CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                         'RT name "name", E name "Workflow"')
            self.failUnless(self.schema['Workflow'].has_unique_values('name'))
            self.failUnless(self.index_exists('Workflow', 'name', unique=True))
            self.commit()
            self.failIf(self.schema['Workflow'].has_unique_values('name'))
            self.failIf(self.index_exists('Workflow', 'name', unique=True))

    def test_required_change_1(self):
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "title", E name "Bookmark"')
        self.commit()
        # should now be able to add bookmark without title
        self.execute('INSERT Bookmark X: X path "/view"')
        self.commit()

    def test_required_change_2(self):
        self.execute('SET DEF cardinality "11" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "surname", E name "CWUser"')
        self.commit()
        # should not be able anymore to add cwuser without surname
        self.assertRaises(ValidationError, self.create_user, "toto")
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "surname", E name "CWUser"')
        self.commit()


    def test_add_attribute_to_base_class(self):
        attreid = self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval "noname", X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                               'WHERE RT name "messageid", E name "BaseTransition", F name "String"')[0][0]
        assert self.execute('SET X read_permission Y WHERE X eid %(x)s, Y name "managers"',
                     {'x': attreid}, 'x')
        self.commit()
        self.schema.rebuild_infered_relations()
        self.failUnless('Transition' in self.schema['messageid'].subjects())
        self.failUnless('WorkflowTransition' in self.schema['messageid'].subjects())
        self.execute('Any X WHERE X is_instance_of BaseTransition, X messageid "hop"')

if __name__ == '__main__':
    unittest_main()
