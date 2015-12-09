from yams import register_base_type
from logilab.database import get_db_helper
from logilab.database.sqlgen import SQLExpression

_GEOM_PARAMETERS = ('srid', 'geom_type', 'coord_dimension')
register_base_type('Geometry', _GEOM_PARAMETERS)

# Add the datatype to the helper mapping
pghelper = get_db_helper('postgres')


def pg_geometry_sqltype(rdef):
    """Return a PostgreSQL column type corresponding to rdef's geom_type, srid
    and coord_dimension.
    """
    target_geom_type = rdef.geom_type
    if rdef.coord_dimension >= 3:  # XXX: handle 2D+M
        target_geom_type += 'Z'
    if rdef.coord_dimension == 4:
        target_geom_type += 'M'
    assert target_geom_type
    assert rdef.srid
    return 'geometry(%s, %s)' % (target_geom_type, rdef.srid)


pghelper.TYPE_MAPPING['Geometry'] = pg_geometry_sqltype


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
