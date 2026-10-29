
import { createDevice } from "./api.js";
import { showNotice } from "./ui.js";

const $ = (id) => document.getElementById(id);

export function initializeDeviceForm() {
    const form = $("device-form");

    if (!form) {
        console.warn("Cihaz formu bulunamadı.");
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');

        if (submitButton?.disabled) return;
        if (submitButton) submitButton.disabled = true;

        const device = {
            name: $("device-name-input")?.value.trim() || "",
            id: $("device-id")?.value.trim().toLowerCase() || "",
            room: $("device-room")?.value || "",
            type: $("device-type")?.value || "unknown",
        };

        try {
            const result = await createDevice(device);

            form.reset();

            showNotice(
                `${result.device?.name || device.name} cihaz kaydına eklendi. ` +
                "Fiziksel bağlantı henüz doğrulanmadı.",
                "success"
            );

            window.dispatchEvent(new CustomEvent("devices:refresh"));
        } catch (error) {
            showNotice(error.message || "Cihaz eklenemedi.", "error");
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
}
