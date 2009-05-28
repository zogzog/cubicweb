"""this pytestconf automatically adds the mx's python version in the PYTHONPATH
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
import os.path as osp

import cubicweb
# remove 'mx' modules imported by cubicweb
for modname in sys.modules.keys(): 
    if modname.startswith('mx'):
        sys.modules.pop(modname)

# this is where mx should get imported from
mxpath = osp.abspath(osp.join(osp.dirname(cubicweb.__file__), 'embedded'))
sys.path.insert(1, mxpath)

# make sure the correct mx is imported
import mx
assert osp.dirname(mx.__file__) == osp.join(mxpath, 'mx'), '%s != %s' % (osp.dirname(mx.__file__), mxpath)
