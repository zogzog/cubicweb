from cubicweb.entities import AnyEntity, fetch_config


class BlogEntry(AnyEntity):
    __regid__ = 'BlogEntry'
    fetch_attrs, cw_fetch_order = fetch_config(
        ['creation_date', 'title'], order='DESC')
