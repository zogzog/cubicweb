
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
