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
"""Twisted request handler for CubicWeb"""

__docformat__ = "restructuredtext en"


from cubicweb.web.request import CubicWebRequestBase


class CubicWebTwistedRequestAdapter(CubicWebRequestBase):
    """ from twisted .req to cubicweb .form
    req.files are put into .form[<filefield>]
    """
    def __init__(self, req, vreg, https):
        self._twreq = req
        super(CubicWebTwistedRequestAdapter, self).__init__(
            vreg, https, req.args, headers=req.received_headers)
        for key, name_stream_list in req.files.iteritems():
            for name, stream in name_stream_list:
                if name is not None:
                    name = unicode(name, self.encoding)
                self.form.setdefault(key, []).append((name, stream))
            # 3.16.4 backward compat
            if len(self.form[key]) == 1:
                self.form[key] = self.form[key][0]
        self.content = self._twreq.content # stream

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        return self._twreq.method

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative to
        the instance's root, but some other normalization may be needed so that
        the returned path may be used to compare to generated urls

        :param includeparams:
           boolean indicating if GET form parameters should be kept in the path
        """
        path = self._twreq.uri[1:] # remove the root '/'
        if not includeparams:
            path = path.split('?', 1)[0]
        return path
