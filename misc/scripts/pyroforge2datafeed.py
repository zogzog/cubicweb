"""turn a pyro source into a datafeed source

Once this script is run, execute c-c db-check to cleanup relation tables.
"""
import sys

try:
    source_name, = __args__
    source = repo.sources_by_uri[source_name]
except ValueError:
    print('you should specify the source name as script argument (i.e. after --'
          ' on the command line)')
    sys.exit(1)
except KeyError:
    print '%s is not an active source' % source_name
    sys.exit(1)

# check source is reachable before doing anything
try:
    source.get_connection()._repo
except AttributeError:
    print '%s is not reachable. Fix this before running this script' % source_name
    sys.exit(1)

raw_input('Ensure you have shutdown all instances of this application before continuing.'
          ' Type enter when ready.')

system_source = repo.system_source

from base64 import b64encode
from cubicweb.server.edition import EditedEntity

DONT_GET_BACK_ETYPES = set(( # XXX edit as desired
        'State',
        'RecipeStep', 'RecipeStepInput', 'RecipeStepOutput',
        'RecipeTransition', 'RecipeTransitionCondition',
        'NarvalConditionExpression', 'Recipe',
        # XXX TestConfig
        ))


session.mode = 'write' # hold on the connections set

print '******************** backport entity content ***************************'

from cubicweb.server import debugged
todelete = {}
host = source.config['base-url'].split('://')[1]
for entity in rql('Any X WHERE X cw_source S, S eid %(s)s', {'s': source.eid}).entities():
        etype = entity.cw_etype
        if not source.support_entity(etype):
            print "source doesn't support %s, delete %s" % (etype, entity.eid)
        elif etype in DONT_GET_BACK_ETYPES:
            print 'ignore %s, delete %s' % (etype, entity.eid)
        else:
            try:
                entity.complete()
                if not host in entity.cwuri:
                    print 'SKIP foreign entity', entity.cwuri, source.config['base-url']
                    continue
            except Exception:
                print '%s %s much probably deleted, delete it (extid %s)' % (
                    etype, entity.eid, entity.cw_metainformation()['extid'])
            else:
                print 'get back', etype, entity.eid
                entity.cw_edited = EditedEntity(entity, **entity.cw_attr_cache)
                system_source.add_entity(session, entity)
                sql("UPDATE entities SET asource=%(asource)s, source='system', extid=%(extid)s "
                    "WHERE eid=%(eid)s", {'asource': source_name,
                                          'extid': b64encode(entity.cwuri),
                                          'eid': entity.eid})
                continue
        todelete.setdefault(etype, []).append(entity)

# only cleanup entities table, remaining stuff should be cleaned by a c-c
# db-check to be run after this script
for entities in todelete.itervalues():
    system_source.delete_info_multi(session, entities, source_name)


print '******************** backport mapping **********************************'
session.disable_hook_categories('cw.sources')
mapping = []
for mappart in rql('Any X,SCH WHERE X cw_schema SCH, X cw_for_source S, S eid %(s)s',
                   {'s': source.eid}).entities():
    schemaent = mappart.cw_schema[0]
    if schemaent.cw_etype != 'CWEType':
        assert schemaent.cw_etype == 'CWRType'
        sch = schema._eid_index[schemaent.eid]
        for rdef in sch.rdefs.itervalues():
            if not source.support_entity(rdef.subject) \
                    or not source.support_entity(rdef.object):
                continue
            if rdef.subject in DONT_GET_BACK_ETYPES \
                    and rdef.object in DONT_GET_BACK_ETYPES:
                print 'dont map', rdef
                continue
            if rdef.subject in DONT_GET_BACK_ETYPES:
                options = u'action=link\nlinkattr=name'
                roles = 'object',
            elif rdef.object in DONT_GET_BACK_ETYPES:
                options = u'action=link\nlinkattr=name'
                roles = 'subject',
            else:
                options = u'action=copy'
                if rdef.rtype in ('use_environment',):
                    roles = 'object',
                else:
                    roles = 'subject',
            print 'map', rdef, options, roles
            for role in roles:
                mapping.append( (
                        (str(rdef.subject), str(rdef.rtype), str(rdef.object)),
                        options + '\nrole=%s' % role) )
    mappart.cw_delete()

source_ent = rql('CWSource S WHERE S eid %(s)s', {'s': source.eid}).get_entity(0, 0)
source_ent.init_mapping(mapping)

# change source properties
config = u'''synchronize=yes
synchronization-interval=10min
delete-entities=no
'''
rql('SET X type "datafeed", X parser "cw.entityxml", X url %(url)s, X config %(config)s '
    'WHERE X eid %(x)s',
    {'x': source.eid, 'config': config,
     'url': source.config['base-url']+'/project'})


commit()

from cubes.apycot import recipes
recipes.create_quick_recipe(session)
