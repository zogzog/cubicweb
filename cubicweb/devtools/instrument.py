# copyright 2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
"""Instrumentation utilities"""
import os

try:
    import pygraphviz
except ImportError:
    pygraphviz = None

from cubicweb.cwvreg import CWRegistryStore
from cubicweb.devtools.devctl import DevConfiguration


ALL_COLORS = [
    "00FF00", "0000FF", "FFFF00", "FF00FF", "00FFFF", "000000",
    "800000", "008000", "000080", "808000", "800080", "008080", "808080",
    "C00000", "00C000", "0000C0", "C0C000", "C000C0", "00C0C0", "C0C0C0",
    "400000", "004000", "000040", "404000", "400040", "004040", "404040",
    "200000", "002000", "000020", "202000", "200020", "002020", "202020",
    "600000", "006000", "000060", "606000", "600060", "006060", "606060",
    "A00000", "00A000", "0000A0", "A0A000", "A000A0", "00A0A0", "A0A0A0",
    "E00000", "00E000", "0000E0", "E0E000", "E000E0", "00E0E0", "E0E0E0",
    ]
_COLORS = {}
def get_color(key):
    try:
        return _COLORS[key]
    except KeyError:
        _COLORS[key] = '#'+ALL_COLORS[len(_COLORS) % len(ALL_COLORS)]
        return _COLORS[key]

def warn(msg, *args):
    print('WARNING: %s' % (msg % args))

def info(msg):
    print('INFO: ' + msg)


class PropagationAnalyzer(object):
    """Abstract propagation analyzer, providing utility function to extract
    entities involved in propagation from a schema, as well as propagation
    rules from hooks (provided they use intrumentalized sets, see
    :class:`CubeTracerSet`).

    Concrete classes should at least define `prop_rel` class attribute and
    implements the `is_root` method.

    See `localperms` or `nosylist` cubes for example usage (`ccplugin` module).
    """
    prop_rel = None # name of the propagation relation

    def init(self, cube):
        """Initialize analyze for the given cube, returning the (already loaded)
        vregistry and a set of entities which we're interested in.
        """
        config = DevConfiguration(cube)
        schema = config.load_schema()
        vreg = CWRegistryStore(config)
        vreg.set_schema(schema) # set_schema triggers objects registrations
        eschemas = set(eschema for eschema in schema.entities()
                       if self.should_include(eschema))
        return vreg, eschemas

    def is_root(self, eschema):
        """Return `True` if given entity schema is a root of the graph"""
        raise NotImplementedError()

    def should_include(self, eschema):
        """Return `True` if given entity schema should be included by the graph.
        """

        if self.prop_rel in eschema.subjrels or self.is_root(eschema):
            return True
        return False

    def prop_edges(self, s_rels, o_rels, eschemas):
        """Return a set of edges where propagation has been detected.

        Each edge is defined by a 4-uple (from node, to node, rtype, package)
        where `rtype` is the relation type bringing from <from node> to <to
        node> and `package` is the cube adding the rule to the propagation
        control set (see see :class:`CubeTracerSet`).
        """
        schema = iter(eschemas).next().schema
        prop_edges = set()
        for rtype in s_rels:
            found = False
            for subj, obj in schema.rschema(rtype).rdefs:
                if subj in eschemas and obj in eschemas:
                    found = True
                    prop_edges.add( (subj, obj, rtype, s_rels.value_cube[rtype]) )
            if not found:
                warn('no rdef match for %s', rtype)
        for rtype in o_rels:
            found = False
            for subj, obj in schema.rschema(rtype).rdefs:
                if subj in eschemas and obj in eschemas:
                    found = True
                    prop_edges.add( (obj, subj, rtype, o_rels.value_cube[rtype]) )
            if not found:
                warn('no rdef match for %s', rtype)
        return prop_edges

    def detect_problems(self, eschemas, edges):
        """Given the set of analyzed entity schemas and edges between them,
        return a set of entity schemas where a problem has been detected.
        """
        problematic = set()
        for eschema in eschemas:
            if self.has_problem(eschema, edges):
                problematic.add(eschema)
        not_problematic = set(eschemas).difference(problematic)
        if not_problematic:
            info('nothing problematic in: %s' %
                 ', '.join(e.type for e in not_problematic))
        return problematic

    def has_problem(self, eschema, edges):
        """Return `True` if the given schema is considered problematic,
        considering base propagation rules.
        """
        root = self.is_root(eschema)
        has_prop_rel = self.prop_rel in eschema.subjrels
        # root but no propagation relation
        if root and not has_prop_rel:
            warn('%s is root but miss %s', eschema, self.prop_rel)
            return True
        # propagated but without propagation relation / not propagated but
        # with propagation relation
        if not has_prop_rel and \
                any(edge for edge in edges if edge[1] == eschema):
            warn("%s miss %s but is reached by propagation",
                 eschema, self.prop_rel)
            return True
        elif has_prop_rel and not root:
            rdef = eschema.rdef(self.prop_rel, takefirst=True)
            edges = [edge for edge in edges if edge[1] == eschema]
            if not edges:
                warn("%s has %s but isn't reached by "
                     "propagation", eschema, self.prop_rel)
                return True
            # require_permission relation / propagation rule not added by
            # the same cube
            elif not any(edge for edge in edges if edge[-1] == rdef.package):
                warn('%s has %s relation / propagation rule'
                     ' not added by the same cube (%s / %s)', eschema,
                     self.prop_rel, rdef.package, edges[0][-1])
                return True
        return False

    def init_graph(self, eschemas, edges, problematic):
        """Initialize and return graph, adding given nodes (entity schemas) and
        edges between them.

        Require pygraphviz installed.
        """
        if pygraphviz is None:
            raise RuntimeError('pygraphviz is not installed')
        graph = pygraphviz.AGraph(strict=False, directed=True)
        for eschema in eschemas:
            if eschema in problematic:
                params = {'color': '#ff0000', 'fontcolor': '#ff0000'}
            else:
                params = {}#'color': get_color(eschema.package)}
            graph.add_node(eschema.type, **params)
        for subj, obj, rtype, package in edges:
            graph.add_edge(str(subj), str(obj), label=rtype,
                           color=get_color(package))
        return graph

    def add_colors_legend(self, graph):
        """Add a legend of used colors to the graph."""
        for package, color in sorted(_COLORS.items()):
            graph.add_node(package, color=color, fontcolor=color, shape='record')


class CubeTracerSet(object):
    """Dumb set implementation whose purpose is to keep track of which cube is
    being loaded when something is added to the set.

    Results will be found in the `value_cube` attribute dictionary.

    See `localperms` or `nosylist` cubes for example usage (`hooks` module).
    """
    def __init__(self, vreg, wrapped):
        self.vreg = vreg
        self.wrapped = wrapped
        self.value_cube = {}

    def add(self, value):
        self.wrapped.add(value)
        cube = self.vreg.currently_loading_cube
        if value in self.value_cube:
            warn('%s is propagated by cube %s and cube %s',
                 value, self.value_cube[value], cube)
        else:
            self.value_cube[value] = cube

    def __iter__(self):
        return iter(self.wrapped)

    def __ior__(self, other):
        for value in other:
            self.add(value)
        return self

    def __ror__(self, other):
        other |= self.wrapped
        return other
