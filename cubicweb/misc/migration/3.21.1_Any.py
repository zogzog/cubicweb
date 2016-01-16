# re-read ComputedRelation permissions from schema.py now that we're
# able to serialize them
for computedrtype in schema.iter_computed_relations():
    sync_schema_props_perms(computedrtype.type)
