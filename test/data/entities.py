from cubicweb.entities import AnyEntity, fetch_config

class Personne(AnyEntity):
    """customized class forne Person entities"""
    id = 'Personne'
    fetch_attrs, fetch_order = fetch_config(['nom', 'prenom'])
    rest_attr = 'nom'


class Societe(AnyEntity):
    id = 'Societe'
    fetch_attrs = ('nom',)
    
class Note(AnyEntity):
    id = 'Note'
