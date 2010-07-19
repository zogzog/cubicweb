import os, os.path as osp

from cubicweb.devtools import cwwindmill


class CubicWebWindmillUseCase(cwwindmill.CubicWebWindmillUseCase):
    """class for windmill use case tests

    From test server parameters:

    :params ports_range: range of http ports to test (range(7000, 8000) by default)
    :type ports_range: iterable
    :param anonymous_logged: is anonymous user logged by default ?
    :type anonymous_logged: bool

    The first port found as available in `ports_range` will be used to launch
    the test server

    Instead of toggle `edit_test` value, try `pytest -i`

    From Windmill configuration:

    :param browser: browser identification string (firefox|ie|safari|chrome) (firefox by default)
    :param test_dir: testing file path or directory (./windmill by default)
    :param edit_test: load and edit test for debugging (False by default)
    """
    #ports_range = range(7000, 8000)
    anonymous_logged = False
    #browser = 'firefox'
    #test_dir = osp.join(os.getcwd(), 'windmill')
    #edit_test = False

    # If you prefer, you can put here the use cases recorded by windmill GUI
    # (services transformer) instead of the windmill sub-directory
    # You can change `test_dir` as following:
    #test_dir = __file__


from windmill.authoring import WindmillTestClient
def test_usecase():
    client = WindmillTestClient(__name__)
    import pdb; pdb.set_trace()
    client.open(url=u'/')
#    ...


if __name__ == '__main__':
    cwwindmill.unittest_main()
