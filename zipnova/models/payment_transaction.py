from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _post_process(self):
        """Create Zipnova shipments once the eCommerce payment is confirmed.

        Odoo 18 and 19 confirm the sales order inside `_post_process`.
        """
        res = super()._post_process()
        paid_txs = self.filtered(
            lambda tx: tx.state == "done" and tx.operation != "validation"
        )
        paid_txs.sale_order_ids._zipnova_create_shipping_after_payment()
        return res
