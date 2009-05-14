"""allways executed before all others in server migration

it should only include low level schema changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

if applcubicwebversion < (3, 2, 0) and cubicwebversion >= (3, 2, 0):
   add_cube('card', update_database=False)

if applcubicwebversion < (2, 47, 0) and cubicwebversion >= (2, 47, 0):
    from cubicweb.server import schemaserial
    schemaserial.HAS_FULLTEXT_CONTAINER = False
    session.set_shared_data('do-not-insert-is_instance_of', True)
    add_attribute('CWRType', 'fulltext_container')
    schemaserial.HAS_FULLTEXT_CONTAINER = True



if applcubicwebversion < (2, 50, 0) and cubicwebversion >= (2, 50, 0):
    session.set_shared_data('do-not-insert-is_instance_of', True)
    add_relation_type('is_instance_of')
    # fill the relation using an efficient sql query instead of using rql
    sql('INSERT INTO is_instance_of_relation '
	'  SELECT * from is_relation')
    checkpoint()
    session.set_shared_data('do-not-insert-is_instance_of', False)

if applcubicwebversion < (2, 42, 0) and cubicwebversion >= (2, 42, 0):
    sql('ALTER TABLE entities ADD COLUMN mtime TIMESTAMP')
    sql('UPDATE entities SET mtime=CURRENT_TIMESTAMP')
    sql('CREATE INDEX entities_mtime_idx ON entities(mtime)')
    sql('''CREATE TABLE deleted_entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(64) NOT NULL,
  dtime TIMESTAMP NOT NULL,
  extid VARCHAR(256)
)''')
    sql('CREATE INDEX deleted_entities_type_idx ON deleted_entities(type)')
    sql('CREATE INDEX deleted_entities_dtime_idx ON deleted_entities(dtime)')
    sql('CREATE INDEX deleted_entities_extid_idx ON deleted_entities(extid)')
    checkpoint()

