/* toggle visibility of an element by its id
 * & set current visibility status in a cookie
 * XXX whenever used outside of preferences, don't forget to
 *     move me in a more appropriate place
 */

function toggleVisibility(elemId) {
    _clearPreviousMessages();
    jqNode(elemId).toggleClass('hidden');
}

function closeFieldset(fieldsetid){
    var linklabel = _('open all');
    var linkhref = 'javascript:openFieldset("' +fieldsetid + '")'
    _toggleFieldset(fieldsetid, 1, linklabel, linkhref)
}

function openFieldset(fieldsetid){
    var linklabel = _('close all');
    var linkhref = 'javascript:closeFieldset("'+ fieldsetid + '")'
    _toggleFieldset(fieldsetid, 0, linklabel, linkhref)
}


function _toggleFieldset(fieldsetid, closeaction, linklabel, linkhref){
    jQuery('#'+fieldsetid).find('div.openlink').each(function(){
	    var link = A({'href' : "javascript:noop();",
			  'onclick' : linkhref},
			  linklabel)
	    jQuery(this).empty().append(link);
	});
    jQuery('#'+fieldsetid).find('fieldset[id]').each(function(){
	    var fieldset = jQuery(this);
	    if(closeaction){
		fieldset.addClass('hidden')
	    }else{
		fieldset.removeClass('hidden');
		linkLabel = (_('open all'));
	    }
	});
 
}

function validatePrefsForm(formid){
    var form = getNode(formid);
    freezeFormButtons(formid);
    try {
	var d = _sendForm(formid, null);
    } catch (ex) {
	log('got exception', ex);
	return false;
    }
    function _callback(result, req) {
	_clearPreviousMessages();
	_clearPreviousErrors(formid);
	// success
	if(result[0]){
	    return submitSucces(formid)
	}
 	// Failures
	unfreezeFormButtons(formid);
	var descr = result[1];
        if (!isArrayLike(descr) || descr.length != 2) {
	   log('got strange error :', descr);
	   updateMessage(descr);
	   return ;
	}
        _displayValidationerrors(formid, descr[0], descr[1]);
	var dom = DIV({'class':'critical'},
		      _("please correct errors below"));
	jQuery(form).find('div.formsg').empty().append(dom);
	updateMessage(_(""));
	return false;
    }
    d.addCallback(_callback);
    return false;
}

function submitSucces(formid){
    var form = jQuery('#'+formid);
    setCurrentValues(form);
    var dom = DIV({'class':'message'},
		  _("changes applied"));
    jQuery(form).find('div.formsg').empty().append(dom);
    jQuery(form).find('input').removeClass('changed');
    checkValues(form, true);
    return;
}

function _clearPreviousMessages() {
    jQuery('div#appMsg').addClass('hidden');
    jQuery('div.formsg').empty();
}

function _clearPreviousErrors(formid) {
    jQuery('#' + formid + ' span.error').remove();
}


function checkValues(form, success){
    var unfreezeButtons = false;
    jQuery(form).find('select').each(function () { 
	    unfreezeButtons = _checkValue(jQuery(this), unfreezeButtons);
	});
    jQuery(form).find('[type=text]').each(function () {
	    unfreezeButtons = _checkValue(jQuery(this), unfreezeButtons);
	});
    jQuery(form).find('input[type=radio]').each(function () { 
	    if (jQuery(this).attr('checked')){
		unfreezeButtons = _checkValue(jQuery(this), unfreezeButtons);
	    }
     }); 
   
    if (unfreezeButtons){
	unfreezeFormButtons(form.attr('id'));
    }else{
	if (!success){
	    _clearPreviousMessages();
	}
	_clearPreviousErrors(form.attr('id'));
	freezeFormButtons(form.attr('id'));
    }
}

function _checkValue(input, unfreezeButtons){
     var currentValueInput = jQuery("input[id=current-" + input.attr('name') + "]");
     if (currentValueInput.attr('value') != input.attr('value')){
	 input.addClass('changed');
	 unfreezeButtons = true;
     }else{
	 input.removeClass('changed');
	 jQuery("span[id=err-" + input.attr('id') + "]").remove();
     }	
     input.removeClass('error');
     return unfreezeButtons
}


function setCurrentValues(form){
    jQuery(form).find('input[id^=current-value]').each(function () { 
	    var currentValueInput = jQuery(this);
	    var name = currentValueInput.attr('id').split('-')[1];
	    jQuery(form).find("[name=" + name + "]").each(function (){
		    var input = jQuery(this);
		    if(input.attr('type')=='radio'){
			if(input.attr('checked')){
			    log(input.attr('value'));
			    currentValueInput.attr('value', input.attr('value'));
			}
		    }else{
			currentValueInput.attr('value', input.attr('value'));
		    }
		});
    });
}


function initEvents(){
  jQuery('form').each(function() { 
	  var form = jQuery(this);
	  freezeFormButtons(form.attr('id'));
	  form.find('input[type=text]').keyup(function(){  
		  checkValues(form);	   
          });
	  form.find('input[type=radio]').change(function(){  
		  checkValues(form);	   
          });
	  form.find('select').change(function(){  
		  checkValues(form);	 
          });
    });
}

$(document).ready(function() {
	initEvents();
});

