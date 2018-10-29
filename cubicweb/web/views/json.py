# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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


from cubicweb import _

from cubicweb.uilib import rest_traceback

from cubicweb.utils import json_dumps
from cubicweb.predicates import ExpectedValuePredicate, any_rset, empty_rset
from cubicweb.view import EntityView, AnyRsetView
from cubicweb.web.application import anonymized_request
from cubicweb.web.views import basecontrollers, management


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
        else:  # if no vid is specified, use jsonexport
            self._cw.form['vid'] = 'jsonexport'
        if self._cw.vreg.config['anonymize-jsonp-queries']:
            with anonymized_request(self._cw):
                return self._get_json_data(rset)
        else:
            return self._get_json_data(rset)

    def _get_json_data(self, rset):
        json_data = super(JsonpController, self).publish(rset)
        if 'callback' in self._cw.form:  # jsonp
            json_padding = self._cw.form['callback'].encode('ascii')
            # use ``application/javascript`` if ``callback`` parameter is
            # provided, keep ``application/json`` otherwise
            self._cw.set_content_type('application/javascript')
            json_data = json_padding + b'(' + json_data + b')'
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
        # python's json.dumps escapes non-ascii characters
        self.w(json_dumps(data, indent=indent).encode('ascii'))


class JsonRsetView(JsonMixIn, AnyRsetView):
    """dumps raw result set in JSON format"""
    __regid__ = 'jsonexport'
    __select__ = any_rset()  # means rset might be empty or have any shape
    title = _('json-export-view')

    def call(self):
        # XXX mimic w3c recommandations to serialize SPARQL results in json?
        #     http://www.w3.org/TR/rdf-sparql-json-res/
        self.wdata(self.cw_rset.rows)


class JsonEntityView(JsonMixIn, EntityView):
    """dumps rset entities in JSON

    The following additional metadata is added to each row :

    - ``cw_etype`` : entity type
    - ``cw_source`` : source url
    """
    __regid__ = 'ejsonexport'
    __select__ = EntityView.__select__ | empty_rset()
    title = _('json-entities-export-view')

    def call(self):
        entities = []
        for entity in self.cw_rset.entities():
            serializer = entity.cw_adapt_to('ISerializable')
            entities.append(serializer.serialize())
        self.wdata(entities)


class _requested_vid(ExpectedValuePredicate):
    """predicate that checks vid parameter value

    It differs from ``match_view`` in that it doesn't expect a ``view``
    parameter to be given to ``select`` but will rather check
    ``req.form['vid']`` to match expected vid.
    """
    def __call__(self, cls, req, rset=None, **kwargs):
        return req.form.get('vid') in self.expected


class JsonErrorView(JsonMixIn, management.ErrorView):
    """custom error view selected when client asks for a json view

    The returned json object will contain err / traceback informations.
    """
    __select__ = (management.ErrorView.__select__
                  & _requested_vid('jsonexport', 'ejsonexport'))

    def call(self):
        errmsg, exclass, excinfo = self._excinfo()
        self.wdata({
            'errmsg': errmsg,
            'exclass': exclass,
            'traceback': rest_traceback(excinfo, errmsg),
        })
