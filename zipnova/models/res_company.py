from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    zipnova_id = fields.Char(
        string="Account ID",
        groups="base.group_system",
        help="Zipnova account_id used on quote and create shipment requests.",
    )
    zipnova_key = fields.Char(
        string="API Token",
        groups="base.group_system",
        help="Zipnova API Token (Basic auth user).",
    )
    zipnova_secret = fields.Char(
        string="API Secret",
        groups="base.group_system",
        help="Zipnova API Secret (Basic auth password).",
    )
    zipnova_origin_id = fields.Char(
        string="Origin ID",
        help="Zipnova address book origin. Leave empty to use the account default origin.",
    )
    zipnova_source = fields.Char(
        string="Integration Source",
        default="odoo",
        help="Value sent as `source` so Zipnova can apply quoting rules.",
    )
    zipnova_declared_value = fields.Boolean(
        string="Declare order value",
        default=True,
        help="If enabled, the order amount (shipping excluded) is sent as declared_value.",
    )

    @api.constrains("zipnova_id", "zipnova_origin_id")
    def _check_zipnova_numeric_ids(self):
        for company in self.sudo():
            for value, label in (
                (company.zipnova_id, _("Zipnova Account ID")),
                (company.zipnova_origin_id, _("Zipnova Origin ID")),
            ):
                if value and not value.strip().isdigit():
                    raise ValidationError(_("%s must be numeric.") % label)
