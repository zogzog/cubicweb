from cubicweb.entities import AnyEntity, fetch_config


class Tag(AnyEntity):
    __regid__ = 'Tag'
    fetch_attrs, cw_fetch_order = fetch_config(['name'])
