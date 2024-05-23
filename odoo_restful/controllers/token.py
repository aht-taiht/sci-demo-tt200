# Part of odoo. See LICENSE file for full copyright and licensing details.
import json
import logging

import werkzeug.wrappers

from odoo import http
from ..common import invalid_response, valid_response
from ..common import json_response
from odoo.http import request
from odoo.exceptions import AccessError, AccessDenied

_logger = logging.getLogger(__name__)

expires_in = "odoo_restful.access_token_expires_in"


class AccessToken(http.Controller):
    """."""

    def __init__(self):

        self._token = request.env["api.access_token"]
        self._expires_in = request.env.ref(expires_in).sudo().value

    @http.route("/api/auth/token", methods=["POST"],
                type="json", auth="none", csrf=False)
    def token(self, **post):
        params = json.loads(request.httprequest.get_data().
                            decode(request.httprequest.charset))
        _token = request.env["api.access_token"]

        db, username, password = (
            params.get("db"),
            params.get("login"),
            params.get("password"),
        )
        _credentials_includes_in_body = all([db, username, password])
        if not _credentials_includes_in_body:
            # The request post body is empty the
            # credetials maybe passed via the headers.
            headers = request.httprequest.headers
            db = headers.get("db")
            username = headers.get("login")
            password = headers.get("password")
            _credentials_includes_in_headers = all([db, username, password])
            if not _credentials_includes_in_headers:
                # Empty 'db' or 'username' or 'password:
                return json_response(
                    message='Following are missing [db, username,password]',
                    status=403)
        # Login in odoo database:
        try:
            request.session.authenticate(db, username, password)
        except AccessError as aee:
            return json_response(message="Access error: %s" % aee.name,
                                 status=403)
        except AccessDenied:
            return json_response(
                message="Access denied: Login, password or db invalid",
                status=403)
        except Exception as e:
            # Invalid database:
            info = "The database name is not valid {}".format((e))
            _logger.error(info)
            return json_response(message=info, status=403)

        uid = request.session.uid
        # odoo login failed:
        if not uid:
            info = "authentication failed"
            _logger.error(info)
            return json_response(message=info, status=401)

        # Generate tokens
        access_token = _token.find_one_or_create_token(user_id=uid,
                                                       create=True)
        # Successful response:
        return json_response({
            "uid": uid,
            "user_context": request.session.get_context() if uid else {},
            "company_id": request.env.user.company_id.id if uid else None,
            "company_ids": request.env.user.company_ids.ids if uid else None,
            "partner_id": request.env.user.partner_id.id,
            "access_token": access_token,
            "expires_in": self._expires_in,
        })

    @http.route("/api/auth/token", methods=["DELETE"], type="http",
                auth="none", csrf=False)
    def delete(self, **post):
        """."""
        _token = request.env["api.access_token"]
        access_token = request.httprequest.headers.get("access_token")
        access_token = _token.search([("token", "=", access_token)])
        if not access_token:
            info = "No access token was provided in request!"
            error = "Access token is missing in the request header"
            _logger.error(info)
            return invalid_response(400, error, info)
        for token in access_token:
            token.unlink()
        # Successful response:
        return valid_response([{"desc": "access token successfully deleted",
                                "delete": True}])
