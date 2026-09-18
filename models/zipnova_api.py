import base64
import json
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ZIPNOVA_API_URL = "https://api.zipnova.com.ar/v2"
ID_CORREO_ARGENTINO = 233
ID_OCA = 208
ID_ANDREANI = 1
ID_STANDARD_DELIVERY = 1
ID_PICKUP_DELIVERY = 9
EXTERNAL_ID_MAX = 30
SOURCE_MAX = 150
DEFAULT_SOURCE = "odoo"
WEIGHT_MIN_GRAMS = 10
DIM_MIN_CM = 1


class ZipnovaApiMixin(models.AbstractModel):
    _name = "zipnova.api.mixin"
    _description = "Zipnova API helpers"

    def _zipnova_check_credentials(self, company):
        """Ensure the company has Zipnova API credentials."""
        if not company.zipnova_id or not company.zipnova_key or not company.zipnova_secret:
            raise UserError(
                _("Set the Zipnova Account ID, API Token and API Secret on the company.")
            )

    def _zipnova_headers(self, company):
        token = "%s:%s" % (company.zipnova_key, company.zipnova_secret)
        encoded = base64.b64encode(token.encode("utf-8")).decode("utf-8")
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Basic %s" % encoded,
        }

    def _zipnova_request(
        self,
        company,
        method,
        endpoint,
        payload=None,
        order=None,
        log_name=None,
        expect_json=True,
    ):
        """Perform an authenticated Zipnova HTTP request and optionally log it.

        Returns:
            tuple: (status_code, parsed_json_or_None, raw_content)
        """
        url = ZIPNOVA_API_URL + endpoint
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self._zipnova_headers(company),
                json=payload if payload is not None else None,
                timeout=45,
            )
        except requests.RequestException:
            _logger.exception("Zipnova request failed: %s %s", method, url)
            raise UserError(_("Zipnova connection error. Please try again."))

        if order:
            request_dump = payload if payload is not None else {"url": url}
            self.env["zipnova.log"].sudo().create(
                {
                    "order_id": order.id,
                    "dt_llamada": fields.Datetime.now(),
                    "llamada": log_name or endpoint,
                    "request": json.dumps(request_dump, default=str, ensure_ascii=False),
                    "response": (response.text or "")[:100000],
                }
            )

        data = None
        if expect_json and response.content:
            try:
                data = response.json()
            except ValueError:
                data = None
        return response.status_code, data, response.content

    def _zipnova_source(self, company):
        return (company.zipnova_source or DEFAULT_SOURCE)[:SOURCE_MAX]

    def _zipnova_external_id(self, order):
        name = (order.name or "SO%s" % order.id).replace("/", "-")
        return name[:EXTERNAL_ID_MAX]

    def _zipnova_int_weight(self, grams):
        try:
            value = int(round(float(grams or 0)))
        except (TypeError, ValueError):
            value = WEIGHT_MIN_GRAMS
        return max(value, WEIGHT_MIN_GRAMS)

    def _zipnova_int_dim(self, centimeters):
        try:
            value = int(round(float(centimeters or 0)))
        except (TypeError, ValueError):
            value = DIM_MIN_CM
        return max(value, DIM_MIN_CM)

    def _zipnova_error_message(self, status_code, data):
        if status_code == 408:
            return _(
                "Zipnova is taking too long to respond. Please try again."
            )
        if status_code in (500, 503):
            return _("Zipnova is temporarily unavailable. Please try again later.")
        if status_code == 403:
            return _("Zipnova authorization error. Check the company credentials.")
        if isinstance(data, dict):
            message = data.get("message") or data.get("error") or data.get("errors")
            if message:
                return _("Zipnova error: %s") % message
        return _("Unexpected Zipnova error (HTTP %s).") % status_code
