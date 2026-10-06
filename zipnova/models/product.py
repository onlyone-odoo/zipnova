from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    zipnova_product_length = fields.Float(string="Zipnova Length (cm)")
    zipnova_product_height = fields.Float(string="Zipnova Height (cm)")
    zipnova_product_width = fields.Float(string="Zipnova Width (cm)")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    zipnova_product_length = fields.Float(
        string="Zipnova Length (cm)",
        related="product_variant_ids.zipnova_product_length",
        readonly=False,
    )
    zipnova_product_height = fields.Float(
        string="Zipnova Height (cm)",
        related="product_variant_ids.zipnova_product_height",
        readonly=False,
    )
    zipnova_product_width = fields.Float(
        string="Zipnova Width (cm)",
        related="product_variant_ids.zipnova_product_width",
        readonly=False,
    )

    def _prepare_variant_values(self, combination):
        values = super()._prepare_variant_values(combination)
        if self.zipnova_product_length:
            values["zipnova_product_length"] = self.zipnova_product_length
        if self.zipnova_product_height:
            values["zipnova_product_height"] = self.zipnova_product_height
        if self.zipnova_product_width:
            values["zipnova_product_width"] = self.zipnova_product_width
        return values
