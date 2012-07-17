config['rql-cache-size'] = config['rql-cache-size'] * 10

add_entity_type('CWDataImport')

from cubicweb.schema import CONSTRAINTS, guess_rrqlexpr_mainvars
for rqlcstr in rql('Any X,XT,XV WHERE X is CWConstraint, X cstrtype XT, X value XV,'
                   'X cstrtype XT, XT name IN ("RQLUniqueConstraint","RQLConstraint","RQLVocabularyConstraint"),'
                   'NOT X value ~= ";%"').entities():
    expression = rqlcstr.value
    mainvars = guess_rrqlexpr_mainvars(expression)
    yamscstr = CONSTRAINTS[rqlcstr.type](expression, mainvars)
    rqlcstr.cw_set(value=yamscstr.serialize())
    print 'updated', rqlcstr.type, rqlcstr.value.strip()
