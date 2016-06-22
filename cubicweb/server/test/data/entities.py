from cubicweb.server.sources import datafeed


class SourceParserSuccess(datafeed.DataFeedParser):
    __regid__ = 'test_source_parser_success'

    def process(self, url, raise_on_error=False):
        entity = self._cw.create_entity('Card', title=u'success')
        self.notify_updated(entity)


class SourceParserFail(SourceParserSuccess):
    __regid__ = 'test_source_parser_fail'

    def process(self, url, raise_on_error=False):
        entity = self._cw.create_entity('Card', title=u'fail')
        self.notify_updated(entity)
        raise RuntimeError("fail")
