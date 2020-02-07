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
"""base xml and rss views"""


from cubicweb import _

from yams import xy

from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.view import EntityView
from cubicweb.web.views.xmlrss import SERIALIZERS

try:
    import rdflib
except ImportError:
    rdflib = None

if rdflib is not None:
    RDF = rdflib.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    CW = rdflib.Namespace('http://ns.cubicweb.org/cubicweb/0.0/')
    from rdflib import Literal, URIRef, Namespace

    def urijoin(item):
        base, ext = item
        return URIRef(Namespace(base)[ext])

    SKIP_RTYPES = VIRTUAL_RTYPES | set(['cwuri', 'is', 'is_instance_of'])

    class RDFView(EntityView):
        """rdf view for entities"""
        __regid__ = 'rdf'
        title = _('rdf export')
        templatable = False
        binary = True
        format = 'xml' # or maybe pretty-xml ?
        content_type = 'application/rdf+xml'

        def call(self):
            graph = rdflib.Graph()
            graph.bind('cw', CW)
            for prefix, xmlns in xy.XY.prefixes.items():
                graph.bind(prefix, rdflib.Namespace(xmlns))
            for i in range(self.cw_rset.rowcount):
                entity = self.cw_rset.complete_entity(i, 0)
                self.entity2graph(graph, entity)
            self.w(graph.serialize(format=self.format))

        def entity_call(self, entity):
            self.call()

        def entity2graph(self, graph, entity):
            cwuri = URIRef(entity.cwuri)
            add = graph.add
            add( (cwuri, RDF.type, CW[entity.e_schema.type]) )
            try:
                for item in xy.xeq(entity.e_schema.type):
                    add( (cwuri, RDF.type, urijoin(item)) )
            except xy.UnsupportedVocabulary:
                pass
            for rschema, eschemas, role in entity.e_schema.relation_definitions('relation'):
                rtype = rschema.type
                if rtype in SKIP_RTYPES or rtype.endswith('_permission'):
                    continue
                for eschema in eschemas:
                    if eschema.final:
                        try:
                            value = entity.cw_attr_cache[rtype]
                        except KeyError:
                            continue # assuming rtype is Bytes
                        if value is not None:
                            add( (cwuri, CW[rtype], Literal(value)) )
                            try:
                                for item in xy.xeq('%s %s' % (entity.e_schema.type, rtype)):
                                    add( (cwuri, urijoin(item[1]), Literal(value)) )
                            except xy.UnsupportedVocabulary:
                                pass
                    else:
                        for related in entity.related(rtype, role, entities=True, safe=True):
                            if role == 'subject':
                                add( (cwuri, CW[rtype], URIRef(related.cwuri)) )
                                try:
                                    for item in xy.xeq('%s %s' % (entity.e_schema.type, rtype)):
                                        add( (cwuri, urijoin(item[1]), URIRef(related.cwuri)) )
                                except xy.UnsupportedVocabulary:
                                    pass
                            else:
                                add( (URIRef(related.cwuri), CW[rtype], cwuri) )


    class RDFN3View(RDFView):
        __regid__ = 'rdf.n3'
        format = 'n3'
        content_type = 'text/n3' # see https://www.w3.org/TeamSubmission/n3/#mimetype

    class RDFTurtleView(RDFView):
        __regid__ = 'rdf.turtle'
        format = 'turtle'
        content_type = 'text/turtle' # see https://www.w3.org/TR/turtle/#sec-mediaReg

    class RDFnquadsView(RDFView):
        __regid__ = 'rdf.nquads'
        format = 'nquads'
        content_type = 'application/n-quads' # see https://www.w3.org/TR/n-quads/#sec-mediatype

    class RDFntriplesView(RDFView):
        __regid__ = 'rdf.nt'
        format = 'nt'
        content_type = 'application/n-triples' # see https://www.w3.org/TR/n-triples/#n-triples-mediatype

    class RDFtrigView(RDFView):
        __regid__ = 'rdf.trig'
        format = 'trig'
        content_type = 'application/trig' # see https://www.w3.org/TR/trig/#sec-mime
