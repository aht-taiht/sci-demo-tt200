odoo.define('web.session', function (require) {
"use strict";

var Session = require('web.Session');

var session = new Session(undefined, undefined, {

    setMultiCompanies: function (company_ids) {
        var hash = $.bbq.getState();
        hash.cids = company_ids.sort(function(a, b) {
                return a - b;
            }).join(',');
        utils.set_cookie('cids', hash.cids);
        $.bbq.pushState({'cids': hash.cids}, 0);
        location.reload();
    },
});

return session;

});
