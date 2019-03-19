import os

from cubicweb.server import hook
from cubicweb.predicates import is_instance
from cubicweb.entities import adapters

from cubicweb_file.entities import UnResizeable


class UpdateFileHook(hook.Hook):
    """a file has been updated, check data_format/data_encoding consistency
    """
    __regid__ = 'updatefilehook'
    __select__ = hook.Hook.__select__ & is_instance('File')
    events = ('before_add_entity', 'before_update_entity',)
    order = -1  # should be run before other hooks
    category = 'hash'

    def __call__(self):
        edited = self.entity.cw_edited
        if 'data' in edited:
            self.entity.set_format_and_encoding()
            maxsize = None
            if maxsize and self.entity.data_format.startswith('image/'):
                iimage = self.entity.cw_adapt_to('IImage')
                try:
                    edited['data'] = iimage.resize(maxsize)
                except UnResizeable:
                    # if the resize fails for some reason, do nothing
                    # (original image will be stored)
                    pass

            # thumbnail cache invalidation
            if 'update' in self.event and 'data' in edited:
                thumb = self.entity.cw_adapt_to('IThumbnail')
                if not thumb:
                    return
                thumbpath = thumb.thumbnail_path()
                if thumbpath:
                    try:
                        os.unlink(thumbpath)
                    except Exception as exc:
                        self.warning(
                            'could not invalidate thumbnail file `%s` '
                            '(cause: %s)',
                            thumbpath, exc)


class FileIDownloadableAdapter(adapters.IDownloadableAdapter):
    __select__ = is_instance('File')

    # IDownloadable
    def download_url(self, **kwargs):
        # include filename in download url for nicer url
        name = self._cw.url_quote(self.download_file_name())
        path = '%s/raw/%s' % (self.entity.rest_path(), name)
        return self._cw.build_url(path, **kwargs)

    def download_content_type(self):
        return self.entity.data_format

    def download_encoding(self):
        return self.entity.data_encoding

    def download_file_name(self):
        return self.entity.data_name

    def download_data(self):
        return self.entity.data.getvalue()
