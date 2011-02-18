# Run all scenarii found in windmill directory
from os.path import join, dirname
from cubicweb.devtools.cwwindmill import (CubicWebWindmillUseCase,
                                          unittest_main)

class CubicWebWindmillUseCase(CubicWebWindmillUseCase):
    #test_dir = join(dirname(__file__), "windmill/test_edit_relation.py")
    pass


if __name__ == '__main__':
    unittest_main()
