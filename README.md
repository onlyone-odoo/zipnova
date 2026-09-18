**Zipnova Odoo Connector**

Connector for Zipnova shipping (formerly Zippin) on Odoo 17.

## Setup

1. Install the `zipnova` module.
2. Open **Settings → Sales → Shipping → Zipnova** and fill Account ID, API Token and API Secret
   (from Zipnova: Configuración → Integraciones). The same fields remain on the company form.
3. Optional: set **Origin ID** to a Zipnova address-book origin. If empty, Zipnova uses the account default.
4. Optional: set **Integration Source** (`odoo` by default) so quoting rules can target this connector.
5. Create delivery methods with provider **Zipnova**.
6. Set the Zipnova carrier ID:
   - Correo Argentino: `233`
   - OCA: `208`
   - Andreani: `1`
7. Enable **Pickup point delivery** for branch/sucursal methods.
8. Use integration level **Get Rate**. Create the shipment from the sales order (or it is created after website payment).
9. Put weight (kg) and Zipnova dimensions (cm) on storable products.

## Flow

- Quote from Sales (Add shipping method) or the website checkout.
- Create the shipment from the sales order, download the PDF label, cancel if needed.
- Website pickup methods show nearby pickup points; the selected point is stored on the order.

## Notes

- API base URL: `https://api.zipnova.com.ar/v2`
- Authentication: HTTP Basic (API Token / API Secret)
- `external_id` sent to Zipnova is the sales order number (max 30 characters)
