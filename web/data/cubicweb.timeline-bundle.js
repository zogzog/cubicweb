
var SimileAjax = {
    loaded:                 false,
    loadingScriptsCount:    0,
    error:                  null,
    params:                 { bundle:"true" }
};


/**
 * Parse out the query parameters from a URL
 * @param {String} url    the url to parse, or location.href if undefined
 * @param {Object} to     optional object to extend with the parameters
 * @param {Object} types  optional object mapping keys to value types
 *        (String, Number, Boolean or Array, String by default)
 * @return a key/value Object whose keys are the query parameter names
 * @type Object
 */
SimileAjax.parseURLParameters = function(url, to, types) {
    to = to || {};
    types = types || {};

    if (typeof url == "undefined") {
        url = location.href;
    }
    var q = url.indexOf("?");
    if (q < 0) {
        return to;
    }
    url = (url+"#").slice(q+1, url.indexOf("#")); // toss the URL fragment

    var params = url.split("&"), param, parsed = {};
    var decode = window.decodeURIComponent || unescape;
    for (var i = 0; param = params[i]; i++) {
        var eq = param.indexOf("=");
        var name = decode(param.slice(0,eq));
        var old = parsed[name];
        if (typeof old == "undefined") {
            old = [];
        } else if (!(old instanceof Array)) {
            old = [old];
        }
        parsed[name] = old.concat(decode(param.slice(eq+1)));
    }
    for (var i in parsed) {
        if (!parsed.hasOwnProperty(i)) continue;
        var type = types[i] || String;
        var data = parsed[i];
        if (!(data instanceof Array)) {
            data = [data];
        }
        if (type === Boolean && data[0] == "false") {
            to[i] = false; // because Boolean("false") === true
        } else {
            to[i] = type.apply(this, data);
        }
    }
    return to;
};


SimileAjax.Platform = new Object();

SimileAjax.urlPrefix = baseuri();

/* jquery-1.2.6.js */
(function(){var _jQuery=window.jQuery,_$=window.$;
var jQuery=window.jQuery=window.$=function(selector,context){return new jQuery.fn.init(selector,context);
};
var quickExpr=/^[^<]*(<(.|\s)+>)[^>]*$|^#(\w+)$/,isSimple=/^.[^:#\[\.]*$/,undefined;
jQuery.fn=jQuery.prototype={init:function(selector,context){selector=selector||document;
if(selector.nodeType){this[0]=selector;
this.length=1;
return this;
}if(typeof selector=="string"){var match=quickExpr.exec(selector);
if(match&&(match[1]||!context)){if(match[1]){selector=jQuery.clean([match[1]],context);
}else{var elem=document.getElementById(match[3]);
if(elem){if(elem.id!=match[3]){return jQuery().find(selector);
}return jQuery(elem);
}selector=[];
}}else{return jQuery(context).find(selector);
}}else{if(jQuery.isFunction(selector)){return jQuery(document)[jQuery.fn.ready?"ready":"load"](selector);
}}return this.setArray(jQuery.makeArray(selector));
},jquery:"1.2.6",size:function(){return this.length;
},length:0,get:function(num){return num==undefined?jQuery.makeArray(this):this[num];
},pushStack:function(elems){var ret=jQuery(elems);
ret.prevObject=this;
return ret;
},setArray:function(elems){this.length=0;
Array.prototype.push.apply(this,elems);
return this;
},each:function(callback,args){return jQuery.each(this,callback,args);
},index:function(elem){var ret=-1;
return jQuery.inArray(elem&&elem.jquery?elem[0]:elem,this);
},attr:function(name,value,type){var options=name;
if(name.constructor==String){if(value===undefined){return this[0]&&jQuery[type||"attr"](this[0],name);
}else{options={};
options[name]=value;
}}return this.each(function(i){for(name in options){jQuery.attr(type?this.style:this,name,jQuery.prop(this,options[name],type,i,name));
}});
},css:function(key,value){if((key=="width"||key=="height")&&parseFloat(value)<0){value=undefined;
}return this.attr(key,value,"curCSS");
},text:function(text){if(typeof text!="object"&&text!=null){return this.empty().append((this[0]&&this[0].ownerDocument||document).createTextNode(text));
}var ret="";
jQuery.each(text||this,function(){jQuery.each(this.childNodes,function(){if(this.nodeType!=8){ret+=this.nodeType!=1?this.nodeValue:jQuery.fn.text([this]);
}});
});
return ret;
},wrapAll:function(html){if(this[0]){jQuery(html,this[0].ownerDocument).clone().insertBefore(this[0]).map(function(){var elem=this;
while(elem.firstChild){elem=elem.firstChild;
}return elem;
}).append(this);
}return this;
},wrapInner:function(html){return this.each(function(){jQuery(this).contents().wrapAll(html);
});
},wrap:function(html){return this.each(function(){jQuery(this).wrapAll(html);
});
},append:function(){return this.domManip(arguments,true,false,function(elem){if(this.nodeType==1){this.appendChild(elem);
}});
},prepend:function(){return this.domManip(arguments,true,true,function(elem){if(this.nodeType==1){this.insertBefore(elem,this.firstChild);
}});
},before:function(){return this.domManip(arguments,false,false,function(elem){this.parentNode.insertBefore(elem,this);
});
},after:function(){return this.domManip(arguments,false,true,function(elem){this.parentNode.insertBefore(elem,this.nextSibling);
});
},end:function(){return this.prevObject||jQuery([]);
},find:function(selector){var elems=jQuery.map(this,function(elem){return jQuery.find(selector,elem);
});
return this.pushStack(/[^+>] [^+>]/.test(selector)||selector.indexOf("..")>-1?jQuery.unique(elems):elems);
},clone:function(events){var ret=this.map(function(){if(jQuery.browser.msie&&!jQuery.isXMLDoc(this)){var clone=this.cloneNode(true),container=document.createElement("div");
container.appendChild(clone);
return jQuery.clean([container.innerHTML])[0];
}else{return this.cloneNode(true);
}});
var clone=ret.find("*").andSelf().each(function(){if(this[expando]!=undefined){this[expando]=null;
}});
if(events===true){this.find("*").andSelf().each(function(i){if(this.nodeType==3){return ;
}var events=jQuery.data(this,"events");
for(var type in events){for(var handler in events[type]){jQuery.event.add(clone[i],type,events[type][handler],events[type][handler].data);
}}});
}return ret;
},filter:function(selector){return this.pushStack(jQuery.isFunction(selector)&&jQuery.grep(this,function(elem,i){return selector.call(elem,i);
})||jQuery.multiFilter(selector,this));
},not:function(selector){if(selector.constructor==String){if(isSimple.test(selector)){return this.pushStack(jQuery.multiFilter(selector,this,true));
}else{selector=jQuery.multiFilter(selector,this);
}}var isArrayLike=selector.length&&selector[selector.length-1]!==undefined&&!selector.nodeType;
return this.filter(function(){return isArrayLike?jQuery.inArray(this,selector)<0:this!=selector;
});
},add:function(selector){return this.pushStack(jQuery.unique(jQuery.merge(this.get(),typeof selector=="string"?jQuery(selector):jQuery.makeArray(selector))));
},is:function(selector){return !!selector&&jQuery.multiFilter(selector,this).length>0;
},hasClass:function(selector){return this.is("."+selector);
},val:function(value){if(value==undefined){if(this.length){var elem=this[0];
if(jQuery.nodeName(elem,"select")){var index=elem.selectedIndex,values=[],options=elem.options,one=elem.type=="select-one";
if(index<0){return null;
}for(var i=one?index:0,max=one?index+1:options.length;
i<max;
i++){var option=options[i];
if(option.selected){value=jQuery.browser.msie&&!option.attributes.value.specified?option.text:option.value;
if(one){return value;
}values.push(value);
}}return values;
}else{return(this[0].value||"").replace(/\r/g,"");
}}return undefined;
}if(value.constructor==Number){value+="";
}return this.each(function(){if(this.nodeType!=1){return ;
}if(value.constructor==Array&&/radio|checkbox/.test(this.type)){this.checked=(jQuery.inArray(this.value,value)>=0||jQuery.inArray(this.name,value)>=0);
}else{if(jQuery.nodeName(this,"select")){var values=jQuery.makeArray(value);
jQuery("option",this).each(function(){this.selected=(jQuery.inArray(this.value,values)>=0||jQuery.inArray(this.text,values)>=0);
});
if(!values.length){this.selectedIndex=-1;
}}else{this.value=value;
}}});
},html:function(value){return value==undefined?(this[0]?this[0].innerHTML:null):this.empty().append(value);
},replaceWith:function(value){return this.after(value).remove();
},eq:function(i){return this.slice(i,i+1);
},slice:function(){return this.pushStack(Array.prototype.slice.apply(this,arguments));
},map:function(callback){return this.pushStack(jQuery.map(this,function(elem,i){return callback.call(elem,i,elem);
}));
},andSelf:function(){return this.add(this.prevObject);
},data:function(key,value){var parts=key.split(".");
parts[1]=parts[1]?"."+parts[1]:"";
if(value===undefined){var data=this.triggerHandler("getData"+parts[1]+"!",[parts[0]]);
if(data===undefined&&this.length){data=jQuery.data(this[0],key);
}return data===undefined&&parts[1]?this.data(parts[0]):data;
}else{return this.trigger("setData"+parts[1]+"!",[parts[0],value]).each(function(){jQuery.data(this,key,value);
});
}},removeData:function(key){return this.each(function(){jQuery.removeData(this,key);
});
},domManip:function(args,table,reverse,callback){var clone=this.length>1,elems;
return this.each(function(){if(!elems){elems=jQuery.clean(args,this.ownerDocument);
if(reverse){elems.reverse();
}}var obj=this;
if(table&&jQuery.nodeName(this,"table")&&jQuery.nodeName(elems[0],"tr")){obj=this.getElementsByTagName("tbody")[0]||this.appendChild(this.ownerDocument.createElement("tbody"));
}var scripts=jQuery([]);
jQuery.each(elems,function(){var elem=clone?jQuery(this).clone(true)[0]:this;
if(jQuery.nodeName(elem,"script")){scripts=scripts.add(elem);
}else{if(elem.nodeType==1){scripts=scripts.add(jQuery("script",elem).remove());
}callback.call(obj,elem);
}});
scripts.each(evalScript);
});
}};
jQuery.fn.init.prototype=jQuery.fn;
function evalScript(i,elem){if(elem.src){jQuery.ajax({url:elem.src,async:false,dataType:"script"});
}else{jQuery.globalEval(elem.text||elem.textContent||elem.innerHTML||"");
}if(elem.parentNode){elem.parentNode.removeChild(elem);
}}function now(){return +new Date;
}jQuery.extend=jQuery.fn.extend=function(){var target=arguments[0]||{},i=1,length=arguments.length,deep=false,options;
if(target.constructor==Boolean){deep=target;
target=arguments[1]||{};
i=2;
}if(typeof target!="object"&&typeof target!="function"){target={};
}if(length==i){target=this;
--i;
}for(;
i<length;
i++){if((options=arguments[i])!=null){for(var name in options){var src=target[name],copy=options[name];
if(target===copy){continue;
}if(deep&&copy&&typeof copy=="object"&&!copy.nodeType){target[name]=jQuery.extend(deep,src||(copy.length!=null?[]:{}),copy);
}else{if(copy!==undefined){target[name]=copy;
}}}}}return target;
};
var expando="jQuery"+now(),uuid=0,windowData={},exclude=/z-?index|font-?weight|opacity|zoom|line-?height/i,defaultView=document.defaultView||{};
jQuery.extend({noConflict:function(deep){window.$=_$;
if(deep){window.jQuery=_jQuery;
}return jQuery;
},isFunction:function(fn){return !!fn&&typeof fn!="string"&&!fn.nodeName&&fn.constructor!=Array&&/^[\s[]?function/.test(fn+"");
},isXMLDoc:function(elem){return elem.documentElement&&!elem.body||elem.tagName&&elem.ownerDocument&&!elem.ownerDocument.body;
},globalEval:function(data){data=jQuery.trim(data);
if(data){var head=document.getElementsByTagName("head")[0]||document.documentElement,script=document.createElement("script");
script.type="text/javascript";
if(jQuery.browser.msie){script.text=data;
}else{script.appendChild(document.createTextNode(data));
}head.insertBefore(script,head.firstChild);
head.removeChild(script);
}},nodeName:function(elem,name){return elem.nodeName&&elem.nodeName.toUpperCase()==name.toUpperCase();
},cache:{},data:function(elem,name,data){elem=elem==window?windowData:elem;
var id=elem[expando];
if(!id){id=elem[expando]=++uuid;
}if(name&&!jQuery.cache[id]){jQuery.cache[id]={};
}if(data!==undefined){jQuery.cache[id][name]=data;
}return name?jQuery.cache[id][name]:id;
},removeData:function(elem,name){elem=elem==window?windowData:elem;
var id=elem[expando];
if(name){if(jQuery.cache[id]){delete jQuery.cache[id][name];
name="";
for(name in jQuery.cache[id]){break;
}if(!name){jQuery.removeData(elem);
}}}else{try{delete elem[expando];
}catch(e){if(elem.removeAttribute){elem.removeAttribute(expando);
}}delete jQuery.cache[id];
}},each:function(object,callback,args){var name,i=0,length=object.length;
if(args){if(length==undefined){for(name in object){if(callback.apply(object[name],args)===false){break;
}}}else{for(;
i<length;
){if(callback.apply(object[i++],args)===false){break;
}}}}else{if(length==undefined){for(name in object){if(callback.call(object[name],name,object[name])===false){break;
}}}else{for(var value=object[0];
i<length&&callback.call(value,i,value)!==false;
value=object[++i]){}}}return object;
},prop:function(elem,value,type,i,name){if(jQuery.isFunction(value)){value=value.call(elem,i);
}return value&&value.constructor==Number&&type=="curCSS"&&!exclude.test(name)?value+"px":value;
},className:{add:function(elem,classNames){jQuery.each((classNames||"").split(/\s+/),function(i,className){if(elem.nodeType==1&&!jQuery.className.has(elem.className,className)){elem.className+=(elem.className?" ":"")+className;
}});
},remove:function(elem,classNames){if(elem.nodeType==1){elem.className=classNames!=undefined?jQuery.grep(elem.className.split(/\s+/),function(className){return !jQuery.className.has(classNames,className);
}).join(" "):"";
}},has:function(elem,className){return jQuery.inArray(className,(elem.className||elem).toString().split(/\s+/))>-1;
}},swap:function(elem,options,callback){var old={};
for(var name in options){old[name]=elem.style[name];
elem.style[name]=options[name];
}callback.call(elem);
for(var name in options){elem.style[name]=old[name];
}},css:function(elem,name,force){if(name=="width"||name=="height"){var val,props={position:"absolute",visibility:"hidden",display:"block"},which=name=="width"?["Left","Right"]:["Top","Bottom"];
function getWH(){val=name=="width"?elem.offsetWidth:elem.offsetHeight;
var padding=0,border=0;
jQuery.each(which,function(){padding+=parseFloat(jQuery.curCSS(elem,"padding"+this,true))||0;
border+=parseFloat(jQuery.curCSS(elem,"border"+this+"Width",true))||0;
});
val-=Math.round(padding+border);
}if(jQuery(elem).is(":visible")){getWH();
}else{jQuery.swap(elem,props,getWH);
}return Math.max(0,val);
}return jQuery.curCSS(elem,name,force);
},curCSS:function(elem,name,force){var ret,style=elem.style;
function color(elem){if(!jQuery.browser.safari){return false;
}var ret=defaultView.getComputedStyle(elem,null);
return !ret||ret.getPropertyValue("color")=="";
}if(name=="opacity"&&jQuery.browser.msie){ret=jQuery.attr(style,"opacity");
return ret==""?"1":ret;
}if(jQuery.browser.opera&&name=="display"){var save=style.outline;
style.outline="0 solid black";
style.outline=save;
}if(name.match(/float/i)){name=styleFloat;
}if(!force&&style&&style[name]){ret=style[name];
}else{if(defaultView.getComputedStyle){if(name.match(/float/i)){name="float";
}name=name.replace(/([A-Z])/g,"-$1").toLowerCase();
var computedStyle=defaultView.getComputedStyle(elem,null);
if(computedStyle&&!color(elem)){ret=computedStyle.getPropertyValue(name);
}else{var swap=[],stack=[],a=elem,i=0;
for(;
a&&color(a);
a=a.parentNode){stack.unshift(a);
}for(;
i<stack.length;
i++){if(color(stack[i])){swap[i]=stack[i].style.display;
stack[i].style.display="block";
}}ret=name=="display"&&swap[stack.length-1]!=null?"none":(computedStyle&&computedStyle.getPropertyValue(name))||"";
for(i=0;
i<swap.length;
i++){if(swap[i]!=null){stack[i].style.display=swap[i];
}}}if(name=="opacity"&&ret==""){ret="1";
}}else{if(elem.currentStyle){var camelCase=name.replace(/\-(\w)/g,function(all,letter){return letter.toUpperCase();
});
ret=elem.currentStyle[name]||elem.currentStyle[camelCase];
if(!/^\d+(px)?$/i.test(ret)&&/^\d/.test(ret)){var left=style.left,rsLeft=elem.runtimeStyle.left;
elem.runtimeStyle.left=elem.currentStyle.left;
style.left=ret||0;
ret=style.pixelLeft+"px";
style.left=left;
elem.runtimeStyle.left=rsLeft;
}}}}return ret;
},clean:function(elems,context){var ret=[];
context=context||document;
if(typeof context.createElement=="undefined"){context=context.ownerDocument||context[0]&&context[0].ownerDocument||document;
}jQuery.each(elems,function(i,elem){if(!elem){return ;
}if(elem.constructor==Number){elem+="";
}if(typeof elem=="string"){elem=elem.replace(/(<(\w+)[^>]*?)\/>/g,function(all,front,tag){return tag.match(/^(abbr|br|col|img|input|link|meta|param|hr|area|embed)$/i)?all:front+"></"+tag+">";
});
var tags=jQuery.trim(elem).toLowerCase(),div=context.createElement("div");
var wrap=!tags.indexOf("<opt")&&[1,"<select multiple='multiple'>","</select>"]||!tags.indexOf("<leg")&&[1,"<fieldset>","</fieldset>"]||tags.match(/^<(thead|tbody|tfoot|colg|cap)/)&&[1,"<table>","</table>"]||!tags.indexOf("<tr")&&[2,"<table><tbody>","</tbody></table>"]||(!tags.indexOf("<td")||!tags.indexOf("<th"))&&[3,"<table><tbody><tr>","</tr></tbody></table>"]||!tags.indexOf("<col")&&[2,"<table><tbody></tbody><colgroup>","</colgroup></table>"]||jQuery.browser.msie&&[1,"div<div>","</div>"]||[0,"",""];
div.innerHTML=wrap[1]+elem+wrap[2];
while(wrap[0]--){div=div.lastChild;
}if(jQuery.browser.msie){var tbody=!tags.indexOf("<table")&&tags.indexOf("<tbody")<0?div.firstChild&&div.firstChild.childNodes:wrap[1]=="<table>"&&tags.indexOf("<tbody")<0?div.childNodes:[];
for(var j=tbody.length-1;
j>=0;
--j){if(jQuery.nodeName(tbody[j],"tbody")&&!tbody[j].childNodes.length){tbody[j].parentNode.removeChild(tbody[j]);
}}if(/^\s/.test(elem)){div.insertBefore(context.createTextNode(elem.match(/^\s*/)[0]),div.firstChild);
}}elem=jQuery.makeArray(div.childNodes);
}if(elem.length===0&&(!jQuery.nodeName(elem,"form")&&!jQuery.nodeName(elem,"select"))){return ;
}if(elem[0]==undefined||jQuery.nodeName(elem,"form")||elem.options){ret.push(elem);
}else{ret=jQuery.merge(ret,elem);
}});
return ret;
},attr:function(elem,name,value){if(!elem||elem.nodeType==3||elem.nodeType==8){return undefined;
}var notxml=!jQuery.isXMLDoc(elem),set=value!==undefined,msie=jQuery.browser.msie;
name=notxml&&jQuery.props[name]||name;
if(elem.tagName){var special=/href|src|style/.test(name);
if(name=="selected"&&jQuery.browser.safari){elem.parentNode.selectedIndex;
}if(name in elem&&notxml&&!special){if(set){if(name=="type"&&jQuery.nodeName(elem,"input")&&elem.parentNode){throw"type property can't be changed";
}elem[name]=value;
}if(jQuery.nodeName(elem,"form")&&elem.getAttributeNode(name)){return elem.getAttributeNode(name).nodeValue;
}return elem[name];
}if(msie&&notxml&&name=="style"){return jQuery.attr(elem.style,"cssText",value);
}if(set){elem.setAttribute(name,""+value);
}var attr=msie&&notxml&&special?elem.getAttribute(name,2):elem.getAttribute(name);
return attr===null?undefined:attr;
}if(msie&&name=="opacity"){if(set){elem.zoom=1;
elem.filter=(elem.filter||"").replace(/alpha\([^)]*\)/,"")+(parseInt(value)+""=="NaN"?"":"alpha(opacity="+value*100+")");
}return elem.filter&&elem.filter.indexOf("opacity=")>=0?(parseFloat(elem.filter.match(/opacity=([^)]*)/)[1])/100)+"":"";
}name=name.replace(/-([a-z])/ig,function(all,letter){return letter.toUpperCase();
});
if(set){elem[name]=value;
}return elem[name];
},trim:function(text){return(text||"").replace(/^\s+|\s+$/g,"");
},makeArray:function(array){var ret=[];
if(array!=null){var i=array.length;
if(i==null||array.split||array.setInterval||array.call){ret[0]=array;
}else{while(i){ret[--i]=array[i];
}}}return ret;
},inArray:function(elem,array){for(var i=0,length=array.length;
i<length;
i++){if(array[i]===elem){return i;
}}return -1;
},merge:function(first,second){var i=0,elem,pos=first.length;
if(jQuery.browser.msie){while(elem=second[i++]){if(elem.nodeType!=8){first[pos++]=elem;
}}}else{while(elem=second[i++]){first[pos++]=elem;
}}return first;
},unique:function(array){var ret=[],done={};
try{for(var i=0,length=array.length;
i<length;
i++){var id=jQuery.data(array[i]);
if(!done[id]){done[id]=true;
ret.push(array[i]);
}}}catch(e){ret=array;
}return ret;
},grep:function(elems,callback,inv){var ret=[];
for(var i=0,length=elems.length;
i<length;
i++){if(!inv!=!callback(elems[i],i)){ret.push(elems[i]);
}}return ret;
},map:function(elems,callback){var ret=[];
for(var i=0,length=elems.length;
i<length;
i++){var value=callback(elems[i],i);
if(value!=null){ret[ret.length]=value;
}}return ret.concat.apply([],ret);
}});
var userAgent=navigator.userAgent.toLowerCase();
jQuery.browser={version:(userAgent.match(/.+(?:rv|it|ra|ie)[\/: ]([\d.]+)/)||[])[1],safari:/webkit/.test(userAgent),opera:/opera/.test(userAgent),msie:/msie/.test(userAgent)&&!/opera/.test(userAgent),mozilla:/mozilla/.test(userAgent)&&!/(compatible|webkit)/.test(userAgent)};
var styleFloat=jQuery.browser.msie?"styleFloat":"cssFloat";
jQuery.extend({boxModel:!jQuery.browser.msie||document.compatMode=="CSS1Compat",props:{"for":"htmlFor","class":"className","float":styleFloat,cssFloat:styleFloat,styleFloat:styleFloat,readonly:"readOnly",maxlength:"maxLength",cellspacing:"cellSpacing"}});
jQuery.each({parent:function(elem){return elem.parentNode;
},parents:function(elem){return jQuery.dir(elem,"parentNode");
},next:function(elem){return jQuery.nth(elem,2,"nextSibling");
},prev:function(elem){return jQuery.nth(elem,2,"previousSibling");
},nextAll:function(elem){return jQuery.dir(elem,"nextSibling");
},prevAll:function(elem){return jQuery.dir(elem,"previousSibling");
},siblings:function(elem){return jQuery.sibling(elem.parentNode.firstChild,elem);
},children:function(elem){return jQuery.sibling(elem.firstChild);
},contents:function(elem){return jQuery.nodeName(elem,"iframe")?elem.contentDocument||elem.contentWindow.document:jQuery.makeArray(elem.childNodes);
}},function(name,fn){jQuery.fn[name]=function(selector){var ret=jQuery.map(this,fn);
if(selector&&typeof selector=="string"){ret=jQuery.multiFilter(selector,ret);
}return this.pushStack(jQuery.unique(ret));
};
});
jQuery.each({appendTo:"append",prependTo:"prepend",insertBefore:"before",insertAfter:"after",replaceAll:"replaceWith"},function(name,original){jQuery.fn[name]=function(){var args=arguments;
return this.each(function(){for(var i=0,length=args.length;
i<length;
i++){jQuery(args[i])[original](this);
}});
};
});
jQuery.each({removeAttr:function(name){jQuery.attr(this,name,"");
if(this.nodeType==1){this.removeAttribute(name);
}},addClass:function(classNames){jQuery.className.add(this,classNames);
},removeClass:function(classNames){jQuery.className.remove(this,classNames);
},toggleClass:function(classNames){jQuery.className[jQuery.className.has(this,classNames)?"remove":"add"](this,classNames);
},remove:function(selector){if(!selector||jQuery.filter(selector,[this]).r.length){jQuery("*",this).add(this).each(function(){jQuery.event.remove(this);
jQuery.removeData(this);
});
if(this.parentNode){this.parentNode.removeChild(this);
}}},empty:function(){jQuery(">*",this).remove();
while(this.firstChild){this.removeChild(this.firstChild);
}}},function(name,fn){jQuery.fn[name]=function(){return this.each(fn,arguments);
};
});
jQuery.each(["Height","Width"],function(i,name){var type=name.toLowerCase();
jQuery.fn[type]=function(size){return this[0]==window?jQuery.browser.opera&&document.body["client"+name]||jQuery.browser.safari&&window["inner"+name]||document.compatMode=="CSS1Compat"&&document.documentElement["client"+name]||document.body["client"+name]:this[0]==document?Math.max(Math.max(document.body["scroll"+name],document.documentElement["scroll"+name]),Math.max(document.body["offset"+name],document.documentElement["offset"+name])):size==undefined?(this.length?jQuery.css(this[0],type):null):this.css(type,size.constructor==String?size:size+"px");
};
});
function num(elem,prop){return elem[0]&&parseInt(jQuery.curCSS(elem[0],prop,true),10)||0;
}var chars=jQuery.browser.safari&&parseInt(jQuery.browser.version)<417?"(?:[\\w*_-]|\\\\.)":"(?:[\\w\u0128-\uFFFF*_-]|\\\\.)",quickChild=new RegExp("^>\\s*("+chars+"+)"),quickID=new RegExp("^("+chars+"+)(#)("+chars+"+)"),quickClass=new RegExp("^([#.]?)("+chars+"*)");
jQuery.extend({expr:{"":function(a,i,m){return m[2]=="*"||jQuery.nodeName(a,m[2]);
},"#":function(a,i,m){return a.getAttribute("id")==m[2];
},":":{lt:function(a,i,m){return i<m[3]-0;
},gt:function(a,i,m){return i>m[3]-0;
},nth:function(a,i,m){return m[3]-0==i;
},eq:function(a,i,m){return m[3]-0==i;
},first:function(a,i){return i==0;
},last:function(a,i,m,r){return i==r.length-1;
},even:function(a,i){return i%2==0;
},odd:function(a,i){return i%2;
},"first-child":function(a){return a.parentNode.getElementsByTagName("*")[0]==a;
},"last-child":function(a){return jQuery.nth(a.parentNode.lastChild,1,"previousSibling")==a;
},"only-child":function(a){return !jQuery.nth(a.parentNode.lastChild,2,"previousSibling");
},parent:function(a){return a.firstChild;
},empty:function(a){return !a.firstChild;
},contains:function(a,i,m){return(a.textContent||a.innerText||jQuery(a).text()||"").indexOf(m[3])>=0;
},visible:function(a){return"hidden"!=a.type&&jQuery.css(a,"display")!="none"&&jQuery.css(a,"visibility")!="hidden";
},hidden:function(a){return"hidden"==a.type||jQuery.css(a,"display")=="none"||jQuery.css(a,"visibility")=="hidden";
},enabled:function(a){return !a.disabled;
},disabled:function(a){return a.disabled;
},checked:function(a){return a.checked;
},selected:function(a){return a.selected||jQuery.attr(a,"selected");
},text:function(a){return"text"==a.type;
},radio:function(a){return"radio"==a.type;
},checkbox:function(a){return"checkbox"==a.type;
},file:function(a){return"file"==a.type;
},password:function(a){return"password"==a.type;
},submit:function(a){return"submit"==a.type;
},image:function(a){return"image"==a.type;
},reset:function(a){return"reset"==a.type;
},button:function(a){return"button"==a.type||jQuery.nodeName(a,"button");
},input:function(a){return/input|select|textarea|button/i.test(a.nodeName);
},has:function(a,i,m){return jQuery.find(m[3],a).length;
},header:function(a){return/h\d/i.test(a.nodeName);
},animated:function(a){return jQuery.grep(jQuery.timers,function(fn){return a==fn.elem;
}).length;
}}},parse:[/^(\[) *@?([\w-]+) *([!*$^~=]*) *('?"?)(.*?)\4 *\]/,/^(:)([\w-]+)\("?'?(.*?(\(.*?\))?[^(]*?)"?'?\)/,new RegExp("^([:.#]*)("+chars+"+)")],multiFilter:function(expr,elems,not){var old,cur=[];
while(expr&&expr!=old){old=expr;
var f=jQuery.filter(expr,elems,not);
expr=f.t.replace(/^\s*,\s*/,"");
cur=not?elems=f.r:jQuery.merge(cur,f.r);
}return cur;
},find:function(t,context){if(typeof t!="string"){return[t];
}if(context&&context.nodeType!=1&&context.nodeType!=9){return[];
}context=context||document;
var ret=[context],done=[],last,nodeName;
while(t&&last!=t){var r=[];
last=t;
t=jQuery.trim(t);
var foundToken=false,re=quickChild,m=re.exec(t);
if(m){nodeName=m[1].toUpperCase();
for(var i=0;
ret[i];
i++){for(var c=ret[i].firstChild;
c;
c=c.nextSibling){if(c.nodeType==1&&(nodeName=="*"||c.nodeName.toUpperCase()==nodeName)){r.push(c);
}}}ret=r;
t=t.replace(re,"");
if(t.indexOf(" ")==0){continue;
}foundToken=true;
}else{re=/^([>+~])\s*(\w*)/i;
if((m=re.exec(t))!=null){r=[];
var merge={};
nodeName=m[2].toUpperCase();
m=m[1];
for(var j=0,rl=ret.length;
j<rl;
j++){var n=m=="~"||m=="+"?ret[j].nextSibling:ret[j].firstChild;
for(;
n;
n=n.nextSibling){if(n.nodeType==1){var id=jQuery.data(n);
if(m=="~"&&merge[id]){break;
}if(!nodeName||n.nodeName.toUpperCase()==nodeName){if(m=="~"){merge[id]=true;
}r.push(n);
}if(m=="+"){break;
}}}}ret=r;
t=jQuery.trim(t.replace(re,""));
foundToken=true;
}}if(t&&!foundToken){if(!t.indexOf(",")){if(context==ret[0]){ret.shift();
}done=jQuery.merge(done,ret);
r=ret=[context];
t=" "+t.substr(1,t.length);
}else{var re2=quickID;
var m=re2.exec(t);
if(m){m=[0,m[2],m[3],m[1]];
}else{re2=quickClass;
m=re2.exec(t);
}m[2]=m[2].replace(/\\/g,"");
var elem=ret[ret.length-1];
if(m[1]=="#"&&elem&&elem.getElementById&&!jQuery.isXMLDoc(elem)){var oid=elem.getElementById(m[2]);
if((jQuery.browser.msie||jQuery.browser.opera)&&oid&&typeof oid.id=="string"&&oid.id!=m[2]){oid=jQuery('[@id="'+m[2]+'"]',elem)[0];
}ret=r=oid&&(!m[3]||jQuery.nodeName(oid,m[3]))?[oid]:[];
}else{for(var i=0;
ret[i];
i++){var tag=m[1]=="#"&&m[3]?m[3]:m[1]!=""||m[0]==""?"*":m[2];
if(tag=="*"&&ret[i].nodeName.toLowerCase()=="object"){tag="param";
}r=jQuery.merge(r,ret[i].getElementsByTagName(tag));
}if(m[1]=="."){r=jQuery.classFilter(r,m[2]);
}if(m[1]=="#"){var tmp=[];
for(var i=0;
r[i];
i++){if(r[i].getAttribute("id")==m[2]){tmp=[r[i]];
break;
}}r=tmp;
}ret=r;
}t=t.replace(re2,"");
}}if(t){var val=jQuery.filter(t,r);
ret=r=val.r;
t=jQuery.trim(val.t);
}}if(t){ret=[];
}if(ret&&context==ret[0]){ret.shift();
}done=jQuery.merge(done,ret);
return done;
},classFilter:function(r,m,not){m=" "+m+" ";
var tmp=[];
for(var i=0;
r[i];
i++){var pass=(" "+r[i].className+" ").indexOf(m)>=0;
if(!not&&pass||not&&!pass){tmp.push(r[i]);
}}return tmp;
},filter:function(t,r,not){var last;
while(t&&t!=last){last=t;
var p=jQuery.parse,m;
for(var i=0;
p[i];
i++){m=p[i].exec(t);
if(m){t=t.substring(m[0].length);
m[2]=m[2].replace(/\\/g,"");
break;
}}if(!m){break;
}if(m[1]==":"&&m[2]=="not"){r=isSimple.test(m[3])?jQuery.filter(m[3],r,true).r:jQuery(r).not(m[3]);
}else{if(m[1]=="."){r=jQuery.classFilter(r,m[2],not);
}else{if(m[1]=="["){var tmp=[],type=m[3];
for(var i=0,rl=r.length;
i<rl;
i++){var a=r[i],z=a[jQuery.props[m[2]]||m[2]];
if(z==null||/href|src|selected/.test(m[2])){z=jQuery.attr(a,m[2])||"";
}if((type==""&&!!z||type=="="&&z==m[5]||type=="!="&&z!=m[5]||type=="^="&&z&&!z.indexOf(m[5])||type=="$="&&z.substr(z.length-m[5].length)==m[5]||(type=="*="||type=="~=")&&z.indexOf(m[5])>=0)^not){tmp.push(a);
}}r=tmp;
}else{if(m[1]==":"&&m[2]=="nth-child"){var merge={},tmp=[],test=/(-?)(\d*)n((?:\+|-)?\d*)/.exec(m[3]=="even"&&"2n"||m[3]=="odd"&&"2n+1"||!/\D/.test(m[3])&&"0n+"+m[3]||m[3]),first=(test[1]+(test[2]||1))-0,last=test[3]-0;
for(var i=0,rl=r.length;
i<rl;
i++){var node=r[i],parentNode=node.parentNode,id=jQuery.data(parentNode);
if(!merge[id]){var c=1;
for(var n=parentNode.firstChild;
n;
n=n.nextSibling){if(n.nodeType==1){n.nodeIndex=c++;
}}merge[id]=true;
}var add=false;
if(first==0){if(node.nodeIndex==last){add=true;
}}else{if((node.nodeIndex-last)%first==0&&(node.nodeIndex-last)/first>=0){add=true;
}}if(add^not){tmp.push(node);
}}r=tmp;
}else{var fn=jQuery.expr[m[1]];
if(typeof fn=="object"){fn=fn[m[2]];
}if(typeof fn=="string"){fn=eval("false||function(a,i){return "+fn+";}");
}r=jQuery.grep(r,function(elem,i){return fn(elem,i,m,r);
},not);
}}}}}return{r:r,t:t};
},dir:function(elem,dir){var matched=[],cur=elem[dir];
while(cur&&cur!=document){if(cur.nodeType==1){matched.push(cur);
}cur=cur[dir];
}return matched;
},nth:function(cur,result,dir,elem){result=result||1;
var num=0;
for(;
cur;
cur=cur[dir]){if(cur.nodeType==1&&++num==result){break;
}}return cur;
},sibling:function(n,elem){var r=[];
for(;
n;
n=n.nextSibling){if(n.nodeType==1&&n!=elem){r.push(n);
}}return r;
}});
jQuery.event={add:function(elem,types,handler,data){if(elem.nodeType==3||elem.nodeType==8){return ;
}if(jQuery.browser.msie&&elem.setInterval){elem=window;
}if(!handler.guid){handler.guid=this.guid++;
}if(data!=undefined){var fn=handler;
handler=this.proxy(fn,function(){return fn.apply(this,arguments);
});
handler.data=data;
}var events=jQuery.data(elem,"events")||jQuery.data(elem,"events",{}),handle=jQuery.data(elem,"handle")||jQuery.data(elem,"handle",function(){if(typeof jQuery!="undefined"&&!jQuery.event.triggered){return jQuery.event.handle.apply(arguments.callee.elem,arguments);
}});
handle.elem=elem;
jQuery.each(types.split(/\s+/),function(index,type){var parts=type.split(".");
type=parts[0];
handler.type=parts[1];
var handlers=events[type];
if(!handlers){handlers=events[type]={};
if(!jQuery.event.special[type]||jQuery.event.special[type].setup.call(elem)===false){if(elem.addEventListener){elem.addEventListener(type,handle,false);
}else{if(elem.attachEvent){elem.attachEvent("on"+type,handle);
}}}}handlers[handler.guid]=handler;
jQuery.event.global[type]=true;
});
elem=null;
},guid:1,global:{},remove:function(elem,types,handler){if(elem.nodeType==3||elem.nodeType==8){return ;
}var events=jQuery.data(elem,"events"),ret,index;
if(events){if(types==undefined||(typeof types=="string"&&types.charAt(0)==".")){for(var type in events){this.remove(elem,type+(types||""));
}}else{if(types.type){handler=types.handler;
types=types.type;
}jQuery.each(types.split(/\s+/),function(index,type){var parts=type.split(".");
type=parts[0];
if(events[type]){if(handler){delete events[type][handler.guid];
}else{for(handler in events[type]){if(!parts[1]||events[type][handler].type==parts[1]){delete events[type][handler];
}}}for(ret in events[type]){break;
}if(!ret){if(!jQuery.event.special[type]||jQuery.event.special[type].teardown.call(elem)===false){if(elem.removeEventListener){elem.removeEventListener(type,jQuery.data(elem,"handle"),false);
}else{if(elem.detachEvent){elem.detachEvent("on"+type,jQuery.data(elem,"handle"));
}}}ret=null;
delete events[type];
}}});
}for(ret in events){break;
}if(!ret){var handle=jQuery.data(elem,"handle");
if(handle){handle.elem=null;
}jQuery.removeData(elem,"events");
jQuery.removeData(elem,"handle");
}}},trigger:function(type,data,elem,donative,extra){data=jQuery.makeArray(data);
if(type.indexOf("!")>=0){type=type.slice(0,-1);
var exclusive=true;
}if(!elem){if(this.global[type]){jQuery("*").add([window,document]).trigger(type,data);
}}else{if(elem.nodeType==3||elem.nodeType==8){return undefined;
}var val,ret,fn=jQuery.isFunction(elem[type]||null),event=!data[0]||!data[0].preventDefault;
if(event){data.unshift({type:type,target:elem,preventDefault:function(){},stopPropagation:function(){},timeStamp:now()});
data[0][expando]=true;
}data[0].type=type;
if(exclusive){data[0].exclusive=true;
}var handle=jQuery.data(elem,"handle");
if(handle){val=handle.apply(elem,data);
}if((!fn||(jQuery.nodeName(elem,"a")&&type=="click"))&&elem["on"+type]&&elem["on"+type].apply(elem,data)===false){val=false;
}if(event){data.shift();
}if(extra&&jQuery.isFunction(extra)){ret=extra.apply(elem,val==null?data:data.concat(val));
if(ret!==undefined){val=ret;
}}if(fn&&donative!==false&&val!==false&&!(jQuery.nodeName(elem,"a")&&type=="click")){this.triggered=true;
try{elem[type]();
}catch(e){}}this.triggered=false;
}return val;
},handle:function(event){var val,ret,namespace,all,handlers;
event=arguments[0]=jQuery.event.fix(event||window.event);
namespace=event.type.split(".");
event.type=namespace[0];
namespace=namespace[1];
all=!namespace&&!event.exclusive;
handlers=(jQuery.data(this,"events")||{})[event.type];
for(var j in handlers){var handler=handlers[j];
if(all||handler.type==namespace){event.handler=handler;
event.data=handler.data;
ret=handler.apply(this,arguments);
if(val!==false){val=ret;
}if(ret===false){event.preventDefault();
event.stopPropagation();
}}}return val;
},fix:function(event){if(event[expando]==true){return event;
}var originalEvent=event;
event={originalEvent:originalEvent};
var props="altKey attrChange attrName bubbles button cancelable charCode clientX clientY ctrlKey currentTarget data detail eventPhase fromElement handler keyCode metaKey newValue originalTarget pageX pageY prevValue relatedNode relatedTarget screenX screenY shiftKey srcElement target timeStamp toElement type view wheelDelta which".split(" ");
for(var i=props.length;
i;
i--){event[props[i]]=originalEvent[props[i]];
}event[expando]=true;
event.preventDefault=function(){if(originalEvent.preventDefault){originalEvent.preventDefault();
}originalEvent.returnValue=false;
};
event.stopPropagation=function(){if(originalEvent.stopPropagation){originalEvent.stopPropagation();
}originalEvent.cancelBubble=true;
};
event.timeStamp=event.timeStamp||now();
if(!event.target){event.target=event.srcElement||document;
}if(event.target.nodeType==3){event.target=event.target.parentNode;
}if(!event.relatedTarget&&event.fromElement){event.relatedTarget=event.fromElement==event.target?event.toElement:event.fromElement;
}if(event.pageX==null&&event.clientX!=null){var doc=document.documentElement,body=document.body;
event.pageX=event.clientX+(doc&&doc.scrollLeft||body&&body.scrollLeft||0)-(doc.clientLeft||0);
event.pageY=event.clientY+(doc&&doc.scrollTop||body&&body.scrollTop||0)-(doc.clientTop||0);
}if(!event.which&&((event.charCode||event.charCode===0)?event.charCode:event.keyCode)){event.which=event.charCode||event.keyCode;
}if(!event.metaKey&&event.ctrlKey){event.metaKey=event.ctrlKey;
}if(!event.which&&event.button){event.which=(event.button&1?1:(event.button&2?3:(event.button&4?2:0)));
}return event;
},proxy:function(fn,proxy){proxy.guid=fn.guid=fn.guid||proxy.guid||this.guid++;
return proxy;
},special:{ready:{setup:function(){bindReady();
return ;
},teardown:function(){return ;
}},mouseenter:{setup:function(){if(jQuery.browser.msie){return false;
}jQuery(this).bind("mouseover",jQuery.event.special.mouseenter.handler);
return true;
},teardown:function(){if(jQuery.browser.msie){return false;
}jQuery(this).unbind("mouseover",jQuery.event.special.mouseenter.handler);
return true;
},handler:function(event){if(withinElement(event,this)){return true;
}event.type="mouseenter";
return jQuery.event.handle.apply(this,arguments);
}},mouseleave:{setup:function(){if(jQuery.browser.msie){return false;
}jQuery(this).bind("mouseout",jQuery.event.special.mouseleave.handler);
return true;
},teardown:function(){if(jQuery.browser.msie){return false;
}jQuery(this).unbind("mouseout",jQuery.event.special.mouseleave.handler);
return true;
},handler:function(event){if(withinElement(event,this)){return true;
}event.type="mouseleave";
return jQuery.event.handle.apply(this,arguments);
}}}};
jQuery.fn.extend({bind:function(type,data,fn){return type=="unload"?this.one(type,data,fn):this.each(function(){jQuery.event.add(this,type,fn||data,fn&&data);
});
},one:function(type,data,fn){var one=jQuery.event.proxy(fn||data,function(event){jQuery(this).unbind(event,one);
return(fn||data).apply(this,arguments);
});
return this.each(function(){jQuery.event.add(this,type,one,fn&&data);
});
},unbind:function(type,fn){return this.each(function(){jQuery.event.remove(this,type,fn);
});
},trigger:function(type,data,fn){return this.each(function(){jQuery.event.trigger(type,data,this,true,fn);
});
},triggerHandler:function(type,data,fn){return this[0]&&jQuery.event.trigger(type,data,this[0],false,fn);
},toggle:function(fn){var args=arguments,i=1;
while(i<args.length){jQuery.event.proxy(fn,args[i++]);
}return this.click(jQuery.event.proxy(fn,function(event){this.lastToggle=(this.lastToggle||0)%i;
event.preventDefault();
return args[this.lastToggle++].apply(this,arguments)||false;
}));
},hover:function(fnOver,fnOut){return this.bind("mouseenter",fnOver).bind("mouseleave",fnOut);
},ready:function(fn){bindReady();
if(jQuery.isReady){fn.call(document,jQuery);
}else{jQuery.readyList.push(function(){return fn.call(this,jQuery);
});
}return this;
}});
jQuery.extend({isReady:false,readyList:[],ready:function(){if(!jQuery.isReady){jQuery.isReady=true;
if(jQuery.readyList){jQuery.each(jQuery.readyList,function(){this.call(document);
});
jQuery.readyList=null;
}jQuery(document).triggerHandler("ready");
}}});
var readyBound=false;
function bindReady(){if(readyBound){return ;
}readyBound=true;
if(document.addEventListener&&!jQuery.browser.opera){document.addEventListener("DOMContentLoaded",jQuery.ready,false);
}if(jQuery.browser.msie&&window==top){(function(){if(jQuery.isReady){return ;
}try{document.documentElement.doScroll("left");
}catch(error){setTimeout(arguments.callee,0);
return ;
}jQuery.ready();
})();
}if(jQuery.browser.opera){document.addEventListener("DOMContentLoaded",function(){if(jQuery.isReady){return ;
}for(var i=0;
i<document.styleSheets.length;
i++){if(document.styleSheets[i].disabled){setTimeout(arguments.callee,0);
return ;
}}jQuery.ready();
},false);
}if(jQuery.browser.safari){var numStyles;
(function(){if(jQuery.isReady){return ;
}if(document.readyState!="loaded"&&document.readyState!="complete"){setTimeout(arguments.callee,0);
return ;
}if(numStyles===undefined){numStyles=jQuery("style, link[rel=stylesheet]").length;
}if(document.styleSheets.length!=numStyles){setTimeout(arguments.callee,0);
return ;
}jQuery.ready();
})();
}jQuery.event.add(window,"load",jQuery.ready);
}jQuery.each(("blur,focus,load,resize,scroll,unload,click,dblclick,mousedown,mouseup,mousemove,mouseover,mouseout,change,select,submit,keydown,keypress,keyup,error").split(","),function(i,name){jQuery.fn[name]=function(fn){return fn?this.bind(name,fn):this.trigger(name);
};
});
var withinElement=function(event,elem){var parent=event.relatedTarget;
while(parent&&parent!=elem){try{parent=parent.parentNode;
}catch(error){parent=elem;
}}return parent==elem;
};
jQuery(window).bind("unload",function(){jQuery("*").add(document).unbind();
});
jQuery.fn.extend({_load:jQuery.fn.load,load:function(url,params,callback){if(typeof url!="string"){return this._load(url);
}var off=url.indexOf(" ");
if(off>=0){var selector=url.slice(off,url.length);
url=url.slice(0,off);
}callback=callback||function(){};
var type="GET";
if(params){if(jQuery.isFunction(params)){callback=params;
params=null;
}else{params=jQuery.param(params);
type="POST";
}}var self=this;
jQuery.ajax({url:url,type:type,dataType:"html",data:params,complete:function(res,status){if(status=="success"||status=="notmodified"){self.html(selector?jQuery("<div/>").append(res.responseText.replace(/<script(.|\s)*?\/script>/g,"")).find(selector):res.responseText);
}self.each(callback,[res.responseText,status,res]);
}});
return this;
},serialize:function(){return jQuery.param(this.serializeArray());
},serializeArray:function(){return this.map(function(){return jQuery.nodeName(this,"form")?jQuery.makeArray(this.elements):this;
}).filter(function(){return this.name&&!this.disabled&&(this.checked||/select|textarea/i.test(this.nodeName)||/text|hidden|password/i.test(this.type));
}).map(function(i,elem){var val=jQuery(this).val();
return val==null?null:val.constructor==Array?jQuery.map(val,function(val,i){return{name:elem.name,value:val};
}):{name:elem.name,value:val};
}).get();
}});
jQuery.each("ajaxStart,ajaxStop,ajaxComplete,ajaxError,ajaxSuccess,ajaxSend".split(","),function(i,o){jQuery.fn[o]=function(f){return this.bind(o,f);
};
});
var jsc=now();
jQuery.extend({get:function(url,data,callback,type){if(jQuery.isFunction(data)){callback=data;
data=null;
}return jQuery.ajax({type:"GET",url:url,data:data,success:callback,dataType:type});
},getScript:function(url,callback){return jQuery.get(url,null,callback,"script");
},getJSON:function(url,data,callback){return jQuery.get(url,data,callback,"json");
},post:function(url,data,callback,type){if(jQuery.isFunction(data)){callback=data;
data={};
}return jQuery.ajax({type:"POST",url:url,data:data,success:callback,dataType:type});
},ajaxSetup:function(settings){jQuery.extend(jQuery.ajaxSettings,settings);
},ajaxSettings:{url:location.href,global:true,type:"GET",timeout:0,contentType:"application/x-www-form-urlencoded",processData:true,async:true,data:null,username:null,password:null,accepts:{xml:"application/xml, text/xml",html:"text/html",script:"text/javascript, application/javascript",json:"application/json, text/javascript",text:"text/plain",_default:"*/*"}},lastModified:{},ajax:function(s){s=jQuery.extend(true,s,jQuery.extend(true,{},jQuery.ajaxSettings,s));
var jsonp,jsre=/=\?(&|$)/g,status,data,type=s.type.toUpperCase();
if(s.data&&s.processData&&typeof s.data!="string"){s.data=jQuery.param(s.data);
}if(s.dataType=="jsonp"){if(type=="GET"){if(!s.url.match(jsre)){s.url+=(s.url.match(/\?/)?"&":"?")+(s.jsonp||"callback")+"=?";
}}else{if(!s.data||!s.data.match(jsre)){s.data=(s.data?s.data+"&":"")+(s.jsonp||"callback")+"=?";
}}s.dataType="json";
}if(s.dataType=="json"&&(s.data&&s.data.match(jsre)||s.url.match(jsre))){jsonp="jsonp"+jsc++;
if(s.data){s.data=(s.data+"").replace(jsre,"="+jsonp+"$1");
}s.url=s.url.replace(jsre,"="+jsonp+"$1");
s.dataType="script";
window[jsonp]=function(tmp){data=tmp;
success();
complete();
window[jsonp]=undefined;
try{delete window[jsonp];
}catch(e){}if(head){head.removeChild(script);
}};
}if(s.dataType=="script"&&s.cache==null){s.cache=false;
}if(s.cache===false&&type=="GET"){var ts=now();
var ret=s.url.replace(/(\?|&)_=.*?(&|$)/,"$1_="+ts+"$2");
s.url=ret+((ret==s.url)?(s.url.match(/\?/)?"&":"?")+"_="+ts:"");
}if(s.data&&type=="GET"){s.url+=(s.url.match(/\?/)?"&":"?")+s.data;
s.data=null;
}if(s.global&&!jQuery.active++){jQuery.event.trigger("ajaxStart");
}var remote=/^(?:\w+:)?\/\/([^\/?#]+)/;
if(s.dataType=="script"&&type=="GET"&&remote.test(s.url)&&remote.exec(s.url)[1]!=location.host){var head=document.getElementsByTagName("head")[0];
var script=document.createElement("script");
script.src=s.url;
if(s.scriptCharset){script.charset=s.scriptCharset;
}if(!jsonp){var done=false;
script.onload=script.onreadystatechange=function(){if(!done&&(!this.readyState||this.readyState=="loaded"||this.readyState=="complete")){done=true;
success();
complete();
head.removeChild(script);
}};
}head.appendChild(script);
return undefined;
}var requestDone=false;
var xhr=window.ActiveXObject?new ActiveXObject("Microsoft.XMLHTTP"):new XMLHttpRequest();
if(s.username){xhr.open(type,s.url,s.async,s.username,s.password);
}else{xhr.open(type,s.url,s.async);
}try{if(s.data){xhr.setRequestHeader("Content-Type",s.contentType);
}if(s.ifModified){xhr.setRequestHeader("If-Modified-Since",jQuery.lastModified[s.url]||"Thu, 01 Jan 1970 00:00:00 GMT");
}xhr.setRequestHeader("X-Requested-With","XMLHttpRequest");
xhr.setRequestHeader("Accept",s.dataType&&s.accepts[s.dataType]?s.accepts[s.dataType]+", */*":s.accepts._default);
}catch(e){}if(s.beforeSend&&s.beforeSend(xhr,s)===false){s.global&&jQuery.active--;
xhr.abort();
return false;
}if(s.global){jQuery.event.trigger("ajaxSend",[xhr,s]);
}var onreadystatechange=function(isTimeout){if(!requestDone&&xhr&&(xhr.readyState==4||isTimeout=="timeout")){requestDone=true;
if(ival){clearInterval(ival);
ival=null;
}status=isTimeout=="timeout"&&"timeout"||!jQuery.httpSuccess(xhr)&&"error"||s.ifModified&&jQuery.httpNotModified(xhr,s.url)&&"notmodified"||"success";
if(status=="success"){try{data=jQuery.httpData(xhr,s.dataType,s.dataFilter);
}catch(e){status="parsererror";
}}if(status=="success"){var modRes;
try{modRes=xhr.getResponseHeader("Last-Modified");
}catch(e){}if(s.ifModified&&modRes){jQuery.lastModified[s.url]=modRes;
}if(!jsonp){success();
}}else{jQuery.handleError(s,xhr,status);
}complete();
if(s.async){xhr=null;
}}};
if(s.async){var ival=setInterval(onreadystatechange,13);
if(s.timeout>0){setTimeout(function(){if(xhr){xhr.abort();
if(!requestDone){onreadystatechange("timeout");
}}},s.timeout);
}}try{xhr.send(s.data);
}catch(e){jQuery.handleError(s,xhr,null,e);
}if(!s.async){onreadystatechange();
}function success(){if(s.success){s.success(data,status);
}if(s.global){jQuery.event.trigger("ajaxSuccess",[xhr,s]);
}}function complete(){if(s.complete){s.complete(xhr,status);
}if(s.global){jQuery.event.trigger("ajaxComplete",[xhr,s]);
}if(s.global&&!--jQuery.active){jQuery.event.trigger("ajaxStop");
}}return xhr;
},handleError:function(s,xhr,status,e){if(s.error){s.error(xhr,status,e);
}if(s.global){jQuery.event.trigger("ajaxError",[xhr,s,e]);
}},active:0,httpSuccess:function(xhr){try{return !xhr.status&&location.protocol=="file:"||(xhr.status>=200&&xhr.status<300)||xhr.status==304||xhr.status==1223||jQuery.browser.safari&&xhr.status==undefined;
}catch(e){}return false;
},httpNotModified:function(xhr,url){try{var xhrRes=xhr.getResponseHeader("Last-Modified");
return xhr.status==304||xhrRes==jQuery.lastModified[url]||jQuery.browser.safari&&xhr.status==undefined;
}catch(e){}return false;
},httpData:function(xhr,type,filter){var ct=xhr.getResponseHeader("content-type"),xml=type=="xml"||!type&&ct&&ct.indexOf("xml")>=0,data=xml?xhr.responseXML:xhr.responseText;
if(xml&&data.documentElement.tagName=="parsererror"){throw"parsererror";
}if(filter){data=filter(data,type);
}if(type=="script"){jQuery.globalEval(data);
}if(type=="json"){data=eval("("+data+")");
}return data;
},param:function(a){var s=[];
if(a.constructor==Array||a.jquery){jQuery.each(a,function(){s.push(encodeURIComponent(this.name)+"="+encodeURIComponent(this.value));
});
}else{for(var j in a){if(a[j]&&a[j].constructor==Array){jQuery.each(a[j],function(){s.push(encodeURIComponent(j)+"="+encodeURIComponent(this));
});
}else{s.push(encodeURIComponent(j)+"="+encodeURIComponent(jQuery.isFunction(a[j])?a[j]():a[j]));
}}}return s.join("&").replace(/%20/g,"+");
}});
jQuery.fn.extend({show:function(speed,callback){return speed?this.animate({height:"show",width:"show",opacity:"show"},speed,callback):this.filter(":hidden").each(function(){this.style.display=this.oldblock||"";
if(jQuery.css(this,"display")=="none"){var elem=jQuery("<"+this.tagName+" />").appendTo("body");
this.style.display=elem.css("display");
if(this.style.display=="none"){this.style.display="block";
}elem.remove();
}}).end();
},hide:function(speed,callback){return speed?this.animate({height:"hide",width:"hide",opacity:"hide"},speed,callback):this.filter(":visible").each(function(){this.oldblock=this.oldblock||jQuery.css(this,"display");
this.style.display="none";
}).end();
},_toggle:jQuery.fn.toggle,toggle:function(fn,fn2){return jQuery.isFunction(fn)&&jQuery.isFunction(fn2)?this._toggle.apply(this,arguments):fn?this.animate({height:"toggle",width:"toggle",opacity:"toggle"},fn,fn2):this.each(function(){jQuery(this)[jQuery(this).is(":hidden")?"show":"hide"]();
});
},slideDown:function(speed,callback){return this.animate({height:"show"},speed,callback);
},slideUp:function(speed,callback){return this.animate({height:"hide"},speed,callback);
},slideToggle:function(speed,callback){return this.animate({height:"toggle"},speed,callback);
},fadeIn:function(speed,callback){return this.animate({opacity:"show"},speed,callback);
},fadeOut:function(speed,callback){return this.animate({opacity:"hide"},speed,callback);
},fadeTo:function(speed,to,callback){return this.animate({opacity:to},speed,callback);
},animate:function(prop,speed,easing,callback){var optall=jQuery.speed(speed,easing,callback);
return this[optall.queue===false?"each":"queue"](function(){if(this.nodeType!=1){return false;
}var opt=jQuery.extend({},optall),p,hidden=jQuery(this).is(":hidden"),self=this;
for(p in prop){if(prop[p]=="hide"&&hidden||prop[p]=="show"&&!hidden){return opt.complete.call(this);
}if(p=="height"||p=="width"){opt.display=jQuery.css(this,"display");
opt.overflow=this.style.overflow;
}}if(opt.overflow!=null){this.style.overflow="hidden";
}opt.curAnim=jQuery.extend({},prop);
jQuery.each(prop,function(name,val){var e=new jQuery.fx(self,opt,name);
if(/toggle|show|hide/.test(val)){e[val=="toggle"?hidden?"show":"hide":val](prop);
}else{var parts=val.toString().match(/^([+-]=)?([\d+-.]+)(.*)$/),start=e.cur(true)||0;
if(parts){var end=parseFloat(parts[2]),unit=parts[3]||"px";
if(unit!="px"){self.style[name]=(end||1)+unit;
start=((end||1)/e.cur(true))*start;
self.style[name]=start+unit;
}if(parts[1]){end=((parts[1]=="-="?-1:1)*end)+start;
}e.custom(start,end,unit);
}else{e.custom(start,val,"");
}}});
return true;
});
},queue:function(type,fn){if(jQuery.isFunction(type)||(type&&type.constructor==Array)){fn=type;
type="fx";
}if(!type||(typeof type=="string"&&!fn)){return queue(this[0],type);
}return this.each(function(){if(fn.constructor==Array){queue(this,type,fn);
}else{queue(this,type).push(fn);
if(queue(this,type).length==1){fn.call(this);
}}});
},stop:function(clearQueue,gotoEnd){var timers=jQuery.timers;
if(clearQueue){this.queue([]);
}this.each(function(){for(var i=timers.length-1;
i>=0;
i--){if(timers[i].elem==this){if(gotoEnd){timers[i](true);
}timers.splice(i,1);
}}});
if(!gotoEnd){this.dequeue();
}return this;
}});
var queue=function(elem,type,array){if(elem){type=type||"fx";
var q=jQuery.data(elem,type+"queue");
if(!q||array){q=jQuery.data(elem,type+"queue",jQuery.makeArray(array));
}}return q;
};
jQuery.fn.dequeue=function(type){type=type||"fx";
return this.each(function(){var q=queue(this,type);
q.shift();
if(q.length){q[0].call(this);
}});
};
jQuery.extend({speed:function(speed,easing,fn){var opt=speed&&speed.constructor==Object?speed:{complete:fn||!fn&&easing||jQuery.isFunction(speed)&&speed,duration:speed,easing:fn&&easing||easing&&easing.constructor!=Function&&easing};
opt.duration=(opt.duration&&opt.duration.constructor==Number?opt.duration:jQuery.fx.speeds[opt.duration])||jQuery.fx.speeds.def;
opt.old=opt.complete;
opt.complete=function(){if(opt.queue!==false){jQuery(this).dequeue();
}if(jQuery.isFunction(opt.old)){opt.old.call(this);
}};
return opt;
},easing:{linear:function(p,n,firstNum,diff){return firstNum+diff*p;
},swing:function(p,n,firstNum,diff){return((-Math.cos(p*Math.PI)/2)+0.5)*diff+firstNum;
}},timers:[],timerId:null,fx:function(elem,options,prop){this.options=options;
this.elem=elem;
this.prop=prop;
if(!options.orig){options.orig={};
}}});
jQuery.fx.prototype={update:function(){if(this.options.step){this.options.step.call(this.elem,this.now,this);
}(jQuery.fx.step[this.prop]||jQuery.fx.step._default)(this);
if(this.prop=="height"||this.prop=="width"){this.elem.style.display="block";
}},cur:function(force){if(this.elem[this.prop]!=null&&this.elem.style[this.prop]==null){return this.elem[this.prop];
}var r=parseFloat(jQuery.css(this.elem,this.prop,force));
return r&&r>-10000?r:parseFloat(jQuery.curCSS(this.elem,this.prop))||0;
},custom:function(from,to,unit){this.startTime=now();
this.start=from;
this.end=to;
this.unit=unit||this.unit||"px";
this.now=this.start;
this.pos=this.state=0;
this.update();
var self=this;
function t(gotoEnd){return self.step(gotoEnd);
}t.elem=this.elem;
jQuery.timers.push(t);
if(jQuery.timerId==null){jQuery.timerId=setInterval(function(){var timers=jQuery.timers;
for(var i=0;
i<timers.length;
i++){if(!timers[i]()){timers.splice(i--,1);
}}if(!timers.length){clearInterval(jQuery.timerId);
jQuery.timerId=null;
}},13);
}},show:function(){this.options.orig[this.prop]=jQuery.attr(this.elem.style,this.prop);
this.options.show=true;
this.custom(0,this.cur());
if(this.prop=="width"||this.prop=="height"){this.elem.style[this.prop]="1px";
}jQuery(this.elem).show();
},hide:function(){this.options.orig[this.prop]=jQuery.attr(this.elem.style,this.prop);
this.options.hide=true;
this.custom(this.cur(),0);
},step:function(gotoEnd){var t=now();
if(gotoEnd||t>this.options.duration+this.startTime){this.now=this.end;
this.pos=this.state=1;
this.update();
this.options.curAnim[this.prop]=true;
var done=true;
for(var i in this.options.curAnim){if(this.options.curAnim[i]!==true){done=false;
}}if(done){if(this.options.display!=null){this.elem.style.overflow=this.options.overflow;
this.elem.style.display=this.options.display;
if(jQuery.css(this.elem,"display")=="none"){this.elem.style.display="block";
}}if(this.options.hide){this.elem.style.display="none";
}if(this.options.hide||this.options.show){for(var p in this.options.curAnim){jQuery.attr(this.elem.style,p,this.options.orig[p]);
}}}if(done){this.options.complete.call(this.elem);
}return false;
}else{var n=t-this.startTime;
this.state=n/this.options.duration;
this.pos=jQuery.easing[this.options.easing||(jQuery.easing.swing?"swing":"linear")](this.state,n,0,1,this.options.duration);
this.now=this.start+((this.end-this.start)*this.pos);
this.update();
}return true;
}};
jQuery.extend(jQuery.fx,{speeds:{slow:600,fast:200,def:400},step:{scrollLeft:function(fx){fx.elem.scrollLeft=fx.now;
},scrollTop:function(fx){fx.elem.scrollTop=fx.now;
},opacity:function(fx){jQuery.attr(fx.elem.style,"opacity",fx.now);
},_default:function(fx){fx.elem.style[fx.prop]=fx.now+fx.unit;
}}});
jQuery.fn.offset=function(){var left=0,top=0,elem=this[0],results;
if(elem){with(jQuery.browser){var parent=elem.parentNode,offsetChild=elem,offsetParent=elem.offsetParent,doc=elem.ownerDocument,safari2=safari&&parseInt(version)<522&&!/adobeair/i.test(userAgent),css=jQuery.curCSS,fixed=css(elem,"position")=="fixed";
if(elem.getBoundingClientRect){var box=elem.getBoundingClientRect();
add(box.left+Math.max(doc.documentElement.scrollLeft,doc.body.scrollLeft),box.top+Math.max(doc.documentElement.scrollTop,doc.body.scrollTop));
add(-doc.documentElement.clientLeft,-doc.documentElement.clientTop);
}else{add(elem.offsetLeft,elem.offsetTop);
while(offsetParent){add(offsetParent.offsetLeft,offsetParent.offsetTop);
if(mozilla&&!/^t(able|d|h)$/i.test(offsetParent.tagName)||safari&&!safari2){border(offsetParent);
}if(!fixed&&css(offsetParent,"position")=="fixed"){fixed=true;
}offsetChild=/^body$/i.test(offsetParent.tagName)?offsetChild:offsetParent;
offsetParent=offsetParent.offsetParent;
}while(parent&&parent.tagName&&!/^body|html$/i.test(parent.tagName)){if(!/^inline|table.*$/i.test(css(parent,"display"))){add(-parent.scrollLeft,-parent.scrollTop);
}if(mozilla&&css(parent,"overflow")!="visible"){border(parent);
}parent=parent.parentNode;
}if((safari2&&(fixed||css(offsetChild,"position")=="absolute"))||(mozilla&&css(offsetChild,"position")!="absolute")){add(-doc.body.offsetLeft,-doc.body.offsetTop);
}if(fixed){add(Math.max(doc.documentElement.scrollLeft,doc.body.scrollLeft),Math.max(doc.documentElement.scrollTop,doc.body.scrollTop));
}}results={top:top,left:left};
}}function border(elem){add(jQuery.curCSS(elem,"borderLeftWidth",true),jQuery.curCSS(elem,"borderTopWidth",true));
}function add(l,t){left+=parseInt(l,10)||0;
top+=parseInt(t,10)||0;
}return results;
};
jQuery.fn.extend({position:function(){var left=0,top=0,results;
if(this[0]){var offsetParent=this.offsetParent(),offset=this.offset(),parentOffset=/^body|html$/i.test(offsetParent[0].tagName)?{top:0,left:0}:offsetParent.offset();
offset.top-=num(this,"marginTop");
offset.left-=num(this,"marginLeft");
parentOffset.top+=num(offsetParent,"borderTopWidth");
parentOffset.left+=num(offsetParent,"borderLeftWidth");
results={top:offset.top-parentOffset.top,left:offset.left-parentOffset.left};
}return results;
},offsetParent:function(){var offsetParent=this[0].offsetParent;
while(offsetParent&&(!/^body|html$/i.test(offsetParent.tagName)&&jQuery.css(offsetParent,"position")=="static")){offsetParent=offsetParent.offsetParent;
}return jQuery(offsetParent);
}});
jQuery.each(["Left","Top"],function(i,name){var method="scroll"+name;
jQuery.fn[method]=function(val){if(!this[0]){return ;
}return val!=undefined?this.each(function(){this==window||this==document?window.scrollTo(!i?val:jQuery(window).scrollLeft(),i?val:jQuery(window).scrollTop()):this[method]=val;
}):this[0]==window||this[0]==document?self[i?"pageYOffset":"pageXOffset"]||jQuery.boxModel&&document.documentElement[method]||document.body[method]:this[0][method];
};
});
jQuery.each(["Height","Width"],function(i,name){var tl=i?"Left":"Top",br=i?"Right":"Bottom";
jQuery.fn["inner"+name]=function(){return this[name.toLowerCase()]()+num(this,"padding"+tl)+num(this,"padding"+br);
};
jQuery.fn["outer"+name]=function(margin){return this["inner"+name]()+num(this,"border"+tl+"Width")+num(this,"border"+br+"Width")+(margin?num(this,"margin"+tl)+num(this,"margin"+br):0);
};
});
})();


/* platform.js */
SimileAjax.jQuery=jQuery.noConflict(true);
if(typeof window["$"]=="undefined"){window.$=SimileAjax.jQuery;
}SimileAjax.Platform.os={isMac:false,isWin:false,isWin32:false,isUnix:false};
SimileAjax.Platform.browser={isIE:false,isNetscape:false,isMozilla:false,isFirefox:false,isOpera:false,isSafari:false,majorVersion:0,minorVersion:0};
(function(){var C=navigator.appName.toLowerCase();
var A=navigator.userAgent.toLowerCase();
SimileAjax.Platform.os.isMac=(A.indexOf("mac")!=-1);
SimileAjax.Platform.os.isWin=(A.indexOf("win")!=-1);
SimileAjax.Platform.os.isWin32=SimileAjax.Platform.isWin&&(A.indexOf("95")!=-1||A.indexOf("98")!=-1||A.indexOf("nt")!=-1||A.indexOf("win32")!=-1||A.indexOf("32bit")!=-1);
SimileAjax.Platform.os.isUnix=(A.indexOf("x11")!=-1);
SimileAjax.Platform.browser.isIE=(C.indexOf("microsoft")!=-1);
SimileAjax.Platform.browser.isNetscape=(C.indexOf("netscape")!=-1);
SimileAjax.Platform.browser.isMozilla=(A.indexOf("mozilla")!=-1);
SimileAjax.Platform.browser.isFirefox=(A.indexOf("firefox")!=-1);
SimileAjax.Platform.browser.isOpera=(C.indexOf("opera")!=-1);
SimileAjax.Platform.browser.isSafari=(C.indexOf("safari")!=-1);
var E=function(G){var F=G.split(".");
SimileAjax.Platform.browser.majorVersion=parseInt(F[0]);
SimileAjax.Platform.browser.minorVersion=parseInt(F[1]);
};
var B=function(H,G,I){var F=H.indexOf(G,I);
return F>=0?F:H.length;
};
if(SimileAjax.Platform.browser.isMozilla){var D=A.indexOf("mozilla/");
if(D>=0){E(A.substring(D+8,B(A," ",D)));
}}if(SimileAjax.Platform.browser.isIE){var D=A.indexOf("msie ");
if(D>=0){E(A.substring(D+5,B(A,";",D)));
}}if(SimileAjax.Platform.browser.isNetscape){var D=A.indexOf("rv:");
if(D>=0){E(A.substring(D+3,B(A,")",D)));
}}if(SimileAjax.Platform.browser.isFirefox){var D=A.indexOf("firefox/");
if(D>=0){E(A.substring(D+8,B(A," ",D)));
}}if(!("localeCompare" in String.prototype)){String.prototype.localeCompare=function(F){if(this<F){return -1;
}else{if(this>F){return 1;
}else{return 0;
}}};
}})();
SimileAjax.Platform.getDefaultLocale=function(){return SimileAjax.Platform.clientLocale;
};


/* ajax.js */
SimileAjax.ListenerQueue=function(A){this._listeners=[];
this._wildcardHandlerName=A;
};
SimileAjax.ListenerQueue.prototype.add=function(A){this._listeners.push(A);
};
SimileAjax.ListenerQueue.prototype.remove=function(C){var B=this._listeners;
for(var A=0;
A<B.length;
A++){if(B[A]==C){B.splice(A,1);
break;
}}};
SimileAjax.ListenerQueue.prototype.fire=function(B,A){var D=[].concat(this._listeners);
for(var C=0;
C<D.length;
C++){var E=D[C];
if(B in E){try{E[B].apply(E,A);
}catch(F){SimileAjax.Debug.exception("Error firing event of name "+B,F);
}}else{if(this._wildcardHandlerName!=null&&this._wildcardHandlerName in E){try{E[this._wildcardHandlerName].apply(E,[B]);
}catch(F){SimileAjax.Debug.exception("Error firing event of name "+B+" to wildcard handler",F);
}}}}};


/* data-structure.js */
SimileAjax.Set=function(A){this._hash={};
this._count=0;
if(A instanceof Array){for(var B=0;
B<A.length;
B++){this.add(A[B]);
}}else{if(A instanceof SimileAjax.Set){this.addSet(A);
}}};
SimileAjax.Set.prototype.add=function(A){if(!(A in this._hash)){this._hash[A]=true;
this._count++;
return true;
}return false;
};
SimileAjax.Set.prototype.addSet=function(B){for(var A in B._hash){this.add(A);
}};
SimileAjax.Set.prototype.remove=function(A){if(A in this._hash){delete this._hash[A];
this._count--;
return true;
}return false;
};
SimileAjax.Set.prototype.removeSet=function(B){for(var A in B._hash){this.remove(A);
}};
SimileAjax.Set.prototype.retainSet=function(B){for(var A in this._hash){if(!B.contains(A)){delete this._hash[A];
this._count--;
}}};
SimileAjax.Set.prototype.contains=function(A){return(A in this._hash);
};
SimileAjax.Set.prototype.size=function(){return this._count;
};
SimileAjax.Set.prototype.toArray=function(){var A=[];
for(var B in this._hash){A.push(B);
}return A;
};
SimileAjax.Set.prototype.visit=function(A){for(var B in this._hash){if(A(B)==true){break;
}}};
SimileAjax.SortedArray=function(B,A){this._a=(A instanceof Array)?A:[];
this._compare=B;
};
SimileAjax.SortedArray.prototype.add=function(C){var A=this;
var B=this.find(function(D){return A._compare(D,C);
});
if(B<this._a.length){this._a.splice(B,0,C);
}else{this._a.push(C);
}};
SimileAjax.SortedArray.prototype.remove=function(C){var A=this;
var B=this.find(function(D){return A._compare(D,C);
});
while(B<this._a.length&&this._compare(this._a[B],C)==0){if(this._a[B]==C){this._a.splice(B,1);
return true;
}else{B++;
}}return false;
};
SimileAjax.SortedArray.prototype.removeAll=function(){this._a=[];
};
SimileAjax.SortedArray.prototype.elementAt=function(A){return this._a[A];
};
SimileAjax.SortedArray.prototype.length=function(){return this._a.length;
};
SimileAjax.SortedArray.prototype.find=function(D){var B=0;
var A=this._a.length;
while(B<A){var C=Math.floor((B+A)/2);
var E=D(this._a[C]);
if(C==B){return E<0?B+1:B;
}else{if(E<0){B=C;
}else{A=C;
}}}return B;
};
SimileAjax.SortedArray.prototype.getFirst=function(){return(this._a.length>0)?this._a[0]:null;
};
SimileAjax.SortedArray.prototype.getLast=function(){return(this._a.length>0)?this._a[this._a.length-1]:null;
};
SimileAjax.EventIndex=function(B){var A=this;
this._unit=(B!=null)?B:SimileAjax.NativeDateUnit;
this._events=new SimileAjax.SortedArray(function(D,C){return A._unit.compare(D.getStart(),C.getStart());
});
this._idToEvent={};
this._indexed=true;
};
SimileAjax.EventIndex.prototype.getUnit=function(){return this._unit;
};
SimileAjax.EventIndex.prototype.getEvent=function(A){return this._idToEvent[A];
};
SimileAjax.EventIndex.prototype.add=function(A){this._events.add(A);
this._idToEvent[A.getID()]=A;
this._indexed=false;
};
SimileAjax.EventIndex.prototype.removeAll=function(){this._events.removeAll();
this._idToEvent={};
this._indexed=false;
};
SimileAjax.EventIndex.prototype.getCount=function(){return this._events.length();
};
SimileAjax.EventIndex.prototype.getIterator=function(A,B){if(!this._indexed){this._index();
}return new SimileAjax.EventIndex._Iterator(this._events,A,B,this._unit);
};
SimileAjax.EventIndex.prototype.getReverseIterator=function(A,B){if(!this._indexed){this._index();
}return new SimileAjax.EventIndex._ReverseIterator(this._events,A,B,this._unit);
};
SimileAjax.EventIndex.prototype.getAllIterator=function(){return new SimileAjax.EventIndex._AllIterator(this._events);
};
SimileAjax.EventIndex.prototype.getEarliestDate=function(){var A=this._events.getFirst();
return(A==null)?null:A.getStart();
};
SimileAjax.EventIndex.prototype.getLatestDate=function(){var A=this._events.getLast();
if(A==null){return null;
}if(!this._indexed){this._index();
}var C=A._earliestOverlapIndex;
var B=this._events.elementAt(C).getEnd();
for(var D=C+1;
D<this._events.length();
D++){B=this._unit.later(B,this._events.elementAt(D).getEnd());
}return B;
};
SimileAjax.EventIndex.prototype._index=function(){var D=this._events.length();
for(var E=0;
E<D;
E++){var C=this._events.elementAt(E);
C._earliestOverlapIndex=E;
}var G=1;
for(var E=0;
E<D;
E++){var C=this._events.elementAt(E);
var B=C.getEnd();
G=Math.max(G,E+1);
while(G<D){var A=this._events.elementAt(G);
var F=A.getStart();
if(this._unit.compare(F,B)<0){A._earliestOverlapIndex=E;
G++;
}else{break;
}}}this._indexed=true;
};
SimileAjax.EventIndex._Iterator=function(B,A,D,C){this._events=B;
this._startDate=A;
this._endDate=D;
this._unit=C;
this._currentIndex=B.find(function(E){return C.compare(E.getStart(),A);
});
if(this._currentIndex-1>=0){this._currentIndex=this._events.elementAt(this._currentIndex-1)._earliestOverlapIndex;
}this._currentIndex--;
this._maxIndex=B.find(function(E){return C.compare(E.getStart(),D);
});
this._hasNext=false;
this._next=null;
this._findNext();
};
SimileAjax.EventIndex._Iterator.prototype={hasNext:function(){return this._hasNext;
},next:function(){if(this._hasNext){var A=this._next;
this._findNext();
return A;
}else{return null;
}},_findNext:function(){var B=this._unit;
while((++this._currentIndex)<this._maxIndex){var A=this._events.elementAt(this._currentIndex);
if(B.compare(A.getStart(),this._endDate)<0&&B.compare(A.getEnd(),this._startDate)>0){this._next=A;
this._hasNext=true;
return ;
}}this._next=null;
this._hasNext=false;
}};
SimileAjax.EventIndex._ReverseIterator=function(B,A,D,C){this._events=B;
this._startDate=A;
this._endDate=D;
this._unit=C;
this._minIndex=B.find(function(E){return C.compare(E.getStart(),A);
});
if(this._minIndex-1>=0){this._minIndex=this._events.elementAt(this._minIndex-1)._earliestOverlapIndex;
}this._maxIndex=B.find(function(E){return C.compare(E.getStart(),D);
});
this._currentIndex=this._maxIndex;
this._hasNext=false;
this._next=null;
this._findNext();
};
SimileAjax.EventIndex._ReverseIterator.prototype={hasNext:function(){return this._hasNext;
},next:function(){if(this._hasNext){var A=this._next;
this._findNext();
return A;
}else{return null;
}},_findNext:function(){var B=this._unit;
while((--this._currentIndex)>=this._minIndex){var A=this._events.elementAt(this._currentIndex);
if(B.compare(A.getStart(),this._endDate)<0&&B.compare(A.getEnd(),this._startDate)>0){this._next=A;
this._hasNext=true;
return ;
}}this._next=null;
this._hasNext=false;
}};
SimileAjax.EventIndex._AllIterator=function(A){this._events=A;
this._index=0;
};
SimileAjax.EventIndex._AllIterator.prototype={hasNext:function(){return this._index<this._events.length();
},next:function(){return this._index<this._events.length()?this._events.elementAt(this._index++):null;
}};


/* date-time.js */
SimileAjax.DateTime=new Object();
SimileAjax.DateTime.MILLISECOND=0;
SimileAjax.DateTime.SECOND=1;
SimileAjax.DateTime.MINUTE=2;
SimileAjax.DateTime.HOUR=3;
SimileAjax.DateTime.DAY=4;
SimileAjax.DateTime.WEEK=5;
SimileAjax.DateTime.MONTH=6;
SimileAjax.DateTime.YEAR=7;
SimileAjax.DateTime.DECADE=8;
SimileAjax.DateTime.CENTURY=9;
SimileAjax.DateTime.MILLENNIUM=10;
SimileAjax.DateTime.EPOCH=-1;
SimileAjax.DateTime.ERA=-2;
SimileAjax.DateTime.gregorianUnitLengths=[];
(function(){var B=SimileAjax.DateTime;
var A=B.gregorianUnitLengths;
A[B.MILLISECOND]=1;
A[B.SECOND]=1000;
A[B.MINUTE]=A[B.SECOND]*60;
A[B.HOUR]=A[B.MINUTE]*60;
A[B.DAY]=A[B.HOUR]*24;
A[B.WEEK]=A[B.DAY]*7;
A[B.MONTH]=A[B.DAY]*31;
A[B.YEAR]=A[B.DAY]*365;
A[B.DECADE]=A[B.YEAR]*10;
A[B.CENTURY]=A[B.YEAR]*100;
A[B.MILLENNIUM]=A[B.YEAR]*1000;
})();
SimileAjax.DateTime._dateRegexp=new RegExp("^(-?)([0-9]{4})("+["(-?([0-9]{2})(-?([0-9]{2}))?)","(-?([0-9]{3}))","(-?W([0-9]{2})(-?([1-7]))?)"].join("|")+")?$");
SimileAjax.DateTime._timezoneRegexp=new RegExp("Z|(([-+])([0-9]{2})(:?([0-9]{2}))?)$");
SimileAjax.DateTime._timeRegexp=new RegExp("^([0-9]{2})(:?([0-9]{2})(:?([0-9]{2})(.([0-9]+))?)?)?$");
SimileAjax.DateTime.setIso8601Date=function(H,F){var I=F.match(SimileAjax.DateTime._dateRegexp);
if(!I){throw new Error("Invalid date string: "+F);
}var B=(I[1]=="-")?-1:1;
var J=B*I[2];
var G=I[5];
var C=I[7];
var E=I[9];
var A=I[11];
var M=(I[13])?I[13]:1;
H.setUTCFullYear(J);
if(E){H.setUTCMonth(0);
H.setUTCDate(Number(E));
}else{if(A){H.setUTCMonth(0);
H.setUTCDate(1);
var L=H.getUTCDay();
var K=(L)?L:7;
var D=Number(M)+(7*Number(A));
if(K<=4){H.setUTCDate(D+1-K);
}else{H.setUTCDate(D+8-K);
}}else{if(G){H.setUTCDate(1);
H.setUTCMonth(G-1);
}if(C){H.setUTCDate(C);
}}}return H;
};
SimileAjax.DateTime.setIso8601Time=function(F,C){var G=C.match(SimileAjax.DateTime._timeRegexp);
if(!G){SimileAjax.Debug.warn("Invalid time string: "+C);
return false;
}var A=G[1];
var E=Number((G[3])?G[3]:0);
var D=(G[5])?G[5]:0;
var B=G[7]?(Number("0."+G[7])*1000):0;
F.setUTCHours(A);
F.setUTCMinutes(E);
F.setUTCSeconds(D);
F.setUTCMilliseconds(B);
return F;
};
SimileAjax.DateTime.timezoneOffset=new Date().getTimezoneOffset();
SimileAjax.DateTime.setIso8601=function(B,A){var D=null;
var E=(A.indexOf("T")==-1)?A.split(" "):A.split("T");
SimileAjax.DateTime.setIso8601Date(B,E[0]);
if(E.length==2){var C=E[1].match(SimileAjax.DateTime._timezoneRegexp);
if(C){if(C[0]=="Z"){D=0;
}else{D=(Number(C[3])*60)+Number(C[5]);
D*=((C[2]=="-")?1:-1);
}E[1]=E[1].substr(0,E[1].length-C[0].length);
}SimileAjax.DateTime.setIso8601Time(B,E[1]);
}if(D==null){D=B.getTimezoneOffset();
}B.setTime(B.getTime()+D*60000);
return B;
};
SimileAjax.DateTime.parseIso8601DateTime=function(A){try{return SimileAjax.DateTime.setIso8601(new Date(0),A);
}catch(B){return null;
}};
SimileAjax.DateTime.parseGregorianDateTime=function(G){if(G==null){return null;
}else{if(G instanceof Date){return G;
}}var B=G.toString();
if(B.length>0&&B.length<8){var C=B.indexOf(" ");
if(C>0){var A=parseInt(B.substr(0,C));
var E=B.substr(C+1);
if(E.toLowerCase()=="bc"){A=1-A;
}}else{var A=parseInt(B);
}var F=new Date(0);
F.setUTCFullYear(A);
return F;
}try{return new Date(Date.parse(B));
}catch(D){return null;
}};
SimileAjax.DateTime.roundDownToInterval=function(B,G,J,K,A){var D=J*SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.HOUR];
var I=new Date(B.getTime()+D);
var E=function(L){L.setUTCMilliseconds(0);
L.setUTCSeconds(0);
L.setUTCMinutes(0);
L.setUTCHours(0);
};
var C=function(L){E(L);
L.setUTCDate(1);
L.setUTCMonth(0);
};
switch(G){case SimileAjax.DateTime.MILLISECOND:var H=I.getUTCMilliseconds();
I.setUTCMilliseconds(H-(H%K));
break;
case SimileAjax.DateTime.SECOND:I.setUTCMilliseconds(0);
var H=I.getUTCSeconds();
I.setUTCSeconds(H-(H%K));
break;
case SimileAjax.DateTime.MINUTE:I.setUTCMilliseconds(0);
I.setUTCSeconds(0);
var H=I.getUTCMinutes();
I.setTime(I.getTime()-(H%K)*SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.MINUTE]);
break;
case SimileAjax.DateTime.HOUR:I.setUTCMilliseconds(0);
I.setUTCSeconds(0);
I.setUTCMinutes(0);
var H=I.getUTCHours();
I.setUTCHours(H-(H%K));
break;
case SimileAjax.DateTime.DAY:E(I);
break;
case SimileAjax.DateTime.WEEK:E(I);
var F=(I.getUTCDay()+7-A)%7;
I.setTime(I.getTime()-F*SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.DAY]);
break;
case SimileAjax.DateTime.MONTH:E(I);
I.setUTCDate(1);
var H=I.getUTCMonth();
I.setUTCMonth(H-(H%K));
break;
case SimileAjax.DateTime.YEAR:C(I);
var H=I.getUTCFullYear();
I.setUTCFullYear(H-(H%K));
break;
case SimileAjax.DateTime.DECADE:C(I);
I.setUTCFullYear(Math.floor(I.getUTCFullYear()/10)*10);
break;
case SimileAjax.DateTime.CENTURY:C(I);
I.setUTCFullYear(Math.floor(I.getUTCFullYear()/100)*100);
break;
case SimileAjax.DateTime.MILLENNIUM:C(I);
I.setUTCFullYear(Math.floor(I.getUTCFullYear()/1000)*1000);
break;
}B.setTime(I.getTime()-D);
};
SimileAjax.DateTime.roundUpToInterval=function(D,F,C,A,B){var E=D.getTime();
SimileAjax.DateTime.roundDownToInterval(D,F,C,A,B);
if(D.getTime()<E){D.setTime(D.getTime()+SimileAjax.DateTime.gregorianUnitLengths[F]*A);
}};
SimileAjax.DateTime.incrementByInterval=function(B,E,A){A=(typeof A=="undefined")?0:A;
var D=A*SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.HOUR];
var C=new Date(B.getTime()+D);
switch(E){case SimileAjax.DateTime.MILLISECOND:C.setTime(C.getTime()+1);
break;
case SimileAjax.DateTime.SECOND:C.setTime(C.getTime()+1000);
break;
case SimileAjax.DateTime.MINUTE:C.setTime(C.getTime()+SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.MINUTE]);
break;
case SimileAjax.DateTime.HOUR:C.setTime(C.getTime()+SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.HOUR]);
break;
case SimileAjax.DateTime.DAY:C.setUTCDate(C.getUTCDate()+1);
break;
case SimileAjax.DateTime.WEEK:C.setUTCDate(C.getUTCDate()+7);
break;
case SimileAjax.DateTime.MONTH:C.setUTCMonth(C.getUTCMonth()+1);
break;
case SimileAjax.DateTime.YEAR:C.setUTCFullYear(C.getUTCFullYear()+1);
break;
case SimileAjax.DateTime.DECADE:C.setUTCFullYear(C.getUTCFullYear()+10);
break;
case SimileAjax.DateTime.CENTURY:C.setUTCFullYear(C.getUTCFullYear()+100);
break;
case SimileAjax.DateTime.MILLENNIUM:C.setUTCFullYear(C.getUTCFullYear()+1000);
break;
}B.setTime(C.getTime()-D);
};
SimileAjax.DateTime.removeTimeZoneOffset=function(B,A){return new Date(B.getTime()+A*SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.HOUR]);
};
SimileAjax.DateTime.getTimezone=function(){var A=new Date().getTimezoneOffset();
return A/-60;
};


/* debug.js */
SimileAjax.Debug={silent:false};
SimileAjax.Debug.log=function(B){var A;
if("console" in window&&"log" in window.console){A=function(C){console.log(C);
};
}else{A=function(C){if(!SimileAjax.Debug.silent){alert(C);
}};
}SimileAjax.Debug.log=A;
A(B);
};
SimileAjax.Debug.warn=function(B){var A;
if("console" in window&&"warn" in window.console){A=function(C){console.warn(C);
};
}else{A=function(C){if(!SimileAjax.Debug.silent){alert(C);
}};
}SimileAjax.Debug.warn=A;
A(B);
};
SimileAjax.Debug.exception=function(B,D){var A,C=SimileAjax.parseURLParameters();
if(C.errors=="throw"||SimileAjax.params.errors=="throw"){A=function(F,E){throw (F);
};
}else{if("console" in window&&"error" in window.console){A=function(F,E){if(E!=null){console.error(E+" %o",F);
}else{console.error(F);
}throw (F);
};
}else{A=function(F,E){if(!SimileAjax.Debug.silent){alert("Caught exception: "+E+"\n\nDetails: "+("description" in F?F.description:F));
}throw (F);
};
}}SimileAjax.Debug.exception=A;
A(B,D);
};
SimileAjax.Debug.objectToString=function(A){return SimileAjax.Debug._objectToString(A,"");
};
SimileAjax.Debug._objectToString=function(D,A){var C=A+" ";
if(typeof D=="object"){var B="{";
for(E in D){B+=C+E+": "+SimileAjax.Debug._objectToString(D[E],C)+"\n";
}B+=A+"}";
return B;
}else{if(typeof D=="array"){var B="[";
for(var E=0;
E<D.length;
E++){B+=SimileAjax.Debug._objectToString(D[E],C)+"\n";
}B+=A+"]";
return B;
}else{return D;
}}};


/* dom.js */
SimileAjax.DOM=new Object();
SimileAjax.DOM.registerEventWithObject=function(C,A,D,B){SimileAjax.DOM.registerEvent(C,A,function(F,E,G){return D[B].call(D,F,E,G);
});
};
SimileAjax.DOM.registerEvent=function(C,B,D){var A=function(E){E=(E)?E:((event)?event:null);
if(E){var F=(E.target)?E.target:((E.srcElement)?E.srcElement:null);
if(F){F=(F.nodeType==1||F.nodeType==9)?F:F.parentNode;
}return D(C,E,F);
}return true;
};
if(SimileAjax.Platform.browser.isIE){C.attachEvent("on"+B,A);
}else{C.addEventListener(B,A,false);
}};
SimileAjax.DOM.getPageCoordinates=function(B){var E=0;
var D=0;
if(B.nodeType!=1){B=B.parentNode;
}var C=B;
while(C!=null){E+=C.offsetLeft;
D+=C.offsetTop;
C=C.offsetParent;
}var A=document.body;
while(B!=null&&B!=A){if("scrollLeft" in B){E-=B.scrollLeft;
D-=B.scrollTop;
}B=B.parentNode;
}return{left:E,top:D};
};
SimileAjax.DOM.getSize=function(B){var A=this.getStyle(B,"width");
var C=this.getStyle(B,"height");
if(A.indexOf("px")>-1){A=A.replace("px","");
}if(C.indexOf("px")>-1){C=C.replace("px","");
}return{w:A,h:C};
};
SimileAjax.DOM.getStyle=function(B,A){if(B.currentStyle){var C=B.currentStyle[A];
}else{if(window.getComputedStyle){var C=document.defaultView.getComputedStyle(B,null).getPropertyValue(A);
}else{var C="";
}}return C;
};
SimileAjax.DOM.getEventRelativeCoordinates=function(A,B){if(SimileAjax.Platform.browser.isIE){if(A.type=="mousewheel"){var C=SimileAjax.DOM.getPageCoordinates(B);
return{x:A.clientX-C.left,y:A.clientY-C.top};
}else{return{x:A.offsetX,y:A.offsetY};
}}else{var C=SimileAjax.DOM.getPageCoordinates(B);
if((A.type=="DOMMouseScroll")&&SimileAjax.Platform.browser.isFirefox&&(SimileAjax.Platform.browser.majorVersion==2)){return{x:A.screenX-C.left,y:A.screenY-C.top};
}else{return{x:A.pageX-C.left,y:A.pageY-C.top};
}}};
SimileAjax.DOM.getEventPageCoordinates=function(A){if(SimileAjax.Platform.browser.isIE){return{x:A.clientX+document.body.scrollLeft,y:A.clientY+document.body.scrollTop};
}else{return{x:A.pageX,y:A.pageY};
}};
SimileAjax.DOM.hittest=function(A,C,B){return SimileAjax.DOM._hittest(document.body,A,C,B);
};
SimileAjax.DOM._hittest=function(C,L,K,H){var M=C.childNodes;
outer:for(var G=0;
G<M.length;
G++){var A=M[G];
for(var F=0;
F<H.length;
F++){if(A==H[F]){continue outer;
}}if(A.offsetWidth==0&&A.offsetHeight==0){var B=SimileAjax.DOM._hittest(A,L,K,H);
if(B!=A){return B;
}}else{var J=0;
var E=0;
var D=A;
while(D){J+=D.offsetTop;
E+=D.offsetLeft;
D=D.offsetParent;
}if(E<=L&&J<=K&&(L-E)<A.offsetWidth&&(K-J)<A.offsetHeight){return SimileAjax.DOM._hittest(A,L,K,H);
}else{if(A.nodeType==1&&A.tagName=="TR"){var I=SimileAjax.DOM._hittest(A,L,K,H);
if(I!=A){return I;
}}}}}return C;
};
SimileAjax.DOM.cancelEvent=function(A){A.returnValue=false;
A.cancelBubble=true;
if("preventDefault" in A){A.preventDefault();
}};
SimileAjax.DOM.appendClassName=function(C,D){var B=C.className.split(" ");
for(var A=0;
A<B.length;
A++){if(B[A]==D){return ;
}}B.push(D);
C.className=B.join(" ");
};
SimileAjax.DOM.createInputElement=function(A){var B=document.createElement("div");
B.innerHTML="<input type='"+A+"' />";
return B.firstChild;
};
SimileAjax.DOM.createDOMFromTemplate=function(B){var A={};
A.elmt=SimileAjax.DOM._createDOMFromTemplate(B,A,null);
return A;
};
SimileAjax.DOM._createDOMFromTemplate=function(A,I,E){if(A==null){return null;
}else{if(typeof A!="object"){var D=document.createTextNode(A);
if(E!=null){E.appendChild(D);
}return D;
}else{var C=null;
if("tag" in A){var J=A.tag;
if(E!=null){if(J=="tr"){C=E.insertRow(E.rows.length);
}else{if(J=="td"){C=E.insertCell(E.cells.length);
}}}if(C==null){C=J=="input"?SimileAjax.DOM.createInputElement(A.type):document.createElement(J);
if(E!=null){E.appendChild(C);
}}}else{C=A.elmt;
if(E!=null){E.appendChild(C);
}}for(var B in A){var G=A[B];
if(B=="field"){I[G]=C;
}else{if(B=="className"){C.className=G;
}else{if(B=="id"){C.id=G;
}else{if(B=="title"){C.title=G;
}else{if(B=="type"&&C.tagName=="input"){}else{if(B=="style"){for(n in G){var H=G[n];
if(n=="float"){n=SimileAjax.Platform.browser.isIE?"styleFloat":"cssFloat";
}C.style[n]=H;
}}else{if(B=="children"){for(var F=0;
F<G.length;
F++){SimileAjax.DOM._createDOMFromTemplate(G[F],I,C);
}}else{if(B!="tag"&&B!="elmt"){C.setAttribute(B,G);
}}}}}}}}}return C;
}}};
SimileAjax.DOM._cachedParent=null;
SimileAjax.DOM.createElementFromString=function(A){if(SimileAjax.DOM._cachedParent==null){SimileAjax.DOM._cachedParent=document.createElement("div");
}SimileAjax.DOM._cachedParent.innerHTML=A;
return SimileAjax.DOM._cachedParent.firstChild;
};
SimileAjax.DOM.createDOMFromString=function(A,C,D){var B=typeof A=="string"?document.createElement(A):A;
B.innerHTML=C;
var E={elmt:B};
SimileAjax.DOM._processDOMChildrenConstructedFromString(E,B,D!=null?D:{});
return E;
};
SimileAjax.DOM._processDOMConstructedFromString=function(D,A,B){var E=A.id;
if(E!=null&&E.length>0){A.removeAttribute("id");
if(E in B){var C=A.parentNode;
C.insertBefore(B[E],A);
C.removeChild(A);
D[E]=B[E];
return ;
}else{D[E]=A;
}}if(A.hasChildNodes()){SimileAjax.DOM._processDOMChildrenConstructedFromString(D,A,B);
}};
SimileAjax.DOM._processDOMChildrenConstructedFromString=function(E,B,D){var C=B.firstChild;
while(C!=null){var A=C.nextSibling;
if(C.nodeType==1){SimileAjax.DOM._processDOMConstructedFromString(E,C,D);
}C=A;
}};


/* graphics.js */
SimileAjax.Graphics=new Object();
SimileAjax.Graphics.pngIsTranslucent=(!SimileAjax.Platform.browser.isIE)||(SimileAjax.Platform.browser.majorVersion>6);
SimileAjax.Graphics._createTranslucentImage1=function(A,C){var B=document.createElement("img");
B.setAttribute("src",A);
if(C!=null){B.style.verticalAlign=C;
}return B;
};
SimileAjax.Graphics._createTranslucentImage2=function(A,C){var B=document.createElement("img");
B.style.width="1px";
B.style.height="1px";
B.style.filter="progid:DXImageTransform.Microsoft.AlphaImageLoader(src='"+A+"', sizingMethod='image')";
B.style.verticalAlign=(C!=null)?C:"middle";
return B;
};
SimileAjax.Graphics.createTranslucentImage=SimileAjax.Graphics.pngIsTranslucent?SimileAjax.Graphics._createTranslucentImage1:SimileAjax.Graphics._createTranslucentImage2;
SimileAjax.Graphics._createTranslucentImageHTML1=function(A,B){return'<img src="'+A+'"'+(B!=null?' style="vertical-align: '+B+';"':"")+" />";
};
SimileAjax.Graphics._createTranslucentImageHTML2=function(A,C){var B="width: 1px; height: 1px; filter:progid:DXImageTransform.Microsoft.AlphaImageLoader(src='"+A+"', sizingMethod='image');"+(C!=null?" vertical-align: "+C+";":"");
return"<img src='"+A+"' style=\""+B+'" />';
};
SimileAjax.Graphics.createTranslucentImageHTML=SimileAjax.Graphics.pngIsTranslucent?SimileAjax.Graphics._createTranslucentImageHTML1:SimileAjax.Graphics._createTranslucentImageHTML2;
SimileAjax.Graphics.setOpacity=function(B,A){if(SimileAjax.Platform.browser.isIE){B.style.filter="progid:DXImageTransform.Microsoft.Alpha(Style=0,Opacity="+A+")";
}else{var C=(A/100).toString();
B.style.opacity=C;
B.style.MozOpacity=C;
}};
SimileAjax.Graphics._bubbleMargins={top:33,bottom:42,left:33,right:40};
SimileAjax.Graphics._arrowOffsets={top:0,bottom:9,left:1,right:8};
SimileAjax.Graphics._bubblePadding=15;
SimileAjax.Graphics._bubblePointOffset=6;
SimileAjax.Graphics._halfArrowWidth=18;
SimileAjax.Graphics.createBubbleForContentAndPoint=function(E,D,C,A,B){if(typeof A!="number"){A=300;
}E.style.position="absolute";
E.style.left="-5000px";
E.style.top="0px";
E.style.width=A+"px";
document.body.appendChild(E);
window.setTimeout(function(){var H=E.scrollWidth+10;
var F=E.scrollHeight+10;
var G=SimileAjax.Graphics.createBubbleForPoint(D,C,H,F,B);
document.body.removeChild(E);
E.style.position="static";
E.style.left="";
E.style.top="";
E.style.width=H+"px";
G.content.appendChild(E);
},200);
};
SimileAjax.Graphics.createBubbleForPoint=function(C,B,N,R,F){function T(){if(typeof window.innerHeight=="number"){return{w:window.innerWidth,h:window.innerHeight};
}else{if(document.documentElement&&document.documentElement.clientHeight){return{w:document.documentElement.clientWidth,h:document.documentElement.clientHeight};
}else{if(document.body&&document.body.clientHeight){return{w:document.body.clientWidth,h:document.body.clientHeight};
}}}}var L=function(){if(!M._closed){document.body.removeChild(M._div);
M._doc=null;
M._div=null;
M._content=null;
M._closed=true;
}};
var M={_closed:false};
var O=T();
var H=O.w;
var G=O.h;
var D=SimileAjax.Graphics._bubbleMargins;
N=parseInt(N,10);
R=parseInt(R,10);
var P=D.left+N+D.right;
var U=D.top+R+D.bottom;
var Q=SimileAjax.Graphics.pngIsTranslucent;
var J=SimileAjax.urlPrefix;
var A=function(Z,Y,a,X){Z.style.position="absolute";
Z.style.width=a+"px";
Z.style.height=X+"px";
if(Q){Z.style.background="url("+Y+")";
}else{Z.style.filter="progid:DXImageTransform.Microsoft.AlphaImageLoader(src='"+Y+"', sizingMethod='crop')";
}};
var K=document.createElement("div");
K.style.width=P+"px";
K.style.height=U+"px";
K.style.position="absolute";
K.style.zIndex=1000;
var W=SimileAjax.WindowManager.pushLayer(L,true,K);
M._div=K;
M.close=function(){SimileAjax.WindowManager.popLayer(W);
};
var I=document.createElement("div");
I.style.width="100%";
I.style.height="100%";
I.style.position="relative";
K.appendChild(I);
var S=function(Z,c,b,a,Y){var X=document.createElement("div");
X.style.left=c+"px";
X.style.top=b+"px";
A(X,Z,a,Y);
I.appendChild(X);
};
S(J+"data/timeline/bubble-top-left.png",0,0,D.left,D.top);
S(J+"data/timeline/bubble-top.png",D.left,0,N,D.top);
S(J+"data/timeline/bubble-top-right.png",D.left+N,0,D.right,D.top);
S(J+"data/timeline/bubble-left.png",0,D.top,D.left,R);
S(J+"data/timeline/bubble-right.png",D.left+N,D.top,D.right,R);
S(J+"data/timeline/bubble-bottom-left.png",0,D.top+R,D.left,D.bottom);
S(J+"data/timeline/bubble-bottom.png",D.left,D.top+R,N,D.bottom);
S(J+"data/timeline/bubble-bottom-right.png",D.left+N,D.top+R,D.right,D.bottom);
var V=document.createElement("div");
V.style.left=(P-D.right+SimileAjax.Graphics._bubblePadding-16-2)+"px";
V.style.top=(D.top-SimileAjax.Graphics._bubblePadding+1)+"px";
V.style.cursor="pointer";
A(V,J+"data/timeline/close-button.png",16,16);
SimileAjax.WindowManager.registerEventWithObject(V,"click",M,"close");
I.appendChild(V);
var E=document.createElement("div");
E.style.position="absolute";
E.style.left=D.left+"px";
E.style.top=D.top+"px";
E.style.width=N+"px";
E.style.height=R+"px";
E.style.overflow="auto";
E.style.background="white";
I.appendChild(E);
M.content=E;
(function(){if(C-SimileAjax.Graphics._halfArrowWidth-SimileAjax.Graphics._bubblePadding>0&&C+SimileAjax.Graphics._halfArrowWidth+SimileAjax.Graphics._bubblePadding<H){var Z=C-Math.round(N/2)-D.left;
Z=C<(H/2)?Math.max(Z,-(D.left-SimileAjax.Graphics._bubblePadding)):Math.min(Z,H+(D.right-SimileAjax.Graphics._bubblePadding)-P);
if((F&&F=="top")||(!F&&(B-SimileAjax.Graphics._bubblePointOffset-U>0))){var X=document.createElement("div");
X.style.left=(C-SimileAjax.Graphics._halfArrowWidth-Z)+"px";
X.style.top=(D.top+R)+"px";
A(X,J+"data/timeline/bubble-bottom-arrow.png",37,D.bottom);
I.appendChild(X);
K.style.left=Z+"px";
K.style.top=(B-SimileAjax.Graphics._bubblePointOffset-U+SimileAjax.Graphics._arrowOffsets.bottom)+"px";
return ;
}else{if((F&&F=="bottom")||(!F&&(B+SimileAjax.Graphics._bubblePointOffset+U<G))){var X=document.createElement("div");
X.style.left=(C-SimileAjax.Graphics._halfArrowWidth-Z)+"px";
X.style.top="0px";
A(X,J+"data/timeline/bubble-top-arrow.png",37,D.top);
I.appendChild(X);
K.style.left=Z+"px";
K.style.top=(B+SimileAjax.Graphics._bubblePointOffset-SimileAjax.Graphics._arrowOffsets.top)+"px";
return ;
}}}var Y=B-Math.round(R/2)-D.top;
Y=B<(G/2)?Math.max(Y,-(D.top-SimileAjax.Graphics._bubblePadding)):Math.min(Y,G+(D.bottom-SimileAjax.Graphics._bubblePadding)-U);
if((F&&F=="left")||(!F&&(C-SimileAjax.Graphics._bubblePointOffset-P>0))){var X=document.createElement("div");
X.style.left=(D.left+N)+"px";
X.style.top=(B-SimileAjax.Graphics._halfArrowWidth-Y)+"px";
A(X,J+"data/timeline/bubble-right-arrow.png",D.right,37);
I.appendChild(X);
K.style.left=(C-SimileAjax.Graphics._bubblePointOffset-P+SimileAjax.Graphics._arrowOffsets.right)+"px";
K.style.top=Y+"px";
}else{if((F&&F=="right")||(!F&&(C-SimileAjax.Graphics._bubblePointOffset-P<H))){var X=document.createElement("div");
X.style.left="0px";
X.style.top=(B-SimileAjax.Graphics._halfArrowWidth-Y)+"px";
A(X,J+"data/timeline/bubble-left-arrow.png",D.left,37);
I.appendChild(X);
K.style.left=(C+SimileAjax.Graphics._bubblePointOffset-SimileAjax.Graphics._arrowOffsets.left)+"px";
K.style.top=Y+"px";
}}})();
document.body.appendChild(K);
return M;
};
SimileAjax.Graphics.createMessageBubble=function(H){var G=H.createElement("div");
if(SimileAjax.Graphics.pngIsTranslucent){var I=H.createElement("div");
I.style.height="33px";
I.style.background="url("+SimileAjax.urlPrefix+"data/timeline/message-top-left.png) top left no-repeat";
I.style.paddingLeft="44px";
G.appendChild(I);
var C=H.createElement("div");
C.style.height="33px";
C.style.background="url("+SimileAjax.urlPrefix+"data/timeline/message-top-right.png) top right no-repeat";
I.appendChild(C);
var F=H.createElement("div");
F.style.background="url("+SimileAjax.urlPrefix+"data/timeline/message-left.png) top left repeat-y";
F.style.paddingLeft="44px";
G.appendChild(F);
var A=H.createElement("div");
A.style.background="url("+SimileAjax.urlPrefix+"data/timeline/message-right.png) top right repeat-y";
A.style.paddingRight="44px";
F.appendChild(A);
var D=H.createElement("div");
A.appendChild(D);
var B=H.createElement("div");
B.style.height="55px";
B.style.background="url("+SimileAjax.urlPrefix+"data/timeline/message-bottom-left.png) bottom left no-repeat";
B.style.paddingLeft="44px";
G.appendChild(B);
var E=H.createElement("div");
E.style.height="55px";
E.style.background="url("+SimileAjax.urlPrefix+"data/timeline/message-bottom-right.png) bottom right no-repeat";
B.appendChild(E);
}else{G.style.border="2px solid #7777AA";
G.style.padding="20px";
G.style.background="white";
SimileAjax.Graphics.setOpacity(G,90);
var D=H.createElement("div");
G.appendChild(D);
}return{containerDiv:G,contentDiv:D};
};
SimileAjax.Graphics.createAnimation=function(B,E,D,C,A){return new SimileAjax.Graphics._Animation(B,E,D,C,A);
};
SimileAjax.Graphics._Animation=function(B,E,D,C,A){this.f=B;
this.cont=(typeof A=="function")?A:function(){};
this.from=E;
this.to=D;
this.current=E;
this.duration=C;
this.start=new Date().getTime();
this.timePassed=0;
};
SimileAjax.Graphics._Animation.prototype.run=function(){var A=this;
window.setTimeout(function(){A.step();
},50);
};
SimileAjax.Graphics._Animation.prototype.step=function(){this.timePassed+=50;
var B=this.timePassed/this.duration;
var A=-Math.cos(B*Math.PI)/2+0.5;
var D=A*(this.to-this.from)+this.from;
try{this.f(D,D-this.current);
}catch(C){}this.current=D;
if(this.timePassed<this.duration){this.run();
}else{this.f(this.to,0);
this["cont"]();
}};
SimileAjax.Graphics.createStructuredDataCopyButton=function(F,D,A,E){var G=document.createElement("div");
G.style.position="relative";
G.style.display="inline";
G.style.width=D+"px";
G.style.height=A+"px";
G.style.overflow="hidden";
G.style.margin="2px";
if(SimileAjax.Graphics.pngIsTranslucent){G.style.background="url("+F+") no-repeat";
}else{G.style.filter="progid:DXImageTransform.Microsoft.AlphaImageLoader(src='"+F+"', sizingMethod='image')";
}var C;
if(SimileAjax.Platform.browser.isIE){C="filter:alpha(opacity=0)";
}else{C="opacity: 0";
}G.innerHTML="<textarea rows='1' autocomplete='off' value='none' style='"+C+"' />";
var B=G.firstChild;
B.style.width=D+"px";
B.style.height=A+"px";
B.onmousedown=function(H){H=(H)?H:((event)?event:null);
if(H.button==2){B.value=E();
B.select();
}};
return G;
};
SimileAjax.Graphics.getFontRenderingContext=function(A,B){return new SimileAjax.Graphics._FontRenderingContext(A,B);
};
SimileAjax.Graphics._FontRenderingContext=function(A,B){this._elmt=A;
this._elmt.style.visibility="hidden";
if(typeof B=="string"){this._elmt.style.width=B;
}else{if(typeof B=="number"){this._elmt.style.width=B+"px";
}}};
SimileAjax.Graphics._FontRenderingContext.prototype.dispose=function(){this._elmt=null;
};
SimileAjax.Graphics._FontRenderingContext.prototype.update=function(){this._elmt.innerHTML="A";
this._lineHeight=this._elmt.offsetHeight;
};
SimileAjax.Graphics._FontRenderingContext.prototype.computeSize=function(A){this._elmt.innerHTML=A;
return{width:this._elmt.offsetWidth,height:this._elmt.offsetHeight};
};
SimileAjax.Graphics._FontRenderingContext.prototype.getLineHeight=function(){return this._lineHeight;
};


/* history.js */
SimileAjax.History={maxHistoryLength:10,historyFile:"__history__.html",enabled:true,_initialized:false,_listeners:new SimileAjax.ListenerQueue(),_actions:[],_baseIndex:0,_currentIndex:0,_plainDocumentTitle:document.title};
SimileAjax.History.formatHistoryEntryTitle=function(A){return SimileAjax.History._plainDocumentTitle+" {"+A+"}";
};
SimileAjax.History.initialize=function(){if(SimileAjax.History._initialized){return ;
}if(SimileAjax.History.enabled){var A=document.createElement("iframe");
A.id="simile-ajax-history";
A.style.position="absolute";
A.style.width="10px";
A.style.height="10px";
A.style.top="0px";
A.style.left="0px";
A.style.visibility="hidden";
A.src=SimileAjax.History.historyFile+"?0";
document.body.appendChild(A);
SimileAjax.DOM.registerEvent(A,"load",SimileAjax.History._handleIFrameOnLoad);
SimileAjax.History._iframe=A;
}SimileAjax.History._initialized=true;
};
SimileAjax.History.addListener=function(A){SimileAjax.History.initialize();
SimileAjax.History._listeners.add(A);
};
SimileAjax.History.removeListener=function(A){SimileAjax.History.initialize();
SimileAjax.History._listeners.remove(A);
};
SimileAjax.History.addAction=function(A){SimileAjax.History.initialize();
SimileAjax.History._listeners.fire("onBeforePerform",[A]);
window.setTimeout(function(){try{A.perform();
SimileAjax.History._listeners.fire("onAfterPerform",[A]);
if(SimileAjax.History.enabled){SimileAjax.History._actions=SimileAjax.History._actions.slice(0,SimileAjax.History._currentIndex-SimileAjax.History._baseIndex);
SimileAjax.History._actions.push(A);
SimileAjax.History._currentIndex++;
var C=SimileAjax.History._actions.length-SimileAjax.History.maxHistoryLength;
if(C>0){SimileAjax.History._actions=SimileAjax.History._actions.slice(C);
SimileAjax.History._baseIndex+=C;
}try{SimileAjax.History._iframe.contentWindow.location.search="?"+SimileAjax.History._currentIndex;
}catch(B){var D=SimileAjax.History.formatHistoryEntryTitle(A.label);
document.title=D;
}}}catch(B){SimileAjax.Debug.exception(B,"Error adding action {"+A.label+"} to history");
}},0);
};
SimileAjax.History.addLengthyAction=function(C,A,B){SimileAjax.History.addAction({perform:C,undo:A,label:B,uiLayer:SimileAjax.WindowManager.getBaseLayer(),lengthy:true});
};
SimileAjax.History._handleIFrameOnLoad=function(){try{var B=SimileAjax.History._iframe.contentWindow.location.search;
var F=(B.length==0)?0:Math.max(0,parseInt(B.substr(1)));
var E=function(){var G=F-SimileAjax.History._currentIndex;
SimileAjax.History._currentIndex+=G;
SimileAjax.History._baseIndex+=G;
SimileAjax.History._iframe.contentWindow.location.search="?"+F;
};
if(F<SimileAjax.History._currentIndex){SimileAjax.History._listeners.fire("onBeforeUndoSeveral",[]);
window.setTimeout(function(){while(SimileAjax.History._currentIndex>F&&SimileAjax.History._currentIndex>SimileAjax.History._baseIndex){SimileAjax.History._currentIndex--;
var G=SimileAjax.History._actions[SimileAjax.History._currentIndex-SimileAjax.History._baseIndex];
try{G.undo();
}catch(H){SimileAjax.Debug.exception(H,"History: Failed to undo action {"+G.label+"}");
}}SimileAjax.History._listeners.fire("onAfterUndoSeveral",[]);
E();
},0);
}else{if(F>SimileAjax.History._currentIndex){SimileAjax.History._listeners.fire("onBeforeRedoSeveral",[]);
window.setTimeout(function(){while(SimileAjax.History._currentIndex<F&&SimileAjax.History._currentIndex-SimileAjax.History._baseIndex<SimileAjax.History._actions.length){var G=SimileAjax.History._actions[SimileAjax.History._currentIndex-SimileAjax.History._baseIndex];
try{G.perform();
}catch(H){SimileAjax.Debug.exception(H,"History: Failed to redo action {"+G.label+"}");
}SimileAjax.History._currentIndex++;
}SimileAjax.History._listeners.fire("onAfterRedoSeveral",[]);
E();
},0);
}else{var A=SimileAjax.History._currentIndex-SimileAjax.History._baseIndex-1;
var D=(A>=0&&A<SimileAjax.History._actions.length)?SimileAjax.History.formatHistoryEntryTitle(SimileAjax.History._actions[A].label):SimileAjax.History._plainDocumentTitle;
SimileAjax.History._iframe.contentWindow.document.title=D;
document.title=D;
}}}catch(C){}};
SimileAjax.History.getNextUndoAction=function(){try{var A=SimileAjax.History._currentIndex-SimileAjax.History._baseIndex-1;
return SimileAjax.History._actions[A];
}catch(B){return null;
}};
SimileAjax.History.getNextRedoAction=function(){try{var A=SimileAjax.History._currentIndex-SimileAjax.History._baseIndex;
return SimileAjax.History._actions[A];
}catch(B){return null;
}};


/* html.js */
SimileAjax.HTML=new Object();
SimileAjax.HTML._e2uHash={};
(function(){var A=SimileAjax.HTML._e2uHash;
A["nbsp"]="\u00A0[space]";
A["iexcl"]="\u00A1";
A["cent"]="\u00A2";
A["pound"]="\u00A3";
A["curren"]="\u00A4";
A["yen"]="\u00A5";
A["brvbar"]="\u00A6";
A["sect"]="\u00A7";
A["uml"]="\u00A8";
A["copy"]="\u00A9";
A["ordf"]="\u00AA";
A["laquo"]="\u00AB";
A["not"]="\u00AC";
A["shy"]="\u00AD";
A["reg"]="\u00AE";
A["macr"]="\u00AF";
A["deg"]="\u00B0";
A["plusmn"]="\u00B1";
A["sup2"]="\u00B2";
A["sup3"]="\u00B3";
A["acute"]="\u00B4";
A["micro"]="\u00B5";
A["para"]="\u00B6";
A["middot"]="\u00B7";
A["cedil"]="\u00B8";
A["sup1"]="\u00B9";
A["ordm"]="\u00BA";
A["raquo"]="\u00BB";
A["frac14"]="\u00BC";
A["frac12"]="\u00BD";
A["frac34"]="\u00BE";
A["iquest"]="\u00BF";
A["Agrave"]="\u00C0";
A["Aacute"]="\u00C1";
A["Acirc"]="\u00C2";
A["Atilde"]="\u00C3";
A["Auml"]="\u00C4";
A["Aring"]="\u00C5";
A["AElig"]="\u00C6";
A["Ccedil"]="\u00C7";
A["Egrave"]="\u00C8";
A["Eacute"]="\u00C9";
A["Ecirc"]="\u00CA";
A["Euml"]="\u00CB";
A["Igrave"]="\u00CC";
A["Iacute"]="\u00CD";
A["Icirc"]="\u00CE";
A["Iuml"]="\u00CF";
A["ETH"]="\u00D0";
A["Ntilde"]="\u00D1";
A["Ograve"]="\u00D2";
A["Oacute"]="\u00D3";
A["Ocirc"]="\u00D4";
A["Otilde"]="\u00D5";
A["Ouml"]="\u00D6";
A["times"]="\u00D7";
A["Oslash"]="\u00D8";
A["Ugrave"]="\u00D9";
A["Uacute"]="\u00DA";
A["Ucirc"]="\u00DB";
A["Uuml"]="\u00DC";
A["Yacute"]="\u00DD";
A["THORN"]="\u00DE";
A["szlig"]="\u00DF";
A["agrave"]="\u00E0";
A["aacute"]="\u00E1";
A["acirc"]="\u00E2";
A["atilde"]="\u00E3";
A["auml"]="\u00E4";
A["aring"]="\u00E5";
A["aelig"]="\u00E6";
A["ccedil"]="\u00E7";
A["egrave"]="\u00E8";
A["eacute"]="\u00E9";
A["ecirc"]="\u00EA";
A["euml"]="\u00EB";
A["igrave"]="\u00EC";
A["iacute"]="\u00ED";
A["icirc"]="\u00EE";
A["iuml"]="\u00EF";
A["eth"]="\u00F0";
A["ntilde"]="\u00F1";
A["ograve"]="\u00F2";
A["oacute"]="\u00F3";
A["ocirc"]="\u00F4";
A["otilde"]="\u00F5";
A["ouml"]="\u00F6";
A["divide"]="\u00F7";
A["oslash"]="\u00F8";
A["ugrave"]="\u00F9";
A["uacute"]="\u00FA";
A["ucirc"]="\u00FB";
A["uuml"]="\u00FC";
A["yacute"]="\u00FD";
A["thorn"]="\u00FE";
A["yuml"]="\u00FF";
A["quot"]="\u0022";
A["amp"]="\u0026";
A["lt"]="\u003C";
A["gt"]="\u003E";
A["OElig"]="";
A["oelig"]="\u0153";
A["Scaron"]="\u0160";
A["scaron"]="\u0161";
A["Yuml"]="\u0178";
A["circ"]="\u02C6";
A["tilde"]="\u02DC";
A["ensp"]="\u2002";
A["emsp"]="\u2003";
A["thinsp"]="\u2009";
A["zwnj"]="\u200C";
A["zwj"]="\u200D";
A["lrm"]="\u200E";
A["rlm"]="\u200F";
A["ndash"]="\u2013";
A["mdash"]="\u2014";
A["lsquo"]="\u2018";
A["rsquo"]="\u2019";
A["sbquo"]="\u201A";
A["ldquo"]="\u201C";
A["rdquo"]="\u201D";
A["bdquo"]="\u201E";
A["dagger"]="\u2020";
A["Dagger"]="\u2021";
A["permil"]="\u2030";
A["lsaquo"]="\u2039";
A["rsaquo"]="\u203A";
A["euro"]="\u20AC";
A["fnof"]="\u0192";
A["Alpha"]="\u0391";
A["Beta"]="\u0392";
A["Gamma"]="\u0393";
A["Delta"]="\u0394";
A["Epsilon"]="\u0395";
A["Zeta"]="\u0396";
A["Eta"]="\u0397";
A["Theta"]="\u0398";
A["Iota"]="\u0399";
A["Kappa"]="\u039A";
A["Lambda"]="\u039B";
A["Mu"]="\u039C";
A["Nu"]="\u039D";
A["Xi"]="\u039E";
A["Omicron"]="\u039F";
A["Pi"]="\u03A0";
A["Rho"]="\u03A1";
A["Sigma"]="\u03A3";
A["Tau"]="\u03A4";
A["Upsilon"]="\u03A5";
A["Phi"]="\u03A6";
A["Chi"]="\u03A7";
A["Psi"]="\u03A8";
A["Omega"]="\u03A9";
A["alpha"]="\u03B1";
A["beta"]="\u03B2";
A["gamma"]="\u03B3";
A["delta"]="\u03B4";
A["epsilon"]="\u03B5";
A["zeta"]="\u03B6";
A["eta"]="\u03B7";
A["theta"]="\u03B8";
A["iota"]="\u03B9";
A["kappa"]="\u03BA";
A["lambda"]="\u03BB";
A["mu"]="\u03BC";
A["nu"]="\u03BD";
A["xi"]="\u03BE";
A["omicron"]="\u03BF";
A["pi"]="\u03C0";
A["rho"]="\u03C1";
A["sigmaf"]="\u03C2";
A["sigma"]="\u03C3";
A["tau"]="\u03C4";
A["upsilon"]="\u03C5";
A["phi"]="\u03C6";
A["chi"]="\u03C7";
A["psi"]="\u03C8";
A["omega"]="\u03C9";
A["thetasym"]="\u03D1";
A["upsih"]="\u03D2";
A["piv"]="\u03D6";
A["bull"]="\u2022";
A["hellip"]="\u2026";
A["prime"]="\u2032";
A["Prime"]="\u2033";
A["oline"]="\u203E";
A["frasl"]="\u2044";
A["weierp"]="\u2118";
A["image"]="\u2111";
A["real"]="\u211C";
A["trade"]="\u2122";
A["alefsym"]="\u2135";
A["larr"]="\u2190";
A["uarr"]="\u2191";
A["rarr"]="\u2192";
A["darr"]="\u2193";
A["harr"]="\u2194";
A["crarr"]="\u21B5";
A["lArr"]="\u21D0";
A["uArr"]="\u21D1";
A["rArr"]="\u21D2";
A["dArr"]="\u21D3";
A["hArr"]="\u21D4";
A["forall"]="\u2200";
A["part"]="\u2202";
A["exist"]="\u2203";
A["empty"]="\u2205";
A["nabla"]="\u2207";
A["isin"]="\u2208";
A["notin"]="\u2209";
A["ni"]="\u220B";
A["prod"]="\u220F";
A["sum"]="\u2211";
A["minus"]="\u2212";
A["lowast"]="\u2217";
A["radic"]="\u221A";
A["prop"]="\u221D";
A["infin"]="\u221E";
A["ang"]="\u2220";
A["and"]="\u2227";
A["or"]="\u2228";
A["cap"]="\u2229";
A["cup"]="\u222A";
A["int"]="\u222B";
A["there4"]="\u2234";
A["sim"]="\u223C";
A["cong"]="\u2245";
A["asymp"]="\u2248";
A["ne"]="\u2260";
A["equiv"]="\u2261";
A["le"]="\u2264";
A["ge"]="\u2265";
A["sub"]="\u2282";
A["sup"]="\u2283";
A["nsub"]="\u2284";
A["sube"]="\u2286";
A["supe"]="\u2287";
A["oplus"]="\u2295";
A["otimes"]="\u2297";
A["perp"]="\u22A5";
A["sdot"]="\u22C5";
A["lceil"]="\u2308";
A["rceil"]="\u2309";
A["lfloor"]="\u230A";
A["rfloor"]="\u230B";
A["lang"]="\u2329";
A["rang"]="\u232A";
A["loz"]="\u25CA";
A["spades"]="\u2660";
A["clubs"]="\u2663";
A["hearts"]="\u2665";
A["diams"]="\u2666";
})();
SimileAjax.HTML.deEntify=function(C){var D=SimileAjax.HTML._e2uHash;
var B=/&(\w+?);/;
while(B.test(C)){var A=C.match(B);
C=C.replace(B,D[A[1]]);
}return C;
};


/* json.js */
SimileAjax.JSON=new Object();
(function(){var m={"\b":"\\b","\t":"\\t","\n":"\\n","\f":"\\f","\r":"\\r",'"':'\\"',"\\":"\\\\"};
var s={array:function(x){var a=["["],b,f,i,l=x.length,v;
for(i=0;
i<l;
i+=1){v=x[i];
f=s[typeof v];
if(f){v=f(v);
if(typeof v=="string"){if(b){a[a.length]=",";
}a[a.length]=v;
b=true;
}}}a[a.length]="]";
return a.join("");
},"boolean":function(x){return String(x);
},"null":function(x){return"null";
},number:function(x){return isFinite(x)?String(x):"null";
},object:function(x){if(x){if(x instanceof Array){return s.array(x);
}var a=["{"],b,f,i,v;
for(i in x){v=x[i];
f=s[typeof v];
if(f){v=f(v);
if(typeof v=="string"){if(b){a[a.length]=",";
}a.push(s.string(i),":",v);
b=true;
}}}a[a.length]="}";
return a.join("");
}return"null";
},string:function(x){if(/["\\\x00-\x1f]/.test(x)){x=x.replace(/([\x00-\x1f\\"])/g,function(a,b){var c=m[b];
if(c){return c;
}c=b.charCodeAt();
return"\\u00"+Math.floor(c/16).toString(16)+(c%16).toString(16);
});
}return'"'+x+'"';
}};
SimileAjax.JSON.toJSONString=function(o){if(o instanceof Object){return s.object(o);
}else{if(o instanceof Array){return s.array(o);
}else{return o.toString();
}}};
SimileAjax.JSON.parseJSON=function(){try{return !(/[^,:{}\[\]0-9.\-+Eaeflnr-u \n\r\t]/.test(this.replace(/"(\\.|[^"\\])*"/g,"")))&&eval("("+this+")");
}catch(e){return false;
}};
})();


/* string.js */
String.prototype.trim=function(){return this.replace(/^\s+|\s+$/g,"");
};
String.prototype.startsWith=function(A){return this.length>=A.length&&this.substr(0,A.length)==A;
};
String.prototype.endsWith=function(A){return this.length>=A.length&&this.substr(this.length-A.length)==A;
};
String.substitute=function(B,D){var A="";
var F=0;
while(F<B.length-1){var C=B.indexOf("%",F);
if(C<0||C==B.length-1){break;
}else{if(C>F&&B.charAt(C-1)=="\\"){A+=B.substring(F,C-1)+"%";
F=C+1;
}else{var E=parseInt(B.charAt(C+1));
if(isNaN(E)||E>=D.length){A+=B.substring(F,C+2);
}else{A+=B.substring(F,C)+D[E].toString();
}F=C+2;
}}}if(F<B.length){A+=B.substring(F);
}return A;
};


/* units.js */
SimileAjax.NativeDateUnit=new Object();
SimileAjax.NativeDateUnit.makeDefaultValue=function(){return new Date();
};
SimileAjax.NativeDateUnit.cloneValue=function(A){return new Date(A.getTime());
};
SimileAjax.NativeDateUnit.getParser=function(A){if(typeof A=="string"){A=A.toLowerCase();
}return(A=="iso8601"||A=="iso 8601")?SimileAjax.DateTime.parseIso8601DateTime:SimileAjax.DateTime.parseGregorianDateTime;
};
SimileAjax.NativeDateUnit.parseFromObject=function(A){return SimileAjax.DateTime.parseGregorianDateTime(A);
};
SimileAjax.NativeDateUnit.toNumber=function(A){return A.getTime();
};
SimileAjax.NativeDateUnit.fromNumber=function(A){return new Date(A);
};
SimileAjax.NativeDateUnit.compare=function(D,C){var B,A;
if(typeof D=="object"){B=D.getTime();
}else{B=Number(D);
}if(typeof C=="object"){A=C.getTime();
}else{A=Number(C);
}return B-A;
};
SimileAjax.NativeDateUnit.earlier=function(B,A){return SimileAjax.NativeDateUnit.compare(B,A)<0?B:A;
};
SimileAjax.NativeDateUnit.later=function(B,A){return SimileAjax.NativeDateUnit.compare(B,A)>0?B:A;
};
SimileAjax.NativeDateUnit.change=function(A,B){return new Date(A.getTime()+B);
};


/* window-manager.js */
SimileAjax.WindowManager={_initialized:false,_listeners:[],_draggedElement:null,_draggedElementCallback:null,_dropTargetHighlightElement:null,_lastCoords:null,_ghostCoords:null,_draggingMode:"",_dragging:false,_layers:[]};
SimileAjax.WindowManager.initialize=function(){if(SimileAjax.WindowManager._initialized){return ;
}SimileAjax.DOM.registerEvent(document.body,"mousedown",SimileAjax.WindowManager._onBodyMouseDown);
SimileAjax.DOM.registerEvent(document.body,"mousemove",SimileAjax.WindowManager._onBodyMouseMove);
SimileAjax.DOM.registerEvent(document.body,"mouseup",SimileAjax.WindowManager._onBodyMouseUp);
SimileAjax.DOM.registerEvent(document,"keydown",SimileAjax.WindowManager._onBodyKeyDown);
SimileAjax.DOM.registerEvent(document,"keyup",SimileAjax.WindowManager._onBodyKeyUp);
SimileAjax.WindowManager._layers.push({index:0});
SimileAjax.WindowManager._historyListener={onBeforeUndoSeveral:function(){},onAfterUndoSeveral:function(){},onBeforeUndo:function(){},onAfterUndo:function(){},onBeforeRedoSeveral:function(){},onAfterRedoSeveral:function(){},onBeforeRedo:function(){},onAfterRedo:function(){}};
SimileAjax.History.addListener(SimileAjax.WindowManager._historyListener);
SimileAjax.WindowManager._initialized=true;
};
SimileAjax.WindowManager.getBaseLayer=function(){SimileAjax.WindowManager.initialize();
return SimileAjax.WindowManager._layers[0];
};
SimileAjax.WindowManager.getHighestLayer=function(){SimileAjax.WindowManager.initialize();
return SimileAjax.WindowManager._layers[SimileAjax.WindowManager._layers.length-1];
};
SimileAjax.WindowManager.registerEventWithObject=function(D,A,E,B,C){SimileAjax.WindowManager.registerEvent(D,A,function(G,F,H){return E[B].call(E,G,F,H);
},C);
};
SimileAjax.WindowManager.registerEvent=function(D,B,E,C){if(C==null){C=SimileAjax.WindowManager.getHighestLayer();
}var A=function(G,F,I){if(SimileAjax.WindowManager._canProcessEventAtLayer(C)){SimileAjax.WindowManager._popToLayer(C.index);
try{E(G,F,I);
}catch(H){SimileAjax.Debug.exception(H);
}}SimileAjax.DOM.cancelEvent(F);
return false;
};
SimileAjax.DOM.registerEvent(D,B,A);
};
SimileAjax.WindowManager.pushLayer=function(C,D,B){var A={onPop:C,index:SimileAjax.WindowManager._layers.length,ephemeral:(D),elmt:B};
SimileAjax.WindowManager._layers.push(A);
return A;
};
SimileAjax.WindowManager.popLayer=function(B){for(var A=1;
A<SimileAjax.WindowManager._layers.length;
A++){if(SimileAjax.WindowManager._layers[A]==B){SimileAjax.WindowManager._popToLayer(A-1);
break;
}}};
SimileAjax.WindowManager.popAllLayers=function(){SimileAjax.WindowManager._popToLayer(0);
};
SimileAjax.WindowManager.registerForDragging=function(B,C,A){SimileAjax.WindowManager.registerEvent(B,"mousedown",function(E,D,F){SimileAjax.WindowManager._handleMouseDown(E,D,C);
},A);
};
SimileAjax.WindowManager._popToLayer=function(C){while(C+1<SimileAjax.WindowManager._layers.length){try{var A=SimileAjax.WindowManager._layers.pop();
if(A.onPop!=null){A.onPop();
}}catch(B){}}};
SimileAjax.WindowManager._canProcessEventAtLayer=function(B){if(B.index==(SimileAjax.WindowManager._layers.length-1)){return true;
}for(var A=B.index+1;
A<SimileAjax.WindowManager._layers.length;
A++){if(!SimileAjax.WindowManager._layers[A].ephemeral){return false;
}}return true;
};
SimileAjax.WindowManager.cancelPopups=function(A){var F=(A)?SimileAjax.DOM.getEventPageCoordinates(A):{x:-1,y:-1};
var E=SimileAjax.WindowManager._layers.length-1;
while(E>0&&SimileAjax.WindowManager._layers[E].ephemeral){var D=SimileAjax.WindowManager._layers[E];
if(D.elmt!=null){var C=D.elmt;
var B=SimileAjax.DOM.getPageCoordinates(C);
if(F.x>=B.left&&F.x<(B.left+C.offsetWidth)&&F.y>=B.top&&F.y<(B.top+C.offsetHeight)){break;
}}E--;
}SimileAjax.WindowManager._popToLayer(E);
};
SimileAjax.WindowManager._onBodyMouseDown=function(B,A,C){if(!("eventPhase" in A)||A.eventPhase==A.BUBBLING_PHASE){SimileAjax.WindowManager.cancelPopups(A);
}};
SimileAjax.WindowManager._handleMouseDown=function(B,A,C){SimileAjax.WindowManager._draggedElement=B;
SimileAjax.WindowManager._draggedElementCallback=C;
SimileAjax.WindowManager._lastCoords={x:A.clientX,y:A.clientY};
SimileAjax.DOM.cancelEvent(A);
return false;
};
SimileAjax.WindowManager._onBodyKeyDown=function(C,A,D){if(SimileAjax.WindowManager._dragging){if(A.keyCode==27){SimileAjax.WindowManager._cancelDragging();
}else{if((A.keyCode==17||A.keyCode==16)&&SimileAjax.WindowManager._draggingMode!="copy"){SimileAjax.WindowManager._draggingMode="copy";
var B=SimileAjax.Graphics.createTranslucentImage(SimileAjax.urlPrefix+"data/timeline/copy.png");
B.style.position="absolute";
B.style.left=(SimileAjax.WindowManager._ghostCoords.left-16)+"px";
B.style.top=(SimileAjax.WindowManager._ghostCoords.top)+"px";
document.body.appendChild(B);
SimileAjax.WindowManager._draggingModeIndicatorElmt=B;
}}}};
SimileAjax.WindowManager._onBodyKeyUp=function(B,A,C){if(SimileAjax.WindowManager._dragging){if(A.keyCode==17||A.keyCode==16){SimileAjax.WindowManager._draggingMode="";
if(SimileAjax.WindowManager._draggingModeIndicatorElmt!=null){document.body.removeChild(SimileAjax.WindowManager._draggingModeIndicatorElmt);
SimileAjax.WindowManager._draggingModeIndicatorElmt=null;
}}}};
SimileAjax.WindowManager._onBodyMouseMove=function(A,N,H){if(SimileAjax.WindowManager._draggedElement!=null){var P=SimileAjax.WindowManager._draggedElementCallback;
var E=SimileAjax.WindowManager._lastCoords;
var M=N.clientX-E.x;
var J=N.clientY-E.y;
if(!SimileAjax.WindowManager._dragging){if(Math.abs(M)>5||Math.abs(J)>5){try{if("onDragStart" in P){P.onDragStart();
}if("ghost" in P&&P.ghost){var K=SimileAjax.WindowManager._draggedElement;
SimileAjax.WindowManager._ghostCoords=SimileAjax.DOM.getPageCoordinates(K);
SimileAjax.WindowManager._ghostCoords.left+=M;
SimileAjax.WindowManager._ghostCoords.top+=J;
var O=K.cloneNode(true);
O.style.position="absolute";
O.style.left=SimileAjax.WindowManager._ghostCoords.left+"px";
O.style.top=SimileAjax.WindowManager._ghostCoords.top+"px";
O.style.zIndex=1000;
SimileAjax.Graphics.setOpacity(O,50);
document.body.appendChild(O);
P._ghostElmt=O;
}SimileAjax.WindowManager._dragging=true;
SimileAjax.WindowManager._lastCoords={x:N.clientX,y:N.clientY};
document.body.focus();
}catch(G){SimileAjax.Debug.exception("WindowManager: Error handling mouse down",G);
SimileAjax.WindowManager._cancelDragging();
}}}else{try{SimileAjax.WindowManager._lastCoords={x:N.clientX,y:N.clientY};
if("onDragBy" in P){P.onDragBy(M,J);
}if("_ghostElmt" in P){var O=P._ghostElmt;
SimileAjax.WindowManager._ghostCoords.left+=M;
SimileAjax.WindowManager._ghostCoords.top+=J;
O.style.left=SimileAjax.WindowManager._ghostCoords.left+"px";
O.style.top=SimileAjax.WindowManager._ghostCoords.top+"px";
if(SimileAjax.WindowManager._draggingModeIndicatorElmt!=null){var I=SimileAjax.WindowManager._draggingModeIndicatorElmt;
I.style.left=(SimileAjax.WindowManager._ghostCoords.left-16)+"px";
I.style.top=SimileAjax.WindowManager._ghostCoords.top+"px";
}if("droppable" in P&&P.droppable){var L=SimileAjax.DOM.getEventPageCoordinates(N);
var H=SimileAjax.DOM.hittest(L.x,L.y,[SimileAjax.WindowManager._ghostElmt,SimileAjax.WindowManager._dropTargetHighlightElement]);
H=SimileAjax.WindowManager._findDropTarget(H);
if(H!=SimileAjax.WindowManager._potentialDropTarget){if(SimileAjax.WindowManager._dropTargetHighlightElement!=null){document.body.removeChild(SimileAjax.WindowManager._dropTargetHighlightElement);
SimileAjax.WindowManager._dropTargetHighlightElement=null;
SimileAjax.WindowManager._potentialDropTarget=null;
}var F=false;
if(H!=null){if((!("canDropOn" in P)||P.canDropOn(H))&&(!("canDrop" in H)||H.canDrop(SimileAjax.WindowManager._draggedElement))){F=true;
}}if(F){var C=4;
var D=SimileAjax.DOM.getPageCoordinates(H);
var B=document.createElement("div");
B.style.border=C+"px solid yellow";
B.style.backgroundColor="yellow";
B.style.position="absolute";
B.style.left=D.left+"px";
B.style.top=D.top+"px";
B.style.width=(H.offsetWidth-C*2)+"px";
B.style.height=(H.offsetHeight-C*2)+"px";
SimileAjax.Graphics.setOpacity(B,30);
document.body.appendChild(B);
SimileAjax.WindowManager._potentialDropTarget=H;
SimileAjax.WindowManager._dropTargetHighlightElement=B;
}}}}}catch(G){SimileAjax.Debug.exception("WindowManager: Error handling mouse move",G);
SimileAjax.WindowManager._cancelDragging();
}}SimileAjax.DOM.cancelEvent(N);
return false;
}};
SimileAjax.WindowManager._onBodyMouseUp=function(B,A,C){if(SimileAjax.WindowManager._draggedElement!=null){try{if(SimileAjax.WindowManager._dragging){var E=SimileAjax.WindowManager._draggedElementCallback;
if("onDragEnd" in E){E.onDragEnd();
}if("droppable" in E&&E.droppable){var D=false;
var C=SimileAjax.WindowManager._potentialDropTarget;
if(C!=null){if((!("canDropOn" in E)||E.canDropOn(C))&&(!("canDrop" in C)||C.canDrop(SimileAjax.WindowManager._draggedElement))){if("onDropOn" in E){E.onDropOn(C);
}C.ondrop(SimileAjax.WindowManager._draggedElement,SimileAjax.WindowManager._draggingMode);
D=true;
}}if(!D){}}}}finally{SimileAjax.WindowManager._cancelDragging();
}SimileAjax.DOM.cancelEvent(A);
return false;
}};
SimileAjax.WindowManager._cancelDragging=function(){var B=SimileAjax.WindowManager._draggedElementCallback;
if("_ghostElmt" in B){var A=B._ghostElmt;
document.body.removeChild(A);
delete B._ghostElmt;
}if(SimileAjax.WindowManager._dropTargetHighlightElement!=null){document.body.removeChild(SimileAjax.WindowManager._dropTargetHighlightElement);
SimileAjax.WindowManager._dropTargetHighlightElement=null;
}if(SimileAjax.WindowManager._draggingModeIndicatorElmt!=null){document.body.removeChild(SimileAjax.WindowManager._draggingModeIndicatorElmt);
SimileAjax.WindowManager._draggingModeIndicatorElmt=null;
}SimileAjax.WindowManager._draggedElement=null;
SimileAjax.WindowManager._draggedElementCallback=null;
SimileAjax.WindowManager._potentialDropTarget=null;
SimileAjax.WindowManager._dropTargetHighlightElement=null;
SimileAjax.WindowManager._lastCoords=null;
SimileAjax.WindowManager._ghostCoords=null;
SimileAjax.WindowManager._draggingMode="";
SimileAjax.WindowManager._dragging=false;
};
SimileAjax.WindowManager._findDropTarget=function(A){while(A!=null){if("ondrop" in A&&(typeof A.ondrop)=="function"){break;
}A=A.parentNode;
}return A;
};


/* xmlhttp.js */
SimileAjax.XmlHttp=new Object();
SimileAjax.XmlHttp._onReadyStateChange=function(A,D,B){switch(A.readyState){case 4:try{if(A.status==0||A.status==200){if(B){B(A);
}}else{if(D){D(A.statusText,A.status,A);
}}}catch(C){SimileAjax.Debug.exception("XmlHttp: Error handling onReadyStateChange",C);
}break;
}};
SimileAjax.XmlHttp._createRequest=function(){if(SimileAjax.Platform.browser.isIE){var A=["Msxml2.XMLHTTP","Microsoft.XMLHTTP","Msxml2.XMLHTTP.4.0"];
for(var B=0;
B<A.length;
B++){try{var C=A[B];
var D=function(){return new ActiveXObject(C);
};
var F=D();
SimileAjax.XmlHttp._createRequest=D;
return F;
}catch(E){}}}try{var D=function(){return new XMLHttpRequest();
};
var F=D();
SimileAjax.XmlHttp._createRequest=D;
return F;
}catch(E){throw new Error("Failed to create an XMLHttpRequest object");
}};
SimileAjax.XmlHttp.get=function(A,D,C){var B=SimileAjax.XmlHttp._createRequest();
B.open("GET",A,true);
B.onreadystatechange=function(){SimileAjax.XmlHttp._onReadyStateChange(B,D,C);
};
B.send(null);
};
SimileAjax.XmlHttp.post=function(B,A,E,D){var C=SimileAjax.XmlHttp._createRequest();
C.open("POST",B,true);
C.onreadystatechange=function(){SimileAjax.XmlHttp._onReadyStateChange(C,E,D);
};
C.send(A);
};
SimileAjax.XmlHttp._forceXML=function(A){try{A.overrideMimeType("text/xml");
}catch(B){A.setrequestheader("Content-Type","text/xml");
}};


window.Timeline = new Object();
Timeline.urlPrefix = baseuri();
window.Timeline.DateTime = window.SimileAjax.DateTime; // for backward compatibility

/* decorators.js */
Timeline.SpanHighlightDecorator=function(A){this._unit=("unit" in A)?A.unit:SimileAjax.NativeDateUnit;
this._startDate=(typeof A.startDate=="string")?this._unit.parseFromObject(A.startDate):A.startDate;
this._endDate=(typeof A.endDate=="string")?this._unit.parseFromObject(A.endDate):A.endDate;
this._startLabel=A.startLabel;
this._endLabel=A.endLabel;
this._color=A.color;
this._cssClass=("cssClass" in A)?A.cssClass:null;
this._opacity=("opacity" in A)?A.opacity:100;
};
Timeline.SpanHighlightDecorator.prototype.initialize=function(B,A){this._band=B;
this._timeline=A;
this._layerDiv=null;
};
Timeline.SpanHighlightDecorator.prototype.paint=function(){if(this._layerDiv!=null){this._band.removeLayerDiv(this._layerDiv);
}this._layerDiv=this._band.createLayerDiv(10);
this._layerDiv.setAttribute("name","span-highlight-decorator");
this._layerDiv.style.display="none";
var F=this._band.getMinDate();
var C=this._band.getMaxDate();
if(this._unit.compare(this._startDate,C)<0&&this._unit.compare(this._endDate,F)>0){F=this._unit.later(F,this._startDate);
C=this._unit.earlier(C,this._endDate);
var D=this._band.dateToPixelOffset(F);
var K=this._band.dateToPixelOffset(C);
var I=this._timeline.getDocument();
var H=function(){var L=I.createElement("table");
L.insertRow(0).insertCell(0);
return L;
};
var B=I.createElement("div");
B.className="timeline-highlight-decorator";
if(this._cssClass){B.className+=" "+this._cssClass;
}if(this._opacity<100){SimileAjax.Graphics.setOpacity(B,this._opacity);
}this._layerDiv.appendChild(B);
var J=H();
J.className="timeline-highlight-label timeline-highlight-label-start";
var G=J.rows[0].cells[0];
G.innerHTML=this._startLabel;
if(this._cssClass){G.className="label_"+this._cssClass;
}this._layerDiv.appendChild(J);
var A=H();
A.className="timeline-highlight-label timeline-highlight-label-end";
var E=A.rows[0].cells[0];
E.innerHTML=this._endLabel;
if(this._cssClass){E.className="label_"+this._cssClass;
}this._layerDiv.appendChild(A);
if(this._timeline.isHorizontal()){B.style.left=D+"px";
B.style.width=(K-D)+"px";
J.style.right=(this._band.getTotalViewLength()-D)+"px";
J.style.width=(this._startLabel.length)+"em";
A.style.left=K+"px";
A.style.width=(this._endLabel.length)+"em";
}else{B.style.top=D+"px";
B.style.height=(K-D)+"px";
J.style.bottom=D+"px";
J.style.height="1.5px";
A.style.top=K+"px";
A.style.height="1.5px";
}}this._layerDiv.style.display="block";
};
Timeline.SpanHighlightDecorator.prototype.softPaint=function(){};
Timeline.PointHighlightDecorator=function(A){this._unit=("unit" in A)?A.unit:SimileAjax.NativeDateUnit;
this._date=(typeof A.date=="string")?this._unit.parseFromObject(A.date):A.date;
this._width=("width" in A)?A.width:10;
this._color=A.color;
this._cssClass=("cssClass" in A)?A.cssClass:"";
this._opacity=("opacity" in A)?A.opacity:100;
};
Timeline.PointHighlightDecorator.prototype.initialize=function(B,A){this._band=B;
this._timeline=A;
this._layerDiv=null;
};
Timeline.PointHighlightDecorator.prototype.paint=function(){if(this._layerDiv!=null){this._band.removeLayerDiv(this._layerDiv);
}this._layerDiv=this._band.createLayerDiv(10);
this._layerDiv.setAttribute("name","span-highlight-decorator");
this._layerDiv.style.display="none";
var C=this._band.getMinDate();
var E=this._band.getMaxDate();
if(this._unit.compare(this._date,E)<0&&this._unit.compare(this._date,C)>0){var B=this._band.dateToPixelOffset(this._date);
var A=B-Math.round(this._width/2);
var D=this._timeline.getDocument();
var F=D.createElement("div");
F.className="timeline-highlight-point-decorator";
F.className+=" "+this._cssClass;
if(this._opacity<100){SimileAjax.Graphics.setOpacity(F,this._opacity);
}this._layerDiv.appendChild(F);
if(this._timeline.isHorizontal()){F.style.left=A+"px";
}else{F.style.top=A+"px";
}}this._layerDiv.style.display="block";
};
Timeline.PointHighlightDecorator.prototype.softPaint=function(){};


/* detailed-painter.js */
Timeline.DetailedEventPainter=function(A){this._params=A;
this._onSelectListeners=[];
this._filterMatcher=null;
this._highlightMatcher=null;
this._frc=null;
this._eventIdToElmt={};
};
Timeline.DetailedEventPainter.prototype.initialize=function(B,A){this._band=B;
this._timeline=A;
this._backLayer=null;
this._eventLayer=null;
this._lineLayer=null;
this._highlightLayer=null;
this._eventIdToElmt=null;
};
Timeline.DetailedEventPainter.prototype.addOnSelectListener=function(A){this._onSelectListeners.push(A);
};
Timeline.DetailedEventPainter.prototype.removeOnSelectListener=function(B){for(var A=0;
A<this._onSelectListeners.length;
A++){if(this._onSelectListeners[A]==B){this._onSelectListeners.splice(A,1);
break;
}}};
Timeline.DetailedEventPainter.prototype.getFilterMatcher=function(){return this._filterMatcher;
};
Timeline.DetailedEventPainter.prototype.setFilterMatcher=function(A){this._filterMatcher=A;
};
Timeline.DetailedEventPainter.prototype.getHighlightMatcher=function(){return this._highlightMatcher;
};
Timeline.DetailedEventPainter.prototype.setHighlightMatcher=function(A){this._highlightMatcher=A;
};
Timeline.DetailedEventPainter.prototype.paint=function(){var B=this._band.getEventSource();
if(B==null){return ;
}this._eventIdToElmt={};
this._prepareForPainting();
var I=this._params.theme.event;
var G=Math.max(I.track.height,this._frc.getLineHeight());
var F={trackOffset:Math.round(this._band.getViewWidth()/2-G/2),trackHeight:G,trackGap:I.track.gap,trackIncrement:G+I.track.gap,icon:I.instant.icon,iconWidth:I.instant.iconWidth,iconHeight:I.instant.iconHeight,labelWidth:I.label.width};
var C=this._band.getMinDate();
var A=this._band.getMaxDate();
var J=(this._filterMatcher!=null)?this._filterMatcher:function(K){return true;
};
var E=(this._highlightMatcher!=null)?this._highlightMatcher:function(K){return -1;
};
var D=B.getEventReverseIterator(C,A);
while(D.hasNext()){var H=D.next();
if(J(H)){this.paintEvent(H,F,this._params.theme,E(H));
}}this._highlightLayer.style.display="block";
this._lineLayer.style.display="block";
this._eventLayer.style.display="block";
};
Timeline.DetailedEventPainter.prototype.softPaint=function(){};
Timeline.DetailedEventPainter.prototype._prepareForPainting=function(){var B=this._band;
if(this._backLayer==null){this._backLayer=this._band.createLayerDiv(0,"timeline-band-events");
this._backLayer.style.visibility="hidden";
var A=document.createElement("span");
A.className="timeline-event-label";
this._backLayer.appendChild(A);
this._frc=SimileAjax.Graphics.getFontRenderingContext(A);
}this._frc.update();
this._lowerTracks=[];
this._upperTracks=[];
if(this._highlightLayer!=null){B.removeLayerDiv(this._highlightLayer);
}this._highlightLayer=B.createLayerDiv(105,"timeline-band-highlights");
this._highlightLayer.style.display="none";
if(this._lineLayer!=null){B.removeLayerDiv(this._lineLayer);
}this._lineLayer=B.createLayerDiv(110,"timeline-band-lines");
this._lineLayer.style.display="none";
if(this._eventLayer!=null){B.removeLayerDiv(this._eventLayer);
}this._eventLayer=B.createLayerDiv(110,"timeline-band-events");
this._eventLayer.style.display="none";
};
Timeline.DetailedEventPainter.prototype.paintEvent=function(B,C,D,A){if(B.isInstant()){this.paintInstantEvent(B,C,D,A);
}else{this.paintDurationEvent(B,C,D,A);
}};
Timeline.DetailedEventPainter.prototype.paintInstantEvent=function(B,C,D,A){if(B.isImprecise()){this.paintImpreciseInstantEvent(B,C,D,A);
}else{this.paintPreciseInstantEvent(B,C,D,A);
}};
Timeline.DetailedEventPainter.prototype.paintDurationEvent=function(B,C,D,A){if(B.isImprecise()){this.paintImpreciseDurationEvent(B,C,D,A);
}else{this.paintPreciseDurationEvent(B,C,D,A);
}};
Timeline.DetailedEventPainter.prototype.paintPreciseInstantEvent=function(K,N,Q,O){var S=this._timeline.getDocument();
var J=K.getText();
var E=K.getStart();
var C=Math.round(this._band.dateToPixelOffset(E));
var A=Math.round(C+N.iconWidth/2);
var I=Math.round(C-N.iconWidth/2);
var G=this._frc.computeSize(J);
var D=this._findFreeTrackForSolid(A,C);
var B=this._paintEventIcon(K,D,I,N,Q);
var T=A+Q.event.label.offsetFromLine;
var P=D;
var F=this._getTrackData(D);
if(Math.min(F.solid,F.text)>=T+G.width){F.solid=I;
F.text=T;
}else{F.solid=I;
T=C+Q.event.label.offsetFromLine;
P=this._findFreeTrackForText(D,T+G.width,function(U){U.line=C-2;
});
this._getTrackData(P).text=I;
this._paintEventLine(K,C,D,P,N,Q);
}var R=Math.round(N.trackOffset+P*N.trackIncrement+N.trackHeight/2-G.height/2);
var M=this._paintEventLabel(K,J,T,R,G.width,G.height,Q);
var L=this;
var H=function(U,V,W){return L._onClickInstantEvent(B.elmt,V,K);
};
SimileAjax.DOM.registerEvent(B.elmt,"mousedown",H);
SimileAjax.DOM.registerEvent(M.elmt,"mousedown",H);
this._createHighlightDiv(O,B,Q);
this._eventIdToElmt[K.getID()]=B.elmt;
};
Timeline.DetailedEventPainter.prototype.paintImpreciseInstantEvent=function(N,Q,V,R){var X=this._timeline.getDocument();
var M=N.getText();
var H=N.getStart();
var S=N.getEnd();
var E=Math.round(this._band.dateToPixelOffset(H));
var B=Math.round(this._band.dateToPixelOffset(S));
var A=Math.round(E+Q.iconWidth/2);
var L=Math.round(E-Q.iconWidth/2);
var J=this._frc.computeSize(M);
var F=this._findFreeTrackForSolid(B,E);
var G=this._paintEventTape(N,F,E,B,V.event.instant.impreciseColor,V.event.instant.impreciseOpacity,Q,V);
var C=this._paintEventIcon(N,F,L,Q,V);
var I=this._getTrackData(F);
I.solid=L;
var W=A+V.event.label.offsetFromLine;
var D=W+J.width;
var T;
if(D<B){T=F;
}else{W=E+V.event.label.offsetFromLine;
D=W+J.width;
T=this._findFreeTrackForText(F,D,function(Y){Y.line=E-2;
});
this._getTrackData(T).text=L;
this._paintEventLine(N,E,F,T,Q,V);
}var U=Math.round(Q.trackOffset+T*Q.trackIncrement+Q.trackHeight/2-J.height/2);
var P=this._paintEventLabel(N,M,W,U,J.width,J.height,V);
var O=this;
var K=function(Y,Z,a){return O._onClickInstantEvent(C.elmt,Z,N);
};
SimileAjax.DOM.registerEvent(C.elmt,"mousedown",K);
SimileAjax.DOM.registerEvent(G.elmt,"mousedown",K);
SimileAjax.DOM.registerEvent(P.elmt,"mousedown",K);
this._createHighlightDiv(R,C,V);
this._eventIdToElmt[N.getID()]=C.elmt;
};
Timeline.DetailedEventPainter.prototype.paintPreciseDurationEvent=function(J,M,S,O){var T=this._timeline.getDocument();
var I=J.getText();
var D=J.getStart();
var P=J.getEnd();
var B=Math.round(this._band.dateToPixelOffset(D));
var A=Math.round(this._band.dateToPixelOffset(P));
var F=this._frc.computeSize(I);
var E=this._findFreeTrackForSolid(A);
var N=J.getColor();
N=N!=null?N:S.event.duration.color;
var C=this._paintEventTape(J,E,B,A,N,100,M,S);
var H=this._getTrackData(E);
H.solid=B;
var U=B+S.event.label.offsetFromLine;
var Q=this._findFreeTrackForText(E,U+F.width,function(V){V.line=B-2;
});
this._getTrackData(Q).text=B-2;
this._paintEventLine(J,B,E,Q,M,S);
var R=Math.round(M.trackOffset+Q*M.trackIncrement+M.trackHeight/2-F.height/2);
var L=this._paintEventLabel(J,I,U,R,F.width,F.height,S);
var K=this;
var G=function(V,W,X){return K._onClickDurationEvent(C.elmt,W,J);
};
SimileAjax.DOM.registerEvent(C.elmt,"mousedown",G);
SimileAjax.DOM.registerEvent(L.elmt,"mousedown",G);
this._createHighlightDiv(O,C,S);
this._eventIdToElmt[J.getID()]=C.elmt;
};
Timeline.DetailedEventPainter.prototype.paintImpreciseDurationEvent=function(L,P,W,S){var Z=this._timeline.getDocument();
var K=L.getText();
var D=L.getStart();
var Q=L.getLatestStart();
var T=L.getEnd();
var X=L.getEarliestEnd();
var B=Math.round(this._band.dateToPixelOffset(D));
var F=Math.round(this._band.dateToPixelOffset(Q));
var A=Math.round(this._band.dateToPixelOffset(T));
var G=Math.round(this._band.dateToPixelOffset(X));
var H=this._frc.computeSize(K);
var E=this._findFreeTrackForSolid(A);
var R=L.getColor();
R=R!=null?R:W.event.duration.color;
var O=this._paintEventTape(L,E,B,A,W.event.duration.impreciseColor,W.event.duration.impreciseOpacity,P,W);
var C=this._paintEventTape(L,E,F,G,R,100,P,W);
var J=this._getTrackData(E);
J.solid=B;
var Y=F+W.event.label.offsetFromLine;
var U=this._findFreeTrackForText(E,Y+H.width,function(a){a.line=F-2;
});
this._getTrackData(U).text=F-2;
this._paintEventLine(L,F,E,U,P,W);
var V=Math.round(P.trackOffset+U*P.trackIncrement+P.trackHeight/2-H.height/2);
var N=this._paintEventLabel(L,K,Y,V,H.width,H.height,W);
var M=this;
var I=function(a,b,c){return M._onClickDurationEvent(C.elmt,b,L);
};
SimileAjax.DOM.registerEvent(C.elmt,"mousedown",I);
SimileAjax.DOM.registerEvent(N.elmt,"mousedown",I);
this._createHighlightDiv(S,C,W);
this._eventIdToElmt[L.getID()]=C.elmt;
};
Timeline.DetailedEventPainter.prototype._findFreeTrackForSolid=function(B,A){for(var D=0;
true;
D++){if(D<this._lowerTracks.length){var C=this._lowerTracks[D];
if(Math.min(C.solid,C.text)>B&&(!(A)||C.line>A)){return D;
}}else{this._lowerTracks.push({solid:Number.POSITIVE_INFINITY,text:Number.POSITIVE_INFINITY,line:Number.POSITIVE_INFINITY});
return D;
}if(D<this._upperTracks.length){var C=this._upperTracks[D];
if(Math.min(C.solid,C.text)>B&&(!(A)||C.line>A)){return -1-D;
}}else{this._upperTracks.push({solid:Number.POSITIVE_INFINITY,text:Number.POSITIVE_INFINITY,line:Number.POSITIVE_INFINITY});
return -1-D;
}}};
Timeline.DetailedEventPainter.prototype._findFreeTrackForText=function(D,C,H){var F;
var G;
var B;
var J;
if(D<0){F=true;
B=-D;
G=this._findFreeUpperTrackForText(B,C);
J=-1-G;
}else{if(D>0){F=false;
B=D+1;
G=this._findFreeLowerTrackForText(B,C);
J=G;
}else{var A=this._findFreeUpperTrackForText(0,C);
var I=this._findFreeLowerTrackForText(1,C);
if(I-1<=A){F=false;
B=1;
G=I;
J=G;
}else{F=true;
B=0;
G=A;
J=-1-G;
}}}if(F){if(G==this._upperTracks.length){this._upperTracks.push({solid:Number.POSITIVE_INFINITY,text:Number.POSITIVE_INFINITY,line:Number.POSITIVE_INFINITY});
}for(var E=B;
E<G;
E++){H(this._upperTracks[E]);
}}else{if(G==this._lowerTracks.length){this._lowerTracks.push({solid:Number.POSITIVE_INFINITY,text:Number.POSITIVE_INFINITY,line:Number.POSITIVE_INFINITY});
}for(var E=B;
E<G;
E++){H(this._lowerTracks[E]);
}}return J;
};
Timeline.DetailedEventPainter.prototype._findFreeLowerTrackForText=function(A,C){for(;
A<this._lowerTracks.length;
A++){var B=this._lowerTracks[A];
if(Math.min(B.solid,B.text)>=C){break;
}}return A;
};
Timeline.DetailedEventPainter.prototype._findFreeUpperTrackForText=function(A,C){for(;
A<this._upperTracks.length;
A++){var B=this._upperTracks[A];
if(Math.min(B.solid,B.text)>=C){break;
}}return A;
};
Timeline.DetailedEventPainter.prototype._getTrackData=function(A){return(A<0)?this._upperTracks[-A-1]:this._lowerTracks[A];
};
Timeline.DetailedEventPainter.prototype._paintEventLine=function(I,C,F,A,G,D){var H=Math.round(G.trackOffset+F*G.trackIncrement+G.trackHeight/2);
var J=Math.round(Math.abs(A-F)*G.trackIncrement);
var E="1px solid "+D.event.label.lineColor;
var B=this._timeline.getDocument().createElement("div");
B.style.position="absolute";
B.style.left=C+"px";
B.style.width=D.event.label.offsetFromLine+"px";
B.style.height=J+"px";
if(F>A){B.style.top=(H-J)+"px";
B.style.borderTop=E;
}else{B.style.top=H+"px";
B.style.borderBottom=E;
}B.style.borderLeft=E;
this._lineLayer.appendChild(B);
};
Timeline.DetailedEventPainter.prototype._paintEventIcon=function(I,E,B,F,D){var H=I.getIcon();
H=H!=null?H:F.icon;
var J=F.trackOffset+E*F.trackIncrement+F.trackHeight/2;
var G=Math.round(J-F.iconHeight/2);
var C=SimileAjax.Graphics.createTranslucentImage(H);
var A=this._timeline.getDocument().createElement("div");
A.style.position="absolute";
A.style.left=B+"px";
A.style.top=G+"px";
A.appendChild(C);
A.style.cursor="pointer";
if(I._title!=null){A.title=I._title;
}this._eventLayer.appendChild(A);
return{left:B,top:G,width:F.iconWidth,height:F.iconHeight,elmt:A};
};
Timeline.DetailedEventPainter.prototype._paintEventLabel=function(H,I,B,F,A,J,D){var G=this._timeline.getDocument();
var K=G.createElement("div");
K.style.position="absolute";
K.style.left=B+"px";
K.style.width=A+"px";
K.style.top=F+"px";
K.style.height=J+"px";
K.style.backgroundColor=D.event.label.backgroundColor;
SimileAjax.Graphics.setOpacity(K,D.event.label.backgroundOpacity);
this._eventLayer.appendChild(K);
var E=G.createElement("div");
E.style.position="absolute";
E.style.left=B+"px";
E.style.width=A+"px";
E.style.top=F+"px";
E.innerHTML=I;
E.style.cursor="pointer";
if(H._title!=null){E.title=H._title;
}var C=H.getTextColor();
if(C==null){C=H.getColor();
}if(C!=null){E.style.color=C;
}this._eventLayer.appendChild(E);
return{left:B,top:F,width:A,height:J,elmt:E};
};
Timeline.DetailedEventPainter.prototype._paintEventTape=function(L,H,E,A,C,G,I,F){var B=A-E;
var D=F.event.tape.height;
var M=I.trackOffset+H*I.trackIncrement+I.trackHeight/2;
var J=Math.round(M-D/2);
var K=this._timeline.getDocument().createElement("div");
K.style.position="absolute";
K.style.left=E+"px";
K.style.width=B+"px";
K.style.top=J+"px";
K.style.height=D+"px";
K.style.backgroundColor=C;
K.style.overflow="hidden";
K.style.cursor="pointer";
if(L._title!=null){K.title=L._title;
}SimileAjax.Graphics.setOpacity(K,G);
this._eventLayer.appendChild(K);
return{left:E,top:J,width:B,height:D,elmt:K};
};
Timeline.DetailedEventPainter.prototype._createHighlightDiv=function(A,C,E){if(A>=0){var D=this._timeline.getDocument();
var G=E.event;
var B=G.highlightColors[Math.min(A,G.highlightColors.length-1)];
var F=D.createElement("div");
F.style.position="absolute";
F.style.overflow="hidden";
F.style.left=(C.left-2)+"px";
F.style.width=(C.width+4)+"px";
F.style.top=(C.top-2)+"px";
F.style.height=(C.height+4)+"px";
F.style.background=B;
this._highlightLayer.appendChild(F);
}};
Timeline.DetailedEventPainter.prototype._onClickInstantEvent=function(B,C,A){var D=SimileAjax.DOM.getPageCoordinates(B);
this._showBubble(D.left+Math.ceil(B.offsetWidth/2),D.top+Math.ceil(B.offsetHeight/2),A);
this._fireOnSelect(A.getID());
C.cancelBubble=true;
SimileAjax.DOM.cancelEvent(C);
return false;
};
Timeline.DetailedEventPainter.prototype._onClickDurationEvent=function(D,C,B){if("pageX" in C){var A=C.pageX;
var F=C.pageY;
}else{var E=SimileAjax.DOM.getPageCoordinates(D);
var A=C.offsetX+E.left;
var F=C.offsetY+E.top;
}this._showBubble(A,F,B);
this._fireOnSelect(B.getID());
C.cancelBubble=true;
SimileAjax.DOM.cancelEvent(C);
return false;
};
Timeline.DetailedEventPainter.prototype.showBubble=function(A){var B=this._eventIdToElmt[A.getID()];
if(B){var C=SimileAjax.DOM.getPageCoordinates(B);
this._showBubble(C.left+B.offsetWidth/2,C.top+B.offsetHeight/2,A);
}};
Timeline.DetailedEventPainter.prototype._showBubble=function(A,D,B){var C=document.createElement("div");
B.fillInfoBubble(C,this._params.theme,this._band.getLabeller());
SimileAjax.WindowManager.cancelPopups();
SimileAjax.Graphics.createBubbleForContentAndPoint(C,A,D,this._params.theme.event.bubble.width);
};
Timeline.DetailedEventPainter.prototype._fireOnSelect=function(B){for(var A=0;
A<this._onSelectListeners.length;
A++){this._onSelectListeners[A](B);
}};


/* ether-painters.js */
Timeline.GregorianEtherPainter=function(A){this._params=A;
this._theme=A.theme;
this._unit=A.unit;
this._multiple=("multiple" in A)?A.multiple:1;
};
Timeline.GregorianEtherPainter.prototype.initialize=function(C,B){this._band=C;
this._timeline=B;
this._backgroundLayer=C.createLayerDiv(0);
this._backgroundLayer.setAttribute("name","ether-background");
this._backgroundLayer.className="timeline-ether-bg";
this._markerLayer=null;
this._lineLayer=null;
var D=("align" in this._params&&this._params.align!=undefined)?this._params.align:this._theme.ether.interval.marker[B.isHorizontal()?"hAlign":"vAlign"];
var A=("showLine" in this._params)?this._params.showLine:this._theme.ether.interval.line.show;
this._intervalMarkerLayout=new Timeline.EtherIntervalMarkerLayout(this._timeline,this._band,this._theme,D,A);
this._highlight=new Timeline.EtherHighlight(this._timeline,this._band,this._theme,this._backgroundLayer);
};
Timeline.GregorianEtherPainter.prototype.setHighlight=function(A,B){this._highlight.position(A,B);
};
Timeline.GregorianEtherPainter.prototype.paint=function(){if(this._markerLayer){this._band.removeLayerDiv(this._markerLayer);
}this._markerLayer=this._band.createLayerDiv(100);
this._markerLayer.setAttribute("name","ether-markers");
this._markerLayer.style.display="none";
if(this._lineLayer){this._band.removeLayerDiv(this._lineLayer);
}this._lineLayer=this._band.createLayerDiv(1);
this._lineLayer.setAttribute("name","ether-lines");
this._lineLayer.style.display="none";
var C=this._band.getMinDate();
var F=this._band.getMaxDate();
var B=this._band.getTimeZone();
var E=this._band.getLabeller();
SimileAjax.DateTime.roundDownToInterval(C,this._unit,B,this._multiple,this._theme.firstDayOfWeek);
var D=this;
var A=function(G){for(var H=0;
H<D._multiple;
H++){SimileAjax.DateTime.incrementByInterval(G,D._unit);
}};
while(C.getTime()<F.getTime()){this._intervalMarkerLayout.createIntervalMarker(C,E,this._unit,this._markerLayer,this._lineLayer);
A(C);
}this._markerLayer.style.display="block";
this._lineLayer.style.display="block";
};
Timeline.GregorianEtherPainter.prototype.softPaint=function(){};
Timeline.GregorianEtherPainter.prototype.zoom=function(A){if(A!=0){this._unit+=A;
}};
Timeline.HotZoneGregorianEtherPainter=function(G){this._params=G;
this._theme=G.theme;
this._zones=[{startTime:Number.NEGATIVE_INFINITY,endTime:Number.POSITIVE_INFINITY,unit:G.unit,multiple:1}];
for(var E=0;
E<G.zones.length;
E++){var B=G.zones[E];
var D=SimileAjax.DateTime.parseGregorianDateTime(B.start).getTime();
var F=SimileAjax.DateTime.parseGregorianDateTime(B.end).getTime();
for(var C=0;
C<this._zones.length&&F>D;
C++){var A=this._zones[C];
if(D<A.endTime){if(D>A.startTime){this._zones.splice(C,0,{startTime:A.startTime,endTime:D,unit:A.unit,multiple:A.multiple});
C++;
A.startTime=D;
}if(F<A.endTime){this._zones.splice(C,0,{startTime:D,endTime:F,unit:B.unit,multiple:(B.multiple)?B.multiple:1});
C++;
A.startTime=F;
D=F;
}else{A.multiple=B.multiple;
A.unit=B.unit;
D=A.endTime;
}}}}};
Timeline.HotZoneGregorianEtherPainter.prototype.initialize=function(C,B){this._band=C;
this._timeline=B;
this._backgroundLayer=C.createLayerDiv(0);
this._backgroundLayer.setAttribute("name","ether-background");
this._backgroundLayer.className="timeline-ether-bg";
this._markerLayer=null;
this._lineLayer=null;
var D=("align" in this._params&&this._params.align!=undefined)?this._params.align:this._theme.ether.interval.marker[B.isHorizontal()?"hAlign":"vAlign"];
var A=("showLine" in this._params)?this._params.showLine:this._theme.ether.interval.line.show;
this._intervalMarkerLayout=new Timeline.EtherIntervalMarkerLayout(this._timeline,this._band,this._theme,D,A);
this._highlight=new Timeline.EtherHighlight(this._timeline,this._band,this._theme,this._backgroundLayer);
};
Timeline.HotZoneGregorianEtherPainter.prototype.setHighlight=function(A,B){this._highlight.position(A,B);
};
Timeline.HotZoneGregorianEtherPainter.prototype.paint=function(){if(this._markerLayer){this._band.removeLayerDiv(this._markerLayer);
}this._markerLayer=this._band.createLayerDiv(100);
this._markerLayer.setAttribute("name","ether-markers");
this._markerLayer.style.display="none";
if(this._lineLayer){this._band.removeLayerDiv(this._lineLayer);
}this._lineLayer=this._band.createLayerDiv(1);
this._lineLayer.setAttribute("name","ether-lines");
this._lineLayer.style.display="none";
var D=this._band.getMinDate();
var A=this._band.getMaxDate();
var K=this._band.getTimeZone();
var I=this._band.getLabeller();
var B=this;
var L=function(N,M){for(var O=0;
O<M.multiple;
O++){SimileAjax.DateTime.incrementByInterval(N,M.unit);
}};
var C=0;
while(C<this._zones.length){if(D.getTime()<this._zones[C].endTime){break;
}C++;
}var E=this._zones.length-1;
while(E>=0){if(A.getTime()>this._zones[E].startTime){break;
}E--;
}for(var H=C;
H<=E;
H++){var G=this._zones[H];
var J=new Date(Math.max(D.getTime(),G.startTime));
var F=new Date(Math.min(A.getTime(),G.endTime));
SimileAjax.DateTime.roundDownToInterval(J,G.unit,K,G.multiple,this._theme.firstDayOfWeek);
SimileAjax.DateTime.roundUpToInterval(F,G.unit,K,G.multiple,this._theme.firstDayOfWeek);
while(J.getTime()<F.getTime()){this._intervalMarkerLayout.createIntervalMarker(J,I,G.unit,this._markerLayer,this._lineLayer);
L(J,G);
}}this._markerLayer.style.display="block";
this._lineLayer.style.display="block";
};
Timeline.HotZoneGregorianEtherPainter.prototype.softPaint=function(){};
Timeline.HotZoneGregorianEtherPainter.prototype.zoom=function(B){if(B!=0){for(var A=0;
A<this._zones.length;
++A){if(this._zones[A]){this._zones[A].unit+=B;
}}}};
Timeline.YearCountEtherPainter=function(A){this._params=A;
this._theme=A.theme;
this._startDate=SimileAjax.DateTime.parseGregorianDateTime(A.startDate);
this._multiple=("multiple" in A)?A.multiple:1;
};
Timeline.YearCountEtherPainter.prototype.initialize=function(C,B){this._band=C;
this._timeline=B;
this._backgroundLayer=C.createLayerDiv(0);
this._backgroundLayer.setAttribute("name","ether-background");
this._backgroundLayer.className="timeline-ether-bg";
this._markerLayer=null;
this._lineLayer=null;
var D=("align" in this._params)?this._params.align:this._theme.ether.interval.marker[B.isHorizontal()?"hAlign":"vAlign"];
var A=("showLine" in this._params)?this._params.showLine:this._theme.ether.interval.line.show;
this._intervalMarkerLayout=new Timeline.EtherIntervalMarkerLayout(this._timeline,this._band,this._theme,D,A);
this._highlight=new Timeline.EtherHighlight(this._timeline,this._band,this._theme,this._backgroundLayer);
};
Timeline.YearCountEtherPainter.prototype.setHighlight=function(A,B){this._highlight.position(A,B);
};
Timeline.YearCountEtherPainter.prototype.paint=function(){if(this._markerLayer){this._band.removeLayerDiv(this._markerLayer);
}this._markerLayer=this._band.createLayerDiv(100);
this._markerLayer.setAttribute("name","ether-markers");
this._markerLayer.style.display="none";
if(this._lineLayer){this._band.removeLayerDiv(this._lineLayer);
}this._lineLayer=this._band.createLayerDiv(1);
this._lineLayer.setAttribute("name","ether-lines");
this._lineLayer.style.display="none";
var B=new Date(this._startDate.getTime());
var F=this._band.getMaxDate();
var E=this._band.getMinDate().getUTCFullYear()-this._startDate.getUTCFullYear();
B.setUTCFullYear(this._band.getMinDate().getUTCFullYear()-E%this._multiple);
var C=this;
var A=function(G){for(var H=0;
H<C._multiple;
H++){SimileAjax.DateTime.incrementByInterval(G,SimileAjax.DateTime.YEAR);
}};
var D={labelInterval:function(G,I){var H=G.getUTCFullYear()-C._startDate.getUTCFullYear();
return{text:H,emphasized:H==0};
}};
while(B.getTime()<F.getTime()){this._intervalMarkerLayout.createIntervalMarker(B,D,SimileAjax.DateTime.YEAR,this._markerLayer,this._lineLayer);
A(B);
}this._markerLayer.style.display="block";
this._lineLayer.style.display="block";
};
Timeline.YearCountEtherPainter.prototype.softPaint=function(){};
Timeline.QuarterlyEtherPainter=function(A){this._params=A;
this._theme=A.theme;
this._startDate=SimileAjax.DateTime.parseGregorianDateTime(A.startDate);
};
Timeline.QuarterlyEtherPainter.prototype.initialize=function(C,B){this._band=C;
this._timeline=B;
this._backgroundLayer=C.createLayerDiv(0);
this._backgroundLayer.setAttribute("name","ether-background");
this._backgroundLayer.className="timeline-ether-bg";
this._markerLayer=null;
this._lineLayer=null;
var D=("align" in this._params)?this._params.align:this._theme.ether.interval.marker[B.isHorizontal()?"hAlign":"vAlign"];
var A=("showLine" in this._params)?this._params.showLine:this._theme.ether.interval.line.show;
this._intervalMarkerLayout=new Timeline.EtherIntervalMarkerLayout(this._timeline,this._band,this._theme,D,A);
this._highlight=new Timeline.EtherHighlight(this._timeline,this._band,this._theme,this._backgroundLayer);
};
Timeline.QuarterlyEtherPainter.prototype.setHighlight=function(A,B){this._highlight.position(A,B);
};
Timeline.QuarterlyEtherPainter.prototype.paint=function(){if(this._markerLayer){this._band.removeLayerDiv(this._markerLayer);
}this._markerLayer=this._band.createLayerDiv(100);
this._markerLayer.setAttribute("name","ether-markers");
this._markerLayer.style.display="none";
if(this._lineLayer){this._band.removeLayerDiv(this._lineLayer);
}this._lineLayer=this._band.createLayerDiv(1);
this._lineLayer.setAttribute("name","ether-lines");
this._lineLayer.style.display="none";
var B=new Date(0);
var E=this._band.getMaxDate();
B.setUTCFullYear(Math.max(this._startDate.getUTCFullYear(),this._band.getMinDate().getUTCFullYear()));
B.setUTCMonth(this._startDate.getUTCMonth());
var C=this;
var A=function(F){F.setUTCMonth(F.getUTCMonth()+3);
};
var D={labelInterval:function(F,H){var G=(4+(F.getUTCMonth()-C._startDate.getUTCMonth())/3)%4;
if(G!=0){return{text:"Q"+(G+1),emphasized:false};
}else{return{text:"Y"+(F.getUTCFullYear()-C._startDate.getUTCFullYear()+1),emphasized:true};
}}};
while(B.getTime()<E.getTime()){this._intervalMarkerLayout.createIntervalMarker(B,D,SimileAjax.DateTime.YEAR,this._markerLayer,this._lineLayer);
A(B);
}this._markerLayer.style.display="block";
this._lineLayer.style.display="block";
};
Timeline.QuarterlyEtherPainter.prototype.softPaint=function(){};
Timeline.EtherIntervalMarkerLayout=function(M,L,C,E,H){var A=M.isHorizontal();
if(A){if(E=="Top"){this.positionDiv=function(O,N){O.style.left=N+"px";
O.style.top="0px";
};
}else{this.positionDiv=function(O,N){O.style.left=N+"px";
O.style.bottom="0px";
};
}}else{if(E=="Left"){this.positionDiv=function(O,N){O.style.top=N+"px";
O.style.left="0px";
};
}else{this.positionDiv=function(O,N){O.style.top=N+"px";
O.style.right="0px";
};
}}var D=C.ether.interval.marker;
var I=C.ether.interval.line;
var B=C.ether.interval.weekend;
var K=(A?"h":"v")+E;
var G=D[K+"Styler"];
var J=D[K+"EmphasizedStyler"];
var F=SimileAjax.DateTime.gregorianUnitLengths[SimileAjax.DateTime.DAY];
this.createIntervalMarker=function(T,a,b,c,Q){var U=Math.round(L.dateToPixelOffset(T));
if(H&&b!=SimileAjax.DateTime.WEEK){var V=M.getDocument().createElement("div");
V.className="timeline-ether-lines";
if(I.opacity<100){SimileAjax.Graphics.setOpacity(V,I.opacity);
}if(A){V.style.left=U+"px";
}else{V.style.top=U+"px";
}Q.appendChild(V);
}if(b==SimileAjax.DateTime.WEEK){var N=C.firstDayOfWeek;
var W=new Date(T.getTime()+(6-N-7)*F);
var Z=new Date(W.getTime()+2*F);
var X=Math.round(L.dateToPixelOffset(W));
var S=Math.round(L.dateToPixelOffset(Z));
var R=Math.max(1,S-X);
var P=M.getDocument().createElement("div");
P.className="timeline-ether-weekends";
if(B.opacity<100){SimileAjax.Graphics.setOpacity(P,B.opacity);
}if(A){P.style.left=X+"px";
P.style.width=R+"px";
}else{P.style.top=X+"px";
P.style.height=R+"px";
}Q.appendChild(P);
}var Y=a.labelInterval(T,b);
var O=M.getDocument().createElement("div");
O.innerHTML=Y.text;
O.className="timeline-date-label";
if(Y.emphasized){O.className+=" timeline-date-label-em";
}this.positionDiv(O,U);
c.appendChild(O);
return O;
};
};
Timeline.EtherHighlight=function(C,E,D,B){var A=C.isHorizontal();
this._highlightDiv=null;
this._createHighlightDiv=function(){if(this._highlightDiv==null){this._highlightDiv=C.getDocument().createElement("div");
this._highlightDiv.setAttribute("name","ether-highlight");
this._highlightDiv.className="timeline-ether-highlight";
var F=D.ether.highlightOpacity;
if(F<100){SimileAjax.Graphics.setOpacity(this._highlightDiv,F);
}B.appendChild(this._highlightDiv);
}};
this.position=function(F,I){this._createHighlightDiv();
var J=Math.round(E.dateToPixelOffset(F));
var H=Math.round(E.dateToPixelOffset(I));
var G=Math.max(H-J,3);
if(A){this._highlightDiv.style.left=J+"px";
this._highlightDiv.style.width=G+"px";
this._highlightDiv.style.height=(E.getViewWidth()-4)+"px";
}else{this._highlightDiv.style.top=J+"px";
this._highlightDiv.style.height=G+"px";
this._highlightDiv.style.width=(E.getViewWidth()-4)+"px";
}};
};


/* ethers.js */
Timeline.LinearEther=function(A){this._params=A;
this._interval=A.interval;
this._pixelsPerInterval=A.pixelsPerInterval;
};
Timeline.LinearEther.prototype.initialize=function(B,A){this._band=B;
this._timeline=A;
this._unit=A.getUnit();
if("startsOn" in this._params){this._start=this._unit.parseFromObject(this._params.startsOn);
}else{if("endsOn" in this._params){this._start=this._unit.parseFromObject(this._params.endsOn);
this.shiftPixels(-this._timeline.getPixelLength());
}else{if("centersOn" in this._params){this._start=this._unit.parseFromObject(this._params.centersOn);
this.shiftPixels(-this._timeline.getPixelLength()/2);
}else{this._start=this._unit.makeDefaultValue();
this.shiftPixels(-this._timeline.getPixelLength()/2);
}}}};
Timeline.LinearEther.prototype.setDate=function(A){this._start=this._unit.cloneValue(A);
};
Timeline.LinearEther.prototype.shiftPixels=function(B){var A=this._interval*B/this._pixelsPerInterval;
this._start=this._unit.change(this._start,A);
};
Timeline.LinearEther.prototype.dateToPixelOffset=function(A){var B=this._unit.compare(A,this._start);
return this._pixelsPerInterval*B/this._interval;
};
Timeline.LinearEther.prototype.pixelOffsetToDate=function(B){var A=B*this._interval/this._pixelsPerInterval;
return this._unit.change(this._start,A);
};
Timeline.LinearEther.prototype.zoom=function(D){var B=0;
var A=this._band._zoomIndex;
var C=A;
if(D&&(A>0)){C=A-1;
}if(!D&&(A<(this._band._zoomSteps.length-1))){C=A+1;
}this._band._zoomIndex=C;
this._interval=SimileAjax.DateTime.gregorianUnitLengths[this._band._zoomSteps[C].unit];
this._pixelsPerInterval=this._band._zoomSteps[C].pixelsPerInterval;
B=this._band._zoomSteps[C].unit-this._band._zoomSteps[A].unit;
return B;
};
Timeline.HotZoneEther=function(A){this._params=A;
this._interval=A.interval;
this._pixelsPerInterval=A.pixelsPerInterval;
this._theme=A.theme;
};
Timeline.HotZoneEther.prototype.initialize=function(H,I){this._band=H;
this._timeline=I;
this._unit=I.getUnit();
this._zones=[{startTime:Number.NEGATIVE_INFINITY,endTime:Number.POSITIVE_INFINITY,magnify:1}];
var B=this._params;
for(var D=0;
D<B.zones.length;
D++){var G=B.zones[D];
var E=this._unit.parseFromObject(G.start);
var F=this._unit.parseFromObject(G.end);
for(var C=0;
C<this._zones.length&&this._unit.compare(F,E)>0;
C++){var A=this._zones[C];
if(this._unit.compare(E,A.endTime)<0){if(this._unit.compare(E,A.startTime)>0){this._zones.splice(C,0,{startTime:A.startTime,endTime:E,magnify:A.magnify});
C++;
A.startTime=E;
}if(this._unit.compare(F,A.endTime)<0){this._zones.splice(C,0,{startTime:E,endTime:F,magnify:G.magnify*A.magnify});
C++;
A.startTime=F;
E=F;
}else{A.magnify*=G.magnify;
E=A.endTime;
}}}}if("startsOn" in this._params){this._start=this._unit.parseFromObject(this._params.startsOn);
}else{if("endsOn" in this._params){this._start=this._unit.parseFromObject(this._params.endsOn);
this.shiftPixels(-this._timeline.getPixelLength());
}else{if("centersOn" in this._params){this._start=this._unit.parseFromObject(this._params.centersOn);
this.shiftPixels(-this._timeline.getPixelLength()/2);
}else{this._start=this._unit.makeDefaultValue();
this.shiftPixels(-this._timeline.getPixelLength()/2);
}}}};
Timeline.HotZoneEther.prototype.setDate=function(A){this._start=this._unit.cloneValue(A);
};
Timeline.HotZoneEther.prototype.shiftPixels=function(A){this._start=this.pixelOffsetToDate(A);
};
Timeline.HotZoneEther.prototype.dateToPixelOffset=function(A){return this._dateDiffToPixelOffset(this._start,A);
};
Timeline.HotZoneEther.prototype.pixelOffsetToDate=function(A){return this._pixelOffsetToDate(A,this._start);
};
Timeline.HotZoneEther.prototype.zoom=function(D){var B=0;
var A=this._band._zoomIndex;
var C=A;
if(D&&(A>0)){C=A-1;
}if(!D&&(A<(this._band._zoomSteps.length-1))){C=A+1;
}this._band._zoomIndex=C;
this._interval=SimileAjax.DateTime.gregorianUnitLengths[this._band._zoomSteps[C].unit];
this._pixelsPerInterval=this._band._zoomSteps[C].pixelsPerInterval;
B=this._band._zoomSteps[C].unit-this._band._zoomSteps[A].unit;
return B;
};
Timeline.HotZoneEther.prototype._dateDiffToPixelOffset=function(I,D){var B=this._getScale();
var H=I;
var C=D;
var A=0;
if(this._unit.compare(H,C)<0){var G=0;
while(G<this._zones.length){if(this._unit.compare(H,this._zones[G].endTime)<0){break;
}G++;
}while(this._unit.compare(H,C)<0){var E=this._zones[G];
var F=this._unit.earlier(C,E.endTime);
A+=(this._unit.compare(F,H)/(B/E.magnify));
H=F;
G++;
}}else{var G=this._zones.length-1;
while(G>=0){if(this._unit.compare(H,this._zones[G].startTime)>0){break;
}G--;
}while(this._unit.compare(H,C)>0){var E=this._zones[G];
var F=this._unit.later(C,E.startTime);
A+=(this._unit.compare(F,H)/(B/E.magnify));
H=F;
G--;
}}return A;
};
Timeline.HotZoneEther.prototype._pixelOffsetToDate=function(H,C){var G=this._getScale();
var E=C;
if(H>0){var F=0;
while(F<this._zones.length){if(this._unit.compare(E,this._zones[F].endTime)<0){break;
}F++;
}while(H>0){var A=this._zones[F];
var D=G/A.magnify;
if(A.endTime==Number.POSITIVE_INFINITY){E=this._unit.change(E,H*D);
H=0;
}else{var B=this._unit.compare(A.endTime,E)/D;
if(B>H){E=this._unit.change(E,H*D);
H=0;
}else{E=A.endTime;
H-=B;
}}F++;
}}else{var F=this._zones.length-1;
while(F>=0){if(this._unit.compare(E,this._zones[F].startTime)>0){break;
}F--;
}H=-H;
while(H>0){var A=this._zones[F];
var D=G/A.magnify;
if(A.startTime==Number.NEGATIVE_INFINITY){E=this._unit.change(E,-H*D);
H=0;
}else{var B=this._unit.compare(E,A.startTime)/D;
if(B>H){E=this._unit.change(E,-H*D);
H=0;
}else{E=A.startTime;
H-=B;
}}F--;
}}return E;
};
Timeline.HotZoneEther.prototype._getScale=function(){return this._interval/this._pixelsPerInterval;
};


/* labellers.js */
Timeline.GregorianDateLabeller=function(A,B){this._locale=A;
this._timeZone=B;
};
Timeline.GregorianDateLabeller.monthNames=[];
Timeline.GregorianDateLabeller.dayNames=[];
Timeline.GregorianDateLabeller.labelIntervalFunctions=[];
Timeline.GregorianDateLabeller.getMonthName=function(B,A){return Timeline.GregorianDateLabeller.monthNames[A][B];
};
Timeline.GregorianDateLabeller.prototype.labelInterval=function(A,C){var B=Timeline.GregorianDateLabeller.labelIntervalFunctions[this._locale];
if(B==null){B=Timeline.GregorianDateLabeller.prototype.defaultLabelInterval;
}return B.call(this,A,C);
};
Timeline.GregorianDateLabeller.prototype.labelPrecise=function(A){return SimileAjax.DateTime.removeTimeZoneOffset(A,this._timeZone).toUTCString();
};
Timeline.GregorianDateLabeller.prototype.defaultLabelInterval=function(B,F){var C;
var E=false;
B=SimileAjax.DateTime.removeTimeZoneOffset(B,this._timeZone);
switch(F){case SimileAjax.DateTime.MILLISECOND:C=B.getUTCMilliseconds();
break;
case SimileAjax.DateTime.SECOND:C=B.getUTCSeconds();
break;
case SimileAjax.DateTime.MINUTE:var A=B.getUTCMinutes();
if(A==0){C=B.getUTCHours()+":00";
E=true;
}else{C=A;
}break;
case SimileAjax.DateTime.HOUR:C=B.getUTCHours()+"hr";
break;
case SimileAjax.DateTime.DAY:C=Timeline.GregorianDateLabeller.getMonthName(B.getUTCMonth(),this._locale)+" "+B.getUTCDate();
break;
case SimileAjax.DateTime.WEEK:C=Timeline.GregorianDateLabeller.getMonthName(B.getUTCMonth(),this._locale)+" "+B.getUTCDate();
break;
case SimileAjax.DateTime.MONTH:var A=B.getUTCMonth();
if(A!=0){C=Timeline.GregorianDateLabeller.getMonthName(A,this._locale);
break;
}case SimileAjax.DateTime.YEAR:case SimileAjax.DateTime.DECADE:case SimileAjax.DateTime.CENTURY:case SimileAjax.DateTime.MILLENNIUM:var D=B.getUTCFullYear();
if(D>0){C=B.getUTCFullYear();
}else{C=(1-D)+"BC";
}E=(F==SimileAjax.DateTime.MONTH)||(F==SimileAjax.DateTime.DECADE&&D%100==0)||(F==SimileAjax.DateTime.CENTURY&&D%1000==0);
break;
default:C=B.toUTCString();
}return{text:C,emphasized:E};
};


/* original-painter.js */
Timeline.OriginalEventPainter=function(A){this._params=A;
this._onSelectListeners=[];
this._filterMatcher=null;
this._highlightMatcher=null;
this._frc=null;
this._eventIdToElmt={};
};
Timeline.OriginalEventPainter.prototype.initialize=function(B,A){this._band=B;
this._timeline=A;
this._backLayer=null;
this._eventLayer=null;
this._lineLayer=null;
this._highlightLayer=null;
this._eventIdToElmt=null;
};
Timeline.OriginalEventPainter.prototype.addOnSelectListener=function(A){this._onSelectListeners.push(A);
};
Timeline.OriginalEventPainter.prototype.removeOnSelectListener=function(B){for(var A=0;
A<this._onSelectListeners.length;
A++){if(this._onSelectListeners[A]==B){this._onSelectListeners.splice(A,1);
break;
}}};
Timeline.OriginalEventPainter.prototype.getFilterMatcher=function(){return this._filterMatcher;
};
Timeline.OriginalEventPainter.prototype.setFilterMatcher=function(A){this._filterMatcher=A;
};
Timeline.OriginalEventPainter.prototype.getHighlightMatcher=function(){return this._highlightMatcher;
};
Timeline.OriginalEventPainter.prototype.setHighlightMatcher=function(A){this._highlightMatcher=A;
};
Timeline.OriginalEventPainter.prototype.paint=function(){var B=this._band.getEventSource();
if(B==null){return ;
}this._eventIdToElmt={};
this._prepareForPainting();
var I=this._params.theme.event;
var G=Math.max(I.track.height,I.tape.height+this._frc.getLineHeight());
var F={trackOffset:I.track.gap,trackHeight:G,trackGap:I.track.gap,trackIncrement:G+I.track.gap,icon:I.instant.icon,iconWidth:I.instant.iconWidth,iconHeight:I.instant.iconHeight,labelWidth:I.label.width};
var C=this._band.getMinDate();
var A=this._band.getMaxDate();
var J=(this._filterMatcher!=null)?this._filterMatcher:function(K){return true;
};
var E=(this._highlightMatcher!=null)?this._highlightMatcher:function(K){return -1;
};
var D=B.getEventReverseIterator(C,A);
while(D.hasNext()){var H=D.next();
if(J(H)){this.paintEvent(H,F,this._params.theme,E(H));
}}this._highlightLayer.style.display="block";
this._lineLayer.style.display="block";
this._eventLayer.style.display="block";
};
Timeline.OriginalEventPainter.prototype.softPaint=function(){};
Timeline.OriginalEventPainter.prototype._prepareForPainting=function(){var B=this._band;
if(this._backLayer==null){this._backLayer=this._band.createLayerDiv(0,"timeline-band-events");
this._backLayer.style.visibility="hidden";
var A=document.createElement("span");
A.className="timeline-event-label";
this._backLayer.appendChild(A);
this._frc=SimileAjax.Graphics.getFontRenderingContext(A);
}this._frc.update();
this._tracks=[];
if(this._highlightLayer!=null){B.removeLayerDiv(this._highlightLayer);
}this._highlightLayer=B.createLayerDiv(105,"timeline-band-highlights");
this._highlightLayer.style.display="none";
if(this._lineLayer!=null){B.removeLayerDiv(this._lineLayer);
}this._lineLayer=B.createLayerDiv(110,"timeline-band-lines");
this._lineLayer.style.display="none";
if(this._eventLayer!=null){B.removeLayerDiv(this._eventLayer);
}this._eventLayer=B.createLayerDiv(115,"timeline-band-events");
this._eventLayer.style.display="none";
};
Timeline.OriginalEventPainter.prototype.paintEvent=function(B,C,D,A){if(B.isInstant()){this.paintInstantEvent(B,C,D,A);
}else{this.paintDurationEvent(B,C,D,A);
}};
Timeline.OriginalEventPainter.prototype.paintInstantEvent=function(B,C,D,A){if(B.isImprecise()){this.paintImpreciseInstantEvent(B,C,D,A);
}else{this.paintPreciseInstantEvent(B,C,D,A);
}};
Timeline.OriginalEventPainter.prototype.paintDurationEvent=function(B,C,D,A){if(B.isImprecise()){this.paintImpreciseDurationEvent(B,C,D,A);
}else{this.paintPreciseDurationEvent(B,C,D,A);
}};
Timeline.OriginalEventPainter.prototype.paintPreciseInstantEvent=function(J,N,P,O){var S=this._timeline.getDocument();
var I=J.getText();
var E=J.getStart();
var C=Math.round(this._band.dateToPixelOffset(E));
var A=Math.round(C+N.iconWidth/2);
var H=Math.round(C-N.iconWidth/2);
var F=this._frc.computeSize(I);
var T=A+P.event.label.offsetFromLine;
var D=T+F.width;
var R=D;
var L=this._findFreeTrack(R);
var Q=Math.round(N.trackOffset+L*N.trackIncrement+N.trackHeight/2-F.height/2);
var B=this._paintEventIcon(J,L,H,N,P);
var M=this._paintEventLabel(J,I,T,Q,F.width,F.height,P);
var K=this;
var G=function(U,V,W){return K._onClickInstantEvent(B.elmt,V,J);
};
SimileAjax.DOM.registerEvent(B.elmt,"mousedown",G);
SimileAjax.DOM.registerEvent(M.elmt,"mousedown",G);
this._createHighlightDiv(O,B,P);
this._eventIdToElmt[J.getID()]=B.elmt;
this._tracks[L]=H;
};
Timeline.OriginalEventPainter.prototype.paintImpreciseInstantEvent=function(L,P,U,R){var W=this._timeline.getDocument();
var K=L.getText();
var G=L.getStart();
var S=L.getEnd();
var D=Math.round(this._band.dateToPixelOffset(G));
var B=Math.round(this._band.dateToPixelOffset(S));
var A=Math.round(D+P.iconWidth/2);
var J=Math.round(D-P.iconWidth/2);
var H=this._frc.computeSize(K);
var X=A+U.event.label.offsetFromLine;
var E=X+H.width;
var V=Math.max(E,B);
var N=this._findFreeTrack(V);
var T=Math.round(P.trackOffset+N*P.trackIncrement+P.trackHeight/2-H.height/2);
var C=this._paintEventIcon(L,N,J,P,U);
var O=this._paintEventLabel(L,K,X,T,H.width,H.height,U);
var Q=L.getColor();
Q=Q!=null?Q:U.event.instant.impreciseColor;
var F=this._paintEventTape(L,N,D,B,Q,U.event.instant.impreciseOpacity,P,U);
var M=this;
var I=function(Y,Z,a){return M._onClickInstantEvent(C.elmt,Z,L);
};
SimileAjax.DOM.registerEvent(C.elmt,"mousedown",I);
SimileAjax.DOM.registerEvent(F.elmt,"mousedown",I);
SimileAjax.DOM.registerEvent(O.elmt,"mousedown",I);
this._createHighlightDiv(R,C,U);
this._eventIdToElmt[L.getID()]=C.elmt;
this._tracks[N]=J;
};
Timeline.OriginalEventPainter.prototype.paintPreciseDurationEvent=function(I,M,Q,O){var T=this._timeline.getDocument();
var H=I.getText();
var E=I.getStart();
var P=I.getEnd();
var B=Math.round(this._band.dateToPixelOffset(E));
var A=Math.round(this._band.dateToPixelOffset(P));
var F=this._frc.computeSize(H);
var U=B;
var C=U+F.width;
var S=Math.max(C,A);
var K=this._findFreeTrack(S);
var R=Math.round(M.trackOffset+K*M.trackIncrement+Q.event.tape.height);
var N=I.getColor();
N=N!=null?N:Q.event.duration.color;
var D=this._paintEventTape(I,K,B,A,N,100,M,Q);
var L=this._paintEventLabel(I,H,U,R,F.width,F.height,Q);
var J=this;
var G=function(V,W,X){return J._onClickDurationEvent(D.elmt,W,I);
};
SimileAjax.DOM.registerEvent(D.elmt,"mousedown",G);
SimileAjax.DOM.registerEvent(L.elmt,"mousedown",G);
this._createHighlightDiv(O,D,Q);
this._eventIdToElmt[I.getID()]=D.elmt;
this._tracks[K]=B;
};
Timeline.OriginalEventPainter.prototype.paintImpreciseDurationEvent=function(K,P,V,S){var Y=this._timeline.getDocument();
var J=K.getText();
var E=K.getStart();
var Q=K.getLatestStart();
var T=K.getEnd();
var X=K.getEarliestEnd();
var B=Math.round(this._band.dateToPixelOffset(E));
var F=Math.round(this._band.dateToPixelOffset(Q));
var A=Math.round(this._band.dateToPixelOffset(T));
var G=Math.round(this._band.dateToPixelOffset(X));
var H=this._frc.computeSize(J);
var Z=F;
var C=Z+H.width;
var W=Math.max(C,A);
var M=this._findFreeTrack(W);
var U=Math.round(P.trackOffset+M*P.trackIncrement+V.event.tape.height);
var R=K.getColor();
R=R!=null?R:V.event.duration.color;
var O=this._paintEventTape(K,M,B,A,V.event.duration.impreciseColor,V.event.duration.impreciseOpacity,P,V);
var D=this._paintEventTape(K,M,F,G,R,100,P,V);
var N=this._paintEventLabel(K,J,Z,U,H.width,H.height,V);
var L=this;
var I=function(a,b,c){return L._onClickDurationEvent(D.elmt,b,K);
};
SimileAjax.DOM.registerEvent(D.elmt,"mousedown",I);
SimileAjax.DOM.registerEvent(N.elmt,"mousedown",I);
this._createHighlightDiv(S,D,V);
this._eventIdToElmt[K.getID()]=D.elmt;
this._tracks[M]=B;
};
Timeline.OriginalEventPainter.prototype._findFreeTrack=function(A){for(var C=0;
C<this._tracks.length;
C++){var B=this._tracks[C];
if(B>A){break;
}}return C;
};
Timeline.OriginalEventPainter.prototype._paintEventIcon=function(I,E,B,F,D){var H=I.getIcon();
H=H!=null?H:F.icon;
var J=F.trackOffset+E*F.trackIncrement+F.trackHeight/2;
var G=Math.round(J-F.iconHeight/2);
var C=SimileAjax.Graphics.createTranslucentImage(H);
var A=this._timeline.getDocument().createElement("div");
A.className="timeline-event-icon";
A.style.left=B+"px";
A.style.top=G+"px";
A.appendChild(C);
if(I._title!=null){A.title=I._title;
}this._eventLayer.appendChild(A);
return{left:B,top:G,width:F.iconWidth,height:F.iconHeight,elmt:A};
};
Timeline.OriginalEventPainter.prototype._paintEventLabel=function(I,J,B,G,A,K,E){var H=this._timeline.getDocument();
var F=H.createElement("div");
F.className="timeline-event-label";
F.style.left=B+"px";
F.style.width=A+"px";
F.style.top=G+"px";
F.innerHTML=J;
if(I._title!=null){F.title=I._title;
}var D=I.getTextColor();
if(D==null){D=I.getColor();
}if(D!=null){F.style.color=D;
}var C=I.getClassName();
if(C!=null){F.className+=" "+C;
}this._eventLayer.appendChild(F);
return{left:B,top:G,width:A,height:K,elmt:F};
};
Timeline.OriginalEventPainter.prototype._paintEventTape=function(O,J,G,A,D,I,K,H){var C=A-G;
var F=H.event.tape.height;
var L=K.trackOffset+J*K.trackIncrement;
var N=this._timeline.getDocument().createElement("div");
N.className="timeline-event-tape";
N.style.left=G+"px";
N.style.width=C+"px";
N.style.height=F+"px";
N.style.top=L+"px";
if(O._title!=null){N.title=O._title;
}if(D!=null){N.style.backgroundColor=D;
}var M=O.getTapeImage();
var E=O.getTapeRepeat();
E=E!=null?E:"repeat";
if(M!=null){N.style.backgroundImage="url("+M+")";
N.style.backgroundRepeat=E;
}SimileAjax.Graphics.setOpacity(N,I);
var B=O.getClassName();
if(B!=null){N.className+=" "+B;
}this._eventLayer.appendChild(N);
return{left:G,top:L,width:C,height:F,elmt:N};
};
Timeline.OriginalEventPainter.prototype._createHighlightDiv=function(A,C,E){if(A>=0){var D=this._timeline.getDocument();
var G=E.event;
var B=G.highlightColors[Math.min(A,G.highlightColors.length-1)];
var F=D.createElement("div");
F.style.position="absolute";
F.style.overflow="hidden";
F.style.left=(C.left-2)+"px";
F.style.width=(C.width+4)+"px";
F.style.top=(C.top-2)+"px";
F.style.height=(C.height+4)+"px";
this._highlightLayer.appendChild(F);
}};
Timeline.OriginalEventPainter.prototype._onClickInstantEvent=function(B,C,A){var D=SimileAjax.DOM.getPageCoordinates(B);
this._showBubble(D.left+Math.ceil(B.offsetWidth/2),D.top+Math.ceil(B.offsetHeight/2),A);
this._fireOnSelect(A.getID());
C.cancelBubble=true;
SimileAjax.DOM.cancelEvent(C);
return false;
};
Timeline.OriginalEventPainter.prototype._onClickDurationEvent=function(D,C,B){if("pageX" in C){var A=C.pageX;
var F=C.pageY;
}else{var E=SimileAjax.DOM.getPageCoordinates(D);
var A=C.offsetX+E.left;
var F=C.offsetY+E.top;
}this._showBubble(A,F,B);
this._fireOnSelect(B.getID());
C.cancelBubble=true;
SimileAjax.DOM.cancelEvent(C);
return false;
};
Timeline.OriginalEventPainter.prototype.showBubble=function(A){var B=this._eventIdToElmt[A.getID()];
if(B){var C=SimileAjax.DOM.getPageCoordinates(B);
this._showBubble(C.left+B.offsetWidth/2,C.top+B.offsetHeight/2,A);
}};
Timeline.OriginalEventPainter.prototype._showBubble=function(A,D,B){var C=document.createElement("div");
B.fillInfoBubble(C,this._params.theme,this._band.getLabeller());
SimileAjax.WindowManager.cancelPopups();
SimileAjax.Graphics.createBubbleForContentAndPoint(C,A,D,this._params.theme.event.bubble.width);
};
Timeline.OriginalEventPainter.prototype._fireOnSelect=function(B){for(var A=0;
A<this._onSelectListeners.length;
A++){this._onSelectListeners[A](B);
}};


/* overview-painter.js */
Timeline.OverviewEventPainter=function(A){this._params=A;
this._onSelectListeners=[];
this._filterMatcher=null;
this._highlightMatcher=null;
};
Timeline.OverviewEventPainter.prototype.initialize=function(B,A){this._band=B;
this._timeline=A;
this._eventLayer=null;
this._highlightLayer=null;
};
Timeline.OverviewEventPainter.prototype.addOnSelectListener=function(A){this._onSelectListeners.push(A);
};
Timeline.OverviewEventPainter.prototype.removeOnSelectListener=function(B){for(var A=0;
A<this._onSelectListeners.length;
A++){if(this._onSelectListeners[A]==B){this._onSelectListeners.splice(A,1);
break;
}}};
Timeline.OverviewEventPainter.prototype.getFilterMatcher=function(){return this._filterMatcher;
};
Timeline.OverviewEventPainter.prototype.setFilterMatcher=function(A){this._filterMatcher=A;
};
Timeline.OverviewEventPainter.prototype.getHighlightMatcher=function(){return this._highlightMatcher;
};
Timeline.OverviewEventPainter.prototype.setHighlightMatcher=function(A){this._highlightMatcher=A;
};
Timeline.OverviewEventPainter.prototype.paint=function(){var B=this._band.getEventSource();
if(B==null){return ;
}this._prepareForPainting();
var H=this._params.theme.event;
var F={trackOffset:H.overviewTrack.offset,trackHeight:H.overviewTrack.height,trackGap:H.overviewTrack.gap,trackIncrement:H.overviewTrack.height+H.overviewTrack.gap};
var C=this._band.getMinDate();
var A=this._band.getMaxDate();
var I=(this._filterMatcher!=null)?this._filterMatcher:function(J){return true;
};
var E=(this._highlightMatcher!=null)?this._highlightMatcher:function(J){return -1;
};
var D=B.getEventReverseIterator(C,A);
while(D.hasNext()){var G=D.next();
if(I(G)){this.paintEvent(G,F,this._params.theme,E(G));
}}this._highlightLayer.style.display="block";
this._eventLayer.style.display="block";
};
Timeline.OverviewEventPainter.prototype.softPaint=function(){};
Timeline.OverviewEventPainter.prototype._prepareForPainting=function(){var A=this._band;
this._tracks=[];
if(this._highlightLayer!=null){A.removeLayerDiv(this._highlightLayer);
}this._highlightLayer=A.createLayerDiv(105,"timeline-band-highlights");
this._highlightLayer.style.display="none";
if(this._eventLayer!=null){A.removeLayerDiv(this._eventLayer);
}this._eventLayer=A.createLayerDiv(110,"timeline-band-events");
this._eventLayer.style.display="none";
};
Timeline.OverviewEventPainter.prototype.paintEvent=function(B,C,D,A){if(B.isInstant()){this.paintInstantEvent(B,C,D,A);
}else{this.paintDurationEvent(B,C,D,A);
}};
Timeline.OverviewEventPainter.prototype.paintInstantEvent=function(C,F,G,B){var A=C.getStart();
var H=Math.round(this._band.dateToPixelOffset(A));
var D=C.getColor();
D=D!=null?D:G.event.duration.color;
var E=this._paintEventTick(C,H,D,100,F,G);
this._createHighlightDiv(B,E,G);
};
Timeline.OverviewEventPainter.prototype.paintDurationEvent=function(K,J,I,D){var A=K.getLatestStart();
var C=K.getEarliestEnd();
var B=Math.round(this._band.dateToPixelOffset(A));
var E=Math.round(this._band.dateToPixelOffset(C));
var H=0;
for(;
H<this._tracks.length;
H++){if(E<this._tracks[H]){break;
}}this._tracks[H]=E;
var G=K.getColor();
G=G!=null?G:I.event.duration.color;
var F=this._paintEventTape(K,H,B,E,G,100,J,I);
this._createHighlightDiv(D,F,I);
};
Timeline.OverviewEventPainter.prototype._paintEventTape=function(K,B,C,J,D,F,G,E){var H=G.trackOffset+B*G.trackIncrement;
var A=J-C;
var L=G.trackHeight;
var I=this._timeline.getDocument().createElement("div");
I.className="timeline-small-event-tape";
I.style.left=C+"px";
I.style.width=A+"px";
I.style.top=H+"px";
if(F<100){SimileAjax.Graphics.setOpacity(I,F);
}this._eventLayer.appendChild(I);
return{left:C,top:H,width:A,height:L,elmt:I};
};
Timeline.OverviewEventPainter.prototype._paintEventTick=function(J,B,D,F,G,E){var K=E.event.overviewTrack.tickHeight;
var H=G.trackOffset-K;
var A=1;
var I=this._timeline.getDocument().createElement("div");
I.className="timeline-small-event-icon";
I.style.left=B+"px";
I.style.top=H+"px";
var C=J.getClassName();
if(C){I.className+=" small-"+C;
}if(F<100){SimileAjax.Graphics.setOpacity(I,F);
}this._eventLayer.appendChild(I);
return{left:B,top:H,width:A,height:K,elmt:I};
};
Timeline.OverviewEventPainter.prototype._createHighlightDiv=function(A,C,E){if(A>=0){var D=this._timeline.getDocument();
var G=E.event;
var B=G.highlightColors[Math.min(A,G.highlightColors.length-1)];
var F=D.createElement("div");
F.style.position="absolute";
F.style.overflow="hidden";
F.style.left=(C.left-1)+"px";
F.style.width=(C.width+2)+"px";
F.style.top=(C.top-1)+"px";
F.style.height=(C.height+2)+"px";
F.style.background=B;
this._highlightLayer.appendChild(F);
}};
Timeline.OverviewEventPainter.prototype.showBubble=function(A){};


/* sources.js */
Timeline.DefaultEventSource=function(A){
    this._events=(A instanceof Object)?A:new SimileAjax.EventIndex();
    this._listeners=[];
};
Timeline.DefaultEventSource.prototype.addListener=function(A){this._listeners.push(A);
};
Timeline.DefaultEventSource.prototype.removeListener=function(B){for(var A=0;
A<this._listeners.length;
A++){if(this._listeners[A]==B){this._listeners.splice(A,1);
break;
}}};
Timeline.DefaultEventSource.prototype.loadXML=function(F,A){var B=this._getBaseURL(A);
var G=F.documentElement.getAttribute("wiki-url");
var K=F.documentElement.getAttribute("wiki-section");
var D=F.documentElement.getAttribute("date-time-format");
var E=this._events.getUnit().getParser(D);
var C=F.documentElement.firstChild;
var H=false;
while(C!=null){if(C.nodeType==1){var J="";
if(C.firstChild!=null&&C.firstChild.nodeType==3){J=C.firstChild.nodeValue;
}var I=new Timeline.DefaultEventSource.Event({id:C.getAttribute("id"),start:E(C.getAttribute("start")),end:E(C.getAttribute("end")),latestStart:E(C.getAttribute("latestStart")),earliestEnd:E(C.getAttribute("earliestEnd")),instant:C.getAttribute("isDuration")!="true",text:C.getAttribute("title"),description:J,image:this._resolveRelativeURL(C.getAttribute("image"),B),link:this._resolveRelativeURL(C.getAttribute("link"),B),icon:this._resolveRelativeURL(C.getAttribute("icon"),B),color:C.getAttribute("color"),textColor:C.getAttribute("textColor"),hoverText:C.getAttribute("hoverText"),classname:C.getAttribute("classname"),tapeImage:C.getAttribute("tapeImage"),tapeRepeat:C.getAttribute("tapeRepeat"),caption:C.getAttribute("caption"),eventID:C.getAttribute("eventID")});
I._node=C;
I.getProperty=function(L){return this._node.getAttribute(L);
};
I.setWikiInfo(G,K);
this._events.add(I);
H=true;
}C=C.nextSibling;
}if(H){this._fire("onAddMany",[]);
}};
Timeline.DefaultEventSource.prototype.loadJSON=function(F,B){var C=this._getBaseURL(B);
var I=false;
if(F&&F.events){var H=("wikiURL" in F)?F.wikiURL:null;
var K=("wikiSection" in F)?F.wikiSection:null;
var D=("dateTimeFormat" in F)?F.dateTimeFormat:null;
var G=this._events.getUnit().getParser(D);
for(var E=0;
E<F.events.length;
E++){var A=F.events[E];
var J=new Timeline.DefaultEventSource.Event({id:("id" in A)?A.id:undefined,start:G(A.start),end:G(A.end),latestStart:G(A.latestStart),earliestEnd:G(A.earliestEnd),instant:A.isDuration||false,text:A.title,description:A.description,image:this._resolveRelativeURL(A.image,C),link:this._resolveRelativeURL(A.link,C),icon:this._resolveRelativeURL(A.icon,C),color:A.color,textColor:A.textColor,hoverText:A.hoverText,classname:A.classname,tapeImage:A.tapeImage,tapeRepeat:A.tapeRepeat,caption:A.caption,eventID:A.eventID});
J._obj=A;
J.getProperty=function(L){return this._obj[L];
};
J.setWikiInfo(H,K);
this._events.add(J);
I=true;
}}if(I){this._fire("onAddMany",[]);
}};
Timeline.DefaultEventSource.prototype.loadSPARQL=function(G,A){var C=this._getBaseURL(A);
var E="iso8601";
var F=this._events.getUnit().getParser(E);
if(G==null){return ;
}var D=G.documentElement.firstChild;
while(D!=null&&(D.nodeType!=1||D.nodeName!="results")){D=D.nextSibling;
}var I=null;
var L=null;
if(D!=null){I=D.getAttribute("wiki-url");
L=D.getAttribute("wiki-section");
D=D.firstChild;
}var J=false;
while(D!=null){if(D.nodeType==1){var B={};
var H=D.firstChild;
while(H!=null){if(H.nodeType==1&&H.firstChild!=null&&H.firstChild.nodeType==1&&H.firstChild.firstChild!=null&&H.firstChild.firstChild.nodeType==3){B[H.getAttribute("name")]=H.firstChild.firstChild.nodeValue;
}H=H.nextSibling;
}if(B["start"]==null&&B["date"]!=null){B["start"]=B["date"];
}var K=new Timeline.DefaultEventSource.Event({id:B["id"],start:F(B["start"]),end:F(B["end"]),latestStart:F(B["latestStart"]),earliestEnd:F(B["earliestEnd"]),instant:B["isDuration"]!="true",text:B["title"],description:B["description"],image:this._resolveRelativeURL(B["image"],C),link:this._resolveRelativeURL(B["link"],C),icon:this._resolveRelativeURL(B["icon"],C),color:B["color"],textColor:B["textColor"],hoverText:B["hoverText"],caption:B["caption"],classname:B["classname"],tapeImage:B["tapeImage"],tapeRepeat:B["tapeRepeat"],eventID:B["eventID"]});
K._bindings=B;
K.getProperty=function(M){return this._bindings[M];
};
K.setWikiInfo(I,L);
this._events.add(K);
J=true;
}D=D.nextSibling;
}if(J){this._fire("onAddMany",[]);
}};
Timeline.DefaultEventSource.prototype.add=function(A){this._events.add(A);
this._fire("onAddOne",[A]);
};
Timeline.DefaultEventSource.prototype.addMany=function(B){for(var A=0;
A<B.length;
A++){this._events.add(B[A]);
}this._fire("onAddMany",[]);
};
Timeline.DefaultEventSource.prototype.clear=function(){this._events.removeAll();
this._fire("onClear",[]);
};
Timeline.DefaultEventSource.prototype.getEvent=function(A){return this._events.getEvent(A);
};
Timeline.DefaultEventSource.prototype.getEventIterator=function(A,B){return this._events.getIterator(A,B);
};
Timeline.DefaultEventSource.prototype.getEventReverseIterator=function(A,B){return this._events.getReverseIterator(A,B);
};
Timeline.DefaultEventSource.prototype.getAllEventIterator=function(){return this._events.getAllIterator();
};
Timeline.DefaultEventSource.prototype.getCount=function(){return this._events.getCount();
};
Timeline.DefaultEventSource.prototype.getEarliestDate=function(){return this._events.getEarliestDate();
};
Timeline.DefaultEventSource.prototype.getLatestDate=function(){return this._events.getLatestDate();
};
Timeline.DefaultEventSource.prototype._fire=function(B,A){for(var C=0;
C<this._listeners.length;
C++){var D=this._listeners[C];
if(B in D){try{D[B].apply(D,A);
}catch(E){SimileAjax.Debug.exception(E);
}}}};
Timeline.DefaultEventSource.prototype._getBaseURL=function(A){if(A.indexOf("://")<0){var C=this._getBaseURL(document.location.href);
if(A.substr(0,1)=="/"){A=C.substr(0,C.indexOf("/",C.indexOf("://")+3))+A;
}else{A=C+A;
}}var B=A.lastIndexOf("/");
if(B<0){return"";
}else{return A.substr(0,B+1);
}};
Timeline.DefaultEventSource.prototype._resolveRelativeURL=function(A,B){if(A==null||A==""){return A;
}else{if(A.indexOf("://")>0){return A;
}else{if(A.substr(0,1)=="/"){return B.substr(0,B.indexOf("/",B.indexOf("://")+3))+A;
}else{return B+A;
}}}};
Timeline.DefaultEventSource.Event=function(A){function C(D){return(A[D]!=null&&A[D]!="")?A[D]:null;
}var B=(A.id)?A.id.trim():"";
this._id=B.length>0?B:("e"+Math.floor(Math.random()*1000000));
this._instant=A.instant||(A.end==null);
this._start=A.start;
this._end=(A.end!=null)?A.end:A.start;
this._latestStart=(A.latestStart!=null)?A.latestStart:(A.instant?this._end:this._start);
this._earliestEnd=(A.earliestEnd!=null)?A.earliestEnd:(A.instant?this._start:this._end);
this._eventID=C("eventID");
this._text=(A.text!=null)?SimileAjax.HTML.deEntify(A.text):"";
this._description=SimileAjax.HTML.deEntify(A.description);
this._image=C("image");
this._link=C("link");
this._title=C("hoverText");
this._title=C("caption");
this._icon=C("icon");
this._color=C("color");
this._textColor=C("textColor");
this._classname=C("classname");
this._tapeImage=C("tapeImage");
this._tapeRepeat=C("tapeRepeat");
this._wikiURL=null;
this._wikiSection=null;
};
Timeline.DefaultEventSource.Event.prototype={getID:function(){return this._id;
},isInstant:function(){return this._instant;
},isImprecise:function(){return this._start!=this._latestStart||this._end!=this._earliestEnd;
},getStart:function(){return this._start;
},getEnd:function(){return this._end;
},getLatestStart:function(){return this._latestStart;
},getEarliestEnd:function(){return this._earliestEnd;
},getEventID:function(){return this._eventID;
},getText:function(){return this._text;
},getDescription:function(){return this._description;
},getImage:function(){return this._image;
},getLink:function(){return this._link;
},getIcon:function(){return this._icon;
},getColor:function(){return this._color;
},getTextColor:function(){return this._textColor;
},getClassName:function(){return this._classname;
},getTapeImage:function(){return this._tapeImage;
},getTapeRepeat:function(){return this._tapeRepeat;
},getProperty:function(A){return null;
},getWikiURL:function(){return this._wikiURL;
},getWikiSection:function(){return this._wikiSection;
},setWikiInfo:function(B,A){this._wikiURL=B;
this._wikiSection=A;
},fillDescription:function(A){A.innerHTML=this._description;
},fillWikiInfo:function(D){D.style.display="none";
if(this._wikiURL==null||this._wikiSection==null){return ;
}var C=this.getProperty("wikiID");
if(C==null||C.length==0){C=this.getText();
}if(C==null||C.length==0){return ;
}D.style.display="inline";
C=C.replace(/\s/g,"_");
var B=this._wikiURL+this._wikiSection.replace(/\s/g,"_")+"/"+C;
var A=document.createElement("a");
A.href=B;
A.target="new";
A.innerHTML=Timeline.strings[Timeline.clientLocale].wikiLinkLabel;
D.appendChild(document.createTextNode("["));
D.appendChild(A);
D.appendChild(document.createTextNode("]"));
},fillTime:function(A,B){if(this._instant){if(this.isImprecise()){A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._start)));
A.appendChild(A.ownerDocument.createElement("br"));
A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._end)));
}else{A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._start)));
}}else{if(this.isImprecise()){A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._start)+" ~ "+B.labelPrecise(this._latestStart)));
A.appendChild(A.ownerDocument.createElement("br"));
A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._earliestEnd)+" ~ "+B.labelPrecise(this._end)));
}else{A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._start)));
A.appendChild(A.ownerDocument.createElement("br"));
A.appendChild(A.ownerDocument.createTextNode(B.labelPrecise(this._end)));
}}},fillInfoBubble:function(A,D,K){var L=A.ownerDocument;
var J=this.getText();
var H=this.getLink();
var C=this.getImage();
if(C!=null){var E=L.createElement("img");
E.src=C;
D.event.bubble.imageStyler(E);
A.appendChild(E);
}var M=L.createElement("div");
var B=L.createTextNode(J);
if(H!=null){var I=L.createElement("a");
I.href=H;
I.appendChild(B);
M.appendChild(I);
}else{M.appendChild(B);
}D.event.bubble.titleStyler(M);
A.appendChild(M);
var N=L.createElement("div");
this.fillDescription(N);
D.event.bubble.bodyStyler(N);
A.appendChild(N);
var G=L.createElement("div");
this.fillTime(G,K);
D.event.bubble.timeStyler(G);
A.appendChild(G);
var F=L.createElement("div");
this.fillWikiInfo(F);
D.event.bubble.wikiStyler(F);
A.appendChild(F);
}};


/* themes.js */
Timeline.ClassicTheme=new Object();
Timeline.ClassicTheme.implementations=[];
Timeline.ClassicTheme.create=function(A){if(A==null){A=Timeline.getDefaultLocale();
}var B=Timeline.ClassicTheme.implementations[A];
if(B==null){B=Timeline.ClassicTheme._Impl;
}return new B();
};
Timeline.ClassicTheme._Impl=function(){this.firstDayOfWeek=0;
this.ether={backgroundColors:[],highlightOpacity:50,interval:{line:{show:true,opacity:25},weekend:{opacity:30},marker:{hAlign:"Bottom",vAlign:"Right"}}};
this.event={track:{height:10,gap:2},overviewTrack:{offset:20,tickHeight:6,height:2,gap:1},tape:{height:4},instant:{icon:Timeline.urlPrefix+"data/timeline/dull-blue-circle.png",iconWidth:10,iconHeight:10,impreciseOpacity:20},duration:{impreciseOpacity:20},label:{backgroundOpacity:50,offsetFromLine:3},highlightColors:[],bubble:{width:250,height:125,titleStyler:function(A){A.className="timeline-event-bubble-title";
},bodyStyler:function(A){A.className="timeline-event-bubble-body";
},imageStyler:function(A){A.className="timeline-event-bubble-image";
},wikiStyler:function(A){A.className="timeline-event-bubble-wiki";
},timeStyler:function(A){A.className="timeline-event-bubble-time";
}}};
this.mouseWheel="scroll";
};


/* timeline.js */
Timeline.strings={};
Timeline.getDefaultLocale=function(){return Timeline.clientLocale;
};
Timeline.create=function(C,B,A,D){return new Timeline._Impl(C,B,A,D);
};
Timeline.HORIZONTAL=0;
Timeline.VERTICAL=1;
Timeline._defaultTheme=null;
Timeline.createBandInfo=function(D){var E=("theme" in D)?D.theme:Timeline.getDefaultTheme();
var B=("eventSource" in D)?D.eventSource:null;
var F={interval:SimileAjax.DateTime.gregorianUnitLengths[D.intervalUnit],pixelsPerInterval:D.intervalPixels};
if("startsOn" in D||"endsOn" in D){if("startsOn" in D){F.startsOn=D.startsOn;
}if("endsOn" in D){F.endsOn=D.endsOn;
}}else{if("date" in D){F.centersOn=D.date;
}else{F.centersOn=new Date();
}}var G=new Timeline.LinearEther(F);
var H=new Timeline.GregorianEtherPainter({unit:D.intervalUnit,multiple:("multiple" in D)?D.multiple:1,theme:E,align:("align" in D)?D.align:undefined});
var J={showText:("showEventText" in D)?D.showEventText:true,theme:E};
if("eventPainterParams" in D){for(var A in D.eventPainterParams){J[A]=D.eventPainterParams[A];
}}if("trackHeight" in D){J.trackHeight=D.trackHeight;
}if("trackGap" in D){J.trackGap=D.trackGap;
}var I=("overview" in D&&D.overview)?"overview":("layout" in D?D.layout:"original");
var C;
if("eventPainter" in D){C=new D.eventPainter(J);
}else{switch(I){case"overview":C=new Timeline.OverviewEventPainter(J);
break;
case"detailed":C=new Timeline.DetailedEventPainter(J);
break;
default:C=new Timeline.OriginalEventPainter(J);
}}return{width:D.width,eventSource:B,timeZone:("timeZone" in D)?D.timeZone:0,ether:G,etherPainter:H,eventPainter:C,theme:E,zoomIndex:("zoomIndex" in D)?D.zoomIndex:0,zoomSteps:("zoomSteps" in D)?D.zoomSteps:null};
};
Timeline.createHotZoneBandInfo=function(D){var E=("theme" in D)?D.theme:Timeline.getDefaultTheme();
var B=("eventSource" in D)?D.eventSource:null;
var F=new Timeline.HotZoneEther({centersOn:("date" in D)?D.date:new Date(),interval:SimileAjax.DateTime.gregorianUnitLengths[D.intervalUnit],pixelsPerInterval:D.intervalPixels,zones:D.zones,theme:E});
var G=new Timeline.HotZoneGregorianEtherPainter({unit:D.intervalUnit,zones:D.zones,theme:E,align:("align" in D)?D.align:undefined});
var I={showText:("showEventText" in D)?D.showEventText:true,theme:E};
if("eventPainterParams" in D){for(var A in D.eventPainterParams){I[A]=D.eventPainterParams[A];
}}if("trackHeight" in D){I.trackHeight=D.trackHeight;
}if("trackGap" in D){I.trackGap=D.trackGap;
}var H=("overview" in D&&D.overview)?"overview":("layout" in D?D.layout:"original");
var C;
if("eventPainter" in D){C=new D.eventPainter(I);
}else{switch(H){case"overview":C=new Timeline.OverviewEventPainter(I);
break;
case"detailed":C=new Timeline.DetailedEventPainter(I);
break;
default:C=new Timeline.OriginalEventPainter(I);
}}return{width:D.width,eventSource:B,timeZone:("timeZone" in D)?D.timeZone:0,ether:F,etherPainter:G,eventPainter:C,theme:E,zoomIndex:("zoomIndex" in D)?D.zoomIndex:0,zoomSteps:("zoomSteps" in D)?D.zoomSteps:null};
};
Timeline.getDefaultTheme=function(){if(Timeline._defaultTheme==null){Timeline._defaultTheme=Timeline.ClassicTheme.create(Timeline.getDefaultLocale());
}return Timeline._defaultTheme;
};
Timeline.setDefaultTheme=function(A){Timeline._defaultTheme=A;
};
Timeline.loadXML=function(A,C){var D=function(G,E,F){alert("Failed to load data xml from "+A+"\n"+G);
};
var B=function(F){var E=F.responseXML;
if(!E.documentElement&&F.responseStream){E.load(F.responseStream);
}C(E,A);
};
SimileAjax.XmlHttp.get(A,D,B);
};
Timeline.loadJSON=function(url,f){var fError=function(statusText,status,xmlhttp){alert("Failed to load json data from "+url+"\n"+statusText);
};
var fDone=function(xmlhttp){f(eval("("+xmlhttp.responseText+")"),url);
};
SimileAjax.XmlHttp.get(url,fError,fDone);
};
Timeline._Impl=function(C,B,A,D){SimileAjax.WindowManager.initialize();
this._containerDiv=C;
this._bandInfos=B;
this._orientation=A==null?Timeline.HORIZONTAL:A;
this._unit=(D!=null)?D:SimileAjax.NativeDateUnit;
this._initialize();
};
Timeline._Impl.prototype.dispose=function(){for(var A=0;
A<this._bands.length;
A++){this._bands[A].dispose();
}this._bands=null;
this._bandInfos=null;
this._containerDiv.innerHTML="";
};
Timeline._Impl.prototype.getBandCount=function(){return this._bands.length;
};
Timeline._Impl.prototype.getBand=function(A){return this._bands[A];
};
Timeline._Impl.prototype.layout=function(){this._distributeWidths();
};
Timeline._Impl.prototype.paint=function(){for(var A=0;
A<this._bands.length;
A++){this._bands[A].paint();
}};
Timeline._Impl.prototype.getDocument=function(){return this._containerDiv.ownerDocument;
};
Timeline._Impl.prototype.addDiv=function(A){this._containerDiv.appendChild(A);
};
Timeline._Impl.prototype.removeDiv=function(A){this._containerDiv.removeChild(A);
};
Timeline._Impl.prototype.isHorizontal=function(){return this._orientation==Timeline.HORIZONTAL;
};
Timeline._Impl.prototype.isVertical=function(){return this._orientation==Timeline.VERTICAL;
};
Timeline._Impl.prototype.getPixelLength=function(){return this._orientation==Timeline.HORIZONTAL?this._containerDiv.offsetWidth:this._containerDiv.offsetHeight;
};
Timeline._Impl.prototype.getPixelWidth=function(){return this._orientation==Timeline.VERTICAL?this._containerDiv.offsetWidth:this._containerDiv.offsetHeight;
};
Timeline._Impl.prototype.getUnit=function(){return this._unit;
};
Timeline._Impl.prototype.loadXML=function(B,D){var A=this;
var E=function(H,F,G){alert("Failed to load data xml from "+B+"\n"+H);
A.hideLoadingMessage();
};
var C=function(G){try{var F=G.responseXML;
if(!F.documentElement&&G.responseStream){F.load(G.responseStream);
}D(F,B);
}finally{A.hideLoadingMessage();
}};
this.showLoadingMessage();
window.setTimeout(function(){SimileAjax.XmlHttp.get(B,E,C);
},0);
};
Timeline._Impl.prototype.loadJSON=function(url,f){var tl=this;
var fError=function(statusText,status,xmlhttp){alert("Failed to load json data from "+url+"\n"+statusText);
tl.hideLoadingMessage();
};
var fDone=function(xmlhttp){try{f(eval("("+xmlhttp.responseText+")"),url);
}finally{tl.hideLoadingMessage();
}};
this.showLoadingMessage();
window.setTimeout(function(){SimileAjax.XmlHttp.get(url,fError,fDone);
},0);
};
Timeline._Impl.prototype._initialize=function(){var E=this._containerDiv;
var G=E.ownerDocument;
E.className=E.className.split(" ").concat("timeline-container").join(" ");
var A=(this.isHorizontal())?"horizontal":"vertical";
E.className+=" timeline-"+A;
while(E.firstChild){E.removeChild(E.firstChild);
}var B=SimileAjax.Graphics.createTranslucentImage(Timeline.urlPrefix+(this.isHorizontal()?"data/timeline/copyright-vertical.png":"data/timeline/copyright.png"));
B.className="timeline-copyright";
B.title="Timeline (c) SIMILE - http://simile.mit.edu/timeline/";
SimileAjax.DOM.registerEvent(B,"click",function(){window.location="http://simile.mit.edu/timeline/";
});
E.appendChild(B);
this._bands=[];
for(var C=0;
C<this._bandInfos.length;
C++){var F=this._bandInfos[C];
var D=F.bandClass||Timeline._Band;
var H=new D(this,F,C);
this._bands.push(H);
}this._distributeWidths();
for(var C=0;
C<this._bandInfos.length;
C++){var F=this._bandInfos[C];
if("syncWith" in F){this._bands[C].setSyncWithBand(this._bands[F.syncWith],("highlight" in F)?F.highlight:false);
}}var I=SimileAjax.Graphics.createMessageBubble(G);
I.containerDiv.className="timeline-message-container";
E.appendChild(I.containerDiv);
I.contentDiv.className="timeline-message";
I.contentDiv.innerHTML="<img src='"+Timeline.urlPrefix+"data/timeline/progress-running.gif' /> Loading...";
this.showLoadingMessage=function(){I.containerDiv.style.display="block";
};
this.hideLoadingMessage=function(){I.containerDiv.style.display="none";
};
};
Timeline._Impl.prototype._distributeWidths=function(){var B=this.getPixelLength();
var A=this.getPixelWidth();
var D=0;
for(var E=0;
E<this._bands.length;
E++){var I=this._bands[E];
var J=this._bandInfos[E];
var F=J.width;
var H=F.indexOf("%");
if(H>0){var G=parseInt(F.substr(0,H));
var C=G*A/100;
}else{var C=parseInt(F);
}I.setBandShiftAndWidth(D,C);
I.setViewLength(B);
D+=C;
}};
Timeline._Impl.prototype.zoom=function(G,B,F,D){var C=new RegExp("^timeline-band-([0-9]+)$");
var E=null;
var A=C.exec(D.id);
if(A){E=parseInt(A[1]);
}if(E!=null){this._bands[E].zoom(G,B,F,D);
}this.paint();
};
Timeline._Band=function(B,C,A){if(B!==undefined){this.initialize(B,C,A);
}};
Timeline._Band.prototype.initialize=function(F,G,B){this._timeline=F;
this._bandInfo=G;
this._index=B;
this._locale=("locale" in G)?G.locale:Timeline.getDefaultLocale();
this._timeZone=("timeZone" in G)?G.timeZone:0;
this._labeller=("labeller" in G)?G.labeller:(("createLabeller" in F.getUnit())?F.getUnit().createLabeller(this._locale,this._timeZone):new Timeline.GregorianDateLabeller(this._locale,this._timeZone));
this._theme=G.theme;
this._zoomIndex=("zoomIndex" in G)?G.zoomIndex:0;
this._zoomSteps=("zoomSteps" in G)?G.zoomSteps:null;
this._dragging=false;
this._changing=false;
this._originalScrollSpeed=5;
this._scrollSpeed=this._originalScrollSpeed;
this._onScrollListeners=[];
var A=this;
this._syncWithBand=null;
this._syncWithBandHandler=function(H){A._onHighlightBandScroll();
};
this._selectorListener=function(H){A._onHighlightBandScroll();
};
var D=this._timeline.getDocument().createElement("div");
D.className="timeline-band-input";
this._timeline.addDiv(D);
this._keyboardInput=document.createElement("input");
this._keyboardInput.type="text";
D.appendChild(this._keyboardInput);
SimileAjax.DOM.registerEventWithObject(this._keyboardInput,"keydown",this,"_onKeyDown");
SimileAjax.DOM.registerEventWithObject(this._keyboardInput,"keyup",this,"_onKeyUp");
this._div=this._timeline.getDocument().createElement("div");
this._div.id="timeline-band-"+B;
this._div.className="timeline-band timeline-band-"+B;
this._timeline.addDiv(this._div);
SimileAjax.DOM.registerEventWithObject(this._div,"mousedown",this,"_onMouseDown");
SimileAjax.DOM.registerEventWithObject(this._div,"mousemove",this,"_onMouseMove");
SimileAjax.DOM.registerEventWithObject(this._div,"mouseup",this,"_onMouseUp");
SimileAjax.DOM.registerEventWithObject(this._div,"mouseout",this,"_onMouseOut");
SimileAjax.DOM.registerEventWithObject(this._div,"dblclick",this,"_onDblClick");
var E=this._theme!=null?this._theme.mouseWheel:"scroll";
if(E==="zoom"||E==="scroll"||this._zoomSteps){if(SimileAjax.Platform.browser.isFirefox){SimileAjax.DOM.registerEventWithObject(this._div,"DOMMouseScroll",this,"_onMouseScroll");
}else{SimileAjax.DOM.registerEventWithObject(this._div,"mousewheel",this,"_onMouseScroll");
}}this._innerDiv=this._timeline.getDocument().createElement("div");
this._innerDiv.className="timeline-band-inner";
this._div.appendChild(this._innerDiv);
this._ether=G.ether;
G.ether.initialize(this,F);
this._etherPainter=G.etherPainter;
G.etherPainter.initialize(this,F);
this._eventSource=G.eventSource;
if(this._eventSource){this._eventListener={onAddMany:function(){A._onAddMany();
},onClear:function(){A._onClear();
}};
this._eventSource.addListener(this._eventListener);
}this._eventPainter=G.eventPainter;
G.eventPainter.initialize(this,F);
this._decorators=("decorators" in G)?G.decorators:[];
for(var C=0;
C<this._decorators.length;
C++){this._decorators[C].initialize(this,F);
}};
Timeline._Band.SCROLL_MULTIPLES=5;
Timeline._Band.prototype.dispose=function(){this.closeBubble();
if(this._eventSource){this._eventSource.removeListener(this._eventListener);
this._eventListener=null;
this._eventSource=null;
}this._timeline=null;
this._bandInfo=null;
this._labeller=null;
this._ether=null;
this._etherPainter=null;
this._eventPainter=null;
this._decorators=null;
this._onScrollListeners=null;
this._syncWithBandHandler=null;
this._selectorListener=null;
this._div=null;
this._innerDiv=null;
this._keyboardInput=null;
};
Timeline._Band.prototype.addOnScrollListener=function(A){this._onScrollListeners.push(A);
};
Timeline._Band.prototype.removeOnScrollListener=function(B){for(var A=0;
A<this._onScrollListeners.length;
A++){if(this._onScrollListeners[A]==B){this._onScrollListeners.splice(A,1);
break;
}}};
Timeline._Band.prototype.setSyncWithBand=function(B,A){if(this._syncWithBand){this._syncWithBand.removeOnScrollListener(this._syncWithBandHandler);
}this._syncWithBand=B;
this._syncWithBand.addOnScrollListener(this._syncWithBandHandler);
this._highlight=A;
this._positionHighlight();
};
Timeline._Band.prototype.getLocale=function(){return this._locale;
};
Timeline._Band.prototype.getTimeZone=function(){return this._timeZone;
};
Timeline._Band.prototype.getLabeller=function(){return this._labeller;
};
Timeline._Band.prototype.getIndex=function(){return this._index;
};
Timeline._Band.prototype.getEther=function(){return this._ether;
};
Timeline._Band.prototype.getEtherPainter=function(){return this._etherPainter;
};
Timeline._Band.prototype.getEventSource=function(){return this._eventSource;
};
Timeline._Band.prototype.getEventPainter=function(){return this._eventPainter;
};
Timeline._Band.prototype.layout=function(){this.paint();
};
Timeline._Band.prototype.paint=function(){this._etherPainter.paint();
this._paintDecorators();
this._paintEvents();
};
Timeline._Band.prototype.softLayout=function(){this.softPaint();
};
Timeline._Band.prototype.softPaint=function(){this._etherPainter.softPaint();
this._softPaintDecorators();
this._softPaintEvents();
};
Timeline._Band.prototype.setBandShiftAndWidth=function(A,D){var C=this._keyboardInput.parentNode;
var B=A+Math.floor(D/2);
if(this._timeline.isHorizontal()){this._div.style.top=A+"px";
this._div.style.height=D+"px";
C.style.top=B+"px";
C.style.left="-1em";
}else{this._div.style.left=A+"px";
this._div.style.width=D+"px";
C.style.left=B+"px";
C.style.top="-1em";
}};
Timeline._Band.prototype.getViewWidth=function(){if(this._timeline.isHorizontal()){return this._div.offsetHeight;
}else{return this._div.offsetWidth;
}};
Timeline._Band.prototype.setViewLength=function(A){this._viewLength=A;
this._recenterDiv();
this._onChanging();
};
Timeline._Band.prototype.getViewLength=function(){return this._viewLength;
};
Timeline._Band.prototype.getTotalViewLength=function(){return Timeline._Band.SCROLL_MULTIPLES*this._viewLength;
};
Timeline._Band.prototype.getViewOffset=function(){return this._viewOffset;
};
Timeline._Band.prototype.getMinDate=function(){return this._ether.pixelOffsetToDate(this._viewOffset);
};
Timeline._Band.prototype.getMaxDate=function(){return this._ether.pixelOffsetToDate(this._viewOffset+Timeline._Band.SCROLL_MULTIPLES*this._viewLength);
};
Timeline._Band.prototype.getMinVisibleDate=function(){return this._ether.pixelOffsetToDate(0);
};
Timeline._Band.prototype.getMaxVisibleDate=function(){return this._ether.pixelOffsetToDate(this._viewLength);
};
Timeline._Band.prototype.getCenterVisibleDate=function(){return this._ether.pixelOffsetToDate(this._viewLength/2);
};
Timeline._Band.prototype.setMinVisibleDate=function(A){if(!this._changing){this._moveEther(Math.round(-this._ether.dateToPixelOffset(A)));
}};
Timeline._Band.prototype.setMaxVisibleDate=function(A){if(!this._changing){this._moveEther(Math.round(this._viewLength-this._ether.dateToPixelOffset(A)));
}};
Timeline._Band.prototype.setCenterVisibleDate=function(A){if(!this._changing){this._moveEther(Math.round(this._viewLength/2-this._ether.dateToPixelOffset(A)));
}};
Timeline._Band.prototype.dateToPixelOffset=function(A){return this._ether.dateToPixelOffset(A)-this._viewOffset;
};
Timeline._Band.prototype.pixelOffsetToDate=function(A){return this._ether.pixelOffsetToDate(A+this._viewOffset);
};
Timeline._Band.prototype.createLayerDiv=function(D,B){var C=this._timeline.getDocument().createElement("div");
C.className="timeline-band-layer"+(typeof B=="string"?(" "+B):"");
C.style.zIndex=D;
this._innerDiv.appendChild(C);
var A=this._timeline.getDocument().createElement("div");
A.className="timeline-band-layer-inner";
if(SimileAjax.Platform.browser.isIE){A.style.cursor="move";
}else{A.style.cursor="-moz-grab";
}C.appendChild(A);
return A;
};
Timeline._Band.prototype.removeLayerDiv=function(A){this._innerDiv.removeChild(A.parentNode);
};
Timeline._Band.prototype.scrollToCenter=function(B,C){var A=this._ether.dateToPixelOffset(B);
if(A<-this._viewLength/2){this.setCenterVisibleDate(this.pixelOffsetToDate(A+this._viewLength));
}else{if(A>3*this._viewLength/2){this.setCenterVisibleDate(this.pixelOffsetToDate(A-this._viewLength));
}}this._autoScroll(Math.round(this._viewLength/2-this._ether.dateToPixelOffset(B)),C);
};
Timeline._Band.prototype.showBubbleForEvent=function(C){var A=this.getEventSource().getEvent(C);
if(A){var B=this;
this.scrollToCenter(A.getStart(),function(){B._eventPainter.showBubble(A);
});
}};
Timeline._Band.prototype.zoom=function(F,A,E,C){if(!this._zoomSteps){return ;
}A+=this._viewOffset;
var D=this._ether.pixelOffsetToDate(A);
var B=this._ether.zoom(F);
this._etherPainter.zoom(B);
this._moveEther(Math.round(-this._ether.dateToPixelOffset(D)));
this._moveEther(A);
};
Timeline._Band.prototype._onMouseDown=function(B,A,C){this.closeBubble();
this._dragging=true;
this._dragX=A.clientX;
this._dragY=A.clientY;
};
Timeline._Band.prototype._onMouseMove=function(D,A,E){if(this._dragging){var C=A.clientX-this._dragX;
var B=A.clientY-this._dragY;
this._dragX=A.clientX;
this._dragY=A.clientY;
this._moveEther(this._timeline.isHorizontal()?C:B);
this._positionHighlight();
}};
Timeline._Band.prototype._onMouseUp=function(B,A,C){this._dragging=false;
this._keyboardInput.focus();
};
Timeline._Band.prototype._onMouseOut=function(B,A,D){var C=SimileAjax.DOM.getEventRelativeCoordinates(A,B);
C.x+=this._viewOffset;
if(C.x<0||C.x>B.offsetWidth||C.y<0||C.y>B.offsetHeight){this._dragging=false;
}};
Timeline._Band.prototype._onMouseScroll=function(G,I,E){var A=new Date();
A=A.getTime();
if(!this._lastScrollTime||((A-this._lastScrollTime)>50)){this._lastScrollTime=A;
var H=0;
if(I.wheelDelta){H=I.wheelDelta/120;
}else{if(I.detail){H=-I.detail/3;
}}var F=this._theme.mouseWheel;
if(this._zoomSteps||F==="zoom"){var D=SimileAjax.DOM.getEventRelativeCoordinates(I,G);
if(H!=0){var C;
if(H>0){C=true;
}if(H<0){C=false;
}this._timeline.zoom(C,D.x,D.y,G);
}}else{if(F==="scroll"){var B=50*(H<0?-1:1);
this._moveEther(B);
}}}if(I.stopPropagation){I.stopPropagation();
}I.cancelBubble=true;
if(I.preventDefault){I.preventDefault();
}I.returnValue=false;
};
Timeline._Band.prototype._onDblClick=function(B,A,D){var C=SimileAjax.DOM.getEventRelativeCoordinates(A,B);
var E=C.x-(this._viewLength/2-this._viewOffset);
this._autoScroll(-E);
};
Timeline._Band.prototype._onKeyDown=function(B,A,C){if(!this._dragging){switch(A.keyCode){case 27:break;
case 37:case 38:this._scrollSpeed=Math.min(50,Math.abs(this._scrollSpeed*1.05));
this._moveEther(this._scrollSpeed);
break;
case 39:case 40:this._scrollSpeed=-Math.min(50,Math.abs(this._scrollSpeed*1.05));
this._moveEther(this._scrollSpeed);
break;
default:return true;
}this.closeBubble();
SimileAjax.DOM.cancelEvent(A);
return false;
}return true;
};
Timeline._Band.prototype._onKeyUp=function(B,A,C){if(!this._dragging){this._scrollSpeed=this._originalScrollSpeed;
switch(A.keyCode){case 35:this.setCenterVisibleDate(this._eventSource.getLatestDate());
break;
case 36:this.setCenterVisibleDate(this._eventSource.getEarliestDate());
break;
case 33:this._autoScroll(this._timeline.getPixelLength());
break;
case 34:this._autoScroll(-this._timeline.getPixelLength());
break;
default:return true;
}this.closeBubble();
SimileAjax.DOM.cancelEvent(A);
return false;
}return true;
};
Timeline._Band.prototype._autoScroll=function(D,C){var A=this;
var B=SimileAjax.Graphics.createAnimation(function(E,F){A._moveEther(F);
},0,D,1000,C);
B.run();
};
Timeline._Band.prototype._moveEther=function(A){this.closeBubble();
this._viewOffset+=A;
this._ether.shiftPixels(-A);
if(this._timeline.isHorizontal()){this._div.style.left=this._viewOffset+"px";
}else{this._div.style.top=this._viewOffset+"px";
}if(this._viewOffset>-this._viewLength*0.5||this._viewOffset<-this._viewLength*(Timeline._Band.SCROLL_MULTIPLES-1.5)){this._recenterDiv();
}else{this.softLayout();
}this._onChanging();
};
Timeline._Band.prototype._onChanging=function(){this._changing=true;
this._fireOnScroll();
this._setSyncWithBandDate();
this._changing=false;
};
Timeline._Band.prototype._fireOnScroll=function(){for(var A=0;
A<this._onScrollListeners.length;
A++){this._onScrollListeners[A](this);
}};
Timeline._Band.prototype._setSyncWithBandDate=function(){if(this._syncWithBand){var A=this._ether.pixelOffsetToDate(this.getViewLength()/2);
this._syncWithBand.setCenterVisibleDate(A);
}};
Timeline._Band.prototype._onHighlightBandScroll=function(){if(this._syncWithBand){var A=this._syncWithBand.getCenterVisibleDate();
var B=this._ether.dateToPixelOffset(A);
this._moveEther(Math.round(this._viewLength/2-B));
if(this._highlight){this._etherPainter.setHighlight(this._syncWithBand.getMinVisibleDate(),this._syncWithBand.getMaxVisibleDate());
}}};
Timeline._Band.prototype._onAddMany=function(){this._paintEvents();
};
Timeline._Band.prototype._onClear=function(){this._paintEvents();
};
Timeline._Band.prototype._positionHighlight=function(){if(this._syncWithBand){var A=this._syncWithBand.getMinVisibleDate();
var B=this._syncWithBand.getMaxVisibleDate();
if(this._highlight){this._etherPainter.setHighlight(A,B);
}}};
Timeline._Band.prototype._recenterDiv=function(){this._viewOffset=-this._viewLength*(Timeline._Band.SCROLL_MULTIPLES-1)/2;
if(this._timeline.isHorizontal()){this._div.style.left=this._viewOffset+"px";
this._div.style.width=(Timeline._Band.SCROLL_MULTIPLES*this._viewLength)+"px";
}else{this._div.style.top=this._viewOffset+"px";
this._div.style.height=(Timeline._Band.SCROLL_MULTIPLES*this._viewLength)+"px";
}this.layout();
};
Timeline._Band.prototype._paintEvents=function(){this._eventPainter.paint();
};
Timeline._Band.prototype._softPaintEvents=function(){this._eventPainter.softPaint();
};
Timeline._Band.prototype._paintDecorators=function(){for(var A=0;
A<this._decorators.length;
A++){this._decorators[A].paint();
}};
Timeline._Band.prototype._softPaintDecorators=function(){for(var A=0;
A<this._decorators.length;
A++){this._decorators[A].softPaint();
}};
Timeline._Band.prototype.closeBubble=function(){SimileAjax.WindowManager.cancelPopups();
};


/* units.js */
Timeline.NativeDateUnit=new Object();
Timeline.NativeDateUnit.createLabeller=function(A,B){return new Timeline.GregorianDateLabeller(A,B);
};
Timeline.NativeDateUnit.makeDefaultValue=function(){return new Date();
};
Timeline.NativeDateUnit.cloneValue=function(A){return new Date(A.getTime());
};
Timeline.NativeDateUnit.getParser=function(A){if(typeof A=="string"){A=A.toLowerCase();
}return(A=="iso8601"||A=="iso 8601")?Timeline.DateTime.parseIso8601DateTime:Timeline.DateTime.parseGregorianDateTime;
};
Timeline.NativeDateUnit.parseFromObject=function(A){return Timeline.DateTime.parseGregorianDateTime(A);
};
Timeline.NativeDateUnit.toNumber=function(A){return A.getTime();
};
Timeline.NativeDateUnit.fromNumber=function(A){return new Date(A);
};
Timeline.NativeDateUnit.compare=function(D,C){var B,A;
if(typeof D=="object"){B=D.getTime();
}else{B=Number(D);
}if(typeof C=="object"){A=C.getTime();
}else{A=Number(C);
}return B-A;
};
Timeline.NativeDateUnit.earlier=function(B,A){return Timeline.NativeDateUnit.compare(B,A)<0?B:A;
};
Timeline.NativeDateUnit.later=function(B,A){return Timeline.NativeDateUnit.compare(B,A)>0?B:A;
};
Timeline.NativeDateUnit.change=function(A,B){return new Date(A.getTime()+B);
};
/*==================================================
 *  Timeline
 *==================================================
 */

Timeline.strings = {}; // localization string tables

Timeline.getDefaultLocale = function() {
    return Timeline.clientLocale;
};

Timeline.create = function(elmt, bandInfos, orientation, unit) {
    return new Timeline._Impl(elmt, bandInfos, orientation, unit);
};

Timeline.HORIZONTAL = 0;
Timeline.VERTICAL = 1;

Timeline._defaultTheme = null;

Timeline.createBandInfo = function(params) {
    var theme = ("theme" in params) ? params.theme : Timeline.getDefaultTheme();

    var eventSource = ("eventSource" in params) ? params.eventSource : null;

    var etherParams = {
        interval:           SimileAjax.DateTime.gregorianUnitLengths[params.intervalUnit],
        pixelsPerInterval:  params.intervalPixels
    };
    if ('startsOn' in params || 'endsOn' in params) {
      if ('startsOn' in params) {
	etherParams.startsOn = params.startsOn;
      }
      if ('endsOn' in params) {
	etherParams.endsOn = params.endsOn;
      }
    } else {
      if ('date' in params) {
	etherParams.centersOn = params.date;
      } else {
	etherParams.centersOn = new Date();
      }
    }
    var ether = new Timeline.LinearEther(etherParams);

    var etherPainter = new Timeline.GregorianEtherPainter({
        unit:       params.intervalUnit,
        multiple:   ("multiple" in params) ? params.multiple : 1,
        theme:      theme,
        align:      ("align" in params) ? params.align : undefined
    });

    var eventPainterParams = {
        showText:   ("showEventText" in params) ? params.showEventText : true,
        theme:      theme
    };
    // pass in custom parameters for the event painter
    if ("eventPainterParams" in params) {
        for (var prop in params.eventPainterParams) {
            eventPainterParams[prop] = params.eventPainterParams[prop];
        }
    }

    if ("trackHeight" in params) {
        eventPainterParams.trackHeight = params.trackHeight;
    }
    if ("trackGap" in params) {
        eventPainterParams.trackGap = params.trackGap;
    }

    var layout = ("overview" in params && params.overview) ? "overview" : ("layout" in params ? params.layout : "original");
    var eventPainter;
    if ("eventPainter" in params) {
        eventPainter = new params.eventPainter(eventPainterParams);
    } else {
        switch (layout) {
            case "overview" :
                eventPainter = new Timeline.OverviewEventPainter(eventPainterParams);
                break;
            case "detailed" :
                eventPainter = new Timeline.DetailedEventPainter(eventPainterParams);
                break;
            default:
                eventPainter = new Timeline.OriginalEventPainter(eventPainterParams);
        }
    }

    return {
        width:          params.width,
        eventSource:    eventSource,
        timeZone:       ("timeZone" in params) ? params.timeZone : 0,
        ether:          ether,
        etherPainter:   etherPainter,
        eventPainter:   eventPainter,
        theme:          theme,
        zoomIndex:      ("zoomIndex" in params) ? params.zoomIndex : 0,
        zoomSteps:      ("zoomSteps" in params) ? params.zoomSteps : null
    };
};

Timeline.createHotZoneBandInfo = function(params) {
    var theme = ("theme" in params) ? params.theme : Timeline.getDefaultTheme();

    var eventSource = ("eventSource" in params) ? params.eventSource : null;

    var ether = new Timeline.HotZoneEther({
        centersOn:          ("date" in params) ? params.date : new Date(),
        interval:           SimileAjax.DateTime.gregorianUnitLengths[params.intervalUnit],
        pixelsPerInterval:  params.intervalPixels,
        zones:              params.zones,
        theme:              theme
    });

    var etherPainter = new Timeline.HotZoneGregorianEtherPainter({
        unit:       params.intervalUnit,
        zones:      params.zones,
        theme:      theme,
        align:      ("align" in params) ? params.align : undefined
    });

    var eventPainterParams = {
        showText:   ("showEventText" in params) ? params.showEventText : true,
        theme:      theme
    };
    // pass in custom parameters for the event painter
    if ("eventPainterParams" in params) {
        for (var prop in params.eventPainterParams) {
            eventPainterParams[prop] = params.eventPainterParams[prop];
        }
    }
    if ("trackHeight" in params) {
        eventPainterParams.trackHeight = params.trackHeight;
    }
    if ("trackGap" in params) {
        eventPainterParams.trackGap = params.trackGap;
    }

    var layout = ("overview" in params && params.overview) ? "overview" : ("layout" in params ? params.layout : "original");
    var eventPainter;
    if ("eventPainter" in params) {
        eventPainter = new params.eventPainter(eventPainterParams);
    } else {
        switch (layout) {
            case "overview" :
                eventPainter = new Timeline.OverviewEventPainter(eventPainterParams);
                break;
            case "detailed" :
                eventPainter = new Timeline.DetailedEventPainter(eventPainterParams);
                break;
            default:
                eventPainter = new Timeline.OriginalEventPainter(eventPainterParams);
        }
    }
    return {
        width:          params.width,
        eventSource:    eventSource,
        timeZone:       ("timeZone" in params) ? params.timeZone : 0,
        ether:          ether,
        etherPainter:   etherPainter,
        eventPainter:   eventPainter,
        theme:          theme,
        zoomIndex:      ("zoomIndex" in params) ? params.zoomIndex : 0,
        zoomSteps:      ("zoomSteps" in params) ? params.zoomSteps : null
    };
};

Timeline.getDefaultTheme = function() {
    if (Timeline._defaultTheme == null) {
        Timeline._defaultTheme = Timeline.ClassicTheme.create(Timeline.getDefaultLocale());
    }
    return Timeline._defaultTheme;
};

Timeline.setDefaultTheme = function(theme) {
    Timeline._defaultTheme = theme;
};

Timeline.loadXML = function(url, f) {
    var fError = function(statusText, status, xmlhttp) {
        alert("Failed to load data xml from " + url + "\n" + statusText);
    };
    var fDone = function(xmlhttp) {
        var xml = xmlhttp.responseXML;
        if (!xml.documentElement && xmlhttp.responseStream) {
            xml.load(xmlhttp.responseStream);
        }
        f(xml, url);
    };
    SimileAjax.XmlHttp.get(url, fError, fDone);
};


Timeline.loadJSON = function(url, f) {
    var fError = function(statusText, status, xmlhttp) {
        alert("Failed to load json data from " + url + "\n" + statusText);
    };
    var fDone = function(xmlhttp) {
        f(eval('(' + xmlhttp.responseText + ')'), url);
    };
    SimileAjax.XmlHttp.get(url, fError, fDone);
};


Timeline._Impl = function(elmt, bandInfos, orientation, unit) {
    SimileAjax.WindowManager.initialize();

    this._containerDiv = elmt;

    this._bandInfos = bandInfos;
    this._orientation = orientation == null ? Timeline.HORIZONTAL : orientation;
    this._unit = (unit != null) ? unit : SimileAjax.NativeDateUnit;

    this._initialize();
};

Timeline._Impl.prototype.dispose = function() {
    for (var i = 0; i < this._bands.length; i++) {
        this._bands[i].dispose();
    }
    this._bands = null;
    this._bandInfos = null;
    this._containerDiv.innerHTML = "";
};

Timeline._Impl.prototype.getBandCount = function() {
    return this._bands.length;
};

Timeline._Impl.prototype.getBand = function(index) {
    return this._bands[index];
};

Timeline._Impl.prototype.layout = function() {
    this._distributeWidths();
};

Timeline._Impl.prototype.paint = function() {
    for (var i = 0; i < this._bands.length; i++) {
        this._bands[i].paint();
    }
};

Timeline._Impl.prototype.getDocument = function() {
    return this._containerDiv.ownerDocument;
};

Timeline._Impl.prototype.addDiv = function(div) {
    this._containerDiv.appendChild(div);
};

Timeline._Impl.prototype.removeDiv = function(div) {
    this._containerDiv.removeChild(div);
};

Timeline._Impl.prototype.isHorizontal = function() {
    return this._orientation == Timeline.HORIZONTAL;
};

Timeline._Impl.prototype.isVertical = function() {
    return this._orientation == Timeline.VERTICAL;
};

Timeline._Impl.prototype.getPixelLength = function() {
    return this._orientation == Timeline.HORIZONTAL ?
        this._containerDiv.offsetWidth : this._containerDiv.offsetHeight;
};

Timeline._Impl.prototype.getPixelWidth = function() {
    return this._orientation == Timeline.VERTICAL ?
        this._containerDiv.offsetWidth : this._containerDiv.offsetHeight;
};

Timeline._Impl.prototype.getUnit = function() {
    return this._unit;
};

Timeline._Impl.prototype.loadXML = function(url, f) {
    var tl = this;


    var fError = function(statusText, status, xmlhttp) {
        alert("Failed to load data xml from " + url + "\n" + statusText);
        tl.hideLoadingMessage();
    };
    var fDone = function(xmlhttp) {
        try {
            var xml = xmlhttp.responseXML;
            if (!xml.documentElement && xmlhttp.responseStream) {
                xml.load(xmlhttp.responseStream);
            }
            f(xml, url);
        } finally {
            tl.hideLoadingMessage();
        }
    };

    this.showLoadingMessage();
    window.setTimeout(function() { SimileAjax.XmlHttp.get(url, fError, fDone); }, 0);
};

Timeline._Impl.prototype.loadJSON = function(url, f) {
    var tl = this;


    var fError = function(statusText, status, xmlhttp) {
        alert("Failed to load json data from " + url + "\n" + statusText);
        tl.hideLoadingMessage();
    };
    var fDone = function(xmlhttp) {
        try {
            f(eval('(' + xmlhttp.responseText + ')'), url);
        } finally {
            tl.hideLoadingMessage();
        }
    };

    this.showLoadingMessage();
    window.setTimeout(function() { SimileAjax.XmlHttp.get(url, fError, fDone); }, 0);
};

Timeline._Impl.prototype._initialize = function() {
    var containerDiv = this._containerDiv;
    var doc = containerDiv.ownerDocument;

    containerDiv.className =
        containerDiv.className.split(" ").concat("timeline-container").join(" ");

	/*
	 * Set css-class on container div that will define orientation
	 */
	var orientation = (this.isHorizontal()) ? 'horizontal' : 'vertical'
	containerDiv.className +=' timeline-'+orientation;


    while (containerDiv.firstChild) {
        containerDiv.removeChild(containerDiv.firstChild);
    }

    /*
     *  inserting copyright and link to simile
     */
    var elmtCopyright = SimileAjax.Graphics.createTranslucentImage(Timeline.urlPrefix + (this.isHorizontal() ? "data/timeline/copyright-vertical.png" : "data/timeline/copyright.png"));
    elmtCopyright.className = "timeline-copyright";
    elmtCopyright.title = "Timeline (c) SIMILE - http://simile.mit.edu/timeline/";
    SimileAjax.DOM.registerEvent(elmtCopyright, "click", function() { window.location = "http://simile.mit.edu/timeline/"; });
    containerDiv.appendChild(elmtCopyright);

    /*
     *  creating bands
     */
    this._bands = [];
    for (var i = 0; i < this._bandInfos.length; i++) {
        var bandInfo = this._bandInfos[i];
        var bandClass = bandInfo.bandClass || Timeline._Band;
        var band = new bandClass(this, bandInfo, i);
        this._bands.push(band);
    }
    this._distributeWidths();

    /*
     *  sync'ing bands
     */
    for (var i = 0; i < this._bandInfos.length; i++) {
        var bandInfo = this._bandInfos[i];
        if ("syncWith" in bandInfo) {
            this._bands[i].setSyncWithBand(
                this._bands[bandInfo.syncWith],
                ("highlight" in bandInfo) ? bandInfo.highlight : false
            );
        }
    }

    /*
     *  creating loading UI
     */
    var message = SimileAjax.Graphics.createMessageBubble(doc);
    message.containerDiv.className = "timeline-message-container";
    containerDiv.appendChild(message.containerDiv);

    message.contentDiv.className = "timeline-message";
    message.contentDiv.innerHTML = "<img src='" + Timeline.urlPrefix + "data/timeline/progress-running.gif' /> Loading...";

    this.showLoadingMessage = function() { message.containerDiv.style.display = "block"; };
    this.hideLoadingMessage = function() { message.containerDiv.style.display = "none"; };
};

Timeline._Impl.prototype._distributeWidths = function() {
    var length = this.getPixelLength();
    var width = this.getPixelWidth();
    var cumulativeWidth = 0;

    for (var i = 0; i < this._bands.length; i++) {
        var band = this._bands[i];
        var bandInfos = this._bandInfos[i];
        var widthString = bandInfos.width;

        var x = widthString.indexOf("%");
        if (x > 0) {
            var percent = parseInt(widthString.substr(0, x));
            var bandWidth = percent * width / 100;
        } else {
            var bandWidth = parseInt(widthString);
        }

        band.setBandShiftAndWidth(cumulativeWidth, bandWidth);
        band.setViewLength(length);

        cumulativeWidth += bandWidth;
    }
};

Timeline._Impl.prototype.zoom = function (zoomIn, x, y, target) {
  var matcher = new RegExp("^timeline-band-([0-9]+)$");
  var bandIndex = null;

  var result = matcher.exec(target.id);
  if (result) {
    bandIndex = parseInt(result[1]);
  }

  if (bandIndex != null) {
    this._bands[bandIndex].zoom(zoomIn, x, y, target);
  }

  this.paint();
};

/*==================================================
 *  Band
 *==================================================
 */
Timeline._Band = function(timeline, bandInfo, index) {
    // hack for easier subclassing
    if (timeline !== undefined) {
        this.initialize(timeline, bandInfo, index);
    }
};

Timeline._Band.prototype.initialize = function(timeline, bandInfo, index) {
    this._timeline = timeline;
    this._bandInfo = bandInfo;
    this._index = index;

    this._locale = ("locale" in bandInfo) ? bandInfo.locale : Timeline.getDefaultLocale();
    this._timeZone = ("timeZone" in bandInfo) ? bandInfo.timeZone : 0;
    this._labeller = ("labeller" in bandInfo) ? bandInfo.labeller :
        (("createLabeller" in timeline.getUnit()) ?
            timeline.getUnit().createLabeller(this._locale, this._timeZone) :
            new Timeline.GregorianDateLabeller(this._locale, this._timeZone));
    this._theme = bandInfo.theme;
    this._zoomIndex = ("zoomIndex" in bandInfo) ? bandInfo.zoomIndex : 0;
    this._zoomSteps = ("zoomSteps" in bandInfo) ? bandInfo.zoomSteps : null;

    this._dragging = false;
    this._changing = false;
    this._originalScrollSpeed = 5; // pixels
    this._scrollSpeed = this._originalScrollSpeed;
    this._onScrollListeners = [];

    var b = this;
    this._syncWithBand = null;
    this._syncWithBandHandler = function(band) {
        b._onHighlightBandScroll();
    };
    this._selectorListener = function(band) {
        b._onHighlightBandScroll();
    };

    /*
     *  Install a textbox to capture keyboard events
     */
    var inputDiv = this._timeline.getDocument().createElement("div");
    inputDiv.className = "timeline-band-input";
    this._timeline.addDiv(inputDiv);

    this._keyboardInput = document.createElement("input");
    this._keyboardInput.type = "text";
    inputDiv.appendChild(this._keyboardInput);
    SimileAjax.DOM.registerEventWithObject(this._keyboardInput, "keydown", this, "_onKeyDown");
    SimileAjax.DOM.registerEventWithObject(this._keyboardInput, "keyup", this, "_onKeyUp");

    /*
     *  The band's outer most div that slides with respect to the timeline's div
     */
    this._div = this._timeline.getDocument().createElement("div");
    this._div.id = "timeline-band-" + index;
    this._div.className = "timeline-band timeline-band-" + index;
    this._timeline.addDiv(this._div);

    SimileAjax.DOM.registerEventWithObject(this._div, "mousedown", this, "_onMouseDown");
    SimileAjax.DOM.registerEventWithObject(this._div, "mousemove", this, "_onMouseMove");
    SimileAjax.DOM.registerEventWithObject(this._div, "mouseup", this, "_onMouseUp");
    SimileAjax.DOM.registerEventWithObject(this._div, "mouseout", this, "_onMouseOut");
    SimileAjax.DOM.registerEventWithObject(this._div, "dblclick", this, "_onDblClick");

    var mouseWheel = this._theme!= null ? this._theme.mouseWheel : 'scroll'; // theme is not always defined
    if (mouseWheel === 'zoom' || mouseWheel === 'scroll' || this._zoomSteps) {
    	// capture mouse scroll
      if (SimileAjax.Platform.browser.isFirefox) {
        SimileAjax.DOM.registerEventWithObject(this._div, "DOMMouseScroll", this, "_onMouseScroll");
      } else {
        SimileAjax.DOM.registerEventWithObject(this._div, "mousewheel", this, "_onMouseScroll");
      }
    }

    /*
     *  The inner div that contains layers
     */
    this._innerDiv = this._timeline.getDocument().createElement("div");
    this._innerDiv.className = "timeline-band-inner";
    this._div.appendChild(this._innerDiv);

    /*
     *  Initialize parts of the band
     */
    this._ether = bandInfo.ether;
    bandInfo.ether.initialize(this, timeline);

    this._etherPainter = bandInfo.etherPainter;
    bandInfo.etherPainter.initialize(this, timeline);

    this._eventSource = bandInfo.eventSource;
    if (this._eventSource) {
        this._eventListener = {
            onAddMany: function() { b._onAddMany(); },
            onClear:   function() { b._onClear(); }
        }
        this._eventSource.addListener(this._eventListener);
    }

    this._eventPainter = bandInfo.eventPainter;
    bandInfo.eventPainter.initialize(this, timeline);

    this._decorators = ("decorators" in bandInfo) ? bandInfo.decorators : [];
    for (var i = 0; i < this._decorators.length; i++) {
        this._decorators[i].initialize(this, timeline);
    }
};

Timeline._Band.SCROLL_MULTIPLES = 5;

Timeline._Band.prototype.dispose = function() {
    this.closeBubble();

    if (this._eventSource) {
        this._eventSource.removeListener(this._eventListener);
        this._eventListener = null;
        this._eventSource = null;
    }

    this._timeline = null;
    this._bandInfo = null;

    this._labeller = null;
    this._ether = null;
    this._etherPainter = null;
    this._eventPainter = null;
    this._decorators = null;

    this._onScrollListeners = null;
    this._syncWithBandHandler = null;
    this._selectorListener = null;

    this._div = null;
    this._innerDiv = null;
    this._keyboardInput = null;
};

Timeline._Band.prototype.addOnScrollListener = function(listener) {
    this._onScrollListeners.push(listener);
};

Timeline._Band.prototype.removeOnScrollListener = function(listener) {
    for (var i = 0; i < this._onScrollListeners.length; i++) {
        if (this._onScrollListeners[i] == listener) {
            this._onScrollListeners.splice(i, 1);
            break;
        }
    }
};

Timeline._Band.prototype.setSyncWithBand = function(band, highlight) {
    if (this._syncWithBand) {
        this._syncWithBand.removeOnScrollListener(this._syncWithBandHandler);
    }

    this._syncWithBand = band;
    this._syncWithBand.addOnScrollListener(this._syncWithBandHandler);
    this._highlight = highlight;
    this._positionHighlight();
};

Timeline._Band.prototype.getLocale = function() {
    return this._locale;
};

Timeline._Band.prototype.getTimeZone = function() {
    return this._timeZone;
};

Timeline._Band.prototype.getLabeller = function() {
    return this._labeller;
};

Timeline._Band.prototype.getIndex = function() {
    return this._index;
};

Timeline._Band.prototype.getEther = function() {
    return this._ether;
};

Timeline._Band.prototype.getEtherPainter = function() {
    return this._etherPainter;
};

Timeline._Band.prototype.getEventSource = function() {
    return this._eventSource;
};

Timeline._Band.prototype.getEventPainter = function() {
    return this._eventPainter;
};

Timeline._Band.prototype.layout = function() {
    this.paint();
};

Timeline._Band.prototype.paint = function() {
    this._etherPainter.paint();
    this._paintDecorators();
    this._paintEvents();
};

Timeline._Band.prototype.softLayout = function() {
    this.softPaint();
};

Timeline._Band.prototype.softPaint = function() {
    this._etherPainter.softPaint();
    this._softPaintDecorators();
    this._softPaintEvents();
};

Timeline._Band.prototype.setBandShiftAndWidth = function(shift, width) {
    var inputDiv = this._keyboardInput.parentNode;
    var middle = shift + Math.floor(width / 2);
    if (this._timeline.isHorizontal()) {
        this._div.style.top = shift + "px";
        this._div.style.height = width + "px";

        inputDiv.style.top = middle + "px";
        inputDiv.style.left = "-1em";
    } else {
        this._div.style.left = shift + "px";
        this._div.style.width = width + "px";

        inputDiv.style.left = middle + "px";
        inputDiv.style.top = "-1em";
    }
};

Timeline._Band.prototype.getViewWidth = function() {
    if (this._timeline.isHorizontal()) {
        return this._div.offsetHeight;
    } else {
        return this._div.offsetWidth;
    }
};

Timeline._Band.prototype.setViewLength = function(length) {
    this._viewLength = length;
    this._recenterDiv();
    this._onChanging();
};

Timeline._Band.prototype.getViewLength = function() {
    return this._viewLength;
};

Timeline._Band.prototype.getTotalViewLength = function() {
    return Timeline._Band.SCROLL_MULTIPLES * this._viewLength;
};

Timeline._Band.prototype.getViewOffset = function() {
    return this._viewOffset;
};

Timeline._Band.prototype.getMinDate = function() {
    return this._ether.pixelOffsetToDate(this._viewOffset);
};

Timeline._Band.prototype.getMaxDate = function() {
    return this._ether.pixelOffsetToDate(this._viewOffset + Timeline._Band.SCROLL_MULTIPLES * this._viewLength);
};

Timeline._Band.prototype.getMinVisibleDate = function() {
    return this._ether.pixelOffsetToDate(0);
};

Timeline._Band.prototype.getMaxVisibleDate = function() {
    return this._ether.pixelOffsetToDate(this._viewLength);
};

Timeline._Band.prototype.getCenterVisibleDate = function() {
    return this._ether.pixelOffsetToDate(this._viewLength / 2);
};

Timeline._Band.prototype.setMinVisibleDate = function(date) {
    if (!this._changing) {
        this._moveEther(Math.round(-this._ether.dateToPixelOffset(date)));
    }
};

Timeline._Band.prototype.setMaxVisibleDate = function(date) {
    if (!this._changing) {
        this._moveEther(Math.round(this._viewLength - this._ether.dateToPixelOffset(date)));
    }
};

Timeline._Band.prototype.setCenterVisibleDate = function(date) {
    if (!this._changing) {
        this._moveEther(Math.round(this._viewLength / 2 - this._ether.dateToPixelOffset(date)));
    }
};

Timeline._Band.prototype.dateToPixelOffset = function(date) {
    return this._ether.dateToPixelOffset(date) - this._viewOffset;
};

Timeline._Band.prototype.pixelOffsetToDate = function(pixels) {
    return this._ether.pixelOffsetToDate(pixels + this._viewOffset);
};

Timeline._Band.prototype.createLayerDiv = function(zIndex, className) {
    var div = this._timeline.getDocument().createElement("div");
    div.className = "timeline-band-layer" + (typeof className == "string" ? (" " + className) : "");
    div.style.zIndex = zIndex;
    this._innerDiv.appendChild(div);

    var innerDiv = this._timeline.getDocument().createElement("div");
    innerDiv.className = "timeline-band-layer-inner";
    if (SimileAjax.Platform.browser.isIE) {
        innerDiv.style.cursor = "move";
    } else {
        innerDiv.style.cursor = "-moz-grab";
    }
    div.appendChild(innerDiv);

    return innerDiv;
};

Timeline._Band.prototype.removeLayerDiv = function(div) {
    this._innerDiv.removeChild(div.parentNode);
};

Timeline._Band.prototype.scrollToCenter = function(date, f) {
    var pixelOffset = this._ether.dateToPixelOffset(date);
    if (pixelOffset < -this._viewLength / 2) {
        this.setCenterVisibleDate(this.pixelOffsetToDate(pixelOffset + this._viewLength));
    } else if (pixelOffset > 3 * this._viewLength / 2) {
        this.setCenterVisibleDate(this.pixelOffsetToDate(pixelOffset - this._viewLength));
    }
    this._autoScroll(Math.round(this._viewLength / 2 - this._ether.dateToPixelOffset(date)), f);
};

Timeline._Band.prototype.showBubbleForEvent = function(eventID) {
    var evt = this.getEventSource().getEvent(eventID);
    if (evt) {
        var self = this;
        this.scrollToCenter(evt.getStart(), function() {
            self._eventPainter.showBubble(evt);
        });
    }
};

Timeline._Band.prototype.zoom = function(zoomIn, x, y, target) {
  if (!this._zoomSteps) {
    // zoom disabled
    return;
  }

  // shift the x value by our offset
  x += this._viewOffset;

  var zoomDate = this._ether.pixelOffsetToDate(x);
  var netIntervalChange = this._ether.zoom(zoomIn);
  this._etherPainter.zoom(netIntervalChange);

  // shift our zoom date to the far left
  this._moveEther(Math.round(-this._ether.dateToPixelOffset(zoomDate)));
  // then shift it back to where the mouse was
  this._moveEther(x);
};

Timeline._Band.prototype._onMouseDown = function(innerFrame, evt, target) {
    this.closeBubble();

    this._dragging = true;
    this._dragX = evt.clientX;
    this._dragY = evt.clientY;
};

Timeline._Band.prototype._onMouseMove = function(innerFrame, evt, target) {
    if (this._dragging) {
        var diffX = evt.clientX - this._dragX;
        var diffY = evt.clientY - this._dragY;

        this._dragX = evt.clientX;
        this._dragY = evt.clientY;

        this._moveEther(this._timeline.isHorizontal() ? diffX : diffY);
        this._positionHighlight();
    }
};

Timeline._Band.prototype._onMouseUp = function(innerFrame, evt, target) {
    this._dragging = false;
    this._keyboardInput.focus();
};

Timeline._Band.prototype._onMouseOut = function(innerFrame, evt, target) {
    var coords = SimileAjax.DOM.getEventRelativeCoordinates(evt, innerFrame);
    coords.x += this._viewOffset;
    if (coords.x < 0 || coords.x > innerFrame.offsetWidth ||
        coords.y < 0 || coords.y > innerFrame.offsetHeight) {
        this._dragging = false;
    }
};

Timeline._Band.prototype._onMouseScroll = function(innerFrame, evt, target) {
  var now = new Date();
  now = now.getTime();

  if (!this._lastScrollTime || ((now - this._lastScrollTime) > 50)) {
    // limit 1 scroll per 200ms due to FF3 sending multiple events back to back
    this._lastScrollTime = now;

    var delta = 0;
    if (evt.wheelDelta) {
      delta = evt.wheelDelta/120;
    } else if (evt.detail) {
      delta = -evt.detail/3;
    }

    // either scroll or zoom
    var mouseWheel = this._theme.mouseWheel;

    if (this._zoomSteps || mouseWheel === 'zoom') {
      var loc = SimileAjax.DOM.getEventRelativeCoordinates(evt, innerFrame);
      if (delta != 0) {
        var zoomIn;
        if (delta > 0)
          zoomIn = true;
        if (delta < 0)
          zoomIn = false;
        // call zoom on the timeline so we could zoom multiple bands if desired
        this._timeline.zoom(zoomIn, loc.x, loc.y, innerFrame);
      }
    }
    else if (mouseWheel === 'scroll') {
    	var move_amt = 50 * (delta < 0 ? -1 : 1);
      this._moveEther(move_amt);
    }
  }

  // prevent bubble
  if (evt.stopPropagation) {
    evt.stopPropagation();
  }
  evt.cancelBubble = true;

  // prevent the default action
  if (evt.preventDefault) {
    evt.preventDefault();
  }
  evt.returnValue = false;
};

Timeline._Band.prototype._onDblClick = function(innerFrame, evt, target) {
    var coords = SimileAjax.DOM.getEventRelativeCoordinates(evt, innerFrame);
    var distance = coords.x - (this._viewLength / 2 - this._viewOffset);

    this._autoScroll(-distance);
};

Timeline._Band.prototype._onKeyDown = function(keyboardInput, evt, target) {
    if (!this._dragging) {
        switch (evt.keyCode) {
        case 27: // ESC
            break;
        case 37: // left arrow
        case 38: // up arrow
            this._scrollSpeed = Math.min(50, Math.abs(this._scrollSpeed * 1.05));
            this._moveEther(this._scrollSpeed);
            break;
        case 39: // right arrow
        case 40: // down arrow
            this._scrollSpeed = -Math.min(50, Math.abs(this._scrollSpeed * 1.05));
            this._moveEther(this._scrollSpeed);
            break;
        default:
            return true;
        }
        this.closeBubble();

        SimileAjax.DOM.cancelEvent(evt);
        return false;
    }
    return true;
};

Timeline._Band.prototype._onKeyUp = function(keyboardInput, evt, target) {
    if (!this._dragging) {
        this._scrollSpeed = this._originalScrollSpeed;

        switch (evt.keyCode) {
        case 35: // end
            this.setCenterVisibleDate(this._eventSource.getLatestDate());
            break;
        case 36: // home
            this.setCenterVisibleDate(this._eventSource.getEarliestDate());
            break;
        case 33: // page up
            this._autoScroll(this._timeline.getPixelLength());
            break;
        case 34: // page down
            this._autoScroll(-this._timeline.getPixelLength());
            break;
        default:
            return true;
        }

        this.closeBubble();

        SimileAjax.DOM.cancelEvent(evt);
        return false;
    }
    return true;
};

Timeline._Band.prototype._autoScroll = function(distance, f) {
    var b = this;
    var a = SimileAjax.Graphics.createAnimation(
        function(abs, diff) {
            b._moveEther(diff);
        },
        0,
        distance,
        1000,
        f
    );
    a.run();
};

Timeline._Band.prototype._moveEther = function(shift) {
    this.closeBubble();

    this._viewOffset += shift;
    this._ether.shiftPixels(-shift);
    if (this._timeline.isHorizontal()) {
        this._div.style.left = this._viewOffset + "px";
    } else {
        this._div.style.top = this._viewOffset + "px";
    }

    if (this._viewOffset > -this._viewLength * 0.5 ||
        this._viewOffset < -this._viewLength * (Timeline._Band.SCROLL_MULTIPLES - 1.5)) {

        this._recenterDiv();
    } else {
        this.softLayout();
    }

    this._onChanging();
}

Timeline._Band.prototype._onChanging = function() {
    this._changing = true;

    this._fireOnScroll();
    this._setSyncWithBandDate();

    this._changing = false;
};

Timeline._Band.prototype._fireOnScroll = function() {
    for (var i = 0; i < this._onScrollListeners.length; i++) {
        this._onScrollListeners[i](this);
    }
};

Timeline._Band.prototype._setSyncWithBandDate = function() {
    if (this._syncWithBand) {
        var centerDate = this._ether.pixelOffsetToDate(this.getViewLength() / 2);
        this._syncWithBand.setCenterVisibleDate(centerDate);
    }
};

Timeline._Band.prototype._onHighlightBandScroll = function() {
    if (this._syncWithBand) {
        var centerDate = this._syncWithBand.getCenterVisibleDate();
        var centerPixelOffset = this._ether.dateToPixelOffset(centerDate);

        this._moveEther(Math.round(this._viewLength / 2 - centerPixelOffset));

        if (this._highlight) {
            this._etherPainter.setHighlight(
                this._syncWithBand.getMinVisibleDate(),
                this._syncWithBand.getMaxVisibleDate());
        }
    }
};

Timeline._Band.prototype._onAddMany = function() {
    this._paintEvents();
};

Timeline._Band.prototype._onClear = function() {
    this._paintEvents();
};

Timeline._Band.prototype._positionHighlight = function() {
    if (this._syncWithBand) {
        var startDate = this._syncWithBand.getMinVisibleDate();
        var endDate = this._syncWithBand.getMaxVisibleDate();

        if (this._highlight) {
            this._etherPainter.setHighlight(startDate, endDate);
        }
    }
};

Timeline._Band.prototype._recenterDiv = function() {
    this._viewOffset = -this._viewLength * (Timeline._Band.SCROLL_MULTIPLES - 1) / 2;
    if (this._timeline.isHorizontal()) {
        this._div.style.left = this._viewOffset + "px";
        this._div.style.width = (Timeline._Band.SCROLL_MULTIPLES * this._viewLength) + "px";
    } else {
        this._div.style.top = this._viewOffset + "px";
        this._div.style.height = (Timeline._Band.SCROLL_MULTIPLES * this._viewLength) + "px";
    }
    this.layout();
};

Timeline._Band.prototype._paintEvents = function() {
    this._eventPainter.paint();
};

Timeline._Band.prototype._softPaintEvents = function() {
    this._eventPainter.softPaint();
};

Timeline._Band.prototype._paintDecorators = function() {
    for (var i = 0; i < this._decorators.length; i++) {
        this._decorators[i].paint();
    }
};

Timeline._Band.prototype._softPaintDecorators = function() {
    for (var i = 0; i < this._decorators.length; i++) {
        this._decorators[i].softPaint();
    }
};

Timeline._Band.prototype.closeBubble = function() {
    SimileAjax.WindowManager.cancelPopups();
};
