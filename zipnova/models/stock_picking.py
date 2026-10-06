from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    zipnova_shipping_id = fields.Char(
        related="sale_id.zipnova_shipping_id",
        string="Zipnova Shipment ID",
    )
    zipnova_shipping_delivery_id = fields.Char(
        related="sale_id.zipnova_shipping_delivery_id",
        string="Zipnova Delivery ID",
    )
    zipnova_shipping_carrier_tracking_id = fields.Char(
        related="sale_id.zipnova_shipping_carrier_tracking_id",
        string="Carrier Tracking",
    )
    zipnova_shipping_carrier_tracking_id_alt = fields.Char(
        related="sale_id.zipnova_shipping_carrier_tracking_id_alt",
        string="Carrier Tracking Alt",
    )
    zipnova_shipping_tracking = fields.Char(
        related="sale_id.zipnova_shipping_tracking",
        string="Tracking URL",
    )
    zipnova_shipping_tracking_external = fields.Char(
        related="sale_id.zipnova_shipping_tracking_external",
        string="External Tracking URL",
    )
    zipnova_estimated_delivery_time = fields.Char(
        related="sale_id.zipnova_estimated_delivery_time",
        string="Estimated delivery",
    )
