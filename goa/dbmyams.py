"""extends yams to be able to load google appengine's schemas

MISSING FEATURES:
 - ListProperty, StringList, EmailProperty, etc. (XXX)
 - ReferenceProperty.verbose_name, collection_name, etc. (XXX)

XXX proprify this knowing we'll use goa.db
"""

from os.path import join
from datetime import datetime, date, time

from google.appengine.ext import db
from google.appengine.api import datastore_types

from yams.buildobjs import (String, Int, Float, Boolean, Date, Time, Datetime,
                            Bytes, SubjectRelation)
from yams.buildobjs import metadefinition, EntityType

from cubicweb.schema import CubicWebSchemaLoader
from cubicweb.goa import db as goadb

# db.Model -> yams ############################################################

DBM2Y_TYPESMAP = {
    basestring: String,
    datastore_types.Text: String,
    int: Int,
    float: Float,
    bool: Boolean,
    time: Time,
    date: Date,
    datetime: Datetime,
    datastore_types.Blob: Bytes,
    }


def dbm2y_default_factory(prop, **kwargs):
    """just wraps the default types map to set
    basic constraints like `required`, `default`, etc.
    """
    yamstype = DBM2Y_TYPESMAP[prop.data_type]
    if 'default' not in kwargs:
        default = prop.default_value()
        if default is not None:
            kwargs['default'] = default
    if prop.required:
        kwargs['required'] = True
    return yamstype(**kwargs)

def dbm2y_string_factory(prop):
    """like dbm2y_default_factory but also deals with `maxsize` and `vocabulary`"""
    kwargs = {}
    if prop.data_type is basestring:
        kwargs['maxsize'] = 500
    if prop.choices is not None:
        kwargs['vocabulary'] = prop.choices
    return dbm2y_default_factory(prop, **kwargs)

def dbm2y_date_factory(prop):
    """like dbm2y_default_factory but also deals with today / now definition"""
    kwargs = {}
    if prop.auto_now_add:
        if prop.data_type is datetime:
            kwargs['default'] = 'now'
        else:
            kwargs['default'] = 'today'
    # XXX no equivalent to Django's `auto_now`
    return dbm2y_default_factory(prop, **kwargs)

    
def dbm2y_relation_factory(etype, prop, multiple=False):
    """called if `prop` is a `db.ReferenceProperty`"""
    if multiple:
        cardinality = '**'
    elif prop.required:
        cardinality = '1*'
    else:
        cardinality = '?*'
    # XXX deal with potential kwargs of ReferenceProperty.__init__()
    try:
        return SubjectRelation(prop.data_type.kind(), cardinality=cardinality)
    except AttributeError, ex:
        # hack, data_type is still _SELF_REFERENCE_MARKER
        return SubjectRelation(etype, cardinality=cardinality)
    
    
DBM2Y_FACTORY = {
    basestring: dbm2y_string_factory,
    datastore_types.Text: dbm2y_string_factory,
    int: dbm2y_default_factory,
    float: dbm2y_default_factory,
    bool: dbm2y_default_factory,
    time: dbm2y_date_factory,
    date: dbm2y_date_factory,
    datetime: dbm2y_date_factory,
    datastore_types.Blob: dbm2y_default_factory,
    }


class GaeSchemaLoader(CubicWebSchemaLoader):
    """Google appengine schema loader class"""
    def __init__(self, *args, **kwargs):
        self.use_gauthservice = kwargs.pop('use_gauthservice', False)
        super(GaeSchemaLoader, self).__init__(*args, **kwargs)
        self.defined = {}
        self.created = []
        self.loaded_files = []
        self._instantiate_handlers()
        
    def finalize(self, register_base_types=False):
        return self._build_schema('google-appengine', register_base_types)

    def load_dbmodel(self, name, props):
        clsdict = {}
        ordered_props = sorted(props.items(),
                               key=lambda x: x[1].creation_counter)
        for pname, prop in ordered_props:
            if isinstance(prop, db.ListProperty):
                if not issubclass(prop.item_type, db.Model):
                    self.error('ignoring list property with %s item type'
                               % prop.item_type)
                    continue
                rdef = dbm2y_relation_factory(name, prop, multiple=True)
            else:
                try:
                    if isinstance(prop, (db.ReferenceProperty,
                                         goadb.ReferencePropertyStub)):
                        rdef = dbm2y_relation_factory(name, prop)
                    else:
                        rdef = DBM2Y_FACTORY[prop.data_type](prop)
                except KeyError, ex:
                    import traceback
                    traceback.print_exc()
                    self.error('ignoring property %s (keyerror on %s)' % (pname, ex))
                    continue
            rdef.creation_rank = prop.creation_counter
            clsdict[pname] = rdef
        edef = metadefinition(name, (EntityType,), clsdict)
        self.add_definition(self, edef())

    def error(self, msg):
        print 'ERROR:', msg

    def import_yams_schema(self, ertype, schemamod):
        erdef = self.pyreader.import_erschema(ertype, schemamod)

    def import_yams_cube_schema(self, templpath):
        for filepath in self.get_schema_files(templpath):
            self.handle_file(filepath)
        
    @property
    def pyreader(self):
        return self._live_handlers['.py']
        
import os
from cubicweb import CW_SOFTWARE_ROOT

if os.environ.get('APYCOT_ROOT'):
    SCHEMAS_LIB_DIRECTORY = join(os.environ['APYCOT_ROOT'],
                                 'local', 'share', 'cubicweb', 'schemas')
else:
    SCHEMAS_LIB_DIRECTORY = join(CW_SOFTWARE_ROOT, 'schemas')

def load_schema(config, schemaclasses=None, extrahook=None):
    """high level method to load all the schema for a lax application"""
    # IMPORTANT NOTE: dbmodel schemas must be imported **BEFORE**
    # the loader is instantiated because this is where the dbmodels
    # are registered in the yams schema
    for compname in config['included-cubes']:
        comp = __import__('%s.schema' % compname)
    loader = GaeSchemaLoader(use_gauthservice=config['use-google-auth'], db=db)
    loader.lib_directory = SCHEMAS_LIB_DIRECTORY
    if schemaclasses is not None:
        for cls in schemaclasses:
            loader.load_dbmodel(cls.__name__, goadb.extract_dbmodel(cls))
    elif config['schema-type'] == 'dbmodel':
        import schema as appschema
        for objname, obj in vars(appschema).items():
            if isinstance(obj, type) and issubclass(obj, goadb.Model) and obj.__module__ == appschema.__name__:
                loader.load_dbmodel(obj.__name__, goadb.extract_dbmodel(obj))
    for erschema in ('EGroup', 'EEType', 'ERType', 'RQLExpression',
                     'is_', 'is_instance_of',
                     'read_permission', 'add_permission',
                     'delete_permission', 'update_permission'):
        loader.import_yams_schema(erschema, 'bootstrap')  
    loader.handle_file(join(SCHEMAS_LIB_DIRECTORY, 'base.py'))
    cubes = config['included-yams-cubes']
    for cube in reversed(config.expand_cubes(cubes)):
        config.info('loading cube %s', cube)
        loader.import_yams_cube_schema(config.cube_dir(cube))
    if config['schema-type'] == 'yams':
        loader.import_yams_cube_schema('.')
    if extrahook is not None:
        extrahook(loader)
    if config['use-google-auth']:
        loader.defined['EUser'].remove_relation('upassword')
        loader.defined['EUser'].permissions['add'] = ()
        loader.defined['EUser'].permissions['delete'] = ()
    for etype in ('EGroup', 'RQLExpression'):
        read_perm_rel = loader.defined[etype].get_relations('read_permission').next()
        read_perm_rel.cardinality = '**'
    # XXX not yet ready for EUser workflow
    loader.defined['EUser'].remove_relation('in_state')
    loader.defined['EUser'].remove_relation('wf_info_for')
    # remove RQLConstraint('NOT O name "owners"') on EUser in_group EGroup
    # since "owners" group is not persistent with gae
    loader.defined['EUser'].get_relations('in_group').next().constraints = []
    # return the full schema including the cubes' schema
    for ertype in loader.defined.values():
        if getattr(ertype, 'inlined', False):
            ertype.inlined = False
    return loader.finalize()

