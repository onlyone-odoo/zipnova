/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.websiteSaleDeliveryZipnova = publicWidget.Widget.extend({
    selector: ".oe_website_sale",
    events: {
        "change select.zipnova-pickup-select": "_onPickupChange",
    },

    /**
     * @override
     */
    start: async function () {
        await this._super(...arguments);
        const selects = this.el.querySelectorAll("select.zipnova-pickup-select");
        for (const select of selects) {
            await this._loadPickupPoints(select);
        }
    },

    /**
     * Load pickup points for a Zipnova pickup carrier.
     *
     * @param {HTMLSelectElement} select
     */
    async _loadPickupPoints(select) {
        const carrierId = select.dataset.deliveryCarrierId;
        if (!carrierId) {
            return;
        }
        if (select.options.length > 1) {
            return;
        }
        try {
            const data = await jsonrpc("/shop/zipnova/pickup_points", {
                carrier_id: parseInt(carrierId, 10),
            });
            if (!data || !data.points || !data.points.length) {
                return;
            }
            data.points.forEach((pickup) => {
                const option = document.createElement("option");
                option.value = pickup.point_id;
                option.dataset.carrierId = pickup.carrier_id;
                option.dataset.pointId = pickup.point_id;
                option.dataset.name = pickup.name || "";
                option.dataset.address = pickup.address || "";
                option.textContent = pickup.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error("Zipnova pickup points failed", error);
        }
    },

    /**
     * Persist the selected pickup point on the cart.
     *
     * @param {Event} ev
     */
    async _onPickupChange(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const select = ev.currentTarget;
        this.el.querySelectorAll("select.zipnova-pickup-select").forEach((other) => {
            if (other !== select) {
                other.selectedIndex = 0;
            }
        });
        if (!select.value) {
            return;
        }
        const option = select.selectedOptions[0];
        const payload = {
            carrier_id: option.dataset.carrierId,
            point_id: option.dataset.pointId,
            name: option.dataset.name,
            address: option.dataset.address,
        };
        try {
            await jsonrpc("/shop/zipnova/pickup", payload);
        } catch (error) {
            console.error("Zipnova pickup save failed", error);
        }
    },
});
