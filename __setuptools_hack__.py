from os import path as osp
import sys
import os

def in_egg(path):
    head, tail = osp.split(path)
    while tail:
        if tail.endswith('.egg'):
            return True
        head, tail = osp.split(head)
    return False

if in_egg(__file__):
    from cubicweb.cwconfig import _find_prefix
    INSTALL_PREFIX = _find_prefix()
    if not osp.exists(osp.join(INSTALL_PREFIX, 'share', 'cubicweb', 'migration')):
        print >> sys.stderr, 'copying cubicweb content to the expected location'
        from shutil import copytree
        import tarfile
        import tempfile
        from pkg_resources import Requirement, resource_filename
        from functools import partial
        file_path = partial(resource_filename, Requirement.parse("cubicweb"))
        for df in ('share', 'lib'):
            # Tar are used to merge with destination directory
            tmp_file = tempfile.NamedTemporaryFile(suffix='.tar')
            tmp_tar  = tarfile.TarFile(tmp_file.name, mode='w')
            tmp_tar.add(file_path(df), arcname=df)
            tmp_tar  = tarfile.TarFile(tmp_file.name, mode='r')
            tmp_tar.extractall(path=INSTALL_PREFIX)
