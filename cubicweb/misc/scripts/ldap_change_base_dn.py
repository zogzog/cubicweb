from __future__ import print_function

from base64 import b64decode, b64encode
try:
    uri, newdn = __args__
except ValueError:
    print('USAGE: cubicweb-ctl shell <instance> ldap_change_base_dn.py -- <ldap source uri> <new dn>')
    print()
    print('you should not have updated your sources file yet')

olddn = repo.source_by_uri(uri).config['user-base-dn']

assert olddn != newdn

raw_input("Ensure you've stopped the instance, type enter when done.")

for eid, olduserdn in rql("Any X, XURI WHERE X cwuri XURI, X cw_source S, S name %(name)s",
                          {'name': uri}):
    newuserdn = olduserdn.replace(olddn, newdn)
    if newuserdn != olduserdn:
        print(olduserdn, '->', newuserdn)
        sql("UPDATE cw_cwuser SET cw_cwuri='%s' WHERE cw_eid=%s" % (newuserdn, eid))

commit()

print('you can now update the sources file to the new dn and restart the instance')
