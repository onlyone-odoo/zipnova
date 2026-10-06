from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    zipnova_shipping_tracking_external = fields.Char(
        string="Zipnova Tracking URL",
        copy=False,
    )
