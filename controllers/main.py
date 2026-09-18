import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

from odoo.addons.zipnova.models.zipnova_api import (
    ID_ANDREANI,
    ID_CORREO_ARGENTINO,
    ID_OCA,
)

_logger = logging.getLogger(__name__)


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
        type="json",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_zipnova_pickup_points(self, carrier_id, **kw):
        order = request.website.sale_get_order()
        if not order:
            return {"points": []}
        carrier = request.env["delivery.carrier"].sudo().browse(int(carrier_id))
        if not carrier.exists() or not carrier.zipnova_shipment_type_is_pickup:
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
        type="json",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_zipnova_set_pickup(self, carrier_id, point_id, name, address, **kw):
        order = request.website.sale_get_order()
        if not order:
            return {"success": False}
        # Public user must persist the selected pickup on the cart.
        order.sudo().write(
            {
                "zipnova_pickup_carrier_id": str(carrier_id or ""),
                "zipnova_pickup_point_id": str(point_id or ""),
                "zipnova_pickup_name": name or "",
                "zipnova_pickup_address": address or "",
                "zipnova_pickup_is_pickup": True,
            }
        )
        pickup = (
            request.env["zipnova.shipping"]
            .sudo()
            .search(
                [
                    ("order_id", "=", order.id),
                    ("point_id", "=", str(point_id or "")),
                ],
                limit=1,
            )
        )
        if pickup and pickup.logistic_type:
            order.sudo().zipnova_logistic_type = pickup.logistic_type
        return {"success": True}

    @http.route(
        "/shop/payment/validate",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_payment_validate(self, sale_order_id=None, **post):
        result = super().shop_payment_validate(sale_order_id, **post)
        if getattr(result, "status_code", None) not in (302, 303):
            return result
        location = getattr(result, "location", "") or ""
        if "/shop/confirmation" not in location:
            return result
        if sale_order_id is None:
            order = request.website.sale_get_order()
            if not order and request.session.get("sale_last_order_id"):
                order = (
                    request.env["sale.order"]
                    .sudo()
                    .browse(request.session["sale_last_order_id"])
                    .exists()
                )
        else:
            order = request.env["sale.order"].sudo().browse(sale_order_id).exists()
        if not order or order.carrier_id.delivery_type != "zipnova":
            return result
        if order.zipnova_pickup_is_pickup and not order.zipnova_pickup_point_id:
            _logger.warning(
                "Zipnova website shipment skipped: missing pickup point on SO %s",
                order.id,
            )
            return result
        try:
            if not order.zipnova_shipping_id:
                order.action_zipnova_create_shipping()
        except Exception:
            _logger.exception(
                "Zipnova website shipment failed for sale.order %s", order.id
            )
        return result
