from cubicweb.entities import AnyEntity, fetch_config


class Card(AnyEntity):
    __regid__ = 'Card'
    rest_attr = 'wikiid'

    fetch_attrs, cw_fetch_order = fetch_config(['title'])

    def rest_path(self):
        if self.wikiid:
            return '%s/%s' % (str(self.e_schema).lower(),
                              self._cw.url_quote(self.wikiid, safe='/'))
        else:
            return super(Card, self).rest_path()
