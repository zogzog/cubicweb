from cubicweb.schema import format_constraint

class Card(EntityType):
    """a card is a textual content used as documentation, reference, procedure reminder"""
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', 'users'),
        'delete': ('managers', 'owners'),
        'update': ('managers', 'owners',),
        }
    
    title    = String(required=True, fulltextindexed=True, maxsize=256)
    synopsis = String(fulltextindexed=True, maxsize=512,
                      description=_("an abstract for this card"))
    content_format = String(meta=True, internationalizable=True, maxsize=50,
                            default='text/rest', constraints=[format_constraint])
    content  = String(fulltextindexed=True)
    wikiid = String(maxsize=64, indexed=True)
