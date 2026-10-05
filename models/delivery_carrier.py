from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from .zipnova_api import ID_PICKUP_DELIVERY, ID_STANDARD_DELIVERY


class DeliveryCarrier(models.Model):
    _name = "delivery.carrier"
    _inherit = ["delivery.carrier", "zipnova.api.mixin"]

    delivery_type = fields.Selection(
        selection_add=[("zipnova", "Zipnova")],
        ondelete={"zipnova": "set default"},
    )
    is_free = fields.Boolean(string="Free shipping product")
    zipnova_shipment_type = fields.Integer(
        string="Zipnova Carrier ID",
        help="Carrier ID in Zipnova. Correo Argentino=233, OCA=208, Andreani=1.",
    )
    zipnova_shipment_type_is_pickup = fields.Boolean(string="Pickup point delivery")
    fixed_margin_time = fields.Integer(
        string="Extra delivery days",
        help="Extra days added to the Zipnova estimated delivery date.",
    )

    def add_margin_to_estimated_delivery(self, estimated_delivery_str, fixed_margin_time):
        """Add a day margin to an ISO-8601 estimated delivery datetime."""
        if not estimated_delivery_str:
            return estimated_delivery_str
        try:
            estimated_delivery = datetime.fromisoformat(
                estimated_delivery_str.replace("Z", "+00:00")
            )
        except ValueError:
            return estimated_delivery_str
        estimated_delivery += relativedelta(days=fixed_margin_time or 0)
        return estimated_delivery.isoformat()

    def _zipnova_rate_error(self, message):
        return {
            "success": False,
            "price": 0,
            "error_message": message,
            "warning_message": False,
            "zipnova_pickup": [],
        }

    def zipnova_rate_shipment(
        self,
        order,
        total_weight=None,
        total_length=None,
        total_height=None,
        total_width=None,
    ):
        self.ensure_one()
        public_partner = self.env.ref("base.public_partner", raise_if_not_found=False)
        if public_partner and order.partner_id == public_partner:
            return self._zipnova_rate_error(False)
        try:
            payload = self._zipnova_prepare_quote_payload(
                order,
                total_weight=total_weight,
                total_length=total_length,
                total_height=total_height,
                total_width=total_width,
            )
            status, data, _raw = self._zipnova_request(
                order.company_id,
                "POST",
                "/shipments/quote",
                payload=payload,
                order=order,
                log_name="quote",
            )
        except UserError as err:
            return self._zipnova_rate_error(str(err))

        if status != 200 or not data:
            return self._zipnova_rate_error(self._zipnova_error_message(status, data))

        result = self._get_rate_vals_from_response(order, data)
        if result.get("success"):
            order._zipnova_replace_pickup_points(
                result.get("zipnova_pickup") or [],
                carrier_code=str(self.zipnova_shipment_type or ""),
            )
        return result

    def _zipnova_finalize_price(self, order, price):
        """Apply fiscal position, margins and free-over like `rate_shipment`."""
        self.ensure_one()
        company = self.company_id or order.company_id or self.env.company
        price = self.product_id._get_tax_included_unit_price(
            company,
            company.currency_id,
            order.date_order,
            "sale",
            fiscal_position=order.fiscal_position_id,
            product_price_unit=price,
            product_currency=company.currency_id,
        )
        price = self.with_context(order=order)._apply_margins(price)
        if self.free_over:
            amount = self._compute_currency(
                order,
                order._compute_amount_total_without_delivery(),
                "pricelist_to_company",
            )
            if amount >= self.amount:
                price = 0.0
        return price

    def _zipnova_prepare_quote_payload(
        self,
        order,
        total_weight=None,
        total_length=None,
        total_height=None,
        total_width=None,
    ):
        """Build the /shipments/quote payload. Raises UserError on missing data."""
        company = order.company_id
        self._zipnova_check_credentials(company)
        items = order._zipnova_prepare_items()
        if not items:
            raise UserError(_("The order has no storable products to ship."))
        order._zipnova_apply_total_overrides(
            items,
            total_weight=total_weight,
            total_length=total_length,
            total_height=total_height,
            total_width=total_width,
        )
        payload = {
            "account_id": self._zipnova_account_id(company),
            "source": self._zipnova_source(company),
            "declared_value": order._zipnova_declared_value(),
            "items": items,
            "destination": order._zipnova_quote_destination(),
        }
        origin_id = self._zipnova_origin_id(company)
        if origin_id:
            payload["origin_id"] = origin_id
        return payload

    def _zipnova_price_from_amounts(self, amounts, company):
        """Return the Zipnova price consistent with the delivery product taxes.

        Odoo adds the delivery product taxes on top of the rated price unless
        they are price-included, so the net price is used in that case to
        avoid charging VAT twice.
        """
        # Public website users cannot read account.tax; only flags are read.
        taxes = self.product_id.sudo().taxes_id._filter_taxes_by_company(company)
        if taxes and not all(taxes.mapped("price_include")):
            return amounts.get("price") or amounts.get("price_incl_tax")
        return amounts.get("price_incl_tax") or amounts.get("price")

    def _get_rate_vals_from_response(self, order, response):
        """Pick the cheapest selectable option for this carrier configuration."""
        self.ensure_one()
        wanted_service = (
            ID_PICKUP_DELIVERY
            if self.zipnova_shipment_type_is_pickup
            else ID_STANDARD_DELIVERY
        )
        wanted_carrier = int(self.zipnova_shipment_type or 0)
        shipment_price = None
        logistic_type = ""
        shipment_type = wanted_carrier
        estimated_delivery = ""
        min_estimated_delivery = ""
        max_estimated_delivery = ""
        pickup_res = []

        for option in response.get("all_results") or []:
            if option.get("selectable") is False:
                continue
            service = option.get("service_type") or {}
            carrier = option.get("carrier") or {}
            carrier_id = carrier.get("id")
            service_id = service.get("id")
            if service_id == wanted_service and carrier_id == wanted_carrier:
                price = self._zipnova_price_from_amounts(
                    option.get("amounts") or {}, order.company_id
                )
                if price and (shipment_price is None or price < shipment_price):
                    shipment_price = price
                    logistic_type = option.get("logistic_type") or ""
                    shipment_type = carrier_id
                    delivery_time = option.get("delivery_time") or {}
                    estimated_delivery = delivery_time.get("estimated_delivery") or ""
                    min_estimated_delivery = delivery_time.get("min") or ""
                    max_estimated_delivery = delivery_time.get("max") or ""
                    pickup_res = []
                    for point in option.get("pickup_points") or []:
                        location = point.get("location") or {}
                        street = location.get("street") or ""
                        street_number = location.get("street_number") or ""
                        city = location.get("city") or ""
                        state = location.get("state") or ""
                        pickup_res.append(
                            {
                                "order_id": order.id,
                                "carrier_id": str(carrier_id),
                                "point_id": str(point.get("point_id") or ""),
                                "name": "%s (%s %s)"
                                % (
                                    point.get("description") or "",
                                    street,
                                    street_number,
                                ),
                                "address": "%s %s %s %s"
                                % (street, street_number, city, state),
                                "logistic_type": option.get("logistic_type") or "",
                            }
                        )

        if shipment_price is None:
            return {
                "success": False,
                "price": 0,
                "error_message": _(
                    "No Zipnova rate is available for this carrier and destination."
                ),
                "warning_message": False,
                "zipnova_pickup": [],
            }

        estimated_delivery = self.add_margin_to_estimated_delivery(
            estimated_delivery, self.fixed_margin_time
        )
        if max_estimated_delivery not in (None, ""):
            try:
                max_estimated_delivery = str(
                    int(max_estimated_delivery) + (self.fixed_margin_time or 0)
                )
            except (TypeError, ValueError):
                pass
        return {
            "success": True,
            "price": shipment_price,
            "zipnova_pickup": pickup_res,
            "logistic_type": logistic_type,
            "error_message": False,
            "warning_message": False,
            "shipment_type": shipment_type,
            "zipnova_estimated_delivery": estimated_delivery,
            "min": min_estimated_delivery,
            "max": max_estimated_delivery,
        }

    def zipnova_send_shipping(self, pickings):
        """Do not create the Zipnova shipment from the picking.

        Shipments are created from the sales order (or website payment).
        """
        res = []
        for picking in pickings:
            tracking = False
            if picking.sale_id:
                tracking = picking.sale_id.zipnova_shipping_id
            res.append({"exact_price": 0.0, "tracking_number": tracking})
        return res

    def zipnova_get_tracking_link(self, picking):
        order = picking.sale_id
        return order.zipnova_shipping_tracking or order.zipnova_shipping_tracking_external

    def zipnova_cancel_shipment(self, pickings):
        for picking in pickings:
            if picking.sale_id and picking.sale_id.zipnova_shipping_id:
                picking.sale_id.action_zipnova_delete_shipping()
