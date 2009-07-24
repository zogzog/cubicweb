from os.path import join
from cubicweb.toolsutils import create_dir

option_renamed('pyro-application-id', 'pyro-instance-id')

create_dir(join(config.appdatahome, 'backup'))
