from odoo import fields, models


class ZipnovaShipping(models.Model):
    _name = "zipnova.shipping"
    _description = "Zipnova Pickup Point"
    _order = "name"

    order_id = fields.Many2one(
        "sale.order",
        string="Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id",
        store=True,
        index=True,
    )
    carrier_id = fields.Char(string="Zipnova Carrier ID", index=True)
    point_id = fields.Char(string="Pickup Point ID")
    name = fields.Char(string="Name")
    address = fields.Char(string="Address")
    logistic_type = fields.Char()
