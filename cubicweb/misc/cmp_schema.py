"""This module compare the Schema on the file system to the one in the database"""

from cStringIO import StringIO
from cubicweb.web.schemaviewer import SchemaViewer
from logilab.common.ureports import TextWriter
import difflib

viewer = SchemaViewer()
layout_db = viewer.visit_schema(schema, display_relations=True)
layout_fs = viewer.visit_schema(fsschema, display_relations=True)
writer = TextWriter()
stream_db = StringIO()
stream_fs = StringIO()
writer.format(layout_db, stream=stream_db)
writer.format(layout_fs, stream=stream_fs)

stream_db.seek(0)
stream_fs.seek(0)
db = stream_db.getvalue().splitlines()
fs = stream_fs.getvalue().splitlines()
open('db_schema.txt', 'w').write(stream_db.getvalue())
open('fs_schema.txt', 'w').write(stream_fs.getvalue())
#for diff in difflib.ndiff(fs, db):
#    print diff
