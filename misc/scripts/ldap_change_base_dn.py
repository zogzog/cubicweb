from base64 import b64decode, b64encode
try:
    uri, newdn = __args__
except ValueError:
    print 'USAGE: cubicweb-ctl shell <instance> ldap_change_base_dn.py -- <ldap source uri> <new dn>'
    print
    print 'you should not have updated your sources file yet'

olddn = repo.sources_by_uri[uri].config['user-base-dn']

assert olddn != newdn

raw_input("Ensure you've stopped the instance, type enter when done.")

for eid, extid in sql("SELECT eid, extid FROM entities WHERE source='%s'" % uri):
    olduserdn = b64decode(extid)
    newuserdn = olduserdn.replace(olddn, newdn)
    if newuserdn != olduserdn:
        print olduserdn, '->', newuserdn
        sql("UPDATE entities SET extid='%s' WHERE eid=%s" % (b64encode(newuserdn), eid))

commit()

print 'you can now update the sources file to the new dn and restart the instance'
