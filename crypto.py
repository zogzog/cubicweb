"""Simple cryptographic routines, based on python-crypto.

:organization: Logilab
:copyright: 2009-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from pickle import dumps, loads
from base64 import b64encode, b64decode

from Crypto.Cipher import Blowfish


_CYPHERERS = {}
def _cypherer(seed):
    try:
        return _CYPHERERS[seed]
    except KeyError:
        _CYPHERERS[seed] = Blowfish.new(seed, Blowfish.MODE_ECB)
        return _CYPHERERS[seed]


def encrypt(data, seed):
    string = dumps(data)
    string = string + '*' * (8 - len(string) % 8)
    string = b64encode(_cypherer(seed).encrypt(string))
    return unicode(string)


def decrypt(string, seed):
    # pickle ignores trailing characters so we do not need to strip them off
    string = _cypherer(seed).decrypt(b64decode(string))
    return loads(string)
