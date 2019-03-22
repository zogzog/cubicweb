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
"""core CubicWeb schema, but not necessary at bootstrap time"""


from yams.buildobjs import (EntityType, RelationType, RelationDefinition,
                            SubjectRelation, String, Bytes, TZDatetime, Password)

from cubicweb import _
from cubicweb.schema import (
    RQLConstraint, WorkflowableEntityType, ERQLExpression, RRQLExpression,
    PUB_SYSTEM_REL_PERMS, PUB_SYSTEM_ATTR_PERMS, RO_ATTR_PERMS)


class CWUser(WorkflowableEntityType):
    """define a CubicWeb user"""
    __permissions__ = {
        'read':   ('managers', 'users', ERQLExpression('X identity U')),
        'add':    ('managers',),
        'delete': ('managers',),
        'update': ('managers', ERQLExpression('X identity U, NOT U in_group G, G name "guests"'),),
        }

    login     = String(required=True, unique=True, maxsize=64,
                       description=_('unique identifier used to connect to the application'))
    upassword = Password(required=True) # password is a reserved word for mysql
    firstname = String(maxsize=64)
    surname   = String(maxsize=64)
    last_login_time = TZDatetime(description=_('last connection date'))
    in_group = SubjectRelation('CWGroup', cardinality='+*',
                               constraints=[RQLConstraint('NOT O name "owners"')],
                               description=_('groups grant permissions to the user'))


class EmailAddress(EntityType):
    """an electronic mail address associated to a short alias"""
    __permissions__ = {
        # application that wishes public email, or use it for something else
        # than users (eg Company, Person), should explicitly change permissions
        'read':   ('managers', ERQLExpression('U use_email X')),
        'add':    ('managers', 'users',),
        'delete': ('managers', 'owners', ERQLExpression('P use_email X, U has_update_permission P')),
        'update': ('managers', 'owners', ERQLExpression('P use_email X, U has_update_permission P')),
        }

    alias   = String(fulltextindexed=True, maxsize=56)
    address = String(required=True,  fulltextindexed=True,
                     indexed=True, unique=True, maxsize=128)
    prefered_form = SubjectRelation('EmailAddress', cardinality='?*',
                                    description=_('when multiple addresses are equivalent \
(such as python-projects@logilab.org and python-projects@lists.logilab.org), set this \
to indicate which is the preferred form.'))

class use_email(RelationType):
    fulltext_container = 'subject'


class use_email_relation(RelationDefinition):
    """user's email account"""
    name = "use_email"
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }
    subject = "CWUser"
    object = "EmailAddress"
    cardinality = '*?'
    composite = 'subject'


class primary_email(RelationDefinition):
    """the prefered email"""
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }
    subject = "CWUser"
    object = "EmailAddress"
    cardinality = '??'
    constraints= [RQLConstraint('S use_email O')]


class prefered_form(RelationType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        # XXX should have update __permissions__ on both subject and object,
        #     though by doing this we will probably have no way to add
        #     this relation in the web ui. The easiest way to acheive this
        #     is probably to be able to have "U has_update_permission O" as
        #     RQLConstraint of the relation definition, though this is not yet
        #     possible
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }

class in_group(RelationType):
    """core relation indicating a user's groups"""
    __permissions__ = PUB_SYSTEM_REL_PERMS

class owned_by(RelationType):
    """core relation indicating owners of an entity. This relation
    implicitly put the owner into the owners group for the entity
    """
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('S owned_by U'),),
        'delete': ('managers', RRQLExpression('S owned_by U'),),
        }
    # 0..n cardinality for entities created by internal session (no attached user)
    # and to support later deletion of a user which has created some entities
    cardinality = '**'
    subject = '*'
    object = 'CWUser'

class created_by(RelationType):
    """core relation indicating the original creator of an entity"""
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    # 0..1 cardinality for entities created by internal session (no attached user)
    # and to support later deletion of a user which has created some entities
    cardinality = '?*'
    subject = '*'
    object = 'CWUser'


class creation_date(RelationType):
    """creation time of an entity"""
    __permissions__ = PUB_SYSTEM_ATTR_PERMS
    cardinality = '11'
    subject = '*'
    object = 'TZDatetime'


class modification_date(RelationType):
    """latest modification time of an entity"""
    __permissions__ = PUB_SYSTEM_ATTR_PERMS
    cardinality = '11'
    subject = '*'
    object = 'TZDatetime'


class cwuri(RelationType):
    """internal entity uri"""
    __permissions__ = RO_ATTR_PERMS
    cardinality = '11'
    subject = '*'
    object = 'String'


# XXX find a better relation name
class for_user(RelationType):
    """link a property to the user which want this property customization. Unless
    you're a site manager, this relation will be handled automatically.
    """
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    inlined = True
    subject = 'CWProperty'
    object = 'CWUser'
    composite = 'object'
    cardinality = '?*'


class ExternalUri(EntityType):
    """a URI representing an object in external data store"""
    uri = String(required=True, unique=True, maxsize=256,
                 description=_('the URI of the object'))


class same_as(RelationType):
    """generic relation to specify that an external entity represent the same
    object as a local one:
       http://www.w3.org/TR/owl-ref/#sameAs-def
    """
    #NOTE: You'll have to explicitly declare which entity types can have a
    #same_as relation
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users'),
        'delete': ('managers', 'owners'),
        }
    cardinality = '**'
    symmetric = True
    # NOTE: the 'object = ExternalUri' declaration will still be mandatory
    #       in the cube's schema.
    object = 'ExternalUri'


class CWSource(EntityType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }
    name = String(required=True, unique=True, maxsize=128,
                  description=_('name of the source'))
    type = String(required=True, maxsize=20, description=_('type of the source'))
    config = String(description=_('source\'s configuration. One key=value per '
                                  'line, authorized keys depending on the '
                                  'source\'s type'),
                    __permissions__={
                        'read':   ('managers',),
                        'add':    ('managers',),
                        'update': ('managers',),
                        })
    # put this here and not in a subclass even if it's only for some sources
    # since having subclasses on generic relation (cw_source) double the number
    # of rdef in the schema, and make ms planning harder since queries solutions
    # may changes when sources are specified
    url = String(description=_('URLs from which content will be imported. You can put one url per line'))
    parser = String(description=_('parser to use to extract entities from content retrieved at given URLs.'))
    latest_retrieval = TZDatetime(description=_('latest synchronization time'))
    in_synchronization = TZDatetime(description=_('start timestamp of the currently in synchronization, or NULL when no synchronization in progress.'))


ENTITY_MANAGERS_PERMISSIONS = {
    'read':   ('managers',),
    'add':    ('managers',),
    'update': ('managers',),
    'delete': ('managers',),
    }
RELATION_MANAGERS_PERMISSIONS = {
    'read':   ('managers',),
    'add':    ('managers',),
    'delete': ('managers',),
    }


class CWSourceHostConfig(EntityType):
    __permissions__ = ENTITY_MANAGERS_PERMISSIONS
    __unique_together__ = [('match_host', 'cw_host_config_of')]
    match_host = String(required=True, maxsize=128,
                        description=_('regexp matching host(s) to which this config applies'))
    config = String(required=True,
                    description=_('Source\'s configuration for a particular host. '
                                  'One key=value per line, authorized keys '
                                  'depending on the source\'s type, overriding '
                                  'values defined on the source.'),
                    __permissions__={
                        'read':   ('managers',),
                        'add':    ('managers',),
                        'update': ('managers',),
                        })


class cw_host_config_of(RelationDefinition):
    __permissions__ = RELATION_MANAGERS_PERMISSIONS
    subject = 'CWSourceHostConfig'
    object = 'CWSource'
    cardinality = '1*'
    composite = 'object'
    inlined = True

class cw_source(RelationDefinition):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    subject = '*'
    object = 'CWSource'
    cardinality = '1*'
    composite = 'object'


class CWDataImport(EntityType):
    __permissions__ = ENTITY_MANAGERS_PERMISSIONS
    start_timestamp = TZDatetime()
    end_timestamp = TZDatetime()
    log = String()
    status = String(required=True, internationalizable=True, indexed=True,
                    default='in progress',
                    vocabulary=[_('in progress'), _('success'), _('failed')])


class cw_import_of(RelationDefinition):
    __permissions__ = RELATION_MANAGERS_PERMISSIONS
    subject = 'CWDataImport'
    object = 'CWSource'
    cardinality = '1*'
    composite = 'object'


# "abtract" relation types, no definition in cubicweb itself ###################

class identical_to(RelationType):
    """identical to"""
    symmetric = True
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        # XXX should have update __permissions__ on both subject and object,
        #     though by doing this we will probably have no way to add
        #     this relation in the web ui. The easiest way to acheive this
        #     is probably to be able to have "U has_update_permission O" as
        #     RQLConstraint of the relation definition, though this is not yet
        #     possible
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }

class see_also(RelationType):
    """generic relation to link one entity to another"""
    symmetric = True
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }


class CWSession(EntityType):
    """Persistent session.

    Used by cubicweb.pyramid to store the session data.
    """
    __permissions__ = {
        'read':   ('managers',),
        'add':    (),
        'update': (),
        'delete': (),
    }
    cwsessiondata = Bytes()
