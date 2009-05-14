import sys

"""
Generates the chapter that list all the modules in CubicWeb
in order to pull all the docstring.
"""

class ModuleGenerator:
    HEADER = """.. -*- coding: utf-8 -*-

============
CubicWeb API
============
"""
    EXCLUDE_DIRS = ('test', 'tests', 'examples', 'data', 'doc', '.hg', 'migration')

    def __init__(self, output_fn, mod_names):
        self.mod_names =  mod_names
        self.fn = open(output_fn, 'w')
        self.fn.write(self.HEADER)

    def done(self):
        self.fn.close()

    def gen_module(self, mod_name):
        mod_entry = """
:mod:`%s`
%s

.. automodule:: %s
   :members:
""" % (mod_name, '='*(len(':mod:``'+mod_name)), mod_name)
        self.fn.write(mod_entry)

    def find_modules(self):
        import os
        modules = []
        for mod_name in self.mod_names:
            for root, dirs, files in os.walk(mod_name):
                if self.keep_module(root):
                    for name in files:
                        if name == "__init__.py":
                            if self.format_mod_name(root, mod_name) not in modules:
                                modules.append(self.format_mod_name(root, mod_name))
                        else:
                            if name.endswith(".py") and name != "__pkginfo__.py" and "__init__.py" in files:
                                filename = root + '/' + name.split('.py')[0]
                                if self.format_mod_name(filename, mod_name) not in modules:
                                    modules.append(self.format_mod_name(filename, mod_name))
        return modules

    def gen_modules(self):
        for module in self.find_modules():
            self.gen_module(module)

    def format_mod_name(self, path, mod_name):
        mod_root = mod_name.split('/')[-1]
        mod_end = path.split(mod_root)[-1]
        return mod_root + mod_end.replace('/', '.')

    def keep_module(self, mod_end):
        """
        Filter modules in order to exclude specific package directories.
        """
        for dir in self.EXCLUDE_DIRS:
            if mod_end.find(dir) != -1:
                return False
        return True

USAGE = """
Two arguments required:
    generate_modules [cubicweb-root] [file-out]

[cubicweb-root] : full path to cubicweb forest
[file-out] : rest file containing the list of modules for Sphinx
"""
def generate_modules_file(args):
    if len(args) != 2:
        print USAGE
        sys.exit()
    CW_ROOT = args[0]
    OUTPUT = args[1]
    modules = (CW_ROOT + '/cubicweb', \
               CW_ROOT + '/indexer', \
               CW_ROOT + '/logilab', \
               CW_ROOT + '/rql', \
               CW_ROOT + '/yams')

    mg = ModuleGenerator(CW_ROOT + '/cubicweb/doc/book/en/' + OUTPUT, modules)
    mg.find_modules()
    mg.gen_modules()
    mg.done()
    print args



if __name__ == '__main__':
    generate_modules_file(sys.argv[1:])

