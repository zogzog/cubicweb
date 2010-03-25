"""custom storages for the system source"""
from os import unlink, path as osp

from cubicweb import Binary
from cubicweb.server.hook import Operation

def set_attribute_storage(repo, etype, attr, storage):
    repo.system_source.set_storage(etype, attr, storage)

def unset_attribute_storage(repo, etype, attr):
    repo.system_source.unset_storage(etype, attr)

class Storage(object):
    """abstract storage

    * If `source_callback` is true (by default), the callback will be run during
      query result process of fetched attribute's valu and should have the
      following prototype::

        callback(self, source, value)

      where `value` is the value actually stored in the backend. None values
      will be skipped (eg callback won't be called).

    * if `source_callback` is false, the callback will be run during sql
      generation when some attribute with a custom storage is accessed and
      should have the following prototype::

        callback(self, generator, relation, linkedvar)

      where `generator` is the sql generator, `relation` the current rql syntax
      tree relation and linkedvar the principal syntax tree variable holding the
      attribute.
    """
    is_source_callback = True

    def callback(self, *args):
        """see docstring for prototype, which vary according to is_source_callback
        """
        raise NotImplementedError()

    def entity_added(self, entity, attr):
        """an entity using this storage for attr has been added"""
        raise NotImplementedError()
    def entity_updated(self, entity, attr):
        """an entity using this storage for attr has been updatded"""
        raise NotImplementedError()
    def entity_deleted(self, entity, attr):
        """an entity using this storage for attr has been deleted"""
        raise NotImplementedError()

# TODO
# * make it configurable without code
# * better file path attribution
# * handle backup/restore

class BytesFileSystemStorage(Storage):
    """store Bytes attribute value on the file system"""
    def __init__(self, defaultdir):
        self.default_directory = defaultdir

    def callback(self, source, value):
        """sql generator callback when some attribute with a custom storage is
        accessed
        """
        fpath = source.binary_to_str(value)
        try:
            return Binary(file(fpath).read())
        except OSError, ex:
            source.critical("can't open %s: %s", value, ex)
            return None

    def entity_added(self, entity, attr):
        """an entity using this storage for attr has been added"""
        if not entity._cw.transaction_data.get('fs_importing'):
            try:
                value = entity.pop(attr)
            except KeyError:
                pass
            else:
                fpath = self.new_fs_path(entity, attr)
                # bytes storage used to store file's path
                entity[attr] = Binary(fpath)
                file(fpath, 'w').write(value.getvalue())
                AddFileOp(entity._cw, filepath=fpath)
        # else entity[attr] is expected to be an already existant file path

    def entity_updated(self, entity, attr):
        """an entity using this storage for attr has been updatded"""
        try:
            value = entity.pop(attr)
        except KeyError:
            pass
        else:
            fpath = self.current_fs_path(entity, attr)
            UpdateFileOp(entity._cw, filepath=fpath, filedata=value.getvalue())

    def entity_deleted(self, entity, attr):
        """an entity using this storage for attr has been deleted"""
        DeleteFileOp(entity._cw, filepath=self.current_fs_path(entity, attr))

    def new_fs_path(self, entity, attr):
        fspath = osp.join(self.default_directory, '%s_%s' % (entity.eid, attr))
        while osp.exists(fspath):
            fspath = '_' + fspath
        return fspath

    def current_fs_path(self, entity, attr):
        sysource = entity._cw.pool.source('system')
        cu = sysource.doexec(entity._cw,
                             'SELECT cw_%s FROM cw_%s WHERE cw_eid=%s' % (
                                 attr, entity.__regid__, entity.eid))
        BINARY = sysource.dbhelper.dbapi_module.BINARY
        return sysource._process_value(cu.fetchone()[0], [None, BINARY],
                                       binarywrap=str)


class AddFileOp(Operation):
    def rollback_event(self):
        try:
            unlink(self.filepath)
        except:
            pass

class DeleteFileOp(Operation):
    def commit_event(self):
        try:
            unlink(self.filepath)
        except:
            pass

class UpdateFileOp(Operation):
    def precommit_event(self):
        try:
            file(self.filepath, 'w').write(self.filedata)
        except Exception, ex:
            self.exception(str(ex))
