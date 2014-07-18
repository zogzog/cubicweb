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
"""Set of views allowing edition of entities/relations using ajax"""

__docformat__ = "restructuredtext en"

from cubicweb import role
from cubicweb.view import View
from cubicweb.predicates import match_form_params, match_kwargs
from cubicweb.web import component, stdmsgs, formwidgets as fw

class AddRelationView(component.EditRelationMixIn, View):
    """base class for view which let add entities linked by a given relation

    subclasses should define at least id, rtype and target class attributes.
    """
    __registry__ = 'views'
    __regid__ = 'xaddrelation'
    __select__ = (match_form_params('rtype', 'target')
                  | match_kwargs('rtype', 'target'))
    cw_property_defs = {} # don't want to inherit this from Box
    expected_kwargs = form_params = ('rtype', 'target')

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
        self.w(u'<div id="%s">' % self.domid)
        self.w(u'<h1>%s</h1>' % self._cw._('relation %(relname)s of %(ent)s')
               % {'relname': rschema.display_name(self._cw, role(self)),
                  'ent': entity.view('incontext')})
        self.w(u'<ul class="list-unstyled">')
        for boxitem in self.unrelated_boxitems(entity):
            self.w('<li>%s</li>' % boxitem)
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
            self.paginate(self._cw, rset=rset, w=self.w)
            return rset.entities()
        super(AddRelationView, self).unrelated_entities(self)


def ajax_composite_form(container, entity, rtype, okjs, canceljs,
                        entityfkwargs=None):
    """
    * if entity is None, edit container (assert container.has_eid())
    * if entity has not eid, will be created
    * if container has not eid, will be created (see vcreview InsertionPoint)
    """
    req = container._cw
    parentexists = entity is None or container.has_eid()
    buttons = [fw.Button(onclick=okjs),
               fw.Button(stdmsgs.BUTTON_CANCEL, onclick=canceljs)]
    freg = req.vreg['forms']
    # main form kwargs
    mkwargs = dict(action='#', domid='%sForm%s' % (rtype, container.eid),
                   form_buttons=buttons,
                   onsubmit='javascript: %s; return false' % okjs)
    # entity form kwargs
    # use formtype=inlined to skip the generic relations edition section
    fkwargs = dict(entity=entity or container, formtype='inlined')
    if entityfkwargs is not None:
        fkwargs.update(entityfkwargs)
    # form values
    formvalues = {}
    if entity is not None: # creation
        formvalues[rtype] = container.eid
    if parentexists: # creation / edition
        mkwargs.update(fkwargs)
        # use formtype=inlined to avoid viewing the relation edition section
        form = freg.select('edition', req, **mkwargs)
    else: # creation of both container and comment entities
        form = freg.select('composite', req, form_renderer_id='default',
                            **mkwargs)
        form.add_subform(freg.select('edition', req, entity=container,
                                      mainform=False, mainentity=True))
        form.add_subform(freg.select('edition', req, mainform=False, **fkwargs))
    return form, formvalues
