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
- Website pickup methods show nearby pickup points; only points returned by the Zipnova
  quote are accepted, and payment is blocked until one is selected.
- Website shipments are created when the payment transaction is `done`
  (pending payments such as wire transfers do not create shipments). Failures are posted
  on the order chatter so they can be retried from the backend.

## Pricing and taxes

- If the delivery product has sale taxes **not included** in price, the net Zipnova price
  (`amounts.price`) is used and Odoo adds VAT.
- If its taxes are price-included, or it has no taxes, `amounts.price_incl_tax` is used.

## Logs

- API calls are logged on the order (Zipnova Logs tab, debug mode). Failed calls are kept
  even when the operation is rolled back.
- Logs older than 30 days are deleted by the daily autovacuum. Change it with the system
  parameter `zipnova.log_retention_days` (`0` keeps them forever).
- API credentials are only visible to Settings administrators.

## Testing

Zipnova has no separate sandbox API. The test mode is a flag that Zipnova support
enables on the account; requests still go to `https://api.zipnova.com.ar/v2` with the
same credentials.

1. Register the account normally and ask Zipnova support to enable test mode before
   creating shipments from a staging database.
2. Quoting does not create a shipment and can be done without test mode.
3. When testing is finished, ask support to switch the account back to operational
   mode. Otherwise carriers will not accept the shipments.

Source: https://ayuda-envios.zipnova.com/hc/es-419/articles/45276943102099

## Notes

- API base URL: `https://api.zipnova.com.ar/v2`
- Authentication: HTTP Basic (API Token / API Secret)
- `external_id` sent to Zipnova is the sales order number (max 30 characters)
- One Zipnova item is sent per unit (UoM converted, kits exploded); max 1000 units per shipment
