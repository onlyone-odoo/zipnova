from odoo import fields, models


class ZipnovaLog(models.Model):
    _name = "zipnova.log"
    _description = "Zipnova API Log"
    _order = "id desc"

    order_id = fields.Many2one(
        "sale.order",
        string="Order",
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id",
        store=True,
        index=True,
    )
    dt_llamada = fields.Datetime(string="Called at")
    llamada = fields.Char(string="Endpoint")
    request = fields.Text()
    response = fields.Text()
