"""pre 3.0 bw compat"""
# pylint: disable-msg=W0614,W0401
from warnings import warn
warn('moved to cubicweb.schema', DeprecationWarning, stacklevel=2)
from cubicweb.schema import *
