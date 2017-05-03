// javascript support code for the GAVO data center


////////////////////////////// possibly generic functions

function decodeGetPars(queryString) {
// an incredibly crappy approach to getting whatever was in the query string
// into javascript.
	var pars = new Object();
	var pairs = queryString.slice(1).split("&");
	for (var ind in pairs) {
		var pair = pairs[ind].split("=");
		var key = 'arg'+unescape(pair[0]).replace("+", " ");
		var value = unescape(pair[1]).replace("+", " ");
		if (pars[key]==undefined) {
			pars[key] = new Array();
		}
		pars[key].push(value);
	}
	return pars;
}


function isIn(item, arr) {
// does a linear search through arr to see if item is in there
// (can't we use assoc. arrs for that?)
	for (var ind in arr) {
		if (arr[ind]==item) {
			return true;
		}
	}
	return false;
}


function getJD(date) {
	return date/86400000+2440587.5;
}


function getJYear(date) {
	return (getJD(date)-2451545)/365.25+2000;
}


///////////// Micro templating.  See develNotes
function htmlEscape(str) {
	return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
		.replace(/'/g, '&apos;').replace(/</g, '&lt;')
		.replace(/>/g, '&gt;');
}

(function () {
	var _tmplCache = {};
	this.renderTemplate = function (templateId, data) {
		var err = "";
		var func = _tmplCache[templateId];
		if (!func) {
			str = document.getElementById(templateId).innerHTML;
			var strFunc =
				"var p=[],print=function(){p.push.apply(p,arguments);};"
				+ "with(obj){p.push('"
				+ str.replace(/[\r\t\n]/g, " ")
				.split("'").join("\\'")
				.split("\t").join("'")
				.replace(/\$([a-zA-Z_]+)/g, "',htmlEscape($1),'")
				.replace(/\$!([a-zA-Z_]+)/g, "',$1,'")
				+ "');}return $.trim(p.join(''));";
				func = new Function("obj", strFunc);
				_tmplCache[str] = func;
		}
		return func(data);
	}
})()




///////////// Code for generating GET-URLs for forms

function getEnclosingForm(element) {
// returns the form element immediately enclosing element.
	if (element.nodeName=="FORM") {
		return element;
	}
	return getEnclosingForm(element.parentNode);
}

function getSelectedEntries(selectElement) {
// returns an array of all selected entries from a select element 
// in url encoded form
	var result = new Array();
	var i;

	for (i=0; i<selectElement.length; i++) {
		if (selectElement.options[i].selected) {
			result.push(selectElement.name+"="+encodeURIComponent(
				selectElement.options[i].value))
		}
	}
	return result;
}

function makeQueryItem(element) {
// returns an url-encoded query tag item out of a form element
	var val=null;

	switch (element.nodeName) {
		case "INPUT":
		case "TEXTAREA":
			if (element.type=="radio" || element.type=="checkbox") {
				if (element.checked) {
					val = element.name+"="+encodeURIComponent(element.value);
				}
			} else if (element.name && element.value) {
				val = element.name+"="+encodeURIComponent(element.value);
			}
			break;
		case "SELECT":
			return getSelectedEntries(element).join("&");
			break;
		case "BUTTON":  // no state here
			break;
		default:
			alert("No handler for "+element.nodeName);
	}
	if (val) {
		return val;
	} else {
		return element.NodeName;
	}
}

function getFormQuery(form, ignoreNames) {
	// returns a link to the result sending the HTML form form would
	// yield.
	var fragments = new Array();
	var i;

	items = form.elements;
	for (i=0; i<items.length; i++) {
		var fragment = makeQueryItem(items[i]);
		if (fragment && ignoreNames[items[i].name]==undefined) {
			fragments.push(fragment);
		} 
	}
	return form.getAttribute("action")+"?"+fragments.join("&");
}


function makeResultLink(form) {
	return getFormQuery(form, []);
}


function makeBookmarkLink(form) {
	return getFormQuery(form, {'__nevow_form__': 1});
}


///////////// Functions for the sidebar

var expandedMetaWidth = '200px';

function markFold(title, markstr) {
	return title.slice(0, title.length-2)+markstr;
}

function toggleCollapsedMeta(el) {
	var contentBox = el.parentNode.nextSibling;
	if (contentBox.style.visibility=='visible') {
		el.childNodes[0].data = markFold(el.childNodes[0].data, ">>");
		collapseMeta(contentBox);
	} else {
		el.childNodes[0].data = markFold(el.childNodes[0].data, "<<");
		expandMeta(contentBox);
	}
}

function collapseMeta(box) {
	box.style.visibility = 'hidden';
	box.style.height = '0px';
	box.style.maxHeight = '0px';
	var parent = box.parentNode;
	parent.style.border = '0px none #707ca0';
	parent.style.padding = '1px';
	parent.style.background = 'none';
}

function expandMeta(box) {
	box.style.visibility = 'visible';
	box.style.height = 'auto';
	box.style.maxHeight = '200px';
	box.style.width = expandedMetaWidth;
	var parent = box.parentNode;
	parent.style.border = '1px solid #707ca0';
	parent.style.padding = '3px';
	parent.style.background = '#ffffff';
	parent.style.width = expandedMetaWidth;
}

function followEmbeddedLink(parent) {
// forwards the browser to the href of the first child that has one.
// this is for the button-type decoration around links.
	for (index in parent.childNodes) {
		child = parent.childNodes[index];
		if (child.href) {
			window.location = child.href;
			break;
		}
	}
}

///////////// Functions dealing with the output format widget
// This incredibly verbose crap hides and shows widgets selecting aspects
// of the output format.  Basically, you have widgets in output_bussedElements
// that get notified when the output format changes and then (un)attach 
// themselves to a container.
//
// To use this, you need:
//  * a block element with id "genForm-_OUTPUT" in which the subwidgets are 
//    displayed
//  * a form element calling output_broadcast(this.value) on a change
//
//  In the DC, the static QueryMeta method getOutputWidget worries about this.


function output_BussedElement(domNode, id, visibleFor) {
	// An element that can be passed to output_broadcast and does something
	// in response.
	domNode.id = id;
	for (var ind in visibleFor) {
		domNode["visibleFor_"+visibleFor[ind]] = true;
	}
	return domNode;
}


function output_verbSelector(pars) {
	// returns a BussedElement for the selector for output verbosity
	var verbosities = new Array("H", "1", "2", "3");
	var root = document.createElement("span")
	var sel = document.createElement("select");
	var curSetting;

	root["class"] = "op_widget";
	root.appendChild(document.createTextNode(" output verbosity "));
	sel.name = "_VERB";
	if (pars['arg'+sel.name]!=undefined) {
		curSetting = pars['arg'+sel.name][0];
	} else {
		curSetting = "H";
	}
	for (verbInd in verbosities) {
		var el = sel.appendChild(document.createElement("option"));
		var verb = verbosities[verbInd];
		el.appendChild(document.createTextNode(verb));
		if (verb==curSetting) {
			el.selected = "selected";
		}
	}
	root.appendChild(sel);
	return output_BussedElement(root, "op_verb", ["VOTable", "FITS",
		"TSV", "JSON"]);
}


function output_tdEncSelector(pars) {
	// returns a BussedElement to select VOTable encoding
	var root = document.createElement("span");
	var box = document.createElement("input");
	var curSetting;

	root["class"] = "op_widget";
	box.name = "_TDENC";
	if (pars['arg'+box.name]!=undefined) {
		curSetting = pars['arg'+box.name][0];
	} else {
		curSetting = "false";
	}
	box.type = "checkbox";
	box.style.width = "auto";
	root.appendChild(box);
	root.appendChild(document.createTextNode(" human-readable "));
	if (curSetting=="true") {
		box.checked = "checked";
	}
	return output_BussedElement(root, "op_tdenc", ["VOTable"]);
}


function output_setFormat(format) {
	var opts=document.getElementById("genForm-_FORMAT").options;
	for (var optInd=0; optInd<opts.length; optInd++) {
		if (opts[optInd].value==format) {
			opts[optInd].selected = true;
		} else {
			opts[optInd].selected = false;
		}
	}
}

var output_bussedElements = new Array();


function output_init() {
	var pars = decodeGetPars(location.search);
	var format = pars["arg_FORMAT"];

	if (!document.getElementById("genForm-_OUTPUT")) { // no form on page
		return;
	}
	output_bussedElements.push(output_verbSelector(pars));
	output_bussedElements.push(output_tdEncSelector(pars));
	output_bussedElements.push(output_itemSelector(pars));
	if (format==undefined) {
		format = "HTML";
	}
	output_broadcast(format);
	outputInited = true;
}

function output_broadcast(newFormat) {
	var visibleForThis = "visibleFor_"+newFormat;

	output_setFormat(newFormat);
	for (var ind in output_bussedElements) {
		var el=output_bussedElements[ind];
		if (el[visibleForThis]) {
			output_show(el);
		} else {
			output_hide(el);
		}
	}
}


$(document).ready(
	function() {
		output_init();
	});



///////////////// jquery-dependent code (TODO: move the rest of the
/// stuff from plain js to jquery, too)


function makeTabCallback(handlers) {
// see develNotes
	return function (ev) {
		$("#tabset_tabs > li").removeClass("selected");
		var curTab = $(ev.currentTarget);
		curTab.addClass("selected");
		var mainId = curTab.find("a").attr("name");
		handlers[mainId]($('#mainbox'));
	}
}


function popupInnerWindow(content, parent, onClose) {
// puts content into a thing that looks like a window and can be
// dragged and resized.  Parent is the element the container
// gets added to within the tree.
// The function returns a closer function destroying the subwindow.
	var prevParent = content.parent()
	prevParent.css({"position": "relative"});
	content.detach();
	content.css("visibility", "visible");

	var container = $("<div class='innerWin'/>");
	var titlebar = $(
		"<p class='innerTitle'><span class='closer'>x&nbsp;</span></p>");
	container.append(titlebar);
	container.append(content);
	content.addClass("innerBody");
	content.show();

	container.draggable({cancel: ".innerBody"});
	parent.append(container);
	// XXX TODO: Why doesn't container expand to content size in the first place?
	container.css({"width": content.width(),
		"height": content.height()+titlebar.height(),
		"position": "relative"});

	closer = function(ignored) {
		container.hide();
		container.detach();
		content.detach();
		content.hide();
		prevParent.append(content);
		onClose();
	}

	container.find(".closer").bind("click", closer);
	return closer;
}


function output_popupAddSel() {
// pops up the dialog with the additional output items.  The popup
// receives a cleanup function.
	var govButton = output_bussedElements[2];
	var closer = popupInnerWindow(
		$("#genForm-_ADDITEMS"), $("#genForm-_OUTPUT"),
		function() {
			govButton.unbind("click");
			govButton.bind("click", output_popupAddSel);
			govButton.contents()[0].data = "More output fields";
		})
	govButton.unbind("click");
	govButton.bind("click", closer);
	govButton.contents()[0].data = "Pop down field selector";
	return false;
}


function output_itemSelector(pars) {
	// returns a Bussedelement to pop up the element Selector
	var root = $('<button type="button" id="op_additem" class="popButton">More output fields</button>');

	root.bind("click", output_popupAddSel);
	// show nowhere unless there actually are items to show
	var showFor = new Array();
	if (document.getElementById("genForm-_ADDITEMS")) {
		showFor.push('HTML');
	}
	res = output_BussedElement(root, "op_additem", showFor);
	return res;
}


function output_show(el) {
	if (!document.getElementById(el.id)) {
		var dest = $("#genForm-_OUTPUT");
		dest.append(document.createTextNode(" "));
		dest.append(el);
	}
}

function output_hide(el) {
	if (document.getElementById(el.id)) {
		$(el).detach();
	}
}



/////////////////////////////////////////////////////////////////////
// Plotting code -- move (most of this) to something loaded on demand

DATETIME_RE = /^(\d\d\d\d)-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d.?\d*)$/
DATE_RE = /^(\d\d\d\d)-(\d\d)-(\d\d)$/
function _getValue(s) {
// tries to make some kind of number from a string s
// if s looks like a datetime, return a julian year
// TODO: do something with hours/sexagesimal angles
// if s looks like a float number, return a float
// else return null.
	var dm = DATETIME_RE.exec(s);
	if (dm!=null) {
		var dt = new Date(parseFloat(dm[1]), parseFloat(dm[2]), parseFloat(dm[3]),
			parseFloat(dm[4]), parseFloat(dm[5]), parseFloat(dm[6]));
		return getJYear(dt);
	}
	var dm = DATE_RE.exec(s);
	if (dm!=null) {
		var dt = new Date(parseFloat(dm[1]), parseFloat(dm[2]), parseFloat(dm[3]));
		return getJYear(dt);
	}

	var num = parseFloat(s);
	if (num==num) { // not NaN
		return num;
	}
	return null;
}
	


function _doLinePlot(table, xInd, yInd, style) {
	var data = new Array();
	var options = {"series": {}};

	table.find('tr.data').each(function(index, row) {
		var tds = $(row).children();
		var x = _getValue(tds[xInd].firstChild.data); 
		var y = _getValue(tds[yInd].firstChild.data);
		if (x!=null && y!=null) {
			data.push([x, y]);
		}
	});
	if (style=="Lines") {
		options.series["lines"] = {'show': true};
		data.sort(function(a,b){return a[0]-b[0]});
	} else {
		options.series["points"] = {'show': true};
	}
	jQuery.plot(jQuery('#plotarea'), [data], options);
}


function _makeHistogram(data, numBins) {
	if (data.length<2) {
		return new Array();
	}
	data.sort(function(a,b){return a-b});
	var zp = data[0];
	var binSize = (data[data.length-1]-zp)/numBins;
	if (binSize==0) {
		binSize = 1;
	}

	var histo = new Array();
	for (var i=0; i<numBins; i++) {
		histo.push(0);
	}
	for (index in data) {
		histo[Math.floor((data[index]-zp)/binSize)]++;
	}
	
	data = new Array();
	for (index in histo) {
		data.push([index*binSize+zp, histo[index]]);
	}
	return data;
}

function _doHistogramPlot(table, colInd) {
	var data = new Array();
	table.find('tr.data').each(function(index, row) {
		var val = _getValue($(row).children()[colInd].firstChild.data);
		if (val!=null) {
			data.push(val);
		}
	});

	var histo = _makeHistogram(data, 20);
	jQuery.plot(jQuery('#plotarea'), [{
		bars: {
			show: true,
			barWidth: histo[1][0]-histo[0][0]},
		data: histo}]);
}	


function _doFlotPlot(table, xsel, ysel, usingSel) {
	xInd = xsel.find("option:selected").val()
	yInd = ysel.find("option:selected").val()
	style = usingSel.find("option:selected").val()
	if (yInd=='Histogram') {
		_doHistogramPlot(table, xInd);
	} else {
		_doLinePlot(table, xInd, yInd, style);
	}
}


function _plotUsingFlot(table, options) {
// allows simple plotting of HTML tables.  This only works from
// within openFlotPlot since it uses javascript that's not loaded
// by default.
	// create the plot element
	var plotElement = $('<div id="plotcontainer" style="position:fixed;z-index:3000;background:white;padding-left:3px;padding-right:3px;padding-bottom:3px;border:2px solid gray"><p class="innerTitle"><span class="closer">x&nbsp;</span></p><div id="plotarea" style="width:700px;height:400px;"/></div>');
	plotElement.draggable();
	plotElement.find(".closer").bind("click", function(){
		plotElement.remove()});
	var controlPara = $('<p class="flotControl"></p>');
	plotElement.append(controlPara);

	// Make column selectors from table headings
	var xsel = $('<select/>');
	$(table.find('tr')[0]).find('th').each(function(index, head) {
		xsel.append($('<option value="'+index+'">'+$(head).text()+'</option>'));
	});
	controlPara.append(xsel);
	controlPara.append(' vs. ');
	var ysel = xsel.clone();
	ysel.append($(
		'<option value="Histogram">Histogram</option>'));
	controlPara.append(ysel);
	controlPara.append(' using ');
	var usingSel = $('<select><option selected="selected">Points</option><option>Lines</option></select>')
	controlPara.append(usingSel);

	// Set default plot features from options if given there
	var xselIndex = 0;
	if (options.xselIndex) {
		xselIndex = options.xselIndex;
	}
	var yselIndex = ysel.children().length-1;
	if (options.yselIndex) {
		yselIndex = options.yselIndex;
	}
	var usingIndex = 0;
	if (options.usingIndex) {
		usingIndex = options.usingIndex;
	}
	xsel.children()[xselIndex].setAttribute("selected", "selected")
	ysel.children()[yselIndex].setAttribute("selected", "selected")
	usingSel.children()[usingIndex].setAttribute("selected", "selected")

	// the callback any form items controlling the plot
	var updatePlot = function() {
		try {
			_doFlotPlot(table, xsel, ysel, usingSel);
		} catch (e) {
			jQuery.plot(jQuery('#plotarea'), [{data:[], label: "unplottable"}]);
			throw e;
		}
	}
	xsel.change(updatePlot);
	ysel.change(updatePlot);
	usingSel.change(updatePlot);

	$("body").prepend(plotElement);
	updatePlot();
}

function openFlotPlot(tableElement, options) {
// opens a div that lets you plot some columns of tableElement
	if (options==undefined) {
		options = {};
	}
	$.getScript("/static/js/jquery.flot.js",
		function() {_plotUsingFlot(tableElement, options)});
}


function openVOPlot() {
	votURL = getFormQuery(
		document.getElementById("genForm"), 
			{'_FORMAT': 1, "_TDENC": 1})+
		"&_FORMAT=VOTable&_TDENC=on&_VERB=H";
	window.open(
		'/__system__/run/voplot/fixed?source='+encodeURIComponent(votURL),
		"_self");
}


function insertPreview(node, width) {
// replaces the text content of node with a DC-generated preview
// image.  node has to have a href attribute pointing to a DC
// FITS product for this to work (width is ignored these days).
	if (!node.getAttribute("href")) {
		return;
	}
	var oldHref = node.getAttribute("href");
	var newPars = "preview=True&width="+width;
	var joiner = "?";
	// TODO: do actual URL parsing here
	if (oldHref.indexOf("?")!=-1) { // assume we have a query
		joiner = "&";
	}

	node.removeAttribute("onmouseover");
	$(node).addClass("busy");

	var previewURL = oldHref+joiner+newPars;
	var img = $("<img/>").attr("src", previewURL
		).attr("alt", "[preview image]");

	img.bind("load", function() {
		node.replaceChild(img[0], node.firstChild);
		$(node).removeClass("busy");
	});
	// TODO: use "complete" here when we've updated jquery
	img.bind("error", function() {
		$(node).removeClass("busy");
	});
}

