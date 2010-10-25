from os.path import join
assert __file__.endswith(join('scripts', 'script2.py')), __file__
assert '__main__' == __name__, __name__
assert ['-v'] == __args__, __args__
