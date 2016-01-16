# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

import sys
import getpass

from cubicweb import Binary
from cubicweb.server.utils import crypt_password


if __args__:
    login = __args__.pop()
else:
    login = raw_input("login? ")

rset = rql('Any U WHERE U is CWUser, U login %(login)s', {'login': login})

if len(rset) != 1:
    sys.exit("user '%s' does not exist!" % login)

pass1 = getpass.getpass(prompt='Enter new password? ')
pass2 = getpass.getpass(prompt='Confirm? ')

if pass1 != pass2:
    sys.exit("passwords don't match!")

crypted = crypt_password(pass1)

cwuser = rset.get_entity(0,0)
cwuser.cw_set(upassword=Binary(crypted))
commit()

print("password updated.")
