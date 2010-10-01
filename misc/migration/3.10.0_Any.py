# rename cwprops for boxes/contentnavigation
for x in rql('Any X,XK WHERE X pkey XK, '
             'X pkey ~= "boxes.%s" OR '
             'X pkey ~= "contentnavigation.%s"').entities():
    x.set_attributes(pkey=u'ctxcomponents.' + x.pkey.split('.', 1)[1])

