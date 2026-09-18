import base64
import re
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = ["sale.order", "zipnova.api.mixin"]

    zipnova_pickup_carrier_id = fields.Char(string="Zipnova Carrier ID", copy=False)
    zipnova_pickup_is_pickup = fields.Boolean(string="Pickup point delivery", copy=False)
    zipnova_pickup_point_id = fields.Char(string="Pickup Point ID", copy=False)
    zipnova_pickup_name = fields.Char(string="Pickup Point", copy=False)
    zipnova_pickup_address = fields.Char(string="Pickup Address", copy=False)
    zipnova_logistic_type = fields.Char(copy=False)

    zipnova_shipping_id = fields.Char(string="Zipnova Shipment ID", copy=False)
    zipnova_shipping_delivery_id = fields.Char(string="Zipnova Delivery ID", copy=False)
    zipnova_shipping_carrier_tracking_id = fields.Char(
        string="Carrier Tracking", copy=False
    )
    zipnova_shipping_carrier_tracking_id_alt = fields.Char(
        string="Carrier Tracking Alt", copy=False
    )
    zipnova_shipping_tracking = fields.Char(string="Tracking URL", copy=False)
    zipnova_shipping_tracking_external = fields.Char(
        string="External Tracking URL", copy=False
    )
    zipnova_shipping_label_bin = fields.Binary(string="Label", copy=False)
    zipnova_shipping_label_filename = fields.Char(
        compute="_compute_shipping_label_filename"
    )
    zipnova_log_ids = fields.One2many(
        "zipnova.log",
        "order_id",
        string="Logs",
        copy=False,
    )
    zipnova_estimated_delivery_time = fields.Char(
        string="Zipnova estimated delivery",
        copy=False,
    )
    zipnova_min_date = fields.Date(
        string="Estimated delivery from",
        tracking=True,
        copy=False,
    )
    zipnova_max_date = fields.Date(
        string="Estimated delivery until",
        tracking=True,
        copy=False,
    )
    zipnova_latest_shipping_query = fields.Date(
        string="Last shipping quote date",
        copy=False,
    )
    zipnova_pickup_ids = fields.One2many(
        "zipnova.shipping",
        "order_id",
        string="Pickup Points",
        copy=False,
    )
    zipnova_delivery_type = fields.Selection(
        related="carrier_id.delivery_type",
        string="Carrier Provider",
    )

    def get_amount_total_without_delivery_amount(self):
        self.ensure_one()
        return self._compute_amount_total_without_delivery()

    def get_lines_delivery(self):
        self.ensure_one()
        return self.order_line.filtered("is_delivery")

    def _zipnova_replace_pickup_points(self, pickup_vals):
        self.ensure_one()
        self.zipnova_pickup_ids.unlink()
        valid_vals = [vals for vals in pickup_vals if vals.get("order_id")]
        if valid_vals:
            self.env["zipnova.shipping"].create(valid_vals)

    def _zipnova_iter_storable_lines(self, product, qty):
        """Yield (product, qty) for storable products, exploding phantom BoMs."""
        phantom_boms = product.bom_ids.filtered(lambda bom: bom.type == "phantom")
        if phantom_boms:
            bom = phantom_boms[0]
            for bom_line in bom.bom_line_ids:
                yield from self._zipnova_iter_storable_lines(
                    bom_line.product_id, qty * bom_line.product_qty
                )
            return
        if product.type == "product":
            yield product, qty

    def _zipnova_prepare_items(self):
        """Build Zipnova `items` with integer weight (g) and dimensions (cm)."""
        self.ensure_one()
        items = []
        for line in self.order_line:
            if line.display_type or line.is_delivery:
                continue
            product = line.product_id
            if not product:
                continue
            normal_boms = product.bom_ids.filtered(lambda bom: bom.type == "normal")
            if normal_boms and product.type != "product":
                bom = normal_boms[0]
                for bom_line in bom.bom_line_ids:
                    for child, child_qty in self._zipnova_iter_storable_lines(
                        bom_line.product_id, line.product_uom_qty * bom_line.product_qty
                    ):
                        items.extend(self._zipnova_items_for_product(child, child_qty))
                continue
            for child, child_qty in self._zipnova_iter_storable_lines(
                product, line.product_uom_qty
            ):
                items.extend(self._zipnova_items_for_product(child, child_qty))
        return items

    def _zipnova_items_for_product(self, product, qty):
        self._zipnova_check_product_dimensions(product)
        units = max(int(qty), 1)
        item = {
            "weight": self._zipnova_int_weight(product.weight * 1000),
            "height": self._zipnova_int_dim(product.zipnova_product_height),
            "width": self._zipnova_int_dim(product.zipnova_product_width),
            "length": self._zipnova_int_dim(product.zipnova_product_length),
            "description": (product.display_name or product.name or "")[:60],
            "classification_id": 1,
        }
        if product.default_code:
            item["sku"] = product.default_code
        return [dict(item) for _unused in range(units)]

    def _zipnova_check_product_dimensions(self, product):
        if (
            not product.weight
            or not product.zipnova_product_height
            or not product.zipnova_product_width
            or not product.zipnova_product_length
        ):
            raise UserError(
                _("Product %s must have weight and Zipnova dimensions.")
                % product.display_name
            )

    def _zipnova_extract_street_and_number(self, address):
        if not address:
            return False
        match = re.match(
            r"^([A-Za-zÀ-ÖØ-öø-ÿ0-9\s.,-]+?)(?:\s(\d{1,5}))?$",
            address.strip(),
        )
        if not match:
            return False
        street = match.group(1).strip()
        number = match.group(2) if match.group(2) else "sin-numero"
        return street, number

    def _zipnova_partner_phone(self, partner):
        parts = [value for value in (partner.phone, partner.mobile) if value]
        return " / ".join(parts)

    def _zipnova_quote_destination(self):
        self.ensure_one()
        partner = self.partner_shipping_id
        if not partner.city:
            raise UserError(_("The delivery address must have a city."))
        if not partner.state_id:
            raise UserError(_("The delivery address must have a state."))
        if not partner.zip:
            raise UserError(_("The delivery address must have a zip code."))
        street_name = partner.street or ""
        street_number = ""
        parsed = self._zipnova_extract_street_and_number(partner.street)
        if parsed:
            street_name, street_number = parsed
        return {
            "city": partner.city,
            "state": partner.state_id.name,
            "zipcode": partner.zip,
            "street": street_name,
            "street_number": street_number or None,
        }

    def _zipnova_create_destination(self):
        self.ensure_one()
        partner = self.partner_shipping_id
        if not partner.email:
            raise UserError(_("The delivery address must have an email."))
        if not partner.phone and not partner.mobile:
            raise UserError(_("The delivery address must have a phone or mobile."))
        phone = self._zipnova_partner_phone(partner)
        if self.zipnova_pickup_is_pickup:
            if not self.zipnova_pickup_point_id:
                raise UserError(_("Select a Zipnova pickup point."))
            return {
                "name": partner.name,
                "document": partner.vat or "",
                "phone": phone,
                "email": partner.email,
                "point_id": int(self.zipnova_pickup_point_id),
            }
        if not partner.street:
            raise UserError(_("The delivery address must have a street."))
        parsed = self._zipnova_extract_street_and_number(partner.street)
        if not parsed:
            raise UserError(
                _(
                    'Street must be in the format "street number", '
                    "for example \"Avenida Siempreviva 742\"."
                )
            )
        street_name, street_number = parsed
        if not partner.city:
            raise UserError(_("The delivery address must have a city."))
        if not partner.state_id:
            raise UserError(_("The delivery address must have a state."))
        if not partner.zip:
            raise UserError(_("The delivery address must have a zip code."))
        return {
            "city": partner.city,
            "state": partner.state_id.name,
            "zipcode": partner.zip,
            "name": partner.name,
            "document": partner.vat or "",
            "street": str(street_name),
            "street_number": str(street_number),
            "street_extras": partner.street2 or "",
            "phone": phone,
            "email": partner.email,
        }

    def action_zipnova_create_shipping(
        self,
        total_weight=None,
        total_length=None,
        total_height=None,
        total_width=None,
    ):
        for order in self:
            order._zipnova_create_shipping(
                total_weight=total_weight,
                total_length=total_length,
                total_height=total_height,
                total_width=total_width,
            )
        return True

    def _zipnova_create_shipping(
        self,
        total_weight=None,
        total_length=None,
        total_height=None,
        total_width=None,
    ):
        self.ensure_one()
        if self.zipnova_shipping_id:
            raise UserError(_("This order already has a Zipnova shipment."))
        if self.zipnova_latest_shipping_query:
            if fields.Date.context_today(self) > self.zipnova_latest_shipping_query:
                raise UserError(_("Refresh the Zipnova delivery estimate before creating the shipment."))
        self._zipnova_check_credentials(self.company_id)

        items = self._zipnova_prepare_items()
        if not items:
            raise UserError(_("The order has no storable products to ship."))
        if total_weight or total_length or total_height or total_width:
            count = len(items)
            item_weight = int(float(total_weight or 0) / count) if total_weight else None
            item_length = int(float(total_length or 0) / count) if total_length else None
            item_height = int(float(total_height or 0) / count) if total_height else None
            item_width = int(float(total_width or 0) / count) if total_width else None
            for item in items:
                if total_weight:
                    item["weight"] = self._zipnova_int_weight(item_weight)
                if total_length:
                    item["length"] = self._zipnova_int_dim(item_length)
                if total_height:
                    item["height"] = self._zipnova_int_dim(item_height)
                if total_width:
                    item["width"] = self._zipnova_int_dim(item_width)

        service_type = (
            "pickup_point" if self.zipnova_pickup_is_pickup else "standard_delivery"
        )
        declared_value = 0
        if self.company_id.zipnova_declared_value:
            declared_value = self.get_amount_total_without_delivery_amount() or 0

        payload = {
            "external_id": self._zipnova_external_id(self),
            "account_id": int(self.company_id.zipnova_id),
            "source": self._zipnova_source(self.company_id),
            "service_type": service_type,
            "declared_value": declared_value,
            "items": items,
            "destination": self._zipnova_create_destination(),
        }
        if self.company_id.zipnova_origin_id:
            try:
                payload["origin_id"] = int(self.company_id.zipnova_origin_id)
            except (TypeError, ValueError) as err:
                raise UserError(_("Zipnova Origin ID must be numeric.")) from err
        if self.zipnova_logistic_type:
            payload["logistic_type"] = self.zipnova_logistic_type
        if self.zipnova_pickup_carrier_id:
            payload["carrier_id"] = int(self.zipnova_pickup_carrier_id)

        status, data, _raw = self._zipnova_request(
            self.company_id,
            "POST",
            "/shipments",
            payload=payload,
            order=self,
            log_name="shipments",
        )
        if status >= 400 or not data:
            raise UserError(self._zipnova_error_message(status, data))

        estimated = ""
        delivery_time = data.get("delivery_time") or {}
        if delivery_time.get("estimated_delivery"):
            estimated = delivery_time["estimated_delivery"][:10]
            if self.carrier_id:
                estimated = self.carrier_id.add_margin_to_estimated_delivery(
                    estimated, self.carrier_id.fixed_margin_time
                )[:10]

        self.write(
            {
                "zipnova_shipping_id": data.get("id") and str(data.get("id")),
                "zipnova_shipping_delivery_id": data.get("delivery_id") or "",
                "zipnova_shipping_carrier_tracking_id": data.get("carrier_tracking_id")
                or "",
                "zipnova_shipping_carrier_tracking_id_alt": data.get(
                    "carrier_tracking_id_alt"
                )
                or "",
                "zipnova_shipping_tracking": data.get("tracking") or "",
                "zipnova_shipping_tracking_external": data.get("tracking_external")
                or "",
                "zipnova_estimated_delivery_time": estimated,
            }
        )

    def action_open_validate_delivery_carrier_wizard(self):
        self.ensure_one()
        items = self._zipnova_prepare_items()
        amount_delivery = self.amount_total - self.get_amount_total_without_delivery_amount()
        return {
            "name": _("Confirm Shipment"),
            "type": "ir.actions.act_window",
            "res_model": "validate.delivery.carrier.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_total_weight": sum(item["weight"] for item in items),
                "default_total_height": sum(item["height"] for item in items),
                "default_total_width": sum(item["width"] for item in items),
                "default_total_length": sum(item["length"] for item in items),
                "default_delivery_price": amount_delivery,
            },
        }

    def action_zipnova_get_label(self):
        self.ensure_one()
        if not self.zipnova_shipping_id:
            raise UserError(_("Create the Zipnova shipment first."))
        status, data, raw = self._zipnova_request(
            self.company_id,
            "GET",
            "/shipments/%s/label.pdf" % self.zipnova_shipping_id,
            order=self,
            log_name="label",
            expect_json=True,
        )
        if status == 409:
            raise UserError(_("The label is not available yet. Try again in a moment."))
        if status >= 400:
            status, data, raw = self._zipnova_request(
                self.company_id,
                "GET",
                "/shipments/%s/documentation?what=label&format=pdf"
                % self.zipnova_shipping_id,
                order=self,
                log_name="label_legacy",
                expect_json=True,
            )
        if status >= 400:
            raise UserError(self._zipnova_error_message(status, data))

        body = None
        if isinstance(data, dict) and data.get("body"):
            body = data["body"]
        elif raw:
            body = base64.b64encode(raw).decode("utf-8")
        if not body:
            raise UserError(_("The label is not available yet. Try again in a moment."))
        self.zipnova_shipping_label_bin = body

    def add_days_to_current_date(self, days_to_add):
        try:
            days = int(days_to_add or 0)
        except (TypeError, ValueError):
            days = 0
        return fields.Date.to_string(fields.Date.context_today(self) + timedelta(days=days))

    def _check_carrier_quotation(self, force_carrier_id=None, keep_carrier=False):
        res = super()._check_carrier_quotation(
            force_carrier_id=force_carrier_id, keep_carrier=keep_carrier
        )
        self.ensure_one()
        carrier = self.carrier_id
        if carrier.delivery_type != "zipnova" or not self.delivery_rating_success:
            return res
        self.zipnova_pickup_carrier_id = str(carrier.zipnova_shipment_type or "")
        self.zipnova_pickup_is_pickup = bool(carrier.zipnova_shipment_type_is_pickup)
        pickup = self.zipnova_pickup_ids[:1]
        if pickup:
            self.zipnova_logistic_type = pickup.logistic_type
        return res

    @api.depends("zipnova_shipping_id")
    def _compute_shipping_label_filename(self):
        for order in self:
            name = (order.zipnova_shipping_id or "zipnova").replace("/", "_").replace(
                ".", "_"
            )
            order.zipnova_shipping_label_filename = "%s.pdf" % name

    def action_open_delivery_wizard(self):
        if any(order.state not in ("draft", "sent") for order in self):
            raise UserError(
                _("Adding a shipping method is only allowed in quotation state.")
            )
        return super().action_open_delivery_wizard()

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.zipnova_shipping_tracking_external:
            values["zipnova_shipping_tracking_external"] = (
                self.zipnova_shipping_tracking_external
            )
        return values

    def action_zipnova_delete_shipping(self):
        for order in self:
            if not order.zipnova_shipping_id:
                continue
            status, data, _raw = order._zipnova_request(
                order.company_id,
                "POST",
                "/shipments/%s/cancel" % order.zipnova_shipping_id,
                order=order,
                log_name="cancel",
            )
            if status == 200:
                order._zipnova_clear_shipping()
                continue
            if status == 401:
                raise UserError(_("Zipnova could not cancel the shipment."))
            raise UserError(order._zipnova_error_message(status, data))

    def _zipnova_clear_shipping(self):
        self.write(
            {
                "zipnova_shipping_label_bin": False,
                "zipnova_shipping_id": False,
                "zipnova_estimated_delivery_time": False,
                "zipnova_shipping_delivery_id": False,
                "zipnova_shipping_carrier_tracking_id": False,
                "zipnova_shipping_carrier_tracking_id_alt": False,
                "zipnova_shipping_tracking": False,
                "zipnova_shipping_tracking_external": False,
            }
        )

    def _zipnova_clear_pickup_info(self):
        self.write(
            {
                "zipnova_pickup_carrier_id": False,
                "zipnova_pickup_is_pickup": False,
                "zipnova_pickup_point_id": False,
                "zipnova_pickup_name": False,
                "zipnova_pickup_address": False,
                "zipnova_logistic_type": False,
            }
        )
        self.zipnova_pickup_ids.unlink()

    @api.onchange("commitment_date", "zipnova_min_date", "zipnova_max_date")
    def update_dates(self):
        for order in self:
            commitment_date = order.commitment_date
            if isinstance(commitment_date, datetime):
                commitment_date = commitment_date.date()
            zipnova_min_date = order.zipnova_min_date
            zipnova_max_date = order.zipnova_max_date
            if zipnova_min_date and zipnova_max_date and zipnova_min_date > zipnova_max_date:
                raise ValidationError(
                    _(
                        "The minimum estimated delivery date must be before "
                        "the maximum estimated delivery date."
                    )
                )
            if (
                commitment_date
                and zipnova_max_date
                and commitment_date > zipnova_max_date
            ):
                raise ValidationError(
                    _(
                        "The delivery date must be before the maximum "
                        "estimated delivery date."
                    )
                )
