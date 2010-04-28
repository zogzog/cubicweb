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
"""cubicweb on google appengine

"""
__docformat__ = "restructuredtext en"


try:
    # WARNING: do not import the google's db module here since it will take
    #          precedence over our own db submodule
    from google.appengine.api.datastore import Key, Get, Query
    from google.appengine.api.datastore_errors import BadKeyError
except ImportError:
    # not in google app environment
    pass
else:

    import os
    _SS = os.environ.get('SERVER_SOFTWARE')
    if _SS is None:
        MODE = 'test'
    elif _SS.startswith('Dev'):
        MODE = 'dev'
    else:
        MODE = 'prod'

    from cubicweb.server import SOURCE_TYPES
    from cubicweb.goa.gaesource import GAESource
    SOURCE_TYPES['gae'] = GAESource


    def do_monkey_patch():

        # monkey patch yams Bytes validator since it should take a bytes string with gae
        # and not a StringIO
        def check_bytes(eschema, value):
            """check value is a bytes string"""
            return isinstance(value, str)
        from yams import constraints
        constraints.BASE_CHECKERS['Bytes'] = check_bytes

        def rql_for_eid(eid):
            return 'Any X WHERE X eid "%s"' % eid
        from cubicweb import uilib
        uilib.rql_for_eid = rql_for_eid

        def typed_eid(eid):
            try:
                return str(Key(eid))
            except BadKeyError:
                raise ValueError(eid)
        import cubicweb
        cubicweb.typed_eid = typed_eid

        # XXX monkey patch cubicweb.schema.CubicWebSchema to have string eid with
        #     optional cardinality (since eid is set after the validation)

        import re
        from yams import buildobjs as ybo

        def add_entity_type(self, edef):
            edef.name = edef.name.encode()
            assert re.match(r'[A-Z][A-Za-z0-9]*[a-z]+[0-9]*$', edef.name), repr(edef.name)
            eschema = super(CubicWebSchema, self).add_entity_type(edef)
            if not eschema.final:
                # automatically add the eid relation to non final entity types
                rdef = ybo.RelationDefinition(eschema.type, 'eid', 'Bytes',
                                              cardinality='?1', uid=True)
                self.add_relation_def(rdef)
                rdef = ybo.RelationDefinition(eschema.type, 'identity', eschema.type)
                self.add_relation_def(rdef)
            self._eid_index[eschema.eid] = eschema
            return eschema

        from cubicweb.schema import CubicWebSchema
        CubicWebSchema.add_entity_type = add_entity_type


        # don't reset vreg on repository set_schema
        from cubicweb.server import repository
        orig_set_schema = repository.Repository.set_schema
        def set_schema(self, schema, resetvreg=True):
            orig_set_schema(self, schema, False)
        repository.Repository.set_schema = set_schema
        # deactivate function ensuring relation cardinality consistency
        repository.del_existing_rel_if_needed = lambda *args: None

        def get_cubes(self):
            """return the list of top level cubes used by this instance"""
            config = self.config
            cubes = config['included-cubes'] + config['included-yams-cubes']
            return config.expand_cubes(cubes)
        repository.Repository.get_cubes = get_cubes

        from rql import RQLHelper
        RQLHelper.simplify = lambda x, r: None

        # activate entity caching on the server side

        def set_entity_cache(self, entity):
            self.transaction_data.setdefault('_eid_cache', {})[entity.eid] = entity

        def entity_cache(self, eid):
            return self.transaction_data['_eid_cache'][eid]

        def drop_entity_cache(self, eid=None):
            if eid is None:
                self.transaction_data['_eid_cache'] = {}
            elif '_eid_cache' in self.transaction_data:
                self.transaction_data['_eid_cache'].pop(eid, None)

        def datastore_get(self, key):
            if isinstance(key, basestring):
                key = Key(key)
            try:
                gentity = self.transaction_data['_key_cache'][key]
                #self.critical('cached %s', gentity)
            except KeyError:
                gentity = Get(key)
                #self.critical('Get %s', gentity)
                self.transaction_data.setdefault('_key_cache', {})[key] = gentity
            return gentity

        def clear_datastore_cache(self, key=None):
            if key is None:
                self.transaction_data['_key_cache'] = {}
            else:
                if isinstance(key, basestring):
                    key = Key(key)
                self.transaction_data['_key_cache'].pop(key, None)

        from cubicweb.server.session import Session
        Session.set_entity_cache = set_entity_cache
        Session.entity_cache = entity_cache
        Session.drop_entity_cache = drop_entity_cache
        Session.datastore_get = datastore_get
        Session.clear_datastore_cache = clear_datastore_cache

        from docutils.frontend import OptionParser
        # avoid a call to expanduser which is not available under gae
        def get_standard_config_files(self):
            return self.standard_config_files
        OptionParser.get_standard_config_files = get_standard_config_files
