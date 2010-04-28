# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Set of views allowing edition of entities/relations using ajax

"""
__docformat__ = "restructuredtext en"

from cubicweb import role
from cubicweb.selectors import match_form_params, match_kwargs
from cubicweb.web.box import EditRelationBoxTemplate

class AddRelationView(EditRelationBoxTemplate):
    """base class for view which let add entities linked
    by a given relation

    subclasses should define at least id, rtype and target
    class attributes.
    """
    __registry__ = 'views'
    __regid__ = 'xaddrelation'
    __select__ = (match_form_params('rtype', 'target')
                  | match_kwargs('rtype', 'target'))
    cw_property_defs = {} # don't want to inherit this from Box
    expected_kwargs = form_params = ('rtype', 'target')

    build_js = EditRelationBoxTemplate.build_reload_js_call

    def cell_call(self, row, col, rtype=None, target=None, etype=None):
        self.rtype = rtype or self._cw.form['rtype']
        self.target = target or self._cw.form['target']
        self.etype = etype or self._cw.form.get('etype')
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(self.rtype)
        if not self.etype:
            if self.target == 'object':
                etypes = rschema.objects(entity.e_schema)
            else:
                etypes = rschema.subjects(entity.e_schema)
            if len(etypes) == 1:
                self.etype = etypes[0]
        self.w(u'<div id="%s">' % self.__regid__)
        self.w(u'<h1>%s</h1>' % self._cw._('relation %(relname)s of %(ent)s')
               % {'relname': rschema.display_name(self._cw, role(self)),
                  'ent': entity.view('incontext')})
        self.w(u'<ul>')
        for boxitem in self.unrelated_boxitems(entity):
            boxitem.render(self.w)
        self.w(u'</ul></div>')

    def unrelated_entities(self, entity):
        """returns the list of unrelated entities

        if etype is not defined on the Box's class, the default
        behaviour is to use the entity's appropraite vocabulary function
        """
        # use entity.unrelated if we've been asked for a particular etype
        if getattr(self, 'etype', None):
            rset = entity.unrelated(self.rtype, self.etype, role(self),
                                    ordermethod='fetch_order')
            self.pagination(self._cw, rset, w=self.w)
            return rset.entities()
        # in other cases, use vocabulary functions
        entities = []
        # XXX to update for 3.2
        for _, eid in entity.vocabulary(self.rtype, role(self)):
            if eid is not None:
                rset = self._cw.eid_rset(eid)
                entities.append(rset.get_entity(0, 0))
        return entities
