from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zipnova_id = fields.Char(
        related="company_id.zipnova_id",
        readonly=False,
    )
    zipnova_key = fields.Char(
        related="company_id.zipnova_key",
        readonly=False,
    )
    zipnova_secret = fields.Char(
        related="company_id.zipnova_secret",
        readonly=False,
    )
    zipnova_origin_id = fields.Char(
        related="company_id.zipnova_origin_id",
        readonly=False,
    )
    zipnova_source = fields.Char(
        related="company_id.zipnova_source",
        readonly=False,
    )
    zipnova_declared_value = fields.Boolean(
        related="company_id.zipnova_declared_value",
        readonly=False,
    )
