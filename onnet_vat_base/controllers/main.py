# -*- coding: utf-8 -*-
import json

from werkzeug.exceptions import InternalServerError

from odoo.http import Controller, request, route, content_disposition
from odoo.tools import html_escape
from odoo.tools.safe_eval import safe_eval
from odoo import http

# TODO: move this code to other module - e.g: report_base


class ReportController(Controller):
    @route(['/report/download/xlsx/<report_name>/<model_name>/<int:record_id>'], type='http', auth="user")
    def report_download(self, report_name, model_name, record_id):
        report = request.env[model_name].browse(record_id)
        try:
            generated_file_data = report.get_xlsx()
            file_type = generated_file_data['file_type']
            file_name = generated_file_data['file_name']
            file_content = generated_file_data['file_content']
            response_headers = self._get_response_headers(file_type, file_name, file_content)
            response = request.make_response(None, headers=response_headers)
            response.stream.write(file_content)

            return response
        except Exception as e:
            data = http.serialize_exception(e)
            raise InternalServerError(response=self._generate_response(data)) from e

    def _generate_response(self, data):
        error = {
            'code': 200,
            'message': 'Odoo Server Error',
            'data': data,
        }
        return request.make_response(html_escape(json.dumps(error)))

    def _get_response_headers(self, file_type, file_name, file_content):
        headers = [
            ('Content-Type', self.get_export_mime_type(file_type)),
            ('Content-Disposition', content_disposition(file_name)),
        ]
        if file_type in ('xml', 'xaf', 'txt', 'csv', 'kvr', 'csv'):
            headers.append(('Content-Length', len(file_content)))

        return headers

    def get_export_mime_type(self, file_type):
        type_mapping = {
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf',
            'xml': 'application/xml',
            'xaf': 'application/vnd.sun.xml.writer',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'zip': 'application/zip',
        }
        return type_mapping.get(file_type, False)
