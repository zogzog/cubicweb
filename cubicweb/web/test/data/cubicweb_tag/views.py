from cubicweb.web import component
from cubicweb.web.views import ajaxcontroller


@ajaxcontroller.ajaxfunc
def tag_entity(self, eid, taglist):
    execute = self._cw.execute
    # get list of tag for this entity
    tagged_by = set(tagname for (tagname,) in
                    execute('Any N WHERE T name N, T tags X, X eid %(x)s',
                            {'x': eid}))
    for tagname in taglist:
        tagname = tagname.strip()
        if not tagname or tagname in tagged_by:
            continue
        tagrset = execute('Tag T WHERE T name %(name)s', {'name': tagname})
        if tagrset:
            rql = 'SET T tags X WHERE T eid %(t)s, X eid %(x)s'
            execute(rql, {'t': tagrset[0][0], 'x': eid})
        else:
            rql = 'INSERT Tag T: T name %(name)s, T tags X WHERE X eid %(x)s'
            execute(rql, {'name': tagname, 'x': eid})


class TagsBox(component.AjaxEditRelationCtxComponent):
    __regid__ = 'tags_box'
    rtype = 'tags'
    role = 'object'
