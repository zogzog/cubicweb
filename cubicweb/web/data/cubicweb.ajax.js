/* copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

/**
 * .. function:: Deferred
 *
 * dummy ultra minimalist implementation of deferred for jQuery
 */

cw.ajax = new Namespace('cw.ajax');

function Deferred() {
    this.__init__(this);
}

jQuery.extend(Deferred.prototype, {
    __init__: function() {
        this._onSuccess = [];
        this._onFailure = [];
        this._req = null;
        this._result = null;
        this._error = null;
    },

    addCallback: function(callback) {
        if (this._req && (this._req.readyState == 4) && this._result) {
            var args = [this._result, this._req];
            jQuery.merge(args, cw.utils.sliceList(arguments, 1));
            callback.apply(null, args);
        }
        else {
            this._onSuccess.push([callback, cw.utils.sliceList(arguments, 1)]);
        }
        return this;
    },

    addErrback: function(callback) {
        if (this._req && this._req.readyState == 4 && this._error) {
            callback.apply(null, [this._error, this._req]);
        }
        else {
            this._onFailure.push([callback, cw.utils.sliceList(arguments, 1)]);
        }
        return this;
    },

    success: function(result) {
        this._result = result;
        for (var i = 0; i < this._onSuccess.length; i++) {
            var callback = this._onSuccess[i][0];
            var args = [result, this._req];
            jQuery.merge(args, this._onSuccess[i][1]);
            callback.apply(null, args);
        }
    },

    error: function(xhr, status, error) {
        this._error = error;
        for (var i = 0; i < this._onFailure.length; i++) {
            var callback = this._onFailure[i][0];
            var args = [error, this._req];
            jQuery.merge(args, this._onFailure[i][1]);
            if (callback !== undefined)
                callback.apply(null, args);
        }
    }

});

var AJAX_PREFIX_URL = 'ajax';
var JSON_BASE_URL = BASE_URL + 'json?';
var AJAX_BASE_URL = BASE_URL + AJAX_PREFIX_URL + '?';


jQuery.extend(cw.ajax, {
    /* variant of jquery evalScript with cache: true in ajax call */
    _evalscript: function ( i, elem ) {
       var src = elem.getAttribute('src');
       if (src) {
           jQuery.ajax({
               url: src,
               async: false,
               cache: true,
               dataType: "script"
           });
       } else {
           jQuery.globalEval( elem.text || elem.textContent || elem.innerHTML || "" );
       }
       if ( elem.parentNode ) {
           elem.parentNode.removeChild( elem );
       }
    },

    evalscripts: function ( scripts ) {
        if ( scripts.length ) {
            jQuery.each(scripts, cw.ajax._evalscript);
        }
    },

    /**
     * returns true if `url` is a mod_concat-like url
     * (e.g. http://..../data??resource1.js,resource2.js)
     */
    _modconcatLikeUrl: function(url) {
        var modconcat_rgx = new RegExp('(' + BASE_URL + 'data/([a-z0-9]+/)?)\\?\\?(.+)');
        return modconcat_rgx.exec(url);
    },

    /**
     * decomposes a mod_concat-like url into its corresponding list of
     * resources' urls
     * >>> _listResources('http://foo.com/data/??a.js,b.js,c.js')
     * ['http://foo.com/data/a.js', 'http://foo.com/data/b.js', 'http://foo.com/data/c.js']
     */
    _listResources: function(src) {
        var resources = [];
        var groups = cw.ajax._modconcatLikeUrl(src);
        if (groups == null) {
            resources.push(src);
        } else {
            var dataurl = groups[1];
            $.each(cw.utils.lastOf(groups).split(','),
                 function() {
                     resources.push(dataurl + this);
                 }
            );
        }
        return resources;
    },

    _buildMissingResourcesUrl: function(url, loadedResources) {
        var resources = cw.ajax._listResources(url);
        var missingResources = $.grep(resources, function(resource) {
            return $.inArray(resource, loadedResources) == -1;
        });
        cw.utils.extend(loadedResources, missingResources);
        var missingResourceUrl = null;
        if (missingResources.length == 1) {
            // only one resource missing: build a node with a single resource url
            // (maybe the browser has it in cache already)
            missingResourceUrl = missingResources[0];
        } else if (missingResources.length > 1) {
            // several resources missing: build a node with a concatenated
            // resources url
            var dataurl = cw.ajax._modconcatLikeUrl(url)[1];
            var missing_path = $.map(missingResources, function(resource) {
                return resource.substring(dataurl.length);
            });
            missingResourceUrl = dataurl + '??' + missing_path.join(',');
        }
        return missingResourceUrl;
    },

    _loadAjaxStylesheets: function($responseHead, $head) {
        $responseHead.find('link[href]').each(function(i) {
            var $srcnode = $(this);
            var url = $srcnode.attr('href');
            if (url) {
                var missingStylesheetsUrl = cw.ajax._buildMissingResourcesUrl(url, cw.loaded_links);
                // compute concat-like url for missing resources and append <link>
                // element to $head
                if (missingStylesheetsUrl) {
                    // IE has problems with dynamic CSS insertions. One symptom (among others)
                    // is a "1 item remaining" message in the status bar. (cf. #2356261)
                    // document.createStyleSheet needs to be used for this, although it seems
                    // that IE can't create more than 31 additional stylesheets with
                    // document.createStyleSheet.
                    if ($.browser.msie) {
                        document.createStyleSheet(missingStylesheetsUrl);
                    } else {
                        $srcnode.attr('href', missingStylesheetsUrl);
                        $srcnode.appendTo($head);
                    }
                }
            }
        });
        $responseHead.find('link[href]').remove();
    },

    _loadAjaxScripts: function($responseHead, $head) {
        $responseHead.find('cubicweb\\:script').each(function(i) {
            var $srcnode = $(this);
            var url = $srcnode.attr('src');
            if (url) {
                var missingScriptsUrl = cw.ajax._buildMissingResourcesUrl(url, cw.loaded_scripts);
                if (missingScriptsUrl) {
                    $srcnode.attr('src', missingScriptsUrl);
                    /* special handling of <script> tags: script nodes appended by jquery
                     * use uncached ajax calls and do not appear in the DOM
                     * (See comments in response to Syt on // http://api.jquery.com/append/),
                     * which cause undesired duplicated load in our case. We now handle
                     * a list of already loaded resources, since bare DOM api gives bugs with the
                     * server-response event, and we lose control on when the
                     * script is loaded (jQuery loads it immediately). */
                    cw.ajax.evalscripts($srcnode);
                }
            } else {
                // <script> contains inlined javascript code, node content
                // must be evaluated
    	        jQuery.globalEval($srcnode.text());
    	    }
        });
        $responseHead.find('cubicweb\\:script').remove();
    }
});

//============= utility function handling remote calls responses. ==============//
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
    cw.ajax._loadAjaxStylesheets($responseHead, $head);
    cw.ajax._loadAjaxScripts($responseHead, $head);
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
    _loadDynamicFragments(node);
    jQuery(cw).trigger('server-response', [true, node]);
    jQuery(node).trigger('server-response', [true, node]);
}

function remoteCallFailed(err, req) {
    cw.log(err);
    if (req.status == 500) {
        updateMessage(err);
    } else {
        updateMessage(_("an error occurred while processing your request"));
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
        'arg': $.map(cw.utils.sliceList(arguments, 2), JSON.stringify)
    });
    return form;
}

/**
 * .. function:: loadxhtml(url, form, reqtype='get', mode='replace', cursor=false)
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
        cw.log('loadxhtml called with more than one element');
    } else if (this.size() < 1) {
        cw.log('loadxhtml called without an element');
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
            node = cw.swapDOM(node, domnode);
            if (!node.id) {
                node.id = origId;
            }
        } else if (mode == 'replace') {
            jQuery(node).empty().append(domnode);
        } else if (mode == 'append') {
            jQuery(node).append(domnode);
        }
        _postAjaxLoad(node);
    });
    d.addErrback(remoteCallFailed);
    if (cursor) {
        d.addCallback(resetCursor);
        d.addErrback(resetCursor);
    }
    return d;
}

/**
 * .. function:: loadRemote(url, form, reqtype='POST', sync=false)
 *
 * Asynchronously (unless `sync` argument is set to true) load a URL or path
 * and return a deferred whose callbacks args are decoded according to the
 * Content-Type response header. `form` should be additional form params
 * dictionary, `reqtype` the HTTP request type (get 'GET' or 'POST').
 */
function loadRemote(url, form, reqtype, sync) {
    if (!url.toLowerCase().startswith(BASE_URL.toLowerCase())) {
        url = BASE_URL + url;
    }
    if (!sync) {
        var deferred = new Deferred();
        jQuery.ajax({
            url: url,
            type: (reqtype || 'POST').toUpperCase(),
            data: form,
            traditional: true,
            async: true,

            beforeSend: function(xhr) {
                deferred._req = xhr;
            },

            success: function(data, status) {
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
        var result;
        // jQuery.ajax returns the XHR object, even for synchronous requests,
        // but in that case, the success callback will be called before
        // jQuery.ajax returns. The first argument of the callback will be
        // the server result, interpreted by jQuery according to the reponse's
        // content-type (i.e. json or xml)
        jQuery.ajax({
            url: url,
            type: (reqtype || 'GET').toUpperCase(),
            data: form,
            traditional: true,
            async: false,
            success: function(res) {
                result = res;
            }
        });
        return result;
    }
}

//============= higher level AJAX functions using remote calls ===============//

var _i18ncache = {};

/**
 * .. function:: _(message)
 *
 * emulation of gettext's _ shortcut
 */
function _(message) {
    var form;
    if (!(message in _i18ncache)) {
        form = ajaxFuncArgs('i18n', null, [message]);
        _i18ncache[message] = loadRemote(AJAX_BASE_URL, form, 'GET', true)[0];
    }
    return _i18ncache[message];
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
        fragment.innerHTML = (
            '<h3>' + LOADING_MSG +
                ' ... <img src="' + BASE_URL + 'data/loading.gif" /></h3>');
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
        $fragment.loadxhtml(AJAX_BASE_URL, ajaxFuncArgs('view', extraparams));
    }
}
function unloadPageData() {
    // NOTE: do not make async calls on unload if you want to avoid
    //       strange bugs
    loadRemote(AJAX_BASE_URL, ajaxFuncArgs('unload_page_data'), 'POST', true);
}

function removeBookmark(beid) {
    var d = loadRemote(AJAX_BASE_URL, ajaxFuncArgs('delete_bookmark', null, beid));
    d.addCallback(function(boxcontent) {
        $('#bookmarks_box').loadxhtml(AJAX_BASE_URL,
                                      ajaxFuncArgs('render', null, 'ctxcomponents',
                                                   'bookmarks_box'),
                                      null, 'swap');
        document.location.hash = '#header';
        updateMessage(_("bookmark has been removed"));
    });
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
                fck.BasePath = BASE_URL + "fckeditor/";
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
    return DIV({'cubicweb:type': "cwResponseWrapper"},
               $.map(children, function(node) {
                       return jQuery(node).clone().context;})
               );
}

/* High-level functions *******************************************************/

/**
 * .. function:: reloadCtxComponentsSection(context, actualEid, creationEid=None)
 *
 * reload all components in the section for a given `context`.
 *
 * This is necessary for cases where the parent entity (on which the section
 * apply) has been created during post, hence the section has to be reloaded to
 * consider its new eid, hence the two additional arguments `actualEid` and
 * `creationEid`: `actualEid` is the eid of newly created top level entity and
 * `creationEid` the fake eid that was given as form creation marker (e.g. A).
 *
 * You can still call this function with only the actual eid if you're not in
 * such creation case.
 */
function reloadCtxComponentsSection(context, actualEid, creationEid) {
    // in this case, actualEid is the eid of newly created top level entity and
    // creationEid the fake eid given as form creation marker (e.g. A)
    if (!creationEid) { creationEid = actualEid ; }
    var $compsholder = $('#' + context + creationEid);
    // reload the whole components section
    $compsholder.children().each(function (index) {
	// XXX this.id[:-len(eid)]
	var compid = this.id.replace("_", ".").rstrip(creationEid);
	var params = ajaxFuncArgs('render', null, 'ctxcomponents',
				  compid, actualEid);
	$(this).loadxhtml(AJAX_BASE_URL, params, null, 'swap', true);
    });
    $compsholder.attr('id', context + actualEid);
}


/**
 * .. function:: reload(domid, compid, registry, formparams, *render_args)
 *
 * `js_render` based reloading of views and components.
 */
function reload(domid, compid, registry, formparams  /* ... */) {
    var ajaxArgs = ['render', formparams, registry, compid];
    ajaxArgs = ajaxArgs.concat(cw.utils.sliceList(arguments, 4));
    var params = ajaxFuncArgs.apply(null, ajaxArgs);
    return $('#'+domid).loadxhtml(AJAX_BASE_URL, params, null, 'swap', true);
}

/* ajax tabs ******************************************************************/

function setTab(tabname, cookiename) {
    // set appropriate cookie
    jQuery.cookie(cookiename, tabname, {path: '/'});
    // trigger show + tabname event
    triggerLoad(tabname);
}

function loadNow(eltsel, holesel, reloadable) {
    var lazydiv = jQuery(eltsel);
    var hole = lazydiv.children(holesel);
    hole.show();
    if ((hole.length == 0) && ! reloadable) {
        /* the hole is already filed */
        return;
    }
    lazydiv.loadxhtml(lazydiv.attr('cubicweb:loadurl'), {'pageid': pageid});
}

function triggerLoad(divid) {
    jQuery('#lazy-' + divid).trigger('load_' + divid);
}

/* DEPRECATED *****************************************************************/

// still used in cwo and keyword cubes at least
reloadComponent = cw.utils.deprecatedFunction(
    '[3.9] reloadComponent() is deprecated, use loadxhtml instead',
    function(compid, rql, registry, nodeid, extraargs) {
        registry = registry || 'components';
        rql = rql || '';
        nodeid = nodeid || (compid + 'Component');
        extraargs = extraargs || {};
        var node = cw.jqNode(nodeid);
        return node.loadxhtml(AJAX_BASE_URL, ajaxFuncArgs('component', null, compid,
                                                          rql, registry, extraargs));
    }
);


function remoteExec(fname /* ... */) {
    setProgressCursor();
    var props = {
        fname: fname,
        pageid: pageid,
        arg: $.map(cw.utils.sliceList(arguments, 1), JSON.stringify)
    };
    var result = jQuery.ajax({
        url: AJAX_BASE_URL,
        data: props,
        async: false,
        traditional: true
    }).responseText;
    if (result) {
        result = cw.evalJSON(result);
    }
    resetCursor();
    return result;
}

function asyncRemoteExec(fname /* ... */) {
    setProgressCursor();
    var props = {
        fname: fname,
        pageid: pageid,
        arg: $.map(cw.utils.sliceList(arguments, 1), JSON.stringify)
    };
    // XXX we should inline the content of loadRemote here
    var deferred = loadRemote(AJAX_BASE_URL, props, 'POST');
    deferred = deferred.addErrback(remoteCallFailed);
    deferred = deferred.addErrback(resetCursor);
    deferred = deferred.addCallback(resetCursor);
    return deferred;
}

jQuery(document).ready(function() {
    _loadDynamicFragments();
    // build loaded_scripts / loaded_links lists
    cw.loaded_scripts = [];
    jQuery('head script[src]').each(function(i) {
        cw.utils.extend(cw.loaded_scripts, cw.ajax._listResources(this.getAttribute('src')));
    });
    cw.loaded_links = [];
    jQuery('head link[href]').each(function(i) {
        cw.utils.extend(cw.loaded_links, cw.ajax._listResources(this.getAttribute('href')));
    });
});
