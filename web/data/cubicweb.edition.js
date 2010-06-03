/**
 * Functions dedicated to edition.
 *
 *  :organization: Logilab
 *  :copyright: 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 */

CubicWeb.require('python.js');
CubicWeb.require('htmlhelpers.js');
CubicWeb.require('ajax.js');

//============= Eproperty form functions =====================================//
/**
 * .. function:: setPropValueWidget(varname, tabindex)
 *
 * called on Eproperty key selection:
 * - get the selected value
 * - get a widget according to the key by a sync query to the server
 * - fill associated div with the returned html
 *
 * * `varname`, the name of the variable as used in the original creation form
 * * `tabindex`, the tabindex that should be set on the widget
 */
function setPropValueWidget(varname, tabindex) {
    var key = firstSelected(document.getElementById('pkey:' + varname));
    if (key) {
        var args = {
            fname: 'prop_widget',
            pageid: pageid,
            arg: map(jQuery.toJSON, [key, varname, tabindex])
        };
        jqNode('div:value:' + varname).loadxhtml(JSON_BASE_URL, args, 'post');
    }
}

// *** EDITION FUNCTIONS ****************************************** //
/**
 * .. function:: reorderTabindex(start, formid)
 *
 * this function is called when an AJAX form was generated to
 * make sure tabindex remains consistent
 */
function reorderTabindex(start, formid) {
    var form = getNode(formid || 'entityForm');
    var inputTypes = ['INPUT', 'SELECT', 'TEXTAREA'];
    var tabindex = (start == null) ? 15: start;
    nodeWalkDepthFirst(form, function(elem) {
        var tagName = elem.tagName.toUpperCase();
        if (inputTypes.contains(tagName)) {
            if (jQuery(elem).attr('tabindex') != null) {
                tabindex += 1;
		jQuery(elem).attr('tabindex', tabindex);
            }
            return null;
        }
        return jQuery.grep(elem.childNodes, isElementNode);
    });
}

function showMatchingSelect(selectedValue, eid) {
    if (selectedValue) {
        divId = 'div' + selectedValue + '_' + eid;
        var divNode = jQuery('#' + divId);
        if (!divNode.length) {
            var args = {
                vid: 'unrelateddivs',
                relation: selectedValue,
                rql: rql_for_eid(eid),
                '__notemplate': 1,
                callback: function() {
                    _showMatchingSelect(eid, jQuery('#' + divId));
                }
            };
            jQuery('#unrelatedDivs_' + eid).loadxhtml(baseuri() + 'view', args, 'post', 'append');
        } else {
            _showMatchingSelect(eid, divNode);
        }
    } else {
        _showMatchingSelect(eid, null);
    }
}

/**
 * .. function:: _showMatchingSelect(eid, divNode)
 *
 * * `divNode`, a jQuery selection
 */
function _showMatchingSelect(eid, divNode) {
    // hide all divs, and then show the matching one
    // (would actually be better to directly hide the displayed one)
    jQuery('#unrelatedDivs_' + eid).children().hide();
    // divNode not found means 'no relation selected' (i.e. first blank item)
    if (divNode && divNode.length) {
        divNode.show();
    }
}

/**
 * .. function:: buildPendingInsertHandle(elementId, element_name, selectNodeId, eid)
 *
 * this function builds a Handle to cancel pending insertion
 */
function buildPendingInsertHandle(elementId, element_name, selectNodeId, eid) {
    jscall = "javascript: cancelPendingInsert('" + [elementId, element_name, selectNodeId, eid].join("', '") + "')";
    return A({
        'class': 'handle',
        'href': jscall,
        'title': _("cancel this insert")
    },
    '[x]');
}

function buildEntityLine(relationName, selectedOptionNode, comboId, eid) {
    // textContent doesn't seem to work on selectedOptionNode
    var content = selectedOptionNode.firstChild.nodeValue;
    var handle = buildPendingInsertHandle(selectedOptionNode.id, 'tr', comboId, eid);
    var link = A({
        'href': 'view?rql=' + selectedOptionNode.value,
        'class': 'editionPending',
        'id': 'a' + selectedOptionNode.id
    },
    content);
    var tr = TR({
        'id': 'tr' + selectedOptionNode.id
    },
    [TH(null, relationName), TD(null, [handle, link])]);
    try {
        var separator = getNode('relationSelectorRow_' + eid);
        //dump('relationSelectorRow_' + eid) XXX warn dump is not implemented in konqueror (at least)
        // XXX Warning: separator.parentNode is not (always ?) the
        // table itself, but an intermediate node (TableSectionElement)
        var tableBody = separator.parentNode;
        tableBody.insertBefore(tr, separator);
    } catch(ex) {
        log("got exception(2)!" + ex);
    }
}

function buildEntityCell(relationName, selectedOptionNode, comboId, eid) {
    var handle = buildPendingInsertHandle(selectedOptionNode.id, 'div_insert_', comboId, eid);
    var link = A({
        'href': 'view?rql=' + selectedOptionNode.value,
        'class': 'editionPending',
        'id': 'a' + selectedOptionNode.id
    },
    content);
    var div = DIV({
        'id': 'div_insert_' + selectedOptionNode.id
    },
    [handle, link]);
    try {
        var td = jQuery('#cell' + relationName + '_' + eid);
        td.appendChild(div);
    } catch(ex) {
        alert("got exception(3)!" + ex);
    }
}

function addPendingInsert(optionNode, eid, cell, relname) {
    var value = jQuery(optionNode).attr('value');
    if (!value) {
        // occurs when the first element in the box is selected (which is not
        // an entity but the combobox title)
        return;
    }
    // 2nd special case
    if (value.indexOf('http') == 0) {
        document.location = value;
        return;
    }
    // add hidden parameter
    var entityForm = jQuery('#entityForm');
    var oid = optionNode.id.substring(2); // option id is prefixed by "id"
    remoteExec('add_pending_inserts', [oid.split(':')]);
    var selectNode = optionNode.parentNode;
    // remove option node
    selectNode.removeChild(optionNode);
    // add line in table
    if (cell) {
        // new relation as a cell in multiple edit
        // var relation_name = relationSelected.getAttribute('value');
        // relation_name = relation_name.slice(0, relation_name.lastIndexOf('_'));
        buildEntityCell(relname, optionNode, selectNode.id, eid);
    }
    else {
        var relationSelector = getNode('relationSelector_' + eid);
        var relationSelected = relationSelector.options[relationSelector.selectedIndex];
        // new relation as a line in simple edit
        buildEntityLine(relationSelected.text, optionNode, selectNode.id, eid);
    }
}

function cancelPendingInsert(elementId, element_name, comboId, eid) {
    // remove matching insert element
    var entityView = jqNode('a' + elementId).text();
    jqNode(element_name + elementId).remove();
    if (comboId) {
        // re-insert option in combobox if it was taken from there
        var selectNode = getNode(comboId);
        // XXX what on object relation
        if (selectNode) {
            var options = selectNode.options;
            var node_id = elementId.substring(0, elementId.indexOf(':'));
            options[options.length] = OPTION({
                'id': elementId,
                'value': node_id
            },
            entityView);
        }
    }
    elementId = elementId.substring(2, elementId.length);
    remoteExec('remove_pending_insert', elementId.split(':'));
}

/**
 * .. function:: buildPendingDeleteHandle(elementId, eid)
 *
 * this function builds a Handle to cancel pending insertion
 */
function buildPendingDeleteHandle(elementId, eid) {
    var jscall = "javascript: addPendingDelete('" + elementId + ', ' + eid + "');";
    return A({
        'href': jscall,
        'class': 'pendingDeleteHandle',
        'title': _("delete this relation")
    },
    '[x]');
}

/**
 * .. function:: addPendingDelete(nodeId, eid)
 *
 * * `nodeId`, eid_from:r_type:eid_to
 */
function addPendingDelete(nodeId, eid) {
    var d = loadRemote('json', ajaxFuncArgs('add_pending_delete', null, nodeId.split(':')));
    d.addCallback(function() {
        // and strike entity view
        jqNode('span' + nodeId).addClass('pendingDelete');
        // replace handle text
        jqNode('handle' + nodeId).text('+');
    });
}

/**
 * .. function:: cancelPendingDelete(nodeId, eid)
 *
 * * `nodeId`, eid_from:r_type:eid_to
 */
function cancelPendingDelete(nodeId, eid) {
    var d = loadRemote('json', ajaxFuncArgs('remove_pending_delete', null, nodeId.split(':')));
    d.addCallback(function() {
        // reset link's CSS class
        jqNode('span' + nodeId).removeClass('pendingDelete');
        // replace handle text
        jqNode('handle' + nodeId).text('x');
    });
}

/**
 * .. function:: togglePendingDelete(nodeId, eid)
 *
 * * `nodeId`, eid_from:r_type:eid_to
 */
function togglePendingDelete(nodeId, eid) {
    // node found means we should cancel deletion
    if (jQuery.className.has(getNode('span' + nodeId), 'pendingDelete')) {
        cancelPendingDelete(nodeId, eid);
    } else {
        addPendingDelete(nodeId, eid);
    }
}

function selectForAssociation(tripletIdsString, originalEid) {
    var tripletlist = map(function(x) {
        return x.split(':');
    },
    tripletIdsString.split('-'));
    var d = loadRemote('json', ajaxFuncArgs('add_pending_inserts', null, tripletlist));
    d.addCallback(function() {
        var args = {
            vid: 'edition',
            __mode: 'normal',
            rql: rql_for_eid(originalEid)
        };
        document.location = 'view?' + asURL(args);
    });

}

function updateInlinedEntitiesCounters(rtype, role) {
    jQuery('div.inline-' + rtype + '-' + role + '-slot span.icounter').each(function(i) {
        this.innerHTML = i + 1;
    });
}

/**
 * .. function:: addInlineCreationForm(peid, petype, ttype, rtype, role, i18nctx, insertBefore)
 *
 * makes an AJAX request to get an inline-creation view's content
 * * `peid`, the parent entity eid
 *
 * * `petype`, the parent entity type
 *
 * * `ttype`, the target (inlined) entity type
 *
 * * `rtype`, the relation type between both entities
 */
function addInlineCreationForm(peid, petype, ttype, rtype, role, i18nctx, insertBefore) {
    insertBefore = insertBefore || getNode('add' + rtype + ':' + peid + 'link').parentNode;
    var args = ajaxFuncArgs('inline_creation_form', null, peid, petype, ttype, rtype, role, i18nctx);
    var d = loadRemote('json', args);
    d.addCallback(function(response) {
        var dom = getDomFromResponse(response);
        preprocessAjaxLoad(null, dom);
        var form = jQuery(dom);
        form.css('display', 'none');
        form.insertBefore(insertBefore).slideDown('fast');
        updateInlinedEntitiesCounters(rtype, role);
        reorderTabindex(null, $(insertBefore).closest('form')[0]);
        jQuery(CubicWeb).trigger('inlinedform-added', form);
        // if the inlined form contains a file input, we must force
        // the form enctype to multipart/form-data
        if (form.find('input:file').length) {
            // NOTE: IE doesn't support dynamic enctype modification, we have
            //       to set encoding too.
            form.closest('form').attr('enctype', 'multipart/form-data').attr('encoding', 'multipart/form-data');
        }
        postAjaxLoad(dom);
    });
    d.addErrback(function(xxx) {
        log('xxx =', xxx);
    });
}

/**
 * .. function:: removeInlineForm(peid, rtype, role, eid, showaddnewlink)
 *
 * removes the part of the form used to edit an inlined entity
 */
function removeInlineForm(peid, rtype, role, eid, showaddnewlink) {
    jqNode(['div', peid, rtype, eid].join('-')).slideUp('fast', function() {
        $(this).remove();
        updateInlinedEntitiesCounters(rtype, role);
    });
    if (showaddnewlink) {
        toggleVisibility(showaddnewlink);
    }
}

/**
 * .. function:: removeInlinedEntity(peid, rtype, eid)
 *
 * alternatively adds or removes the hidden input that make the
 * edition of the relation `rtype` possible between `peid` and `eid`
 * * `peid`, the parent entity eid
 *
 * * `rtype`, the relation type between both entities
 *
 * * `eid`, the inlined entity eid
 */
function removeInlinedEntity(peid, rtype, eid) {
    // XXX work around the eid_param thing (eid + ':' + eid) for #471746
    var nodeid = ['rel', peid, rtype, eid + ':' + eid].join('-');
    var node = jqNode(nodeid);
    if (!node.attr('cubicweb:type')) {
        node.attr('cubicweb:type', node.val());
        node.val('');
        var divid = ['div', peid, rtype, eid].join('-');
        jqNode(divid).fadeTo('fast', 0.5);
        var noticeid = ['notice', peid, rtype, eid].join('-');
        jqNode(noticeid).fadeIn('fast');
    }
}

function restoreInlinedEntity(peid, rtype, eid) {
    // XXX work around the eid_param thing (eid + ':' + eid) for #471746
    var nodeid = ['rel', peid, rtype, eid + ':' + eid].join('-');
    var node = jqNode(nodeid);
    if (node.attr('cubicweb:type')) {
        node.val(node.attr('cubicweb:type'));
        node.attr('cubicweb:type', '');
        jqNode(['fs', peid, rtype, eid].join('-')).append(node);
        var divid = ['div', peid, rtype, eid].join('-');
        jqNode(divid).fadeTo('fast', 1);
        var noticeid = ['notice', peid, rtype, eid].join('-');
        jqNode(noticeid).hide();
    }
}

function _clearPreviousErrors(formid) {
    // on some case (eg max request size exceeded, we don't know the formid
    if (formid) {
        jQuery('#' + formid + 'ErrorMessage').remove();
        jQuery('#' + formid + ' span.errorMsg').remove();
        jQuery('#' + formid + ' .error').removeClass('error');
    } else {
        jQuery('span.errorMsg').remove();
        jQuery('.error').removeClass('error');
    }
}

function _displayValidationerrors(formid, eid, errors) {
    var globalerrors = [];
    var firsterrfield = null;
    for (fieldname in errors) {
        var errmsg = errors[fieldname];
        if (!fieldname) {
            globalerrors.push(errmsg);
        } else {
            var fieldid = fieldname + ':' + eid;
            var suffixes = ['', '-subject', '-object'];
            var found = false;
            // XXX remove suffixes at some point
            for (var i = 0, length = suffixes.length; i < length; i++) {
                var field = jqNode(fieldname + suffixes[i] + ':' + eid);
                if (field && jQuery(field).attr('type') != 'hidden') {
                    if (!firsterrfield) {
                        firsterrfield = 'err-' + fieldid;
                    }
                    jQuery(field).addClass('error');
                    var span = SPAN({
                        'id': 'err-' + fieldid,
                        'class': "errorMsg"
                    },
                    errmsg);
                    field.before(span);
                    found = true;
                    break;
                }
            }
            if (!found) {
                firsterrfield = formid;
                globalerrors.push(_(fieldname) + ' : ' + errmsg);
            }
        }
    }
    if (globalerrors.length) {
        if (globalerrors.length == 1) {
            var innernode = SPAN(null, globalerrors[0]);
        } else {
            var innernode = UL(null, map(partial(LI, null), globalerrors));
        }
        // insert DIV and innernode before the form
        var div = DIV({
            'class': "errorMessage",
            'id': formid + 'ErrorMessage'
        });
        div.appendChild(innernode);
        jQuery('#' + formid).before(div);
    }
    return firsterrfield || formid;
}

function handleFormValidationResponse(formid, onsuccess, onfailure, result, cbargs) {
    // Success
    if (result[0]) {
        if (onsuccess) {
            onsuccess(result, formid, cbargs);
        } else {
            document.location.href = result[1];
        }
        return true;
    }
    if (onfailure && ! onfailure(result, formid, cbargs)) {
        return false;
    }
    unfreezeFormButtons(formid);
    // Failures
    _clearPreviousErrors(formid);
    var descr = result[1];
    // Unknown structure
    if (!isArrayLike(descr) || descr.length != 2) {
        updateMessage(descr);
        return false;
    }
    _displayValidationerrors(formid, descr[0], descr[1]);
    updateMessage(_('please correct errors below'));
    // ensure the browser does not scroll down
    document.location.hash = '#header';
    return false;
}

/**
 * .. function:: unfreezeFormButtons(formid)
 *
 * unfreeze form buttons when the validation process is over
 */
function unfreezeFormButtons(formid) {
    jQuery('#progress').hide();
    // on some case (eg max request size exceeded, we don't know the formid
    if (formid) {
        jQuery('#' + formid + ' .validateButton').removeAttr('disabled');
    } else {
        jQuery('.validateButton').removeAttr('disabled');
    }
    return true;
}

/**
 * .. function:: freezeFormButtons(formid)
 *
 * disable form buttons while the validation is being done
 */
function freezeFormButtons(formid) {
    jQuery('#progress').show();
    jQuery('#' + formid + ' .validateButton').attr('disabled', 'disabled');
    return true;
}

/**
 * .. function:: postForm(bname, bvalue, formid)
 *
 * used by additional submit buttons to remember which button was clicked
 */
function postForm(bname, bvalue, formid) {
    var form = getNode(formid);
    if (bname) {
        var child = form.appendChild(INPUT({
            type: 'hidden',
            name: bname,
            value: bvalue
        }));
    }
    var onsubmit = form.onsubmit;
    if (!onsubmit || (onsubmit && onsubmit())) {
        form.submit();
    }
    if (bname) {
        jQuery(child).remove();
        /* cleanup */
    }
}

/**
 * .. function:: setFormsTarget(node)
 *
 * called on load to set target and iframeso object.
 *
 * .. note::
 *
 *    this is a hack to make the XHTML compliant.
 *
 * .. note::
 *
 *   `object` nodes might be a potential replacement for iframes
 *
 * .. note::
 *
 *    there is a XHTML module allowing iframe elements but there
 *    is still the problem of the form's `target` attribute
 */
function setFormsTarget(node) {
    var $node = jQuery(node || document.body);
    $node.find('form').each(function() {
        var form = jQuery(this);
        var target = form.attr('cubicweb:target');
        if (target) {
            form.attr('target', target);
            /* do not use display: none because some browsers ignore iframe
             * with no display */
            form.append(IFRAME({
                name: target,
                id: target,
                src: 'javascript: void(0)',
                width: '0px',
                height: '0px'
            }));
        }
    });
}

jQuery(document).ready(function() {
    setFormsTarget();
});

/**
 * .. function:: validateForm(formid, action, onsuccess, onfailure)
 *
 * called on traditionnal form submission : the idea is to try
 * to post the form. If the post is successful, `validateForm` redirects
 * to the appropriate URL. Otherwise, the validation errors are displayed
 * around the corresponding input fields.
 */
function validateForm(formid, action, onsuccess, onfailure) {
    try {
        var zipped = formContents(formid);
        var args = ajaxFuncArgs('validate_form', null, action, zipped[0], zipped[1]);
        var d = loadRemote('json', args);
    } catch(ex) {
        log('got exception', ex);
        return false;
    }
    function _callback(result, req) {
        handleFormValidationResponse(formid, onsuccess, onfailure, result);
    }
    d.addCallback(_callback);
    return false;
}


/**
 * .. function:: inlineValidateRelationFormOptions(rtype, eid, divid, options)
 *
 * called by reledit forms to submit changes
 * * `rtype`, the attribute being edited
 *
 * * `eid`, the eid of the entity being edited
 *
 * * `options`, a dictionnary of options used by the form validation handler such
 *    as ``role``, ``onsuccess``, ``onfailure``, ``reload``, ``vid``, ``lzone``
 *    and ``default_value``:
 *
 *     * `onsucess`, javascript function to execute on success, default is noop
 *
 *     * `onfailure`, javascript function to execute on failure, default is noop
 *
 *     * `default_value`, value if the field is empty
 *
 *     * `lzone`, html fragment (string) for a clic-zone triggering actual edition
 */
function inlineValidateRelationFormOptions(rtype, eid, divid, options) {
    try {
        var form = getNode(divid + '-form');
        var relname = rtype + ':' + eid;
        var newtarget = jQuery('[name=' + relname + ']').val();
        var zipped = cw.utils.formContents(form);
        var args = ajaxFuncArgs('validate_form', null, 'apply', zipped[0], zipped[1]);
        var d = loadRemote(JSON_BASE_URL, args, 'POST')
    } catch(ex) {
        return false;
    }
    d.addCallback(function(result, req) {
        execFormValidationResponse(rtype, eid, divid, options, result);
    });
    return false;
}

function execFormValidationResponse(rtype, eid, divid, options, result) {
    options = $.extend({onsuccess: noop,
                        onfailure: noop
                       }, options);
    if (handleFormValidationResponse(divid + '-form', options.onsucess , options.onfailure, result)) {
        if (options.reload) {
            document.location.reload();
        } else {
            var args = {
                fname: 'reledit_form',
                rtype: rtype,
                role: options.role,
                eid: eid,
                divid: divid,
                reload: options.reload,
                vid: options.vid,
                default_value: options.default_value,
                landing_zone: options.lzone
            };
            jQuery('#' + divid + '-reledit').parent().loadxhtml(JSON_BASE_URL, args, 'post');
        }
    }

}


/**
 * .. function:: loadInlineEditionFormOptions(eid, rtype, divid, options)
 *
 * inline edition
 */
function loadInlineEditionFormOptions(eid, rtype, divid, options) {
    var args = {
        fname: 'reledit_form',
        rtype: rtype,
        role: options.role,
        eid: eid,
        divid: divid,
        reload: options.reload,
        vid: options.vid,
        default_value: options.default_value,
        landing_zone: options.lzone,
        callback: function() {
            showInlineEditionForm(eid, rtype, divid);
        }
    };
    jQuery('#' + divid + '-reledit').parent().loadxhtml(JSON_BASE_URL, args, 'post');
}
function showInlineEditionForm(eid, rtype, divid) {
    jQuery('#' + divid).hide();
    jQuery('#' + divid + '-value').hide();
    jQuery('#' + divid + '-form').show();
}

function hideInlineEdit(eid, rtype, divid) {
    jQuery('#appMsg').hide();
    jQuery('div.errorMessage').remove();
    jQuery('#' + divid).show();
    jQuery('#' + divid + '-value').show();
    jQuery('#' + divid + '-form').hide();
}

CubicWeb.provide('edition.js');

// ======================= DEPRECATED FUNCTIONS ========================= //
inlineValidateRelationForm = cw.utils.deprecatedFunction(
    '[3.9] inlineValidateRelationForm() function is deprecated, use inlineValidateRelationFormOptions instead',
    function(rtype, role, eid, divid, reload, vid, default_value, lzone, onsucess, onfailure) {
        try {
            var form = getNode(divid + '-form');
            var relname = rtype + ':' + eid;
            var newtarget = jQuery('[name=' + relname + ']').val();
            var zipped = formContents(form);
            var d = asyncRemoteExec('validate_form', 'apply', zipped[0], zipped[1]);
        } catch(ex) {
            return false;
        }
        d.addCallback(function(result, req) {
        var options = {role : role,
                       reload: reload,
                       vid: vid,
                       default_value: default_value,
                       lzone: lzone,
                       onsucess: onsucess || $.noop,
                       onfailure: onfailure || $.noop
                      };
            execFormValidationResponse(rtype, eid, divid, options);
        });
        return false;
    }
);

loadInlineEditionForm = cw.utils.deprecatedFunction(
    '[3.9] loadInlineEditionForm() function is deprecated, use loadInlineEditionFormOptions instead',
    function(eid, rtype, role, divid, reload, vid, default_value, lzone) {
        var args = {
            fname: 'reledit_form',
            rtype: rtype,
            role: role,
            eid: eid,
            divid: divid,
            reload: reload,
            vid: vid,
            default_value: default_value,
            landing_zone: lzone,
            callback: function() {
                showInlineEditionForm(eid, rtype, divid);
            }
        };
        jQuery('#' + divid + '-reledit').parent().loadxhtml(JSON_BASE_URL, args, 'post');
    }
);
