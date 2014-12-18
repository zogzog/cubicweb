"""define default ui properties"""

# CSS stylesheets to include systematically in HTML headers
# use the following line if you *need* to keep the old stylesheet
STYLESHEETS =       [data('cubicweb.css'), ]
STYLESHEETS_IE =    [data('cubicweb.ie.css')]
STYLESHEETS_PRINT = [data('cubicweb.print.css')]

# Javascripts files to include systematically in HTML headers
JAVASCRIPTS = [data('jquery.js'),
               data('jquery-migrate.js'),
               data('cubicweb.js'),
               data('cubicweb.compat.js'),
               data('cubicweb.python.js'),
               data('cubicweb.htmlhelpers.js')]

# where is installed fckeditor
FCKEDITOR_PATH = '/usr/share/fckeditor/'

# favicon and logo for the instance
FAVICON = data('favicon.ico')
LOGO = data('logo.png')

# rss logo (link to get the rss view of a selection)
RSS_LOGO = data('rss.png')
RSS_LOGO_16 = data('feed-icon16x16.png')
RSS_LOGO_32 = data('feed-icon32x32.png')

# XXX cleanup resources below, some of them are probably not used
# (at least entity types icons...)

# images
HELP = data('help.png')
SEARCH_GO = data('go.png')
PUCE_UP = data('puce_up.png')
PUCE_DOWN = data('puce_down.png')

# button icons
OK_ICON = data('ok.png')
CANCEL_ICON = data('cancel.png')
APPLY_ICON = data('plus.png')
TRASH_ICON = data('trash_can_small.png')

# icons for entity types
BOOKMARK_ICON = data('icon_bookmark.gif')
EMAILADDRESS_ICON = data('icon_emailaddress.gif')
EUSER_ICON = data('icon_euser.gif')
STATE_ICON = data('icon_state.gif')

# other icons
CALENDAR_ICON = data('calendar.gif')
CANCEL_EMAIL_ICON = data('sendcancel.png')
SEND_EMAIL_ICON = data('sendok.png')
DOWNLOAD_ICON = data('download.gif')
UPLOAD_ICON = data('upload.gif')
GMARKER_ICON = data('gmap_blue_marker.png')
UP_ICON = data('up.gif')

# colors, fonts, etc

# default (body, html)
defaultColor = '#000'
defaultFontFamily = "'Bitstream Vera Sans','Lucida Grande','Lucida Sans Unicode','Geneva','Verdana',sans-serif"
defaultSize = '12px'
defaultLineHeight = '1.5'
defaultLineHeightEm = lazystr('%(defaultLineHeight)sem')

inputHeight = '1.3em'
inputPadding = 'O.2em'
# XXX
defaultLayoutMargin = '8px'

# header
headerBgColor = '#ff7700'
headerBg = lazystr('%(headerBgColor)s url("banner.png") repeat-x top left')


# scale 3:5 stranded
# h1 { font-size:2em; }
# h2 { font-size:1.61538em; }
# h3 { font-size:1.23077em; }
#
# scale le corbusier */
# h1 { font-size:2.11538em; }
# h2 { font-size:1.61538em; }
# h3 { font-size:1.30769em; }

# h
h1FontSize = '2.3em' # 25.3833px
h1Padding = '0 0 0.14em 0 '
h1Margin = '0.8em 0 0.5em'
h1Color = '#000'
h1BorderBottomStyle = lazystr('0.06em solid %(h1Color)s')

h2FontSize = '2em' #
h2Padding = '0.4em 0 0.35em 0' # 22.0667px
h2Margin = '0'

h3FontSize = '1.7em' #18.75px
h3Padding = '0.5em 0 0.57em 0'
h3Margin = '0'

h4FontSize = '1.4em' # 15.45px

# links
aColor = '#e6820e'


# page frame
pageBgColor = '#e2e2e2'
pageContentBorderColor = '#ccc'
pageContentBgColor = '#fff'
pageContentPadding = '1em'
pageMinHeight = '800px'

# boxes ########################################################################

# title of contextFree / contextual boxes
contextFreeBoxTitleBgColor = '#CFCEB7'
contextFreeBoxTitleBg = lazystr('%(contextFreeBoxTitleBgColor)s url("contextFreeBoxHeader.png") repeat-x 50%% 50%%')
contextFreeBoxTitleColor = '#000'

contextualBoxTitleBgColor = '#FF9900'
contextualBoxTitleBg = lazystr('%(contextualBoxTitleBgColor)s url("contextualBoxHeader.png") repeat-x 50%% 50%%')
contextualBoxTitleColor = '#FFF'

# title of 'incontext' boxes (eg displayed inside the primary view)
incontextBoxTitleBgColor = lazystr('%(contextFreeBoxTitleBgColor)s')
incontextBoxTitleBg = lazystr('%(incontextBoxTitleBgColor)s url("incontextBoxHeader.png") repeat-x 50%% 50%%')
incontextBoxTitleColor = '#000'

# body of boxes in the left or right column (whatever contextFree / contextual)
leftrightBoxBodyBgColor = '#FFF'
leftrightBoxBodyBg = lazystr('%(leftrightBoxBodyBgColor)s')
leftrightBoxBodyColor = 'black'
leftrightBoxBodyHoverBgColor = '#EEEDD9'

# body of 'incontext' boxes (eg displayed insinde the primary view)
incontextBoxBodyBgColor = '#f8f8ee'
incontextBoxBodyBg = lazystr('%(incontextBoxBodyBgColor)s')
incontextBoxBodyColor = '#555544'
incontextBoxBodyHoverBgColor = lazystr('%(incontextBoxBodyBgColor)s')


# table listing & co ###########################################################
listingBorderColor = '#ccc'
listingHeaderBgColor = '#efefef'
listingHighlightedBgColor = '#fbfbfb'

# puce
bulletDownImg = 'url("puce_down.png") 98% 6px no-repeat'

#forms
formHeaderBgColor = lazystr('%(listingHeaderBgColor)s')
helperColor = '#555'

# button
buttonBorderColor = '#edecd2'
buttonBgColor = '#fffff8'
buttonBgImg = 'url("button.png") repeat-x 50% 50%'

# messages
msgBgColor = '#f8f8ee'
infoMsgBgImg = 'url("information.png") 5px center no-repeat'
errorMsgBgImg = 'url("error.png") 100% 50% no-repeat'
errorMsgColor = '#ed0d0d'

# facets
facet_titleFont = 'bold SansSerif'
facet_Padding = '.4em'
facet_MarginBottom = '.4em'
facet_vocabMaxHeight = '12em' # ensure < FACET_GROUP_HEIGHT by some const. factor (e.g 3em)
