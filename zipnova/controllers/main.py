from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale

from odoo.addons.zipnova.models.zipnova_api import (
    ID_ANDREANI,
    ID_CORREO_ARGENTINO,
    ID_OCA,
)


class ZipnovaWebsiteSale(WebsiteSale):

    def _get_shop_payment_values(self, order, **kwargs):
        values = super()._get_shop_payment_values(order, **kwargs)
        pickups = request.env["zipnova.shipping"].sudo().search(
            [("order_id", "=", order.id)]
        )
        values["zipnova_car_suc"] = pickups.filtered(
            lambda rec: rec.carrier_id == str(ID_CORREO_ARGENTINO)
        )
        values["zipnova_oca_suc"] = pickups.filtered(
            lambda rec: rec.carrier_id == str(ID_OCA)
        )
        values["zipnova_and_suc"] = pickups.filtered(
            lambda rec: rec.carrier_id == str(ID_ANDREANI)
        )
        return values

    @http.route(
        "/shop/zipnova/pickup_points",
        type="jsonrpc",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_zipnova_pickup_points(self, carrier_id, **kw):
        order = request.website.sale_get_order()
        if not order:
            return {"points": []}
        carrier = request.env["delivery.carrier"].sudo().browse(int(carrier_id))
        if (
            not carrier.exists()
            or carrier.delivery_type != "zipnova"
            or not carrier.zipnova_shipment_type_is_pickup
        ):
            return {"points": []}
        # Public website user cannot write sale.order; rating uses sudo.
        vals = carrier.rate_shipment(order.sudo())
        if not vals.get("success"):
            return {
                "points": [],
                "error": vals.get("error_message") or "",
            }
        return {
            "points": [
                {
                    "name": rec.get("name"),
                    "carrier_id": rec.get("carrier_id"),
                    "point_id": rec.get("point_id"),
                    "address": rec.get("address"),
                }
                for rec in vals.get("zipnova_pickup") or []
            ]
        }

    @http.route(
        "/shop/zipnova/pickup",
        type="jsonrpc",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_zipnova_set_pickup(self, carrier_id, point_id, delivery_carrier_id=None, **kw):
        order = request.website.sale_get_order()
        if not order:
            return {"success": False}
        order = order.sudo()
        point = self._zipnova_find_quoted_point(order, carrier_id, point_id)
        if not point and delivery_carrier_id:
            # The carrier click re-rates the cart in parallel and may have
            # replaced the stored points; quote again before rejecting.
            carrier = request.env["delivery.carrier"].sudo().browse(
                int(delivery_carrier_id)
            )
            if carrier.exists() and carrier.delivery_type == "zipnova":
                carrier.rate_shipment(order)
                point = self._zipnova_find_quoted_point(order, carrier_id, point_id)
        if not point:
            return {"success": False}
        order._zipnova_set_pickup_point(point)
        return {"success": True}

    def _zipnova_find_quoted_point(self, order, carrier_id, point_id):
        """Only points returned by the Zipnova quote of this cart are accepted."""
        return (
            request.env["zipnova.shipping"]
            .sudo()
            .search(
                [
                    ("order_id", "=", order.id),
                    ("carrier_id", "=", str(carrier_id or "")),
                    ("point_id", "=", str(point_id or "")),
                ],
                limit=1,
            )
        )
