"""dynamically generated image views

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import os
from tempfile import mktemp
from itertools import cycle

from logilab.common.graph import escape, GraphGenerator, DotBackend
from yams import schema2dot as s2d

from cubicweb.common.view import EntityView, StartupView


class RestrictedSchemaDotPropsHandler(s2d.SchemaDotPropsHandler):
    def __init__(self, req):
        # FIXME: colors are arbitrary
        self.nextcolor = cycle( ('#aa0000', '#00aa00', '#0000aa',
                                 '#000000', '#888888') ).next
        self.req = req
        
    def display_attr(self, rschema):
        return not rschema.meta and (rschema.has_local_role('read')
                                     or rschema.has_perm(self.req, 'read'))
    
    # XXX remove this method once yams > 0.20 is out
    def node_properties(self, eschema):
        """return default DOT drawing options for an entity schema"""
        label = ['{',eschema.type,'|']
        label.append(r'\l'.join(rel.type for rel in eschema.subject_relations()
                                if rel.final and self.display_attr(rel)))
        label.append(r'\l}') # trailing \l ensure alignement of the last one
        return {'label' : ''.join(label), 'shape' : "record",
                'fontname' : "Courier", 'style' : "filled"}

    def edge_properties(self, rschema, subjnode, objnode):
        kwargs = super(RestrictedSchemaDotPropsHandler, self).edge_properties(rschema, subjnode, objnode)
        # symetric rels are handled differently, let yams decide what's best
        if not rschema.symetric:
            kwargs['color'] = self.nextcolor()
        kwargs['fontcolor'] = kwargs['color']
        # dot label decoration is just awful (1 line underlining the label
        # + 1 line going to the closest edge spline point)
        kwargs['decorate'] = 'false'
        return kwargs
    

class RestrictedSchemaVisitorMiIn:
    def __init__(self, req, *args, **kwargs):
        # hack hack hack
        assert len(self.__class__.__bases__) == 2
        self.__parent = self.__class__.__bases__[1]
        self.__parent.__init__(self, *args, **kwargs)
        self.req = req
        
    def nodes(self):
        for etype, eschema in self.__parent.nodes(self):
            if eschema.has_local_role('read') or eschema.has_perm(self.req, 'read'):
                yield eschema.type, eschema
            
    def edges(self):
        for setype, oetype, rschema in self.__parent.edges(self):
            if rschema.has_local_role('read') or rschema.has_perm(self.req, 'read'):
                yield setype, oetype, rschema

class FullSchemaVisitor(RestrictedSchemaVisitorMiIn, s2d.FullSchemaVisitor):
    pass

class OneHopESchemaVisitor(RestrictedSchemaVisitorMiIn, s2d.OneHopESchemaVisitor):
    pass

class OneHopRSchemaVisitor(RestrictedSchemaVisitorMiIn, s2d.OneHopRSchemaVisitor):
    pass
                
        
class TmpFileViewMixin(object):
    binary = True
    content_type = 'application/octet-stream'
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default 
    
    def call(self):
        self.cell_call()
        
    def cell_call(self, row=0, col=0):
        self.row, self.col = row, col # in case one need it
        tmpfile = mktemp('.png')
        try:
            self._generate(tmpfile)
            self.w(open(tmpfile).read())
        finally:
            os.unlink(tmpfile)
    
class SchemaImageView(TmpFileViewMixin, StartupView):
    id = 'schemagraph'
    content_type = 'image/png'
    skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')
    def _generate(self, tmpfile):
        """display global schema information"""
        skipmeta = not int(self.req.form.get('withmeta', 0))
        visitor = FullSchemaVisitor(self.req, self.schema, skiprels=self.skip_rels, skipmeta=skipmeta)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))

class EETypeSchemaImageView(TmpFileViewMixin, EntityView):
    id = 'eschemagraph'
    content_type = 'image/png'
    accepts = ('EEType',)
    skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')
    
    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        eschema = self.vreg.schema.eschema(entity.name)
        visitor = OneHopESchemaVisitor(self.req, eschema, skiprels=self.skip_rels)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))

class ERTypeSchemaImageView(EETypeSchemaImageView):
    accepts = ('ERType',)
    
    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        rschema = self.vreg.schema.rschema(entity.name)
        visitor = OneHopRSchemaVisitor(self.req, rschema)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))



class WorkflowDotPropsHandler(object):
    def __init__(self, req):
        self._ = req._
        
    def node_properties(self, stateortransition):
        """return default DOT drawing options for a state or transition"""
        props = {'label': stateortransition.name, 
                 'fontname': 'Courier'}
        if hasattr(stateortransition, 'state_of'):
            props['shape'] = 'box'
            props['style'] = 'filled'
            if stateortransition.reverse_initial_state:
                props['color'] = '#88CC88'
        else:
            props['shape'] = 'ellipse'
            descr = []
            tr = stateortransition
            if tr.require_group:
                descr.append('%s %s'% (
                    self._('groups:'),
                    ','.join(g.name for g in tr.require_group)))
            if tr.condition:
                descr.append('%s %s'% (self._('condition:'), tr.condition))
            if descr:
                props['label'] += escape('\n'.join(descr))
        return props
    
    def edge_properties(self, transition, fromstate, tostate):
        return {'label': '', 'dir': 'forward',
                'color': 'black', 'style': 'filled'}

class WorkflowVisitor:
    def __init__(self, entity):
        self.entity = entity

    def nodes(self):
        for state in self.entity.reverse_state_of:
            state.complete()
            yield state.eid, state
            
        for transition in self.entity.reverse_transition_of:
            transition.complete()
            yield transition.eid, transition
            
    def edges(self):
        for transition in self.entity.reverse_transition_of:
            for incomingstate in transition.reverse_allowed_transition:
                yield incomingstate.eid, transition.eid, transition
            yield transition.eid, transition.destination().eid, transition


class EETypeWorkflowImageView(TmpFileViewMixin, EntityView):
    id = 'ewfgraph'
    content_type = 'image/png'
    accepts = ('EEType',)
    
    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        visitor = WorkflowVisitor(entity)
        prophdlr = WorkflowDotPropsHandler(self.req)
        generator = GraphGenerator(DotBackend('workflow', 'LR',
                                              ratio='compress', size='30,12'))
        return generator.generate(visitor, prophdlr, tmpfile)
