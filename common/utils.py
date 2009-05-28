"""pre 3.2 bw compat

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
# pylint: disable-msg=W0614,W0401
from warnings import warn
warn('moved to cubicweb.utils', DeprecationWarning, stacklevel=2)
from cubicweb.utils import *
