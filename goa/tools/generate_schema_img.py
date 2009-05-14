import sys
from os.path import dirname, abspath, join
from yams import schema2dot

APPLROOT = abspath(join(dirname(abspath(__file__)), '..'))

try:
    import custom
except ImportError:
    sys.path.insert(0, APPLROOT)
    import custom


schema = custom.SCHEMA
skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')
path = join(APPLROOT, 'data', 'schema.png')
schema2dot.schema2dot(schema, path, #size=size,
                      skiprels=skip_rels, skipmeta=True)
print 'generated', path
path = join(APPLROOT, 'data', 'metaschema.png')
schema2dot.schema2dot(schema, path, #size=size,
                      skiprels=skip_rels, skipmeta=False)
print 'generated', path
