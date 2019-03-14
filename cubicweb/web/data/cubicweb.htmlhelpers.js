/* in CW 3.10, we should move these functions in this namespace */
cw.htmlhelpers = new Namespace('cw.htmlhelpers');

jQuery.extend(cw.htmlhelpers, {
    popupLoginBox: function(loginboxid, focusid) {
        $('#'+loginboxid).toggleClass('hidden');
        jQuery('#' + focusid +':visible').focus();
    }
});


/**
 * .. function:: setProgressCursor()
 *
 * set body's cursor to 'progress'
 */
function setProgressCursor() {
    var body = document.getElementsByTagName('body')[0];
    body.style.cursor = 'progress';
}

/**
 * .. function:: resetCursor(result)
 *
 * reset body's cursor to default (mouse cursor). The main
 * purpose of this function is to be used as a callback in the
 * deferreds' callbacks chain.
 */
function resetCursor(result) {
    var body = document.getElementsByTagName('body')[0];
    body.style.cursor = '';
    // pass result to next callback in the callback chain
    return result;
}

function updateMessage(msg) {
    var msgdiv = DIV({
        'class': 'message'
    });
    // don't pass msg to DIV() directly because DIV will html escape it
    // and msg should alreay be html escaped at this point.
    msgdiv.innerHTML = msg;
    jQuery('#appMsg').removeClass('hidden').empty().append(msgdiv);
}

/**
 * .. function:: asURL(props)
 *
 * builds a URL from an object (used as a dictionary)
 *
 * >>> asURL({'rql' : "RQL", 'x': [1, 2], 'itemvid' : "oneline"})
 * rql=RQL&vid=list&itemvid=oneline&x=1&x=2
 * >>> asURL({'rql' : "a&b", 'x': [1, 2], 'itemvid' : "oneline"})
 * rql=a%26b&x=1&x=2&itemvid=oneline
 */
function asURL(props) {
    var chunks = [];
    for (key in props) {
        var value = props[key];
        // generate a list of couple key=value if key is multivalued
        if (cw.utils.isArrayLike(value)) {
            for (var i = 0; i < value.length; i++) {
                chunks.push(key + '=' + cw.urlEncode(value[i]));
            }
        } else {
            chunks.push(key + '=' + cw.urlEncode(value));
        }
    }
    return chunks.join('&');
}

/**
 * .. function:: firstSelected(selectNode)
 *
 * return selected value of a combo box if any
 */
function firstSelected(selectNode) {
    var $selection = $(selectNode).find('option:selected:first');
    return ($selection.length > 0) ? $selection[0] : null;
}

/**
 * .. function:: toggleVisibility(elemId)
 *
 * toggle visibility of an element by its id
 */
function toggleVisibility(elemId) {
    cw.jqNode(elemId).toggleClass('hidden');
}

/**
 * .. function getElementsMatching(tagName, properties, \/* optional \*\/ parent)
 *
 * returns the list of elements in the document matching the tag name
 * and the properties provided
 *
 * * `tagName`, the tag's name
 *
 * * `properties`, a js Object used as a dict
 *
 * Return an iterator (if a *real* array is needed, you can use the
 *                      list() function)
 */
function getElementsMatching(tagName, properties, /* optional */ parent) {
    parent = parent || document;
    return jQuery.grep(parent.getElementsByTagName(tagName), function elementMatches(element) {
        for (prop in properties) {
            if (jQuery(element).attr(prop) != properties[prop]) {
                return false;
            }
        }
        return true;
    });
}

/**
 * .. function:: setCheckboxesState(nameprefix, value, checked)
 *
 * sets checked/unchecked status of checkboxes
 */

function setCheckboxesState(nameprefix, value, checked) {
    // XXX: this looks in *all* the document for inputs
    jQuery('input:checkbox[name^=' + nameprefix + ']').each(function() {
        if (value == null || this.value == value) {
            this.checked = checked;
        }
    });
}

/**
 * .. function:: html2dom(source)
 *
 * this function is a hack to build a dom node from html source
 */
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
function rql_for_eid(eid) {
    return 'Any X WHERE X eid ' + eid;
}
function isTextNode(domNode) {
    return domNode.nodeType == 3;
}
function isElementNode(domNode) {
    return domNode.nodeType == 1;
}

function autogrow(area) {
    if (area.scrollHeight > area.clientHeight && ! window.opera) {
        if (area.rows < 20) {
            area.rows += 2;
        }
    }
}

