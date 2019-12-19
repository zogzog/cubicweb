from yams import register_base_type
from logilab.database import get_db_helper

_NUMERIC_PARAMETERS = {'scale': 0, 'precision': None}
register_base_type('Numeric', _NUMERIC_PARAMETERS)

# Add the datatype to the helper mapping
pghelper = get_db_helper('postgres')


def pg_numeric_sqltype(rdef):
    """Return a PostgreSQL column type corresponding to rdef
    """
    return 'numeric(%s, %s)' % (rdef.precision, rdef.scale)


pghelper.TYPE_MAPPING['Numeric'] = pg_numeric_sqltype
