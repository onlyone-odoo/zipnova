from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _reconcile_after_done(self):
        """Create Zipnova shipments once the eCommerce payment is confirmed."""
        res = super()._reconcile_after_done()
        paid_txs = self.filtered(
            lambda tx: tx.state == "done" and tx.operation != "validation"
        )
        paid_txs.sale_order_ids._zipnova_create_shipping_after_payment()
        return res
