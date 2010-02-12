"""pre 3.6 bw compat"""
# pylint: disable-msg=W0614,W0401
from warnings import warn
warn('moved to cubicweb.uilib', DeprecationWarning, stacklevel=2)
from cubicweb.uilib import *
