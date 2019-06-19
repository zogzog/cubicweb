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
"""Simple cryptographic routines, based on python-crypto."""


from base64 import b64encode, b64decode
import pickle

from Cryptodome.Cipher import Blowfish


_CYPHERERS = {}


def _cypherer(seed):
    if isinstance(seed, str):
        seed = seed.encode('utf-8')
    try:
        return _CYPHERERS[seed]
    except KeyError:
        _CYPHERERS[seed] = Blowfish.new(seed, Blowfish.MODE_ECB)
        return _CYPHERERS[seed]


def encrypt(data, seed):
    string = pickle.dumps(data)
    string = string + b'*' * (8 - len(string) % 8)
    string = b64encode(_cypherer(seed).encrypt(string))
    return string.decode('utf-8')


def decrypt(string, seed):
    string = string.encode('utf-8')
    # pickle ignores trailing characters so we do not need to strip them off
    string = _cypherer(seed).decrypt(b64decode(string))
    return pickle.loads(string)
