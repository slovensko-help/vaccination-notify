function rot13(a) {
    return a.replace(/[a-zA-Z]/g, function(c){
      return String.fromCharCode((c <= "Z" ? 90 : 122) >= (c = c.charCodeAt(0) + 13) ? c : c - 26);
    })
}

function mail_inner() {
    var elems = document.getElementsByClassName("mail-inner");
    for (var i = 0; i < elems.length; i++) {
        elems[i].innerHTML = rot13(elems[i].dataset.rot13);
    }
}

function mail_href() {
    var elems = document.getElementsByClassName("mail-href");
    for (var i = 0; i < elems.length; i++) {
        elems[i].href = rot13("znvygb:" + elems[i].dataset.rot13);
    }
}

function mail() {
    mail_href();
    mail_inner();
}

window.addEventListener("load", mail);
