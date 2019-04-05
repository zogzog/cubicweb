from logilab.mtconverter import guess_mimetype_and_encoding
from cubicweb.entities import AnyEntity, fetch_config


class File(AnyEntity):
    """customized class for File entities"""
    __regid__ = 'File'
    fetch_attrs, cw_fetch_order = fetch_config(['data_name', 'title'])

    def set_format_and_encoding(self):
        """try to set format and encoding according to known values (filename,
        file content, format, encoding).

        This method must be called in a before_[add|update]_entity hook else it
        won't have any effect.
        """
        assert 'data' in self.cw_edited, "missing mandatory attribute data"
        if self.cw_edited.get('data'):
            if (hasattr(self.data, 'filename')
                    and not self.cw_edited.get('data_name')):
                self.cw_edited['data_name'] = self.data.filename
        else:
            self.cw_edited['data_format'] = None
            self.cw_edited['data_encoding'] = None
            self.cw_edited['data_name'] = None
            return
        if 'data_format' in self.cw_edited:
            format = self.cw_edited.get('data_format')
        else:
            format = None
        if 'data_encoding' in self.cw_edited:
            encoding = self.cw_edited.get('data_encoding')
        else:
            encoding = None
        if not (format and encoding):
            format, encoding = guess_mimetype_and_encoding(
                data=self.cw_edited.get('data'),
                # use get and not get_value since data has changed, we only
                # want to consider explicitly specified values, not old ones
                filename=self.cw_edited.get('data_name'),
                format=format, encoding=encoding,
                fallbackencoding=self._cw.encoding)
            if format:
                self.cw_edited['data_format'] = str(format)
            if encoding:
                self.cw_edited['data_encoding'] = str(encoding)


class UnResizeable(Exception):
    pass
