from os import unlink
from os.path import isfile, join
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg

regdir = cwcfg.instances_dir()

if isfile(join(regdir, 'startorder')):
    if confirm('The startorder file is not used anymore in Cubicweb 3.22. '
               'Should I delete it?',
               shell=False, pdb=False):
        unlink(join(regdir, 'startorder'))

