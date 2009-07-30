"""allways executed before all others in server migration

it should only include low level schema changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

applcubicwebversion, cubicwebversion = versions_map['cubicweb']

if applcubicwebversion < (3, 4, 0) and cubicwebversion >= (3, 4, 0):
    from cubicweb import RepositoryError
    from cubicweb.server.hooks import uniquecstrcheck_before_modification
    session.set_shared_data('do-not-insert-cwuri', True)
    repo.hm.unregister_hook(uniquecstrcheck_before_modification, 'before_add_entity', '')
    repo.hm.unregister_hook(uniquecstrcheck_before_modification, 'before_update_entity', '')
    add_relation_type('cwuri')
    base_url = session.base_url()
    # use an internal session since some entity might forbid modifications to admin
    isession = repo.internal_session()
    for eid, in rql('Any X', ask_confirm=False):
        try:
            isession.execute('SET X cwuri %(u)s WHERE X eid %(x)s',
                             {'x': eid, 'u': base_url + u'eid/%s' % eid})
        except RepositoryError:
            print 'unable to set cwuri for', eid, session.describe(eid)
    isession.commit()
    repo.hm.register_hook(uniquecstrcheck_before_modification, 'before_add_entity', '')
    repo.hm.register_hook(uniquecstrcheck_before_modification, 'before_update_entity', '')
    session.set_shared_data('do-not-insert-cwuri', False)

if applcubicwebversion < (3, 2, 2) and cubicwebversion >= (3, 2, 1):
    from base64 import b64encode
    for table in ('entities', 'deleted_entities'):
        for eid, extid in sql('SELECT eid, extid FROM %s WHERE extid is NOT NULL'
                              % table, ask_confirm=False):
            sql('UPDATE %s SET extid=%%(extid)s WHERE eid=%%(eid)s' % table,
                {'extid': b64encode(extid), 'eid': eid}, ask_confirm=False)
    checkpoint()

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
