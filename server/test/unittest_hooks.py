# -*- coding: utf-8 -*-
"""functional tests for core hooks

note: most schemahooks.py hooks are actually tested in unittest_migrations.py
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

from datetime import datetime

from cubicweb import (ConnectionError, RepositoryError, ValidationError,
                      AuthenticationError, BadConnectionId)
from cubicweb.devtools.apptest import RepositoryBasedTC, get_versions

from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.repository import Repository

orig_get_versions = Repository.get_versions

def setup_module(*args):
    Repository.get_versions = get_versions

def teardown_module(*args):
    Repository.get_versions = orig_get_versions



class CoreHooksTC(RepositoryBasedTC):

    def test_delete_internal_entities(self):
        self.assertRaises(RepositoryError, self.execute,
                          'DELETE CWEType X WHERE X name "CWEType"')
        self.assertRaises(RepositoryError, self.execute,
                          'DELETE CWRType X WHERE X name "relation_type"')
        self.assertRaises(RepositoryError, self.execute,
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
        self.execute('INSERT CWRelation X: X from_entity FE, X relation_type RT, X to_entity TE '
                     'WHERE FE name "Affaire", RT name "concerne", TE name "String"')
        self.assertRaises(ValidationError,
                          self.commit)


    def test_html_tidy_hook(self):
        entity = self.execute('INSERT Affaire A: A descr_format "text/html", A descr "yo"').get_entity(0, 0)
        self.assertEquals(entity.descr, u'yo')
        entity = self.execute('INSERT Affaire A: A descr_format "text/html", A descr "<b>yo"').get_entity(0, 0)
        self.assertEquals(entity.descr, u'<b>yo</b>')
        entity = self.execute('INSERT Affaire A: A descr_format "text/html", A descr "<b>yo</b>"').get_entity(0, 0)
        self.assertEquals(entity.descr, u'<b>yo</b>')
        entity = self.execute('INSERT Affaire A: A descr_format "text/html", A descr "<b>R&D</b>"').get_entity(0, 0)
        self.assertEquals(entity.descr, u'<b>R&amp;D</b>')
        xml = u"<div>c&apos;est <b>l'ét&eacute;"
        entity = self.execute('INSERT Affaire A: A descr_format "text/html", A descr %(d)s',
                              {'d': xml}).get_entity(0, 0)
        self.assertEquals(entity.descr, u"<div>c'est <b>l'été</b></div>")

    def test_nonregr_html_tidy_hook_no_update(self):
        entity = self.execute('INSERT Affaire A: A descr_format "text/html", A descr "yo"').get_entity(0, 0)
        self.assertEquals(entity.descr, u'yo')
        self.execute('SET A ref "REF" WHERE A eid %s' % entity.eid)
        entity = self.execute('Any A WHERE A eid %s' % entity.eid).get_entity(0, 0)
        self.assertEquals(entity.descr, u'yo')
        self.execute('SET A descr "R&D<p>yo" WHERE A eid %s' % entity.eid)
        entity = self.execute('Any A WHERE A eid %s' % entity.eid).get_entity(0, 0)
        self.assertEquals(entity.descr, u'R&amp;D<p>yo</p>')


    def test_metadata_cwuri(self):
        eid = self.execute('INSERT Note X')[0][0]
        cwuri = self.execute('Any U WHERE X eid %s, X cwuri U' % eid)[0][0]
        self.assertEquals(cwuri, self.repo.config['base-url'] + 'eid/%s' % eid)

    def test_metadata_creation_modification_date(self):
        _now = datetime.now()
        eid = self.execute('INSERT Note X')[0][0]
        creation_date, modification_date = self.execute('Any CD, MD WHERE X eid %s, '
                                                        'X creation_date CD, '
                                                        'X modification_date MD' % eid)[0]
        self.assertEquals((creation_date - _now).seconds, 0)
        self.assertEquals((modification_date - _now).seconds, 0)

    def test_metadata__date(self):
        _now = datetime.now()
        eid = self.execute('INSERT Note X')[0][0]
        creation_date = self.execute('Any D WHERE X eid %s, X creation_date D' % eid)[0][0]
        self.assertEquals((creation_date - _now).seconds, 0)

    def test_metadata_created_by(self):
        eid = self.execute('INSERT Note X')[0][0]
        self.commit() # fire operations
        rset = self.execute('Any U WHERE X eid %s, X created_by U' % eid)
        self.assertEquals(len(rset), 1) # make sure we have only one creator
        self.assertEquals(rset[0][0], self.session.user.eid)

    def test_metadata_owned_by(self):
        eid = self.execute('INSERT Note X')[0][0]
        self.commit() # fire operations
        rset = self.execute('Any U WHERE X eid %s, X owned_by U' % eid)
        self.assertEquals(len(rset), 1) # make sure we have only one owner
        self.assertEquals(rset[0][0], self.session.user.eid)


class UserGroupHooksTC(RepositoryBasedTC):

    def test_user_synchronization(self):
        self.create_user('toto', password='hop', commit=False)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, u'toto', 'hop')
        self.commit()
        cnxid = self.repo.connect(u'toto', 'hop')
        self.failIfEqual(cnxid, self.cnxid)
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
        ueid = self.create_user('toto')
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


class CWPropertyHooksTC(RepositoryBasedTC):

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


class SchemaHooksTC(RepositoryBasedTC):

    def test_duplicate_etype_error(self):
        # check we can't add a CWEType or CWRType entity if it already exists one
        # with the same name
        #
        # according to hook order, we'll get a repository or validation error
        self.assertRaises((ValidationError, RepositoryError),
                          self.execute, 'INSERT CWEType X: X name "Societe"')
        self.assertRaises((ValidationError, RepositoryError),
                          self.execute, 'INSERT CWRType X: X name "in_group"')

    def test_validation_unique_constraint(self):
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWUser X: X login "admin"')
        try:
            self.execute('INSERT CWUser X: X login "admin"')
        except ValidationError, ex:
            self.assertIsInstance(ex.entity, int)
            self.assertEquals(ex.errors, {'login': 'the value "admin" is already used, use another one'})


class SchemaModificationHooksTC(RepositoryBasedTC):

    def setUp(self):
        if not hasattr(self, '_repo'):
            # first initialization
            repo = self.repo # set by the RepositoryBasedTC metaclass
            # force to read schema from the database to get proper eid set on schema instances
            repo.config._cubes = None
            repo.fill_schema()
        RepositoryBasedTC.setUp(self)

    def index_exists(self, etype, attr, unique=False):
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        return dbhelper.index_exists(sqlcursor, SQL_PREFIX + etype, SQL_PREFIX + attr, unique=unique)

    def test_base(self):
        schema = self.repo.schema
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        # schema should be update on insertion (after commit)
        self.execute('INSERT CWEType X: X name "Societe2", X description "", X final FALSE')
        self.execute('INSERT CWRType X: X name "concerne2", X description "", X final FALSE, X symetric FALSE')
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        self.execute('SET X read_permission G WHERE X is CWEType, X name "Societe2", G is CWGroup')
        self.execute('SET X read_permission G WHERE X is CWRType, X name "concerne2", G is CWGroup')
        self.execute('SET X add_permission G WHERE X is CWEType, X name "Societe2", G is CWGroup, G name "managers"')
        self.execute('SET X add_permission G WHERE X is CWRType, X name "concerne2", G is CWGroup, G name "managers"')
        self.execute('SET X delete_permission G WHERE X is CWEType, X name "Societe2", G is CWGroup, G name "owners"')
        self.execute('SET X delete_permission G WHERE X is CWRType, X name "concerne2", G is CWGroup, G name "owners"')
        # have to commit before adding definition relations
        self.commit()
        self.failUnless(schema.has_entity('Societe2'))
        self.failUnless(schema.has_relation('concerne2'))
        self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval "noname", X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                     'WHERE RT name "nom", E name "Societe2", F name "String"')
        concerne2_rdef_eid = self.execute(
            'INSERT CWRelation X: X cardinality "**", X relation_type RT, X from_entity E, X to_entity E '
            'WHERE RT name "concerne2", E name "Societe2"')[0][0]
        self.execute('INSERT CWRelation X: X cardinality "?*", X relation_type RT, X from_entity E, X to_entity C '
                     'WHERE RT name "comments", E name "Societe2", C name "Comment"')
        self.failIf('nom' in schema['Societe2'].subject_relations())
        self.failIf('concerne2' in schema['Societe2'].subject_relations())
        self.failIf(self.index_exists('Societe2', 'nom'))
        self.commit()
        self.failUnless('nom' in schema['Societe2'].subject_relations())
        self.failUnless('concerne2' in schema['Societe2'].subject_relations())
        self.failUnless(self.index_exists('Societe2', 'nom'))
        # now we should be able to insert and query Societe2
        s2eid = self.execute('INSERT Societe2 X: X nom "logilab"')[0][0]
        self.execute('Societe2 X WHERE X nom "logilab"')
        self.execute('SET X concerne2 X WHERE X nom "logilab"')
        rset = self.execute('Any X WHERE X concerne2 Y')
        self.assertEquals(rset.rows, [[s2eid]])
        # check that when a relation definition is deleted, existing relations are deleted
        self.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, X from_entity E, X to_entity E '
                     'WHERE RT name "concerne2", E name "Societe"')
        self.commit()
        self.execute('DELETE CWRelation X WHERE X eid %(x)s', {'x': concerne2_rdef_eid}, 'x')
        self.commit()
        self.failUnless('concerne2' in schema['Societe'].subject_relations())
        self.failIf('concerne2' in schema['Societe2'].subject_relations())
        self.failIf(self.execute('Any X WHERE X concerne2 Y'))
        # schema should be cleaned on delete (after commit)
        self.execute('DELETE CWEType X WHERE X name "Societe2"')
        self.execute('DELETE CWRType X WHERE X name "concerne2"')
        self.failUnless(self.index_exists('Societe2', 'nom'))
        self.failUnless(schema.has_entity('Societe2'))
        self.failUnless(schema.has_relation('concerne2'))
        self.commit()
        self.failIf(self.index_exists('Societe2', 'nom'))
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))

    def test_is_instance_of_insertions(self):
        seid = self.execute('INSERT SubDivision S: S nom "subdiv"')[0][0]
        is_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is ET, ET name ETN' % seid)]
        self.assertEquals(is_etypes, ['SubDivision'])
        instanceof_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is_instance_of ET, ET name ETN' % seid)]
        self.assertEquals(sorted(instanceof_etypes), ['Division', 'Societe', 'SubDivision'])
        snames = [name for name, in self.execute('Any N WHERE S is Societe, S nom N')]
        self.failIf('subdiv' in snames)
        snames = [name for name, in self.execute('Any N WHERE S is Division, S nom N')]
        self.failIf('subdiv' in snames)
        snames = [name for name, in self.execute('Any N WHERE S is_instance_of Societe, S nom N')]
        self.failUnless('subdiv' in snames)
        snames = [name for name, in self.execute('Any N WHERE S is_instance_of Division, S nom N')]
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
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        # Personne inline2 Affaire inline
        # insert a person without inline2 relation (not mandatory)
        self.execute('INSERT Personne X: X nom "toto"')
        peid = self.execute('INSERT Personne X: X nom "tutu"')[0][0]
        aeid = self.execute('INSERT Affaire X: X ref "tata"')[0][0]
        self.execute('SET X inline2 Y WHERE X eid %(x)s, Y eid %(y)s', {'x': peid, 'y': aeid})
        self.failUnless(self.schema['inline2'].inlined)
        try:
            try:
                self.execute('SET X inlined FALSE WHERE X name "inline2"')
                self.failUnless(self.schema['inline2'].inlined)
                self.commit()
                self.failIf(self.schema['inline2'].inlined)
                self.failIf(self.index_exists('Personne', 'inline2'))
                rset = self.execute('Any X, Y WHERE X inline2 Y')
                self.assertEquals(len(rset), 1)
                self.assertEquals(rset.rows[0], [peid, aeid])
            except:
                import traceback
                traceback.print_exc()
                raise
        finally:
            self.execute('SET X inlined TRUE WHERE X name "inline2"')
            self.failIf(self.schema['inline2'].inlined)
            self.commit()
            self.failUnless(self.schema['inline2'].inlined)
            self.failUnless(self.index_exists('Personne', 'inline2'))
            rset = self.execute('Any X, Y WHERE X inline2 Y')
            self.assertEquals(len(rset), 1)
            self.assertEquals(rset.rows[0], [peid, aeid])

    def test_indexed_change(self):
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        try:
            self.execute('SET X indexed TRUE WHERE X relation_type R, R name "sujet"')
            self.failIf(self.schema['sujet'].rproperty('Affaire', 'String', 'indexed'))
            self.failIf(self.index_exists('Affaire', 'sujet'))
            self.commit()
            self.failUnless(self.schema['sujet'].rproperty('Affaire', 'String', 'indexed'))
            self.failUnless(self.index_exists('Affaire', 'sujet'))
        finally:
            self.execute('SET X indexed FALSE WHERE X relation_type R, R name "sujet"')
            self.failUnless(self.schema['sujet'].rproperty('Affaire', 'String', 'indexed'))
            self.failUnless(self.index_exists('Affaire', 'sujet'))
            self.commit()
            self.failIf(self.schema['sujet'].rproperty('Affaire', 'String', 'indexed'))
            self.failIf(self.index_exists('Affaire', 'sujet'))

    def test_unique_change(self):
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        try:
            try:
                self.execute('INSERT CWConstraint X: X cstrtype CT, DEF constrained_by X '
                             'WHERE CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                             'RT name "sujet", E name "Affaire"')
                self.failIf(self.schema['Affaire'].has_unique_values('sujet'))
                self.failIf(self.index_exists('Affaire', 'sujet', unique=True))
                self.commit()
                self.failUnless(self.schema['Affaire'].has_unique_values('sujet'))
                self.failUnless(self.index_exists('Affaire', 'sujet', unique=True))
            except:
                import traceback
                traceback.print_exc()
                raise
        finally:
            self.execute('DELETE DEF constrained_by X WHERE X cstrtype CT, '
                         'CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                         'RT name "sujet", E name "Affaire"')
            self.failUnless(self.schema['Affaire'].has_unique_values('sujet'))
            self.failUnless(self.index_exists('Affaire', 'sujet', unique=True))
            self.commit()
            self.failIf(self.schema['Affaire'].has_unique_values('sujet'))
            self.failIf(self.index_exists('Affaire', 'sujet', unique=True))

    def test_required_change_1(self):
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "nom", E name "Personne"')
        self.commit()
        # should now be able to add personne without nom
        self.execute('INSERT Personne X')
        self.commit()

    def test_required_change_2(self):
        self.execute('SET DEF cardinality "11" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "prenom", E name "Personne"')
        self.commit()
        # should not be able anymore to add personne without prenom
        self.assertRaises(ValidationError, self.execute, 'INSERT Personne X: X nom "toto"')
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "prenom", E name "Personne"')
        self.commit()


    def test_add_attribute_to_base_class(self):
        self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval "noname", X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                     'WHERE RT name "nom", E name "BaseTransition", F name "String"')
        self.commit()
        self.schema.rebuild_infered_relations()
        self.failUnless('Transition' in self.schema['nom'].subjects())
        self.failUnless('WorkflowTransition' in self.schema['nom'].subjects())
        self.execute('Any X WHERE X is_instance_of BaseTransition, X nom "hop"')

if __name__ == '__main__':
    unittest_main()
