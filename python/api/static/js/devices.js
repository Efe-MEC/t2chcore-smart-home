
import {
    deleteDevice as deleteDeviceRequest,
    sendDeviceCommand,
} from "./api.js";
import { showNotice, updateLastUpdated } from "./ui.js";

const $ = (id) => document.getElementById(id);

function createElement(tag, className = "", text = "") {
    const element = document.createElement(tag);

    if (className) element.className = className;
    element.textContent = text;

    return element;
}

function formatRoom(room) {
    const names = {
        "living-room": "Salon",
        bedroom: "Yatak Odası",
        kitchen: "Mutfak",
        bathroom: "Banyo",
        hallway: "Koridor",
        balcony: "Balkon",
        other: "Diğer",
    };

    return names[room] || String(room || "Genel").replaceAll("-", " ");
}

function getDeviceIcon(type) {
    const icons = {
        light: "💡",
        switch: "⏻",
        sensor: "◉",
        thermostat: "🌡",
        unknown: "◈",
    };

    return icons[type] || "◈";
}

function renderDeviceCard(device) {
    const card = createElement("article", "panel device-card");
    const top = createElement("div", "device-top");
    const online = device.online === true;

    const icon = createElement(
        "div",
        "device-icon",
        getDeviceIcon(device.type)
    );

    const identity = createElement("div", "device-identity");

    identity.append(
        createElement("div", "device-name", device.name || device.id),
        createElement("div", "device-room", formatRoom(device.room))
    );

    const status = createElement("div", "device-status");

    status.append(
        createElement(
            "span",
            `status-dot${online ? " online" : ""}`
        ),
        createElement(
            "div",
            "device-room",
            online ? "Çevrimiçi" : "Çevrimdışı"
        )
    );

    top.append(icon, identity, status);
    card.append(top);

    const state = String(device.state ?? "unknown").toUpperCase();
    const stateClass = state === "ON"
        ? "on"
        : state === "OFF"
            ? "off"
            : "unknown";

    card.append(
        createElement("div", `device-state ${stateClass}`, state)
    );

    card.append(
        createElement(
            "p",
            "device-hint",
            online
                ? "Cihaz bağlantı bildirimi alınmış."
                : "Son bilinen durum; fiziksel bağlantı doğrulanmadı."
        )
    );

    const actions = createElement("div", "device-actions");

    for (const desiredState of ["ON", "OFF"]) {
        const button = createElement(
            "button",
            `button${desiredState === "ON" ? " button-primary" : ""}`,
            desiredState === "ON" ? "Aç" : "Kapat"
        );

        button.type = "button";

        button.addEventListener("click", () => {
            void sendDeviceCommand(device.id, desiredState, button);
        });

        actions.append(button);
    }

    card.append(actions);

    const removeButton = createElement(
        "button",
        "button device-delete-button",
        "Cihazı Sil"
    );

    removeButton.type = "button";

    removeButton.addEventListener("click", async () => {
        const result = await deleteDeviceRequest(device.id, removeButton);

        if (result) {
            window.dispatchEvent(new CustomEvent("devices:refresh"));
        }
    });

    card.append(removeButton);

    return card;
}

export function renderDevices(devices) {
    const container = $("device-list");

    if (!container) {
        console.error("Cihaz listesi kapsayıcısı bulunamadı.");
        return;
    }

    const safeDevices = Array.isArray(devices) ? devices : [];
    container.replaceChildren();

    const count = $("device-count");
    if (count) count.textContent = String(safeDevices.length);

    const onlineCount = $("online-count");

    if (onlineCount) {
        onlineCount.textContent = String(
            safeDevices.filter((device) => device.online === true).length
        );
    }

    const sectionCount = $("device-section-count");

    if (sectionCount) {
        sectionCount.textContent = `${safeDevices.length} cihaz`;
    }

    if (safeDevices.length === 0) {
        container.append(
            createElement(
                "div",
                "panel empty-state",
                "Henüz kayıtlı cihaz yok."
            )
        );
    } else {
        for (const device of safeDevices) {
            container.append(renderDeviceCard(device));
        }
    }

    updateLastUpdated();
}

export function applyDeviceUpdate(devices) {
    renderDevices(devices);
}
