/* copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 * contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 * This file is part of CubicWeb.
 *
 * CubicWeb is free software: you can redistribute it and/or modify it under the
 * terms of the GNU Lesser General Public License as published by the Free
 * Software Foundation, either version 2.1 of the License, or (at your option)
 * any later version.
 *
 * CubicWeb is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
 * details.
 *
 * You should have received a copy of the GNU Lesser General Public License along
 * with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
 */

CubicWeb.require('python.js');
CubicWeb.require('htmlhelpers.js');

var JSON_BASE_URL = baseuri() + 'json?';

//============= utility function handling remote calls responses. ==============//
function _loadAjaxHtmlHead(node, head, tag, srcattr) {
    var loaded = [];
    var jqtagfilter = tag + '[' + srcattr + ']';
    jQuery('head ' + jqtagfilter).each(function(i) {
        loaded.push(this.getAttribute(srcattr));
    });
    node.find(tag).each(function(i) {
        if (this.getAttribute(srcattr)) {
            if (jQuery.inArray(this.getAttribute(srcattr), loaded) == -1) {
                jQuery(this).appendTo(head);
            }
        } else {
            jQuery(this).appendTo(head);
        }
    });
    node.find(jqtagfilter).remove();
}

/**
 * .. function:: function loadAjaxHtmlHead(response)
 *
 * inspect dom response (as returned by getDomFromResponse), search for
 * a <div class="ajaxHtmlHead"> node and put its content into the real
 * document's head.
 * This enables dynamic css and js loading and is used by replacePageChunk
 */
function loadAjaxHtmlHead(response) {
    var $head = jQuery('head');
    var $responseHead = jQuery(response).find('div.ajaxHtmlHead');
    // no ajaxHtmlHead found, no processing required
    if (!$responseHead.length) {
        return response;
    }
    _loadAjaxHtmlHead($responseHead, $head, 'script', 'src');
    _loadAjaxHtmlHead($responseHead, $head, 'link', 'href');
    // add any remaining children (e.g. meta)
    $responseHead.children().appendTo($head);
    // remove original container, which is now empty
    $responseHead.remove();
    // if there was only one actual node in the reponse besides
    // the ajaxHtmlHead, then remove the wrapper created by
    // getDomFromResponse() and return this single element
    // For instance :
    // 1/ CW returned the following content :
    //    <div>the-actual-content</div><div class="ajaxHtmlHead">...</div>
    // 2/ getDomFromReponse() wrapped this into a single DIV to hold everything
    //    in one, unique, dom element
    // 3/ now that we've removed the ajaxHtmlHead div, the only
    //    node left in the wrapper if the 'real' node built by the view,
    //    we can safely return this node. Otherwise, the view itself
    //    returned several 'root' nodes and we need to keep the wrapper
    //    created by getDomFromResponse()
    if (response.childNodes.length == 1 && response.getAttribute('cubicweb:type') == 'cwResponseWrapper') {
        return response.firstChild;
    }
    return response;
}

function _postAjaxLoad(node) {
    // find sortable tables if there are some
    if (typeof(Sortable) != 'undefined') {
        Sortable.sortTables(node);
    }
    // find textareas and wrap them if there are some
    if (typeof(FCKeditor) != 'undefined') {
        buildWysiwygEditors();
    }
    if (typeof initFacetBoxEvents != 'undefined') {
        initFacetBoxEvents(node);
    }
    if (typeof buildWidgets != 'undefined') {
        buildWidgets(node);
    }
    if (typeof roundedCorners != 'undefined') {
        roundedCorners(node);
    }
    if (typeof setFormsTarget != 'undefined') {
        setFormsTarget(node);
    }
    _loadDynamicFragments(node);
    // XXX [3.7] jQuery.one is now used instead jQuery.bind,
    // jquery.treeview.js can be unpatched accordingly.
    jQuery(CubicWeb).trigger('server-response', [true, node]);
    jQuery(node).trigger('server-response', [true, node]);
}

function remoteCallFailed(err, req) {
    cw.log(err);
    if (req.status == 500) {
        updateMessage(err);
    } else {
        updateMessage(_("an error occured while processing your request"));
    }
}

//============= base AJAX functions to make remote calls =====================//
/**
 * .. function:: ajaxFuncArgs(fname, form, *args)
 *
 * extend `form` parameters to call the js_`fname` function of the json
 * controller with `args` arguments.
 */
function ajaxFuncArgs(fname, form /* ... */) {
    form = form || {};
    $.extend(form, {
        'fname': fname,
        'pageid': pageid,
        'arg': map(jQuery.toJSON, sliceList(arguments, 2))
    });
    return form;
}

/**
 * .. function:: loadxhtml(url, form, reqtype='get', mode='replace', cursor=true)
 *
 * build url given by absolute or relative `url` and `form` parameters
 * (dictionary), fetch it using `reqtype` method, then evaluate the
 * returned XHTML and insert it according to `mode` in the
 * document. Possible modes are :
 *
 *    - 'replace' to replace the node's content with the generated HTML
 *    - 'swap' to replace the node itself with the generated HTML
 *    - 'append' to append the generated HTML to the node's content
 *
 * If `cursor`, turn mouse cursor into 'progress' cursor until the remote call
 * is back.
 */
jQuery.fn.loadxhtml = function(url, form, reqtype, mode, cursor) {
    if (this.size() > 1) {
        cw.log('loadxhtml was called with more than one element');
    }
    var callback = null;
    if (form && form.callback) {
        cw.log('[3.9] callback given through form.callback is deprecated, add ' + 'callback on the defered');
        callback = form.callback;
        delete form.callback;
    }
    var node = this.get(0); // only consider the first element
    if (cursor) {
        setProgressCursor();
    }
    var d = loadRemote(url, form, reqtype);
    d.addCallback(function(response) {
        var domnode = getDomFromResponse(response);
        domnode = loadAjaxHtmlHead(domnode);
        mode = mode || 'replace';
        // make sure the component is visible
        $(node).removeClass("hidden");
        if (mode == 'swap') {
            var origId = node.id;
            node = swapDOM(node, domnode);
            if (!node.id) {
                node.id = origId;
            }
        } else if (mode == 'replace') {
            jQuery(node).empty().append(domnode);
        } else if (mode == 'append') {
            jQuery(node).append(domnode);
        }
        _postAjaxLoad(node);
        while (jQuery.isFunction(callback)) {
            callback = callback.apply(this, [domnode]);
        }
    });
    if (cursor) {
        d.addCallback(resetCursor);
        d.addErrback(resetCursor);
        d.addErrback(remoteCallFailed);
    }
    return d;
}

/**
 * .. function:: loadRemote(url, form, reqtype='GET', async=true)
 *
 * Asynchronously (unless `async` argument is set to false) load an url or path
 * and return a deferred whose callbacks args are decoded according to the
 * Content-Type response header. `form` should be additional form params
 * dictionary, `reqtype` the HTTP request type (get 'GET' or 'POST').
 */
function loadRemote(url, form, reqtype, sync) {
    if (!url.startswith(baseuri())) {
        url = baseuri() + url;
    }
    if (!sync) {
        var deferred = new Deferred();
        jQuery.ajax({
            url: url,
            type: (reqtype || 'GET').toUpperCase(),
            data: form,
            async: true,

            beforeSend: function(xhr) {
                deferred._req = xhr;
            },

            success: function(data, status) {
                if (deferred._req.getResponseHeader("content-type") == 'application/json') {
                    data = cw.evalJSON(data);
                }
                deferred.success(data);
            },

            error: function(xhr, status, error) {
                try {
                    if (xhr.status == 500) {
                        var reason_dict = cw.evalJSON(xhr.responseText);
                        deferred.error(xhr, status, reason_dict['reason']);
                        return;
                    }
                } catch(exc) {
                    cw.log('error with server side error report:' + exc);
                }
                deferred.error(xhr, status, null);
            }
        });
        return deferred;
    } else {
        var result = jQuery.ajax({
            url: url,
            type: (reqtype || 'GET').toUpperCase(),
            data: form,
            async: false
        });
        if (result) {
            // XXX no good reason to force json here, 
            // it should depends on request content-type
            result = cw.evalJSON(result.responseText);
        }
        return result
    }
}

//============= higher level AJAX functions using remote calls ===============//
/**
 * .. function:: _(message)
 *
 * emulation of gettext's _ shortcut
 */
function _(message) {
    return loadRemote('json', ajaxFuncArgs('i18n', null, [message]), 'GET', true)[0];
}

/**
 * .. function:: _loadDynamicFragments(node)
 *
 * finds each dynamic fragment in the page and executes the
 * the associated RQL to build them (Async call)
 */
function _loadDynamicFragments(node) {
    if (node) {
        var fragments = jQuery(node).find('div.dynamicFragment');
    } else {
        var fragments = jQuery('div.dynamicFragment');
    }
    if (fragments.length == 0) {
        return;
    }
    if (typeof LOADING_MSG == 'undefined') {
        LOADING_MSG = 'loading'; // this is only a safety belt, it should not happen
    }
    for (var i = 0; i < fragments.length; i++) {
        var fragment = fragments[i];
        fragment.innerHTML = '<h3>' + LOADING_MSG + ' ... <img src="data/loading.gif" /></h3>';
        var $fragment = jQuery(fragment);
        // if cubicweb:loadurl is set, just pick the url et send it to loadxhtml
        var url = $fragment.attr('cubicweb:loadurl');
        if (url) {
            $fragment.loadxhtml(url);
            continue;
        }
        // else: rebuild full url by fetching cubicweb:rql, cubicweb:vid, etc.
        var rql = $fragment.attr('cubicweb:rql');
        var items = $fragment.attr('cubicweb:vid').split('&');
        var vid = items[0];
        var extraparams = {};
        // case where vid='myvid&param1=val1&param2=val2': this is a deprecated abuse-case
        if (items.length > 1) {
            cw.log("[3.5] you're using extraargs in cubicweb:vid " +
                   "attribute, this is deprecated, consider using " +
                   "loadurl instead");
            for (var j = 1; j < items.length; j++) {
                var keyvalue = items[j].split('=');
                extraparams[keyvalue[0]] = keyvalue[1];
            }
        }
        var actrql = $fragment.attr('cubicweb:actualrql');
        if (actrql) {
            extraparams['actualrql'] = actrql;
        }
        var fbvid = $fragment.attr('cubicweb:fallbackvid');
        if (fbvid) {
            extraparams['fallbackvid'] = fbvid;
        }
        extraparams['rql'] = rql;
        extraparams['vid'] = vid;
        $(fragment.id).loadxhtml('json', ajaxFuncArgs('view', extraparams));
    }
}
jQuery(document).ready(function() {
    _loadDynamicFragments();
});

function unloadPageData() {
    // NOTE: do not make async calls on unload if you want to avoid
    //       strange bugs
    loadRemote('json', ajaxFuncArgs('unload_page_data'), 'GET', true);
}

function removeBookmark(beid) {
    var d = loadRemote('json', ajaxFuncArgs('delete_bookmark', null, beid));
    d.addCallback(function(boxcontent) {
        $('#bookmarks_box').loadxhtml('json',
                                      ajaxFuncArgs('render', null, 'boxes',
                                                   'bookmarks_box'));
        document.location.hash = '#header';
        updateMessage(_("bookmark has been removed"));
    });
}

function userCallback(cbname) {
    setProgressCursor();
    var d = loadRemote('json', ajaxFuncArgs('user_callback', null, cbname));
    d.addCallback(resetCursor);
    d.addErrback(resetCursor);
    d.addErrback(remoteCallFailed);
    return d;
}

function userCallbackThenUpdateUI(cbname, compid, rql, msg, registry, nodeid) {
    var d = userCallback(cbname);
    d.addCallback(function() {
        $('#' + nodeid).loadxhtml('json', ajaxFuncArgs('render', {
            'rql': rql
        },
        registry, compid));
        if (msg) {
            updateMessage(msg);
        }
    });
}

function userCallbackThenReloadPage(cbname, msg) {
    var d = userCallback(cbname);
    d.addCallback(function() {
        window.location.reload();
        if (msg) {
            updateMessage(msg);
        }
    });
}

/**
 * .. function:: unregisterUserCallback(cbname)
 *
 * unregisters the python function registered on the server's side
 * while the page was generated.
 */
function unregisterUserCallback(cbname) {
    setProgressCursor();
    var d = loadRemote('json', ajaxFuncArgs('unregister_user_callback',
                                            null, cbname));
    d.addCallback(resetCursor);
    d.addErrback(resetCursor);
    d.addErrback(remoteCallFailed);
}

//============= XXX move those functions? ====================================//
function openHash() {
    if (document.location.hash) {
        var nid = document.location.hash.replace('#', '');
        var node = jQuery('#' + nid);
        if (node) {
            $(node).removeClass("hidden");
        }
    };
}
jQuery(document).ready(openHash);

/**
 * .. function:: buildWysiwygEditors(parent)
 *
 *XXX: this function should go in edition.js but as for now, htmlReplace
 * references it.
 *
 * replace all textareas with fckeditors.
 */
function buildWysiwygEditors(parent) {
    jQuery('textarea').each(function() {
        if (this.getAttribute('cubicweb:type') == 'wysiwyg') {
            // mark editor as instanciated, we may be called a number of times
            // (see _postAjaxLoad)
            this.setAttribute('cubicweb:type', 'fckeditor');
            if (typeof FCKeditor != "undefined") {
                var fck = new FCKeditor(this.id);
                fck.Config['CustomConfigurationsPath'] = fckconfigpath;
                fck.Config['DefaultLanguage'] = fcklang;
                fck.BasePath = "fckeditor/";
                fck.ReplaceTextarea();
            } else {
                cw.log('fckeditor could not be found.');
            }
        }
    });
}
jQuery(document).ready(buildWysiwygEditors);

/**
 * .. function:: stripEmptyTextNodes(nodelist)
 *
 * takes a list of DOM nodes and removes all empty text nodes
 */
function stripEmptyTextNodes(nodelist) {
    /* this DROPS empty text nodes */
    var stripped = [];
    for (var i = 0; i < nodelist.length; i++) {
        var node = nodelist[i];
        if (isTextNode(node)) {
            /* all browsers but FF -> innerText, FF -> textContent  */
            var text = node.innerText || node.textContent;
            if (text && ! text.strip()) {
                continue;
            }
        } else {
            stripped.push(node);
        }
    }
    return stripped;
}

/**
 * .. function:: getDomFromResponse(response)
 *
 * convenience function that returns a DOM node based on req's result.
 * XXX clarify the need to clone
 * */
function getDomFromResponse(response) {
    if (typeof(response) == 'string') {
        var doc = html2dom(response);
    } else {
        var doc = response.documentElement;
    }
    var children = doc.childNodes;
    if (!children.length) {
        // no child (error cases) => return the whole document
        return jQuery(doc).clone().context;
    }
    children = stripEmptyTextNodes(children);
    if (children.length == 1) {
        // only one child => return it
        return jQuery(children[0]).clone().context;
    }
    // several children => wrap them in a single node and return the wrap
    return DIV({
        'cubicweb:type': "cwResponseWrapper"
    },
    map(function(node) {
        return jQuery(node).clone().context;
    },
    children));
}

CubicWeb.provide('ajax.js');

/* DEPRECATED *****************************************************************/

preprocessAjaxLoad = cw.utils.deprecatedFunction(
    '[3.9] preprocessAjaxLoad() is deprecated, use loadAjaxHtmlHead instead',
    function(node, newdomnode) {
        return loadAjaxHtmlHead(newdomnode);
    }
);

reloadComponent = cw.utils.deprecatedFunction(
    '[3.9] reloadComponent() is deprecated, use loadxhtml instead',
    function(compid, rql, registry, nodeid, extraargs) {
        registry = registry || 'components';
        rql = rql || '';
        nodeid = nodeid || (compid + 'Component');
        extraargs = extraargs || {};
        var node = jqNode(nodeid);
        return node.loadxhtml('json', ajaxFuncArgs('component', null, compid,
                                                   rql, registry, extraargs));
    }
);

reloadBox = cw.utils.deprecatedFunction(
    '[3.9] reloadBox() is deprecated, use loadxhtml instead',
    function(boxid, rql) {
        return reloadComponent(boxid, rql, 'boxes', boxid);
    }
);

replacePageChunk = cw.utils.deprecatedFunction(
    '[3.9] replacePageChunk() is deprecated, use loadxhtml instead',
    function(nodeId, rql, vid, extraparams, /* ... */ swap, callback) {
        var params = null;
        if (callback) {
            params = {
                callback: callback
            };
        }
        var node = jQuery('#' + nodeId)[0];
        var props = {};
        if (node) {
            props['rql'] = rql;
            props['fname'] = 'view';
            props['pageid'] = pageid;
            if (vid) {
                props['vid'] = vid;
            }
            if (extraparams) {
                jQuery.extend(props, extraparams);
            }
            // FIXME we need to do asURL(props) manually instead of
            // passing `props` directly to loadxml because replacePageChunk
            // is sometimes called (abusively) with some extra parameters in `vid`
            var mode = swap ? 'swap': 'replace';
            var url = JSON_BASE_URL + asURL(props);
            jQuery(node).loadxhtml(url, params, 'get', mode);
        } else {
            cw.log('Node', nodeId, 'not found');
        }
    }
);

loadxhtml = cw.utils.deprecatedFunction(
    '[3.9] loadxhtml() function is deprecated, use loadxhtml method instead',
    function(nodeid, url, /* ... */ replacemode) {
        jQuery('#' + nodeid).loadxhtml(url, null, 'post', replacemode);
    }
);

remoteExec = cw.utils.deprecatedFunction(
    '[3.9] remoteExec() is deprecated, use loadRemote instead',
    function(fname /* ... */) {
        setProgressCursor();
        var props = {
            'fname': fname,
            'pageid': pageid,
            'arg': map(jQuery.toJSON, sliceList(arguments, 1))
        };
        var result = jQuery.ajax({
            url: JSON_BASE_URL,
            data: props,
            async: false
        }).responseText;
        if (result) {
            result = cw.evalJSON(result);
        }
        resetCursor();
        return result;
    }
);

asyncRemoteExec = cw.utils.deprecatedFunction(
    '[3.9] asyncRemoteExec() is deprecated, use loadRemote instead',
    function(fname /* ... */) {
        setProgressCursor();
        var props = {
            'fname': fname,
            'pageid': pageid,
            'arg': map(jQuery.toJSON, sliceList(arguments, 1))
        };
        // XXX we should inline the content of loadRemote here
        var deferred = loadRemote(JSON_BASE_URL, props, 'POST');
        deferred = deferred.addErrback(remoteCallFailed);
        deferred = deferred.addErrback(resetCursor);
        deferred = deferred.addCallback(resetCursor);
        return deferred;
    }
);

