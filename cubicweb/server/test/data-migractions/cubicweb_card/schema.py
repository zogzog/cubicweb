from yams.buildobjs import EntityType, String, RichString


class Card(EntityType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', 'users'),
        'delete': ('managers', 'owners'),
        'update': ('managers', 'owners',),
    }

    title = String(required=True, fulltextindexed=True, maxsize=256)
    synopsis = String(fulltextindexed=True, maxsize=512,
                      description=("an abstract for this card"))
    content = RichString(fulltextindexed=True, internationalizable=True,
                         default_format='text/rest')
    wikiid = String(maxsize=64, unique=True)
