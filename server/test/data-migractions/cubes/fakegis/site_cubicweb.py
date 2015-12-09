from yams import register_base_type
from logilab.database import get_db_helper
from logilab.database.sqlgen import SQLExpression

_GEOM_PARAMETERS = ('srid', 'geom_type', 'coord_dimension')
register_base_type('Geometry', _GEOM_PARAMETERS)

# Add the datatype to the helper mapping
pghelper = get_db_helper('postgres')
pghelper.TYPE_MAPPING['Geometry'] = 'geometry'


# Add a converter for Geometry
def convert_geom(x):
    if isinstance(x, (tuple, list)):
        # We give the (Geometry, SRID)
        return SQLExpression('ST_GeomFromText(%(geo)s, %(srid)s)', geo=x[0], srid=x[1])
    else:
        # We just give the Geometry
        return SQLExpression('ST_GeomFromText(%(geo)s, %(srid)s)', geo=x, srid=-1)

# Add the converter function to the known SQL_CONVERTERS
pghelper.TYPE_CONVERTERS['Geometry'] = convert_geom
