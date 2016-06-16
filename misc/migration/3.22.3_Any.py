from yams.constraints import UniqueConstraint

for rschema in schema.relations():
    if rschema.rule or not rschema.final:
        continue
    for rdef in rschema.rdefs.values():
        if (rdef.object != 'String'
                and any(isinstance(cstr, UniqueConstraint) for cstr in rdef.constraints)):
            table = 'cw_{0}'.format(rdef.subject)
            column = 'cw_{0}'.format(rdef.rtype)
            repo.system_source.create_index(cnx, table, column, unique=True)
