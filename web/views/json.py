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
"""json export views"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"
_ = unicode

from cubicweb.utils import json_dumps
from cubicweb.predicates import any_rset
from cubicweb.view import EntityView, AnyRsetView
from cubicweb.web.application import anonymized_request
from cubicweb.web.views import basecontrollers

class JsonpController(basecontrollers.ViewController):
    """The jsonp controller is the same as a ViewController but :

    - anonymize request (avoid CSRF attacks)
    - if ``vid`` parameter is passed, make sure it's sensible (i.e. either
      "jsonexport" or "ejsonexport")
    - if ``callback`` request parameter is passed, it's used as json padding


    Response's content-type will either be ``application/javascript`` or
    ``application/json`` depending on ``callback`` parameter presence or not.
    """
    __regid__ = 'jsonp'

    def publish(self, rset=None):
        if 'vid' in self._cw.form:
            vid = self._cw.form['vid']
            if vid not in ('jsonexport', 'ejsonexport'):
                self.warning("vid %s can't be used with jsonp controller, "
                             "falling back to jsonexport", vid)
                self._cw.form['vid'] = 'jsonexport'
        else: # if no vid is specified, use jsonexport
            self._cw.form['vid'] = 'jsonexport'
        if self._cw.vreg.config['anonymize-jsonp-queries']:
            with anonymized_request(self._cw):
                return self._get_json_data(rset)
        else:
            return self._get_json_data(rset)

    def _get_json_data(self, rset):
        json_data = super(JsonpController, self).publish(rset)
        if 'callback' in self._cw.form: # jsonp
            json_padding = self._cw.form['callback']
            # use ``application/javascript`` is ``callback`` parameter is
            # provided, let ``application/json`` otherwise
            self._cw.set_content_type('application/javascript')
            json_data = '%s(%s)' % (json_padding, json_data)
        return json_data


class JsonMixIn(object):
    """mixin class for json views

    Handles the following optional request parameters:

    - ``_indent`` : must be an integer. If found, it is used to pretty print
      json output
    """
    templatable = False
    content_type = 'application/json'
    binary = True

    def wdata(self, data):
        if '_indent' in self._cw.form:
            indent = int(self._cw.form['_indent'])
        else:
            indent = None
        self.w(json_dumps(data, indent=indent))


class JsonRsetView(JsonMixIn, AnyRsetView):
    """dumps raw result set in JSON format"""
    __regid__ = 'jsonexport'
    __select__ = any_rset() # means rset might be empty or have any shape
    title = _('json-export-view')

    def call(self):
        # XXX mimic w3c recommandations to serialize SPARQL results in json ?
        #     http://www.w3.org/TR/rdf-sparql-json-res/
        self.wdata(self.cw_rset.rows)


class JsonEntityView(JsonMixIn, EntityView):
    """dumps rset entities in JSON

    The following additional metadata is added to each row :

    - ``__cwetype__`` : entity type
    """
    __regid__ = 'ejsonexport'
    title = _('json-entities-export-view')

    def call(self):
        entities = []
        for entity in self.cw_rset.entities():
            entity.complete() # fetch all attributes
            # hack to add extra metadata
            entity.cw_attr_cache.update({
                    '__cwetype__': entity.__regid__,
                    })
            entities.append(entity)
        self.wdata(entities)
