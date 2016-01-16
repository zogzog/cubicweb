from os.path import join
assert __file__.endswith(join('scripts', 'script1.py')), __file__
assert '__main__' == __name__, __name__
assert [] == __args__, __args__
