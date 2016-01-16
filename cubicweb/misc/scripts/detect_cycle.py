from __future__ import print_function

try:
    rtype, = __args__
except ValueError:
    print('USAGE: cubicweb-ctl shell <instance> detect_cycle.py -- <relation type>')
    print()

graph = {}
for fromeid, toeid in rql('Any X,Y WHERE X %s Y' % rtype):
    graph.setdefault(fromeid, []).append(toeid)

from logilab.common.graph import get_cycles

for cycle in get_cycles(graph):
    print('cycle', '->'.join(str(n) for n in cycle))
