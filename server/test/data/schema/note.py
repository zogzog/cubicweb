"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

class para(AttributeRelationType):
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', ERQLExpression('X in_state S, S name "todo"')),
        'delete': ('managers', ERQLExpression('X in_state S, S name "todo"')),
        }

class in_state(RelationDefinition):
    subject = 'Note'
    object = 'State'
    cardinality = '1*'
    constraints=[RQLConstraint('S is ET, O state_of ET')]

class wf_info_for(RelationDefinition):
    subject = 'TrInfo'
    object = 'Note'
    cardinality = '1*'
