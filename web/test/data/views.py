# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.web.views.ajaxcontroller import ajaxfunc

def _recursive_replace_stream_by_content(tree):
    """ Search for streams (i.e. object that have a 'read' method) in a tree
    (which branches are lists or tuples), and substitute them by their content,
    leaving other leafs identical. A copy of the tree with only lists as
    branches is returned.
    """
    if not isinstance(tree, (list, tuple)):
        if hasattr(tree, 'read'):
            return tree.read()
        return tree
    else:
        return [_recursive_replace_stream_by_content(value)
                for value in tree]            


@ajaxfunc(output_type='json')
def fileupload(self):
    """ Return a json copy of the web request formin which uploaded files
    are read and their content substitute the received streams.
    """
    try:
        result_dict = {}
        for key, value in self._cw.form.iteritems():
            result_dict[key] = _recursive_replace_stream_by_content(value)
        return result_dict
    except Exception, ex:
        import traceback as tb
        tb.print_exc(ex)
