from odoo import _, api, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if self.env.context.get("skip_zipnova_refund"):
            return lines
        refund_product = self.env.ref(
            "zipnova.zipnova_delivery_refund", raise_if_not_found=False
        )
        if not refund_product:
            return lines
        extra_vals = []
        for line in lines:
            carrier = line.order_id.carrier_id
            if not line.is_delivery or not carrier.is_free:
                continue
            extra_vals.append(
                {
                    "order_id": line.order_id.id,
                    "product_id": refund_product.id,
                    "name": refund_product.display_name,
                    "price_unit": -(line.price_unit or 0.0),
                    "product_uom_qty": 1,
                    "product_uom": refund_product.uom_id.id,
                }
            )
        if extra_vals:
            super(
                SaleOrderLine, self.with_context(skip_zipnova_refund=True)
            ).create(extra_vals)
        return lines

    def unlink(self):
        orders = self.filtered("is_delivery").mapped("order_id")
        for order in orders:
            if order.zipnova_shipping_id:
                raise UserError(
                    _(
                        "Cancel the Zipnova shipment before removing the "
                        "delivery line."
                    )
                )
        result = super().unlink()
        for order in orders.exists():
            if not order.order_line.filtered("is_delivery"):
                order._zipnova_clear_pickup_info()
                order._zipnova_clear_shipping()
        return result
