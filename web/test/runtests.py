# -*- coding: ISO-8859-1 -*-
"""Script used to fire all tests"""

__revision__ = '$Id: runtests.py,v 1.1 2005-06-17 14:09:18 adim Exp $'

from logilab.common.testlib import main

if __name__ == '__main__':
    import sys, os
    main(os.path.dirname(sys.argv[0]) or '.')
