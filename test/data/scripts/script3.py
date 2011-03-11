from os.path import join
assert __file__.endswith(join('scripts', 'script3.py')), __file__
assert '__main__' == __name__, __name__
assert ['-vd', '-f', 'FILE.TXT'] == __args__, __args__
