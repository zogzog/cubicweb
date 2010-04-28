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
"""

"""

from yams.buildobjs import EntityType, String, SubjectRelation, RelationDefinition

class Personne(EntityType):
    nom = String(required=True)
    prenom = String()
    type = String()
    travaille = SubjectRelation('Societe')
    evaluee = SubjectRelation(('Note', 'Personne'))
    connait = SubjectRelation('Personne', symmetric=True)

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
