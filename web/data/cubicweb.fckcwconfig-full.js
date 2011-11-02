// cf /usr/share/fckeditor/fckconfig.js

FCKConfig.AutoDetectLanguage = false ;

FCKConfig.ToolbarSets["Default"] = [
    // removed : 'Save','NewPage','DocProps','-','Templates','-','Preview'
        ['Source'],
    // removed: 'Print','-','SpellCheck'
        ['Cut','Copy','Paste','PasteText','PasteWord'],
        ['Undo','Redo','-','Find','Replace','-','SelectAll','RemoveFormat'],
    //['Form','Checkbox','Radio','TextField','Textarea','Select','Button','ImageButton','HiddenField'],
        '/',
    // ,'StrikeThrough','-','Subscript','Superscript'
        ['Bold','Italic','Underline'],
    // ,'-','Outdent','Indent','Blockquote'
        ['OrderedList','UnorderedList'],
    // ['JustifyLeft','JustifyCenter','JustifyRight','JustifyFull'],
        ['Link','Unlink','Anchor'],
    // removed : 'Image','Flash','Smiley','PageBreak'
        ['Table','Rule','SpecialChar']
    // , '/',
    // ['Style','FontFormat','FontName','FontSize'],
    // ['TextColor','BGColor'],
    //,'ShowBlocks'
    // ['FitWindow','-','About']                // No comma for the last row.
] ;

// 'Flash','Select','Textarea','Checkbox','Radio','TextField','HiddenField','ImageButton','Button','Form',
FCKConfig.ContextMenu = ['Generic','Link','Anchor','Image','BulletedList','NumberedList','Table'] ;

FCKConfig.LinkUpload = false ;
FCKConfig.LinkBrowser = false ;
FCKConfig.ImageUpload = false ;
FCKConfig.ImageBrowser = false ;
FCKConfig.FlashUpload = false ;
FCKConfig.FlashBrowser = false ;

