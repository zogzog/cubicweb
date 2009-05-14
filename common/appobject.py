"""pre 3.2 bw compat"""
# pylint: disable-msg=W0614,W0401
from warnings import warn
warn('moved to cubicweb.appobject', DeprecationWarning, stacklevel=2)
from cubicweb.appobject import *
