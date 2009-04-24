from cubicweb.entities import AnyEntity, fetch_config

class Societe(AnyEntity):
    id = 'Societe'
    fetch_attrs = ('nom',)

class Personne(Societe):
    """customized class forne Person entities"""
    id = 'Personne'
    fetch_attrs, fetch_order = fetch_config(['nom', 'prenom'])
    rest_attr = 'nom'


class Note(AnyEntity):
    id = 'Note'
