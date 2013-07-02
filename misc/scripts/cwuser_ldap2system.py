import base64
from cubicweb.server.utils import crypt_password

dbdriver  = config.system_source_config['db-driver']
from logilab.database import get_db_helper
dbhelper = get_db_helper(driver)

insert = ('INSERT INTO cw_cwuser (cw_creation_date,'
          '                       cw_eid,'
          '                       cw_modification_date,'
          '                       cw_login,'
          '                       cw_firstname,'
          '                       cw_surname,'
          '                       cw_last_login_time,' 
          '                       cw_upassword,'
          '                       cw_cwuri) '
          "VALUES (%(mtime)s, %(eid)s, %(mtime)s, %(login)s, "
          "        %(firstname)s, %(surname)s, %(mtime)s, %(pwd)s, 'foo');")
update = "UPDATE entities SET source='system' WHERE eid=%(eid)s;"
rset = sql("SELECT eid,type,source,extid,mtime FROM entities WHERE source!='system'", ask_confirm=False)
for eid, type, source, extid, mtime in rset:
    if type != 'CWUser':
        print "don't know what to do with entity type", type
        continue
    if not source.lower().startswith('ldap'):
        print "don't know what to do with source type", source
        continue
    extid = base64.decodestring(extid)
    ldapinfos = [x.strip().split('=') for x in extid.split(',')]
    login = ldapinfos[0][1]
    firstname = login.capitalize()
    surname = login.capitalize()
    args = dict(eid=eid, type=type, source=source, login=login,
                firstname=firstname, surname=surname, mtime=mtime,
                pwd=dbhelper.binary_value(crypt_password('toto')))
    print args
    sql(insert, args)
    sql(update, args)

commit()
