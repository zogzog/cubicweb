assert 'data/scripts/script3.py' == __file__
assert '__main__' == __name__
assert ['-vd', '-f', 'FILE.TXT'] == scriptargs, scriptargs
