"""custom storages for the system source"""
from os import unlink, path as osp

from cubicweb import Binary
from cubicweb.server.hook import Operation

def set_attribute_storage(repo, etype, attr, storage):
    repo.system_source.set_storage(etype, attr, storage)

def unset_attribute_storage(repo, etype, attr):
    repo.system_source.unset_storage(etype, attr)

class Storage(object):
    """abstract storage"""
    def sqlgen_callback(self, generator, relation, linkedvar):
        """sql generator callback when some attribute with a custom storage is
        accessed
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

    def sqlgen_callback(self, generator, linkedvar, relation):
        """sql generator callback when some attribute with a custom storage is
        accessed
        """
        linkedvar.accept(generator)
        return '_fsopen(%s.cw_%s)' % (
            linkedvar._q_sql.split('.', 1)[0], # table name
            relation.r_type) # attribute name

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
        return sysource._process_value(cu.fetchone()[0], [None, dbmod.BINARY],
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
