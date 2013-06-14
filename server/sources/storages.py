# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""custom storages for the system source"""

import os
import sys
from os import unlink, path as osp
from contextlib import contextmanager

from yams.schema import role_name

from cubicweb import Binary, ValidationError
from cubicweb.server import hook
from cubicweb.server.edition import EditedEntity


def set_attribute_storage(repo, etype, attr, storage):
    repo.system_source.set_storage(etype, attr, storage)

def unset_attribute_storage(repo, etype, attr):
    repo.system_source.unset_storage(etype, attr)


class Storage(object):
    """abstract storage

    * If `source_callback` is true (by default), the callback will be run during
      query result process of fetched attribute's value and should have the
      following prototype::

        callback(self, source, session, value)

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
    def migrate_entity(self, entity, attribute):
        """migrate an entity attribute to the storage"""
        raise NotImplementedError()

# TODO
# * make it configurable without code
# * better file path attribution
# * handle backup/restore

def uniquify_path(dirpath, basename):
    """return a unique file name for `basename` in `dirpath`, or None
    if all attemps failed.

    XXX subject to race condition.
    """
    path = osp.join(dirpath, basename.replace(osp.sep, '-'))
    if not osp.isfile(path):
        return path
    base, ext = osp.splitext(path)
    for i in xrange(1, 256):
        path = '%s%s%s' % (base, i, ext)
        if not osp.isfile(path):
            return path
    return None

@contextmanager
def fsimport(session):
    present = 'fs_importing' in session.transaction_data
    old_value = session.transaction_data.get('fs_importing')
    session.transaction_data['fs_importing'] = True
    yield
    if present:
        session.transaction_data['fs_importing'] = old_value
    else:
        del session.transaction_data['fs_importing']


class BytesFileSystemStorage(Storage):
    """store Bytes attribute value on the file system"""
    def __init__(self, defaultdir, fsencoding='utf-8', wmode=0444):
        if type(defaultdir) is unicode:
            defaultdir = defaultdir.encode(fsencoding)
        self.default_directory = defaultdir
        self.fsencoding = fsencoding
        # extra umask to use when creating file
        # 0444 as in "only allow read bit in permission"
        self._wmode = wmode

    def _writecontent(self, path, binary):
        """write the content of a binary in readonly file

        As the bfss never alter a create file it does not prevent it to work as
        intended. This is a beter safe than sorry approach.
        """
        write_flag = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if sys.platform == 'win32':
            write_flag |= os.O_BINARY
        fd = os.open(path, write_flag, self._wmode)
        fileobj = os.fdopen(fd, 'wb')
        binary.to_file(fileobj)
        fileobj.close()


    def callback(self, source, session, value):
        """sql generator callback when some attribute with a custom storage is
        accessed
        """
        fpath = source.binary_to_str(value)
        try:
            return Binary.from_file(fpath)
        except EnvironmentError as ex:
            source.critical("can't open %s: %s", value, ex)
            return None

    def entity_added(self, entity, attr):
        """an entity using this storage for attr has been added"""
        if entity._cw.transaction_data.get('fs_importing'):
            binary = Binary.from_file(entity.cw_edited[attr].getvalue())
            entity._cw_dont_cache_attribute(attr, repo_side=True)
        else:
            binary = entity.cw_edited.pop(attr)
            fpath = self.new_fs_path(entity, attr)
            # bytes storage used to store file's path
            entity.cw_edited.edited_attribute(attr, Binary(fpath))
            self._writecontent(fpath, binary)
            AddFileOp.get_instance(entity._cw).add_data(fpath)
        return binary

    def entity_updated(self, entity, attr):
        """an entity using this storage for attr has been updated"""
        # get the name of the previous file containing the value
        oldpath = self.current_fs_path(entity, attr)
        if entity._cw.transaction_data.get('fs_importing'):
            # If we are importing from the filesystem, the file already exists.
            # We do not need to create it but we need to fetch the content of
            # the file as the actual content of the attribute
            fpath = entity.cw_edited[attr].getvalue()
            entity._cw_dont_cache_attribute(attr, repo_side=True)
            assert fpath is not None
            binary = Binary.from_file(fpath)
        else:
            # We must store the content of the attributes
            # into a file to stay consistent with the behaviour of entity_add.
            # Moreover, the BytesFileSystemStorage expects to be able to
            # retrieve the current value of the attribute at anytime by reading
            # the file on disk. To be able to rollback things, use a new file
            # and keep the old one that will be removed on commit if everything
            # went ok.
            #
            # fetch the current attribute value in memory
            binary = entity.cw_edited.pop(attr)
            if binary is None:
                fpath = None
            else:
                # Get filename for it
                fpath = self.new_fs_path(entity, attr)
                assert not osp.exists(fpath)
                # write attribute value on disk
                self._writecontent(fpath, binary)
                # Mark the new file as added during the transaction.
                # The file will be removed on rollback
                AddFileOp.get_instance(entity._cw).add_data(fpath)
            # reinstall poped value
            if fpath is None:
                entity.cw_edited.edited_attribute(attr, None)
            else:
                # register the new location for the file.
                entity.cw_edited.edited_attribute(attr, Binary(fpath))
        if oldpath is not None and oldpath != fpath:
            # Mark the old file as useless so the file will be removed at
            # commit.
            DeleteFileOp.get_instance(entity._cw).add_data(oldpath)
        return binary

    def entity_deleted(self, entity, attr):
        """an entity using this storage for attr has been deleted"""
        fpath = self.current_fs_path(entity, attr)
        if fpath is not None:
            DeleteFileOp.get_instance(entity._cw).add_data(fpath)

    def new_fs_path(self, entity, attr):
        # We try to get some hint about how to name the file using attribute's
        # name metadata, so we use the real file name and extension when
        # available. Keeping the extension is useful for example in the case of
        # PIL processing that use filename extension to detect content-type, as
        # well as providing more understandable file names on the fs.
        basename = [str(entity.eid), attr]
        name = entity.cw_attr_metadata(attr, 'name')
        if name is not None:
            basename.append(name.encode(self.fsencoding))
        fspath = uniquify_path(self.default_directory,
                               '_'.join(basename))
        if fspath is None:
            msg = entity._cw._('failed to uniquify path (%s, %s)') % (
                self.default_directory, '_'.join(basename))
            raise ValidationError(entity.eid, {role_name(attr, 'subject'): msg})
        return fspath

    def current_fs_path(self, entity, attr):
        """return the current fs_path of the attribute, or None is the attr is
        not stored yet.
        """
        sysource = entity._cw.cnxset.source('system')
        cu = sysource.doexec(entity._cw,
                             'SELECT cw_%s FROM cw_%s WHERE cw_eid=%s' % (
                             attr, entity.cw_etype, entity.eid))
        rawvalue = cu.fetchone()[0]
        if rawvalue is None: # no previous value
            return None
        return sysource._process_value(rawvalue, cu.description[0],
                                       binarywrap=str)

    def migrate_entity(self, entity, attribute):
        """migrate an entity attribute to the storage"""
        entity.cw_edited = EditedEntity(entity, **entity.cw_attr_cache)
        self.entity_added(entity, attribute)
        session = entity._cw
        source = session.repo.system_source
        attrs = source.preprocess_entity(entity)
        sql = source.sqlgen.update('cw_' + entity.cw_etype, attrs,
                                   ['cw_eid'])
        source.doexec(session, sql, attrs)
        entity.cw_edited = None


class AddFileOp(hook.DataOperationMixIn, hook.Operation):
    def rollback_event(self):
        for filepath in self.get_data():
            try:
                unlink(filepath)
            except Exception as ex:
                self.error('cant remove %s: %s' % (filepath, ex))

class DeleteFileOp(hook.DataOperationMixIn, hook.Operation):
    def postcommit_event(self):
        for filepath in self.get_data():
            try:
                unlink(filepath)
            except Exception as ex:
                self.error('cant remove %s: %s' % (filepath, ex))
