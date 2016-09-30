"""entity/relation schemas to store email in an cubicweb instance

:organization: Logilab
:copyright: 2006-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from cubicweb import _

# pylint: disable-msg=E0611,F0401
from yams.buildobjs import (SubjectRelation, RelationType, EntityType,
                            String, Datetime, Int, RelationDefinition)
from yams.reader import context

from cubicweb.schema import ERQLExpression


class Email(EntityType):
    """electronic mail"""
    subject   = String(fulltextindexed=True)
    date      = Datetime(description=_('UTC time on which the mail was sent'))
    messageid = String(required=True, indexed=True)
    headers   = String(description=_('raw headers'))

    sender     = SubjectRelation('EmailAddress', cardinality='?*')
    # an email with only Bcc is acceptable, don't require any recipients
    recipients = SubjectRelation('EmailAddress')
    cc         = SubjectRelation('EmailAddress')

    parts       = SubjectRelation('EmailPart', cardinality='*1', composite='subject')
    attachment  = SubjectRelation('File')

    reply_to    = SubjectRelation('Email', cardinality='?*')
    cites       = SubjectRelation('Email')
    in_thread   = SubjectRelation('EmailThread', cardinality='?*')


class EmailPart(EntityType):
    """an email attachment"""
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',), # XXX if E parts X, U has_read_permission E
        'add':    ('managers', ERQLExpression('E parts X, U has_update_permission E'),),
        'delete': ('managers', ERQLExpression('E parts X, U has_update_permission E')),
        'update': ('managers', 'owners',),
        }

    content  = String(fulltextindexed=True)
    content_format = String(required=True, maxsize=50)
    ordernum = Int(required=True)
    alternative = SubjectRelation('EmailPart', symmetric=True)


class EmailThread(EntityType):
    """discussion thread"""
    title = String(required=True, indexed=True, fulltextindexed=True)
    see_also = SubjectRelation('EmailThread')
    forked_from = SubjectRelation('EmailThread', cardinality='?*')

class parts(RelationType):
    """ """
    fulltext_container = 'subject'

class sender(RelationType):
    """ """
    inlined = True

class in_thread(RelationType):
    """ """
    inlined = True

class reply_to(RelationType):
    """ """
    inlined = True

class generated_by(RelationType):
    """mark an entity as generated from an email"""
    cardinality = '?*'
    subject = ('TrInfo',)
    object = 'Email'

# if comment is installed
if 'Comment' in context.defined:
    class comment_generated_by(RelationDefinition):
        subject = 'Comment'
        name = 'generated_by'
        object = 'Email'
