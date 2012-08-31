from logilab.common.shellutils import generate_password
from cubicweb.server.utils import crypt_password

for user in rql('CWUser U WHERE U cw_source S, S name "system", U upassword P, U login L').entities():
    salt = user.upassword.getvalue()
    if crypt_password('', salt) == salt:
        passwd = generate_password()
        print 'setting random password for user %s' % user.login
        user.set_attributes(upassword=passwd)

commit()
