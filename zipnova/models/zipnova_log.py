from datetime import timedelta

from odoo import api, fields, models

DEFAULT_RETENTION_DAYS = 30


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
    dt_llamada = fields.Datetime(string="Called at", index=True)
    llamada = fields.Char(string="Endpoint")
    request = fields.Text()
    response = fields.Text()

    @api.autovacuum
    def _gc_zipnova_logs(self):
        """Delete API logs older than `zipnova.log_retention_days` (default 30)."""
        param = self.env["ir.config_parameter"].sudo().get_param(
            "zipnova.log_retention_days", DEFAULT_RETENTION_DAYS
        )
        try:
            days = int(param)
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        if days <= 0:
            return
        limit_date = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([("dt_llamada", "<", limit_date)]).unlink()
