"""distutils / __pkginfo__ helpers for cubicweb applications"""

import os
from os.path import isdir, join


def get_distutils_datafiles(cube, i18n=True, recursive=False):
    """
    :param cube: application cube's name
    """
    data_files = []
    data_files += get_basepyfiles(cube)
    data_files += get_webdatafiles(cube)
    if i18n:
        data_files += get_i18nfiles(cube)
    data_files += get_viewsfiles(cube, recursive=recursive)
    data_files += get_migrationfiles(cube)
    data_files += get_schemafiles(cube)
    return data_files



## listdir filter funcs ################################################
def nopyc_and_nodir(fname):
    if isdir(fname) or fname.endswith('.pyc') or fname.endswith('~'):
        return False
    return True

def no_version_control(fname):
    if fname in ('CVS', '.svn', '.hg'):
        return False
    if fname.endswith('~'):
        return False
    return True

def basepy_files(fname):
    if fname.endswith('.py') and fname != 'setup.py':
        return True
    return False

def chain(*filters):
    def newfilter(fname):
        for filterfunc in filters:
            if not filterfunc(fname):
                return False
        return True
    return newfilter

def listdir_with_path(path='.', filterfunc=None):
    if filterfunc:
        return [join(path, fname) for fname in os.listdir(path) if filterfunc(join(path, fname))]
    else:
        return [join(path, fname) for fname in os.listdir(path)]


## data_files helpers ##################################################
CUBES_DIR = join('share', 'cubicweb', 'cubes')

def get_i18nfiles(cube):
    """returns i18n files in a suitable format for distutils's
    data_files parameter
    """
    i18ndir = join(CUBES_DIR, cube, 'i18n')
    potfiles = [(i18ndir, listdir_with_path('i18n', chain(no_version_control, nopyc_and_nodir)))]
    return potfiles


def get_viewsfiles(cube, recursive=False):
    """returns views files in a suitable format for distutils's
    data_files parameter

    :param recursive: include views' subdirs recursively if True
    """
    if recursive:
        datafiles = []
        for dirpath, dirnames, filenames in os.walk('views'):
            filenames = [join(dirpath, fname) for fname in filenames
                         if nopyc_and_nodir(join(dirpath, fname))]
            dirpath = join(CUBES_DIR, cube, dirpath)
            datafiles.append((dirpath, filenames))
        return datafiles
    else:
        viewsdir = join(CUBES_DIR, cube, 'views')
        return [(viewsdir,
                 listdir_with_path('views', filterfunc=nopyc_and_nodir))]


def get_basepyfiles(cube):
    """returns cube's base python scripts (tali18n.py, etc.)
    in a suitable format for distutils's data_files parameter
    """
    return [(join(CUBES_DIR, cube),
             [fname for fname in os.listdir('.')
              if fname.endswith('.py') and fname != 'setup.py'])]


def get_webdatafiles(cube):
    """returns web's data files (css, png, js, etc.) in a suitable
    format for distutils's data_files parameter
    """
    return [(join(CUBES_DIR, cube, 'data'),
             listdir_with_path('data', filterfunc=no_version_control))]


def get_migrationfiles(cube):
    """returns cube's migration scripts
    in a suitable format for distutils's data_files parameter
    """
    return [(join(CUBES_DIR, cube, 'migration'),
             listdir_with_path('migration', no_version_control))]


def get_schemafiles(cube):
    """returns cube's schema files
    in a suitable format for distutils's data_files parameter
    """
    return [(join(CUBES_DIR, cube, 'schema'),
             listdir_with_path('schema', no_version_control))]


