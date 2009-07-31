"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from yams.buildobjs import EntityType, String, SubjectRelation, RelationDefinition

class Personne(EntityType):
    nom = String(required=True)
    prenom = String()
    type = String()
    travaille = SubjectRelation('Societe')
    evaluee = SubjectRelation(('Note', 'Personne'))
    connait = SubjectRelation('Personne', symetric=True)

class Societe(EntityType):
    nom = String()
    evaluee = SubjectRelation('Note')

class Note(EntityType):
    type = String()
    ecrit_par = SubjectRelation('Personne')

class SubNote(Note):
    __specializes_schema__ = True
    description = String()

class tags(RelationDefinition):
    subject = 'Tag'
    object = ('Personne', 'Note')

class evaluee(RelationDefinition):
    subject = 'CWUser'
    object = 'Note'
