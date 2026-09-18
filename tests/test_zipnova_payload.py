from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.zipnova.models.zipnova_api import (
    EXTERNAL_ID_MAX,
    ID_OCA,
    ID_PICKUP_DELIVERY,
    ID_STANDARD_DELIVERY,
)


@tagged("post_install", "-at_install")
class TestZipnovaPayload(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "zipnova_id": "3355",
                "zipnova_key": "token",
                "zipnova_secret": "secret",
                "zipnova_source": "odoo-test",
            }
        )
        argentina = cls.env.ref("base.ar")
        state = cls.env["res.country.state"].search(
            [("country_id", "=", argentina.id)], limit=1
        )
        if not state:
            state = cls.env["res.country.state"].create(
                {
                    "name": "Cordoba",
                    "code": "X",
                    "country_id": argentina.id,
                }
            )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Test",
                "street": "Avenida Siempreviva 742",
                "city": "Cordoba",
                "zip": "5000",
                "email": "cliente@example.com",
                "phone": "3511111111",
                "country_id": argentina.id,
                "state_id": state.id if state else False,
                "vat": "20111111112",
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Caja Test",
                "type": "product",
                "weight": 0.5,
                "zipnova_product_length": 10.4,
                "zipnova_product_height": 5.6,
                "zipnova_product_width": 8.2,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "uom_po_id": cls.env.ref("uom.product_uom_unit").id,
            }
        )
        delivery_product = cls.env["product.product"].create(
            {
                "name": "Envio Zipnova",
                "type": "service",
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "uom_po_id": cls.env.ref("uom.product_uom_unit").id,
            }
        )
        cls.carrier = cls.env["delivery.carrier"].create(
            {
                "name": "OCA a Domicilio",
                "delivery_type": "zipnova",
                "product_id": delivery_product.id,
                "zipnova_shipment_type": ID_OCA,
                "zipnova_shipment_type_is_pickup": False,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "partner_shipping_id": cls.partner.id,
                "carrier_id": cls.carrier.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 2,
                        },
                    )
                ],
            }
        )

    def test_external_id_max_length(self):
        self.order.name = "S000000000000000000000000000999"
        external_id = self.order._zipnova_external_id(self.order)
        self.assertLessEqual(len(external_id), EXTERNAL_ID_MAX)

    def test_items_are_integers(self):
        items = self.order._zipnova_prepare_items()
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIsInstance(item["weight"], int)
            self.assertIsInstance(item["height"], int)
            self.assertIsInstance(item["width"], int)
            self.assertIsInstance(item["length"], int)
            self.assertGreaterEqual(item["weight"], 10)
            self.assertEqual(item["length"], 10)
            self.assertEqual(item["height"], 6)
            self.assertEqual(item["width"], 8)

    def test_street_parsing(self):
        street, number = self.order._zipnova_extract_street_and_number(
            "Avenida Siempreviva 742"
        )
        self.assertEqual(street, "Avenida Siempreviva")
        self.assertEqual(number, "742")

    def test_rate_filters_standard_carrier(self):
        response = {
            "all_results": [
                {
                    "selectable": True,
                    "logistic_type": "carrier_pickup",
                    "carrier": {"id": ID_OCA, "name": "OCA"},
                    "service_type": {"id": ID_STANDARD_DELIVERY, "code": "standard_delivery"},
                    "amounts": {"price": 1000, "price_incl_tax": 1210},
                    "delivery_time": {
                        "estimated_delivery": "2026-09-20T18:00:00",
                        "min": 2,
                        "max": 4,
                    },
                    "pickup_points": [],
                },
                {
                    "selectable": True,
                    "logistic_type": "xd_dropoff",
                    "carrier": {"id": ID_OCA, "name": "OCA"},
                    "service_type": {"id": ID_PICKUP_DELIVERY, "code": "pickup_point"},
                    "amounts": {"price": 500, "price_incl_tax": 605},
                    "delivery_time": {"estimated_delivery": "2026-09-18T18:00:00"},
                    "pickup_points": [
                        {
                            "point_id": 99,
                            "description": "Sucursal Centro",
                            "location": {
                                "street": "San Martin",
                                "street_number": "100",
                                "city": "Cordoba",
                                "state": "Cordoba",
                            },
                        }
                    ],
                },
            ]
        }
        vals = self.carrier._get_rate_vals_from_response(self.order, response)
        self.assertTrue(vals["success"])
        self.assertEqual(vals["price"], 1210)
        self.assertEqual(vals["shipment_type"], ID_OCA)
        self.assertFalse(vals["zipnova_pickup"])

    def test_rate_filters_pickup_carrier(self):
        self.carrier.zipnova_shipment_type_is_pickup = True
        response = {
            "all_results": [
                {
                    "selectable": True,
                    "logistic_type": "xd_dropoff",
                    "carrier": {"id": ID_OCA, "name": "OCA"},
                    "service_type": {"id": ID_PICKUP_DELIVERY, "code": "pickup_point"},
                    "amounts": {"price": 500, "price_incl_tax": 605},
                    "delivery_time": {
                        "estimated_delivery": "2026-09-18T18:00:00",
                        "min": 1,
                        "max": 3,
                    },
                    "pickup_points": [
                        {
                            "point_id": 99,
                            "description": "Sucursal Centro",
                            "location": {
                                "street": "San Martin",
                                "street_number": "100",
                                "city": "Cordoba",
                                "state": "Cordoba",
                            },
                        }
                    ],
                }
            ]
        }
        vals = self.carrier._get_rate_vals_from_response(self.order, response)
        self.assertTrue(vals["success"])
        self.assertEqual(vals["price"], 605)
        self.assertEqual(len(vals["zipnova_pickup"]), 1)
        self.assertEqual(vals["zipnova_pickup"][0]["point_id"], "99")

    @patch("odoo.addons.zipnova.models.zipnova_api.requests.request")
    def test_quote_sends_source(self, mock_request):
        mock_response = mock_request.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {"all_results": []}
        mock_response.content = b'{"all_results": []}'
        mock_response.text = '{"all_results": []}'
        self.carrier.zipnova_rate_shipment(self.order)
        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["source"], "odoo-test")
        self.assertEqual(payload["account_id"], 3355)
        self.assertTrue(payload["items"])
        self.assertIsInstance(payload["items"][0]["weight"], int)

    def test_missing_dimensions_raise(self):
        self.product.zipnova_product_length = 0
        with self.assertRaises(UserError):
            self.order._zipnova_prepare_items()
