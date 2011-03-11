from cubicweb.devtools import DEFAULT_SOURCES
LOGIN, PASSWORD = DEFAULT_SOURCES['admin'].values()

# Generated by the windmill services transformer
from windmill.authoring import WindmillTestClient


def test_edit_relation():
    client = WindmillTestClient(__name__)

    client.open(url=u'/logout')
    client.open(url=u'/')
    client.asserts.assertJS(js=u"$('#loginForm').is(':visible')")
    client.type(text=LOGIN, id=u'__login')
    client.type(text=PASSWORD, id=u'__password')
    client.execJS(js=u"$('#loginForm').submit()")
    client.waits.forPageLoad(timeout=u'20000')
    client.open(url=u'/add/Folder')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(timeout=u'8000', id=u'name-subject:A')
    client.click(id=u'name-subject:A')
    client.type(text=u'folder1', id=u'name-subject:A')
    client.click(value=u'button_ok')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(link=u'add Folder filed_under Folder object', timeout=u'8000')
    client.click(link=u'add Folder filed_under Folder object')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(timeout=u'8000', id=u'name-subject:A')
    client.click(id=u'name-subject:A')
    client.type(text=u'subfolder1', id=u'name-subject:A')
    client.click(value=u'button_ok')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(link=u'more actions', timeout=u'8000')
    client.click(link=u'more actions')
    client.click(link=u'copy')
    client.waits.forPageLoad(timeout=u'20000')
    client.type(text=u'folder2', id=u'name-subject:A')
    client.click(value=u'button_ok')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(link=u'modify', timeout=u'8000')
    client.click(link=u'modify')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(timeout=u'8000', id=u'footer')
    client.click(link=u'x')
    client.click(value=u'button_ok')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(link=u'add Folder filed_under Folder object', timeout=u'8000')
    client.click(link=u'add Folder filed_under Folder object')
    client.waits.forPageLoad(timeout=u'20000')
    client.type(text=u'subfolder2', id=u'name-subject:A')
    client.click(value=u'button_ok')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(link=u'subfolder2', timeout=u'8000')
    client.click(link=u'subfolder2')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(link=u'modify', timeout=u'8000')
    client.click(link=u'modify')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(timeout=u'8000', id=u'footer')
    client.click(link=u'x')
    client.select(xpath=u'//select', index=u'1')
    #client.execJQuery(jquery=u'("select").trigger(\'change\')') # BUGGY freeze UI..
    client.execJS(js=u'$("select").trigger(\'change\')')
    client.waits.sleep(milliseconds=u'2000')
    client.select(jquery=u'(\'select:contains("Search")\')[0]', option=u'Search for folder')
    client.waits.forPageLoad(timeout=u'20000')
    client.click(link=u'folder1')
    client.waits.forPageLoad(timeout=u'20000')
    client.waits.forElement(timeout=u'8000', value=u'button_ok')
    client.click(value=u'button_ok')
    client.waits.forPageLoad(timeout=u'20000')
    client.asserts.assertText(xpath=u'//h1', validator=u'subfolder2')
    client.waits.forElement(link=u'folder_plural', timeout=u'8000')
    client.click(link=u'folder_plural')
    client.waits.forPageLoad(timeout=u'20000')
    client.asserts.assertText(jquery=u"('#contentmain div a')[0]", validator=u'folder1')
    client.asserts.assertText(jquery=u"('#contentmain div a')[1]", validator=u'folder2')
    client.asserts.assertText(jquery=u"('#contentmain div a')[2]", validator=u'subfolder1')
    client.asserts.assertText(jquery=u"('#contentmain div a')[3]", validator=u'subfolder2')
    client.click(link=u'subfolder2')
    client.click(link=u'modify')
    client.click(link=u'folder1')
