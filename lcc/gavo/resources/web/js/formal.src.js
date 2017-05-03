if(typeof(Forms) == 'undefined') {
    Forms = {};
}

if(typeof(Forms.Util) == 'undefined') {
    Forms.Util = {};
}

Forms.Util.previewShow = function(divId, frameId, u) {
    var div = document.getElementById(divId);
    var frame = document.getElementById(frameId);
    div.className = 'preview-show';
    frame.src = u;
    return false;
}

Forms.Util.previewHide = function(divId) {
    var div = document.getElementById(divId);
    div.className = 'preview-hidden';
    return false;
}

