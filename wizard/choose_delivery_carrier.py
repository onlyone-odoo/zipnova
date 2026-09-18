from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = "choose.delivery.carrier"

    zipnova_pickup_view_invisible = fields.Boolean(default=True)
    zipnova_pickup_view_id = fields.Char()
    zipnova_logistic_type = fields.Char()
    zipnova_pickup = fields.Many2one("zipnova.shipping", string="Pickup Points")
    zipnova_estimated_delivery = fields.Datetime(string="Estimated delivery")
    zipnova_min_days = fields.Integer(string="Min. delivery days")
    zipnova_max_days = fields.Integer(string="Max. delivery days")

    @api.onchange("carrier_id", "total_weight")
    def _onchange_carrier_id(self):
        result = super()._onchange_carrier_id()
        self.zipnova_pickup = False
        self.zipnova_pickup_view_invisible = not bool(
            self.carrier_id.zipnova_shipment_type_is_pickup
        )
        self.zipnova_pickup_view_id = str(self.carrier_id.zipnova_shipment_type or "")
        return result

    def _parse_estimated_delivery(self, value):
        if not value:
            return False
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return False

    def _get_shipment_rate(self):
        if self.carrier_id.delivery_type != "zipnova":
            return super()._get_shipment_rate()
        vals = self.carrier_id.with_context(
            order_weight=self.total_weight
        ).rate_shipment(self.order_id)
        if not vals.get("success"):
            return {"error_message": vals.get("error_message")}
        self.delivery_message = vals.get("warning_message", False)
        self.delivery_price = vals["price"]
        self.display_price = vals.get("carrier_price", vals["price"])
        self.zipnova_logistic_type = vals.get("logistic_type")
        self.zipnova_estimated_delivery = self._parse_estimated_delivery(
            vals.get("zipnova_estimated_delivery")
        )
        try:
            self.zipnova_min_days = int(vals.get("min") or 0)
        except (TypeError, ValueError):
            self.zipnova_min_days = 0
        try:
            self.zipnova_max_days = int(vals.get("max") or 0)
        except (TypeError, ValueError):
            self.zipnova_max_days = 0
        return {"no_rate": vals.get("no_rate", False)}

    def set_only_the_date(self):
        self.ensure_one()
        if self.delivery_type == "zipnova" and not self.zipnova_estimated_delivery:
            raise UserError(_("Get the Zipnova rate first."))
        if self.zipnova_estimated_delivery:
            self.order_id.write(
                {
                    "zipnova_min_date": self.order_id.add_days_to_current_date(
                        self.zipnova_min_days
                    ),
                    "zipnova_max_date": self.order_id.add_days_to_current_date(
                        self.zipnova_max_days
                    ),
                    "commitment_date": self.zipnova_estimated_delivery,
                    "zipnova_latest_shipping_query": fields.Date.context_today(self),
                }
            )
        return {"type": "ir.actions.act_window_close"}

    def button_confirm(self):
        self.ensure_one()
        pickup = self.zipnova_pickup
        if self.delivery_type == "zipnova":
            if (
                not self.zipnova_logistic_type
                and not self.display_price
                and not self.carrier_id.free_over
                and not self.carrier_id.is_free
            ):
                raise UserError(_("Get the Zipnova rate first."))
            if self.carrier_id.zipnova_shipment_type_is_pickup and not pickup:
                raise UserError(_("Select a Zipnova pickup point."))
        result = super().button_confirm()
        if self.delivery_type != "zipnova":
            return result
        values = {
            "zipnova_pickup_carrier_id": str(self.carrier_id.zipnova_shipment_type or ""),
            "zipnova_pickup_is_pickup": bool(
                self.carrier_id.zipnova_shipment_type_is_pickup
            ),
            "zipnova_logistic_type": self.zipnova_logistic_type,
            "zipnova_min_date": self.order_id.add_days_to_current_date(
                self.zipnova_min_days
            ),
            "zipnova_max_date": self.order_id.add_days_to_current_date(
                self.zipnova_max_days
            ),
            "commitment_date": self.zipnova_estimated_delivery,
            "zipnova_latest_shipping_query": fields.Date.context_today(self),
        }
        if pickup:
            values.update(
                {
                    "zipnova_pickup_carrier_id": pickup.carrier_id,
                    "zipnova_pickup_point_id": pickup.point_id,
                    "zipnova_pickup_name": pickup.name,
                    "zipnova_pickup_address": pickup.address,
                    "zipnova_logistic_type": pickup.logistic_type
                    or self.zipnova_logistic_type,
                }
            )
        else:
            values.update(
                {
                    "zipnova_pickup_point_id": False,
                    "zipnova_pickup_name": False,
                    "zipnova_pickup_address": False,
                }
            )
        self.order_id.write(values)
        return result
