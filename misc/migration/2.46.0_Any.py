

rql('SET X value "navtop" WHERE X pkey ~= "contentnavigation.%.context", X value "header"')
rql('SET X value "navcontenttop" WHERE X pkey ~= "contentnavigation%.context", X value "incontext"')
rql('SET X value "navcontentbottom" WHERE X pkey ~= "contentnavigation%.context", X value "footer"')
checkpoint()

if 'require_permission' in schema:
    synchronize_rschema('require_permission')
