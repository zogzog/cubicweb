class Personne(EntityType):
    nom = String()
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
    descr = String()

class tags(RelationDefinition):
    subject = 'Tag'
    object = ('Personne', 'Note')

class evaluee(RelationDefinition):
    subject = 'EUser'
    object = 'Note'
