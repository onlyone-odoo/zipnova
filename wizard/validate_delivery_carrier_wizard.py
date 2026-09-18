from odoo import _, fields, models
from odoo.exceptions import UserError


class ValidateDeliveryCarrierWizard(models.TransientModel):
    _name = "validate.delivery.carrier.wizard"
    _description = "Confirm Zipnova Shipment"

    order_id = fields.Many2one("sale.order", string="Order", required=True, ondelete="cascade")
    carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Carrier",
        related="order_id.carrier_id",
    )
    total_weight = fields.Float(string="Total weight (g)")
    total_length = fields.Float(string="Total length (cm)")
    total_height = fields.Float(string="Total height (cm)")
    total_width = fields.Float(string="Total width (cm)")
    delivery_price = fields.Float(string="Cost", readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id")
    company_id = fields.Many2one(related="order_id.company_id")

    def update_order_lines_delivery_price(self):
        self.order_id.get_lines_delivery().write({"price_unit": self.delivery_price})

    def update_price(self):
        self.ensure_one()
        vals = self.carrier_id.zipnova_rate_shipment(
            self.order_id,
            total_weight=self.total_weight,
            total_length=self.total_length,
            total_height=self.total_height,
            total_width=self.total_width,
        )
        if vals.get("error_message"):
            raise UserError(vals["error_message"])
        if vals.get("success"):
            self.delivery_price = vals["price"]
        return {
            "name": _("Confirm Shipment"),
            "type": "ir.actions.act_window",
            "res_model": "validate.delivery.carrier.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        self.order_id.action_zipnova_create_shipping(
            total_weight=self.total_weight,
            total_length=self.total_length,
            total_height=self.total_height,
            total_width=self.total_width,
        )
        self.update_order_lines_delivery_price()
        return {"type": "ir.actions.act_window_close"}
