# Run all scenarii found in windmill directory
from cubicweb.devtools.cwwindmill import (CubicWebWindmillUseCase,
                                          unittest_main)

class CubicWebWindmillUseCase(CubicWebWindmillUseCase): pass

if __name__ == '__main__':
    unittest_main()
