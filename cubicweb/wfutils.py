# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Workflow setup utilities.

These functions work with a declarative workflow definition:

.. code-block:: python

        {
            'etypes': 'CWGroup',
            'default': True,
            'initial_state': u'draft',
            'states': [u'draft', u'published'],
            'transitions': {
                u'publish': {
                    'fromstates': u'draft',
                    'tostate': u'published',
                    'requiredgroups': u'managers'
                    'conditions': (
                        'U in_group X',
                        'X owned_by U'
                    )
                }
            }
        }

.. autofunction:: setup_workflow
.. autofunction:: cleanupworkflow
"""

import collections

from six import text_type

from cubicweb import NoResultError


def get_tuple_or_list(value):
    if value is None:
        return None
    if not isinstance(value, (tuple, list)):
        value = (value,)
    return value


def cleanupworkflow(cnx, wf, wfdef):
    """Cleanup an existing workflow by removing the states and transitions that
    do not exist in the given definition.

    :param cnx: A connexion with enough permissions to define a workflow
    :param wf: A `Workflow` entity
    :param wfdef: A workflow definition
    """
    cnx.execute(
        'DELETE State S WHERE S state_of WF, WF eid %%(wf)s, '
        'NOT S name IN (%s)' % (
            ', '.join('"%s"' % s for s in wfdef['states'])),
        {'wf': wf.eid})

    cnx.execute(
        'DELETE Transition T WHERE T transition_of WF, WF eid %%(wf)s, '
        'NOT T name IN (%s)' % (
            ', '.join('"%s"' % s for s in wfdef['transitions'])),
        {'wf': wf.eid})


def setup_workflow(cnx, name, wfdef, cleanup=True):
    """Create or update a workflow definition so it matches the given
    definition.

    :param cnx: A connexion with enough permissions to define a workflow
    :param name: The workflow name. Used to create the `Workflow` entity, or
                 to find an existing one.
    :param wfdef: A workflow definition.
    :param cleanup: Remove extra states and transitions. Can be done separatly
                    by calling :func:`cleanupworkflow`.
    :return: The created/updated workflow entity
    """
    name = text_type(name)
    try:
        wf = cnx.find('Workflow', name=name).one()
    except NoResultError:
        wf = cnx.create_entity('Workflow', name=name)

    etypes = get_tuple_or_list(wfdef['etypes'])
    cnx.execute('DELETE WF workflow_of ETYPE WHERE WF eid %%(wf)s, '
                'NOT ETYPE name IN (%s)' % ','.join('"%s"' for e in etypes),
                {'wf': wf.eid})
    cnx.execute('SET WF workflow_of ETYPE WHERE'
                ' NOT WF workflow_of ETYPE, WF eid %%(wf)s, ETYPE name IN (%s)'
                % ','.join('"%s"' % e for e in etypes),
                {'wf': wf.eid})
    if wfdef['default']:
        cnx.execute(
            'SET ETYPE default_workflow X '
            'WHERE '
            'NOT ETYPE default_workflow X, '
            'X eid %%(x)s, ETYPE name IN (%s)' % ','.join(
                '"%s"' % e for e in etypes),
            {'x': wf.eid})

    states = {}
    states_transitions = collections.defaultdict(list)
    for state in wfdef['states']:
        st = wf.state_by_name(state) or wf.add_state(state)
        states[state] = st

    if 'initial_state' in wfdef:
        wf.cw_set(initial_state=states[wfdef['initial_state']])

    for trname, trdef in wfdef['transitions'].items():
        tr = (wf.transition_by_name(trname)
              or cnx.create_entity('Transition', name=trname))
        tr.cw_set(transition_of=wf)
        if trdef.get('tostate'):
            tr.cw_set(destination_state=states[trdef['tostate']])
        fromstates = get_tuple_or_list(trdef.get('fromstates', ()))
        for stname in fromstates:
            states_transitions[stname].append(tr)

        requiredgroups = get_tuple_or_list(trdef.get('requiredgroups', ()))
        conditions = get_tuple_or_list(trdef.get('conditions', ()))

        tr.set_permissions(requiredgroups, conditions, reset=True)

    for stname, transitions in states_transitions.items():
        state = states[stname]
        state.cw_set(allowed_transition=None)
        state.cw_set(allowed_transition=transitions)

    if cleanup:
        cleanupworkflow(cnx, wf, wfdef)

    return wf
