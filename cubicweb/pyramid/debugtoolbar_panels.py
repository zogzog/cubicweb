# copyright 2019 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from collections import defaultdict

from pyramid_debugtoolbar.panels import DebugPanel
from cubicweb.debug import subscribe_to_debug_channel, unsubscribe_to_debug_channel
from cubicweb.misc.source_highlight import highlight_html, generate_css


class RQLDebugPanel(DebugPanel):
    """
    CubicWeb RQL debug panel
    """

    """
    Excepted formats:
    SQL: {
        'rql_query_tracing_token': 'some_token',
        'args': {dict with some args},
        'rollback': False|True,
        'time': time_in_float,
        'sql':_sql_query_as_a_string,
    }
    """

    name = 'RQL'
    title = 'RQL queries'
    nav_title = 'RQL'
    nav_subtitle_style = 'progress-bar-info'

    has_content = True
    template = 'cubicweb.pyramid:debug_toolbar_templates/rql.dbtmako'

    def __init__(self, request):
        self.data = {
            'rql_queries': [],
            'sql_queries': [],
            'highlight': highlight_html,
            'generate_css': generate_css,
        }
        subscribe_to_debug_channel("rql", self.collect_rql_queries)
        subscribe_to_debug_channel("sql", self.collect_sql_queries)

    @property
    def nav_subtitle(self):
        return '%d' % len(self.data['rql_queries'])

    def collect_rql_queries(self, rql_query):
        rql_query["generated_sql_queries"] = []

        # link sql queries to rql's one
        for sql_query in self.data["sql_queries"]:
            if sql_query["rql_query_tracing_token"] == rql_query["rql_query_tracing_token"]:
                rql_query["generated_sql_queries"].append(sql_query)

        self.data["rql_queries"].append(rql_query)

    def collect_sql_queries(self, sql_query):
        self.data["sql_queries"].append(sql_query)

    def process_response(self, response):
        unsubscribe_to_debug_channel("rql", self.collect_rql_queries)
        unsubscribe_to_debug_channel("sql", self.collect_sql_queries)


def includeme(config):
    config.add_debugtoolbar_panel(RQLDebugPanel)
