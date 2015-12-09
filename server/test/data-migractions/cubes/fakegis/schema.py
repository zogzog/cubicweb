
from yams.buildobjs import EntityType, make_type

Geometry = make_type('Geometry')

class Location(EntityType):
    geometry = Geometry(
        geom_type='GEOMETRYCOLLECTION', srid=4326, coord_dimension=2,
        description='Geospatial indication of the location')
