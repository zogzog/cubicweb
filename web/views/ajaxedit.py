"""Set of views allowing edition of entities/relations using ajax

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.selectors import match_form_params, match_kwargs
from cubicweb.web.box import EditRelationBoxTemplate

class AddRelationView(EditRelationBoxTemplate):
    """base class for view which let add entities linked
    by a given relation

    subclasses should define at least id, rtype and target
    class attributes.
    """
    __registry__ = 'views'
    __select__ = (match_form_params('rtype', 'target')
                  | match_kwargs('rtype', 'target'))
    property_defs = {} # don't want to inherit this from Box
    id = 'xaddrelation'
    expected_kwargs = form_params = ('rtype', 'target')

    build_js = EditRelationBoxTemplate.build_reload_js_call
    
    def cell_call(self, row, col, rtype=None, target=None, etype=None):
        self.rtype = rtype or self.req.form['rtype']
        self.target = target or self.req.form['target']
        self.etype = etype or self.req.form.get('etype')
        entity = self.entity(row, col)
        rschema = self.schema.rschema(self.rtype)
        if not self.etype:
            if self.target == 'object':
                etypes = rschema.objects(entity.e_schema)
            else:
                etypes = rschema.subjects(entity.e_schema)
            if len(etypes) == 1:
                self.etype = etypes[0]
        fakebox = []
        self.w(u'<div id="%s">' % self.id)
        self.w(u'<h1>%s</h1>' % self.req._('relation %(relname)s of %(ent)s')
               % {'relname': rschema.display_name(self.req, self.xtarget()[0]),
                  'ent': entity.view('incontext')})
        self.w(u'<ul>')
        self.w_unrelated(fakebox, entity)
        for boxitem in fakebox:
            boxitem.render(self.w)
        self.w(u'</ul></div>')

    def unrelated_entities(self, entity):
        """returns the list of unrelated entities

        if etype is not defined on the Box's class, the default
        behaviour is to use the entity's appropraite vocabulary function
        """
        x, target = self.xtarget()
        # use entity.unrelated if we've been asked for a particular etype
        if getattr(self, 'etype', None):
            rset = entity.unrelated(self.rtype, self.etype, x, ordermethod='fetch_order')
            self.pagination(self.req, rset, w=self.w)
            return rset.entities()
        # in other cases, use vocabulary functions
        entities = []
        for _, eid in entity.vocabulary(self.rtype, x):
            if eid is not None:
                rset = self.req.eid_rset(eid)
                entities.append(rset.get_entity(0, 0))
        return entities
