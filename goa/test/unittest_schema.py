"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.goa.testlib import *

class Article(db.Model):
    content = db.TextProperty()
    synopsis = db.StringProperty(default='hello')

class Blog(db.Model):
    diem = db.DateProperty(required=True, auto_now_add=True)
    title = db.StringProperty(required=True)
    content = db.TextProperty()
    talks_about = db.ReferenceProperty(Article)
    cites = db.SelfReferenceProperty()


class SomeViewsTC(GAEBasedTC):
    MODEL_CLASSES = (Article, Blog)

    def test_entities_and_relation(self):
        schema = self.schema
        self.assertSetEquals(set(str(e) for e in schema.entities()),
                             set(('Boolean', 'Bytes', 'Date', 'Datetime', 'Float',
                              'Decimal',
                              'Int', 'Interval', 'Password', 'String', 'Time',
                              'CWEType', 'CWGroup', 'CWPermission', 'CWProperty', 'CWRType',
                              'CWUser', 'EmailAddress',
                              'RQLExpression', 'State', 'Transition', 'TrInfo',
                              'Article', 'Blog', 'YamsEntity')))
        self.assertSetEquals(set(str(e) for e in schema.relations()),
                             set(('add_permission', 'address', 'alias', 'allowed_transition',
                                  'ambiguous_relation', 'canonical', 'cites',
                                  'comment', 'comment_format', 'condition', 'content',
                                  'created_by', 'creation_date', 'delete_permission',
                                  'description', 'description_format', 'destination_state',
                                  'diem', 'eid', 'expression', 'exprtype', 'final', 'firstname',
                                  'for_user', 'from_state', 'fulltext_container', 'has_text',
                                  'identical_to', 'identity', 'in_group', 'initial_state',
                                  'inlined', 'inlined_relation', 'is', 'is_instance_of',
                                  'label', 'last_login_time', 'login',
                                  'mainvars', 'meta', 'modification_date', 'name', 'owned_by', 'pkey', 'primary_email',
                                  'read_permission', 'require_group', 'state_of', 'surname', 'symetric',
                                  'synopsis', 'talks_about', 'title', 'to_state', 'transition_of',
                                  'update_permission', 'use_email', 'value')))

    def test_dbmodel_imported(self):
        eschema = self.schema['Blog']
        orels = [str(e) for e in eschema.ordered_relations()]
        # only relations defined in the class are actually ordered
        orels, others = orels[:5], orels[5:]
        self.assertEquals(orels,
                          ['diem', 'title', 'content', 'talks_about', 'cites'])
        self.assertUnorderedIterableEquals(others,
                             ['eid', 'identity', 'owned_by', 'modification_date',
                              'created_by', 'creation_date', 'is', 'is_instance_of'])
        self.assertUnorderedIterableEquals((str(e) for e in eschema.object_relations()),
                             ('ambiguous_relation', 'cites', 'identity', 'inlined_relation'))
        eschema = self.schema['Article']
        orels = [str(e) for e in eschema.ordered_relations()]
        # only relations defined in the class are actually ordered
        orels, others = orels[:2], orels[2:]
        self.assertEquals(orels,
                          ['content', 'synopsis'])
        self.assertUnorderedIterableEquals(others,
                             ['eid', 'identity', 'owned_by', 'modification_date',
                              'created_by', 'creation_date', 'is', 'is_instance_of'])
        self.assertUnorderedIterableEquals((str(e) for e in eschema.object_relations()),
                             ('ambiguous_relation', 'talks_about', 'identity'))

    def test_yams_imported(self):
        eschema = self.schema['CWProperty']
        # only relations defined in the class are actually ordered
        orels = [str(e) for e in eschema.ordered_relations()]
        orels, others = orels[:3], orels[3:]
        self.assertEquals(orels,
                          ['pkey', 'value', 'for_user'])
        self.assertEquals(others,
                          ['created_by', 'creation_date', 'eid', 'identity',
                           'is', 'is_instance_of', 'modification_date', 'owned_by'])
        self.assertUnorderedIterableEquals((str(e) for e in eschema.object_relations()),
                             ('identity',))

    def test_yams_ambiguous_relation(self):
        rschema = self.schema['ambiguous_relation']
        # only relations defined in the class are actually ordered
        self.assertUnorderedIterableEquals((str(e) for e in rschema.subjects()),
                             ('YamsEntity',))
        self.assertUnorderedIterableEquals((str(e) for e in rschema.objects()),
                             ('Blog', 'Article'))

    def test_euser(self):
        eschema = self.schema['CWUser']
        # XXX pretend to have some relations it has not
        self.assertEquals([str(e) for e in eschema.ordered_relations()],
                          ['login', 'firstname', 'surname', 'last_login_time',
                           'primary_email', 'use_email', 'in_group', 'created_by',
                           'creation_date', 'eid', 'has_text', 'identity',
                           'is', 'is_instance_of', 'modification_date',
                           'owned_by'])
        self.assertUnorderedIterableEquals((str(e) for e in eschema.object_relations()),
                             ('owned_by', 'created_by', 'identity', 'for_user'))

    def test_eid(self):
        rschema = self.schema['eid']
        self.assertEquals(rschema.objects(), ('Bytes',))
        self.assertEquals(rschema.rproperty('Blog', 'Bytes', 'cardinality'), '?1')


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
