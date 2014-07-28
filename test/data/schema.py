# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from yams.buildobjs import (EntityType, String, SubjectRelation,
                            RelationDefinition)

from cubicweb.schema import (WorkflowableEntityType,
                             RQLConstraint, RQLVocabularyConstraint)


class Personne(EntityType):
    nom = String(required=True)
    prenom = String()
    type = String()
    travaille = SubjectRelation('Societe')
    evaluee = SubjectRelation(('Note', 'Personne'))
    connait = SubjectRelation(
        'Personne', symmetric=True,
        constraints=[
            RQLConstraint('NOT S identity O'),
            # conflicting constraints, see cw_unrelated_rql tests in
            # unittest_entity.py
            RQLVocabularyConstraint('NOT (S connait P, P nom "toto")'),
            RQLVocabularyConstraint('S travaille P, P nom "tutu"')])
    actionnaire = SubjectRelation('Societe', cardinality='??',
                                  constraints=[RQLConstraint('NOT EXISTS(O contrat_exclusif S)')])
    dirige = SubjectRelation('Societe', cardinality='??',
                             constraints=[RQLConstraint('S actionnaire O')])
    associe = SubjectRelation('Personne', cardinality='?*',
                              constraints=[RQLConstraint('S actionnaire SOC, O actionnaire SOC')])

class Ami(EntityType):
    """A Person, for which surname is not required"""
    prenom = String()
    nom = String()

class Societe(EntityType):
    nom = String()
    evaluee = SubjectRelation('Note')
    fournit = SubjectRelation(('Service', 'Produit'), cardinality='1*')
    contrat_exclusif = SubjectRelation('Personne', cardinality='??')

class Service(EntityType):
    fabrique_par = SubjectRelation('Personne', cardinality='1*')


class Produit(EntityType):
    fabrique_par = SubjectRelation('Usine', cardinality='1*', inlined=True)


class Usine(EntityType):
    lieu = String(required=True)


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


class StateFull(WorkflowableEntityType):
    name = String()


class Reference(EntityType):
    nom = String(unique=True)
    ean = String(unique=True, required=True)
