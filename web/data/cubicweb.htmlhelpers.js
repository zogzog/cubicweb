CubicWeb.require('python.js');
CubicWeb.require('jquery.corner.js');

/* returns the document's baseURI. (baseuri() uses document.baseURI if
 * available and inspects the <base> tag manually otherwise.)
*/
function baseuri() {
    var uri = document.baseURI;
    if (uri) { // some browsers don't define baseURI
	return uri;
    }
    var basetags = document.getElementsByTagName('base');
    if (basetags.length) {
	return getNodeAttribute(basetags[0], 'href');
    }
    return '';
}

// XXX this is used exactly ONCE in web/views/massmailing.py
function insertText(text, areaId) {
    var textarea = jQuery('#' + areaId);
    if (document.selection) { // IE
        var selLength;
        textarea.focus();
        sel = document.selection.createRange();
        selLength = sel.text.length;
        sel.text = text;
        sel.moveStart('character', selLength-text.length);
        sel.select();
    } else if (textarea.selectionStart || textarea.selectionStart == '0') { // mozilla
        var startPos = textarea.selectionStart;
        var endPos = textarea.selectionEnd;
	// insert text so that it replaces the [startPos, endPos] part
        textarea.value = textarea.value.substring(0,startPos) + text + textarea.value.substring(endPos,textarea.value.length);
	// set cursor pos at the end of the inserted text
        textarea.selectionStart = textarea.selectionEnd = startPos+text.length;
        textarea.focus();
    } else { // safety belt for other browsers
        textarea.value += text;
    }
}

/* taken from dojo toolkit */
// XXX this looks unused
function setCaretPos(element, start, end){
    if(!end){ end = element.value.length; }  // NOTE: Strange - should be able to put caret at start of text?
    // Mozilla
    // parts borrowed from http://www.faqts.com/knowledge_base/view.phtml/aid/13562/fid/130
    if(element.setSelectionRange){
        element.focus();
        element.setSelectionRange(start, end);
    } else if(element.createTextRange){ // IE
        var range = element.createTextRange();
        with(range){
            collapse(true);
            moveEnd('character', end);
            moveStart('character', start);
            select();
        }
    } else { //otherwise try the event-creation hack (our own invention)
        // do we need these?
        element.value = element.value;
        element.blur();
        element.focus();
        // figure out how far back to go
        var dist = parseInt(element.value.length)-end;
        var tchar = String.fromCharCode(37);
        var tcc = tchar.charCodeAt(0);
        for(var x = 0; x < dist; x++){
            var te = document.createEvent("KeyEvents");
            te.initKeyEvent("keypress", true, true, null, false, false, false, false, tcc, tcc);
            element.dispatchEvent(te);
        }
    }
}


// XXX this looks unused
function setProgressMessage(label) {
    var body = document.getElementsByTagName('body')[0];
    body.appendChild(DIV({id: 'progress'}, label));
    jQuery('#progress').show();
}

// XXX this looks unused
function resetProgressMessage() {
    var body = document.getElementsByTagName('body')[0];
    jQuery('#progress').hide();
}


/* set body's cursor to 'progress' */
function setProgressCursor() {
    var body = document.getElementsByTagName('body')[0];
    body.style.cursor = 'progress';
}

/* reset body's cursor to default (mouse cursor). The main
 * purpose of this function is to be used as a callback in the
 * deferreds' callbacks chain. */
function resetCursor(result) {
    var body = document.getElementsByTagName('body')[0];
    body.style.cursor = 'default';
    // pass result to next callback in the callback chain
    return result;
}

function updateMessage(msg) {
    var msgdiv = DIV({'class':'message'});
    // don't pass msg to DIV() directly because DIV will html escape it
    // and msg should alreay be html escaped at this point.
    msgdiv.innerHTML = msg;
    jQuery('#appMsg').removeClass('hidden').empty().append(msgdiv);
}

/* builds an url from an object (used as a dictionnary)
 * Notable difference with MochiKit's queryString: asURL does not
 * *url_quote* each value found in the dictionnary
 *
 * >>> asURL({'rql' : "RQL", 'x': [1, 2], 'itemvid' : "oneline"})
 * rql=RQL&vid=list&itemvid=oneline&x=1&x=2
 */
function asURL(props) {
    var chunks = [];
    for(key in props) {
	var value = props[key];
	// generate a list of couple key=value if key is multivalued
	if (isArrayLike(value)) {
	    for (var i=0; i<value.length;i++) {
		chunks.push(key + '=' + value[i]);
	    }
	} else {
	    chunks.push(key + '=' + value);
	}
    }
    return chunks.join('&');
}

/* return selected value of a combo box if any
 */
function firstSelected(selectNode) {
    var selection = filter(attrgetter('selected'), selectNode.options);
    return (selection.length > 0) ? getNodeAttribute(selection[0], 'value'):null;
}

/* toggle visibility of an element by its id
 */
function toggleVisibility(elemId) {
    jqNode(elemId).toggleClass('hidden');
}


/* toggles visibility of login popup div */
// XXX used exactly ONCE
function popupLoginBox() {
    toggleVisibility('popupLoginBox');
    jQuery('#__login:visible').focus();
}


/* returns the list of elements in the document matching the tag name
 * and the properties provided
 *
 * @param tagName the tag's name
 * @param properties a js Object used as a dict
 * @return an iterator (if a *real* array is needed, you can use the
 *                      list() function)
 */
function getElementsMatching(tagName, properties, /* optional */ parent) {
    parent = parent || document;
    return filter(function elementMatches(element) {
                     for (prop in properties) {
                       if (getNodeAttribute(element, prop) != properties[prop]) {
	                 return false;}}
                    return true;},
                  parent.getElementsByTagName(tagName));
}

/*
 * sets checked/unchecked status of checkboxes
 */
function setCheckboxesState(nameprefix, checked){
    // XXX: this looks in *all* the document for inputs
    var elements = getElementsMatching('input', {'type': "checkbox"});
    filterfunc = function(cb) { return nameprefix && cb.name.startsWith(nameprefix); };
    forEach(filter(filterfunc, elements), function(cb) {cb.checked=checked;});
}

function setCheckboxesState2(nameprefix, value, checked){
    // XXX: this looks in *all* the document for inputs
    var elements = getElementsMatching('input', {'type': "checkbox"});
    filterfunc = function(cb) { return nameprefix && cb.name.startsWith(nameprefix) && cb.value == value; };
    forEach(filter(filterfunc, elements), function(cb) {cb.checked=checked;});
}

/* centers an HTML element on the screen */
// XXX looks unused
function centerElement(obj){
    var vpDim = getViewportDimensions();
    var elemDim = getElementDimensions(obj);
    setElementPosition(obj, {'x':((vpDim.w - elemDim.w)/2),
			     'y':((vpDim.h - elemDim.h)/2)});
}

/* this function is a hack to build a dom node from html source */
function html2dom(source) {
    var tmpNode = SPAN();
    tmpNode.innerHTML = source;
    if (tmpNode.childNodes.length == 1) {
	return tmpNode.firstChild;
    }
    else {
	// we leave the span node when `source` has no root node
	// XXX This is cleary not the best solution, but css/html-wise,
	///    a span not should not be too  much disturbing
	return tmpNode;
    }
}


// *** HELPERS **************************************************** //
function rql_for_eid(eid) { return 'Any X WHERE X eid ' + eid; }
function isTextNode(domNode) { return domNode.nodeType == 3; }
function isElementNode(domNode) { return domNode.nodeType == 1; }

// XXX this looks unused
function changeLinkText(link, newText) {
    jQuery(link).text(newText);
}


function autogrow(area) {
    log('scrollHeight ' + area.scrollHeight);
    log('clientHeight ' + area.clientHeight);
    if (area.scrollHeight > area.clientHeight && !window.opera) {
	if (area.rows < 20) {
	    area.rows += 2;
	}
    }
}

// XXX this looks unused
function limitTextAreaSize(textarea, size) {
    var $area = jQuery(textarea);
    $area.val($area.val().slice(0, size));
}

//============= page loading events ==========================================//

CubicWeb.rounded = [
		    ['div.sideBoxBody', 'bottom 6px'],
		    ['div.boxTitle, div.boxPrefTitle, div.sideBoxTitle, th.month', 'top 6px']
		    ];



function roundedCorners(node) {
    node = jQuery(node);
    for(var r=0; r < CubicWeb.rounded.length; r++) {
       node.find(CubicWeb.rounded[r][0]).corner(CubicWeb.rounded[r][1]);
    }
}

jQuery(document).ready(function () {roundedCorners(this.body)});

CubicWeb.provide('htmlhelpers.js');

