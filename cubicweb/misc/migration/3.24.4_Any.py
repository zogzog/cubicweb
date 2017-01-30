
from yams.constraints import UniqueConstraint
from cubicweb.schema import PURE_VIRTUAL_RTYPES
from cubicweb.server.checkintegrity import expected_indexes, database_indexes

source = repo.system_source

for rschema in schema.relations():
    if rschema.rule or rschema in PURE_VIRTUAL_RTYPES:
        continue
    if rschema.final or rschema.inlined:
        for rdef in rschema.rdefs.values():
            table = 'cw_{0}'.format(rdef.subject)
            column = 'cw_{0}'.format(rdef.rtype)
            if any(isinstance(cstr, UniqueConstraint) for cstr in rdef.constraints):
                source.create_index(cnx, table, column, unique=True)
                commit(ask_confirm=False)
            if rschema.inlined or rdef.indexed:
                source.create_index(cnx, table, column)
                commit(ask_confirm=False)

schema_indices = expected_indexes(cnx)
db_indices = database_indexes(cnx)
for additional_index in (db_indices - set(schema_indices)):
    try:
        sql('DROP INDEX %s' % additional_index)
        commit()
    except:
        # ignore if this is not an index but a constraint
        pass

if source.dbhelper == 'postgres' and 'appears_words_idx' not in db_indices:
    sql('CREATE INDEX appears_words_idx ON appears USING gin(words)')
    db_indices.add('appears_words_idx')

for missing_index in (set(schema_indices) - db_indices):
    print('WARNING: missing index', missing_index)

