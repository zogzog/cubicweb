from cubicweb.devtools import DEFAULT_SOURCES
LOGIN, PASSWORD = DEFAULT_SOURCES['admin'].values()

# Generated by the windmill services transformer
from windmill.authoring import WindmillTestClient


def test_connect():
    client = WindmillTestClient(__name__)

    client.open(url=u'/')
    client.asserts.assertJS(js=u"$('#loginForm').is(':visible')")
    client.type(text=LOGIN, id=u'__login')
    client.type(text=PASSWORD, id=u'__password')
    client.execJS(js=u"$('#loginForm').submit()")
    client.waits.forPageLoad(timeout=u'20000')
    client.asserts.assertJS(js=u'$(\'.message\').text() == "welcome %s !"' % LOGIN)
    client.open(url=u'/logout')
    client.open(url=u'/')
    client.asserts.assertJS(js=u"$('#loginForm').is(':visible')")

def test_wrong_connect():
    client = WindmillTestClient(__name__)

    client.open(url=u'/')
    # XXX windmill wants to use its proxy internally on 403 :-(
    #client.asserts.assertJS(js=u"$('#loginForm').is(':visible')")
    #client.type(text=LOGIN, id=u'__login')
    #client.type(text=u'novalidpassword', id=u'__password')
    #client.click(value=u'log in')
    client.open(url=u'/?__login=user&__password=nopassword')
    client.waits.forPageLoad(timeout=u'20000')
    client.asserts.assertTextIn(validator=u'authentication failure', id=u'loginBox')
    client.open(url=u'/')
    client.asserts.assertJS(js=u"$('#loginForm').is(':visible')")
