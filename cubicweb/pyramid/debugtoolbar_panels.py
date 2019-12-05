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

from pyramid_debugtoolbar.panels import DebugPanel

from cubicweb.debug import subscribe_to_debug_channel, unsubscribe_to_debug_channel
from cubicweb.misc.source_highlight import highlight_html, generate_css, has_pygments
from cubicweb.pyramid.debug_source_code import source_code_url, source_code_url_in_stack


class CubicWebDebugPanel(DebugPanel):
    """
    CubicWeb general debug panel
    """

    """
    Excepted formats:
    Controller: {
        "kind": ctrlid,
        "request": req,
        "path": req.path,
        "controller": controller,
    }
    """

    name = 'CubicWeb'
    nav_title = 'CubicWeb'
    title = 'CubicWeb general panel'

    has_content = True
    template = 'cubicweb.pyramid:debug_toolbar_templates/cw.dbtmako'

    def __init__(self, request):
        self.data = {
            'controller': None,
            'source_code_url': source_code_url,
        }

        subscribe_to_debug_channel("controller", self.collect_controller)

    def collect_controller(self, controller):
        self.data["controller"] = controller

    def process_response(self, response):
        unsubscribe_to_debug_channel("controller", self.collect_controller)


class RegistryDecisionsDebugPanel(DebugPanel):
    """
    CubicWeb registry decisions debug panel
    """

    name = 'RegistryDecisions'
    title = 'Registry Decisions'
    nav_title = 'Registry Decisions'

    has_content = True
    template = 'cubicweb.pyramid:debug_toolbar_templates/registry_decisions.dbtmako'

    def __init__(self, request):
        # clear on every new response
        self.data = {
            'registry_decisions': [],
            'vreg': None,
            'highlight': highlight_html,
            'generate_css': generate_css,
            'source_code_url': source_code_url,
        }

        subscribe_to_debug_channel("vreg", self.collect_vreg)
        subscribe_to_debug_channel("registry_decisions", self.collect_registry_decisions)

    def collect_vreg(self, message):
        self.data["vreg"] = message["vreg"]

    def collect_registry_decisions(self, decision):
        # decision = {
        #     "all_objects": [],
        #     "end_score": int,
        #     "winners": [],
        #     "registry": obj,
        #     "args": args,
        #     "kwargs": kwargs,
        #     "self": registry,
        # }
        decision["key"] = None
        self.data["registry_decisions"].append(decision)

    def link_registry_to_their_key(self):
        if self.data["vreg"]:
            # use "id" here to be hashable
            registry_to_key = {id(registry): key for key, registry in self.data["vreg"].items()}
            for decision in self.data["registry_decisions"]:
                decision["key"] = registry_to_key.get(id(decision["self"]))

    def process_response(self, response):
        unsubscribe_to_debug_channel("registry_decisions", self.collect_registry_decisions)
        unsubscribe_to_debug_channel("vreg", self.collect_vreg)

        self.link_registry_to_their_key()


class RegistryDebugPanel(DebugPanel):
    """
    CubicWeb registry content and decisions debug panel
    """

    name = 'Registry'
    title = 'Registry Store'
    nav_title = 'Registry Store'

    has_content = True
    template = 'cubicweb.pyramid:debug_toolbar_templates/registry.dbtmako'

    def __init__(self, request):
        self.data = {
            'vreg': None,
            'source_code_url': source_code_url,
        }
        subscribe_to_debug_channel("vreg", self.collect_vreg)

    def collect_vreg(self, message):
        self.data["vreg"] = message["vreg"]

    def process_response(self, response):
        unsubscribe_to_debug_channel("vreg", self.collect_vreg)


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
            'has_pygments': has_pygments,
            'source_code_url_in_stack': source_code_url_in_stack,
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


class SQLDebugPanel(DebugPanel):
    """
    CubicWeb SQL debug panel
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

    name = 'SQL'
    title = 'SQL queries'
    nav_title = 'SQL'
    nav_subtitle_style = 'progress-bar-info'

    has_content = True
    template = 'cubicweb.pyramid:debug_toolbar_templates/sql.dbtmako'

    def __init__(self, request):
        self.data = {
            'rql_queries': [],
            'sql_queries': [],
            'highlight': highlight_html,
            'generate_css': generate_css,
            'has_pygments': has_pygments,
            'source_code_url_in_stack': source_code_url_in_stack,
        }
        subscribe_to_debug_channel("rql", self.collect_rql_queries)
        subscribe_to_debug_channel("sql", self.collect_sql_queries)

    @property
    def nav_subtitle(self):
        return len(self.data['sql_queries'])

    def collect_rql_queries(self, rql_query):
        self.data["rql_queries"].append(rql_query)

        # link sql queries to rql's one
        for sql_query in self.data["sql_queries"]:
            if sql_query["rql_query_tracing_token"] == rql_query["rql_query_tracing_token"]:
                sql_query["from_rql_query"] = rql_query

    def collect_sql_queries(self, sql_query):
        sql_query["from_rql_query"] = None
        self.data["sql_queries"].append(sql_query)

    def process_response(self, response):
        unsubscribe_to_debug_channel("rql", self.collect_rql_queries)
        unsubscribe_to_debug_channel("sql", self.collect_sql_queries)


def includeme(config):
    config.add_debugtoolbar_panel(CubicWebDebugPanel)
    config.add_debugtoolbar_panel(RegistryDecisionsDebugPanel)
    config.add_debugtoolbar_panel(RegistryDebugPanel)
    config.add_debugtoolbar_panel(RQLDebugPanel)
    config.add_debugtoolbar_panel(SQLDebugPanel)
