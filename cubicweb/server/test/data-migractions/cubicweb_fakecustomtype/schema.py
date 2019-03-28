
from yams.buildobjs import EntityType, make_type

Numeric = make_type('Numeric')

class Location(EntityType):
    num = Numeric(scale=10, precision=18)
