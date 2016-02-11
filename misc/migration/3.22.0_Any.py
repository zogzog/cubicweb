if confirm('use Europe/Paris as timezone?'):
    timezone = 'Europe/Paris'
else:
    import pytz
    while True:
        timezone = raw_input('enter your timezone')
        if timezone in pytz.common_timezones:
            break

dbdriver = repo.system_source.dbdriver
if dbdriver == 'postgres':
    sql("SET TIME ZONE '%s'" % timezone)

for entity in schema.entities():
    if entity.final or entity.type not in fsschema:
        continue
    change_attribute_type(entity.type, 'creation_date', 'TZDatetime', ask_confirm=False)
    change_attribute_type(entity.type, 'modification_date', 'TZDatetime', ask_confirm=False)

if dbdriver == 'postgres':
    sql("SET TIME ZONE UTC")
