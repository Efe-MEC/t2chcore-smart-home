
import { loadPartials } from "./html-loader.js";
import { getDashboardData } from "./api.js";
import { renderDevices } from "./devices.js";
import { initializeDeviceForm } from "./device-form.js";
import { initializeAssistant } from "./assistant.js";
import {
    showNotice,
    updateConnectionStatus,
} from "./ui.js";
import {
    connectWebSocket,
    disconnectWebSocket,
} from "./websocket.js";

let refreshInProgress = false;
let refreshRequested = false;

async function loadDashboard() {
    if (refreshInProgress) {
        refreshRequested = true;
        return;
    }

    refreshInProgress = true;

    try {
        const { health, devices } = await getDashboardData();

        updateConnectionStatus(health);
        renderDevices(devices);

        if (health.mqtt) {
            showNotice("Dashboard verileri güncellendi.", "success");
        } else {
            showNotice(
                "API çalışıyor ancak MQTT bağlantısı yok.",
                "warning"
            );
        }
    } catch (error) {
        showNotice(
            error.message || "Dashboard verileri yüklenemedi.",
            "error"
        );
    } finally {
        refreshInProgress = false;

        if (refreshRequested) {
            refreshRequested = false;
            void loadDashboard();
        }
    }
}

function initializeNavigation() {
    document.querySelectorAll(".sidebar-nav .nav-link").forEach((link) => {
        link.addEventListener("click", () => {
            document.querySelectorAll(".sidebar-nav .nav-link")
                .forEach((item) => item.classList.remove("active"));

            link.classList.add("active");
        });
    });
}

function initializeRefreshButton() {
    const button = document.getElementById("refresh-button");

    if (button) {
        button.addEventListener("click", () => {
            void loadDashboard();
        });
    }
}

function initializeRealtimeUpdates() {
    connectWebSocket({
        onDevices(devices) {
            renderDevices(devices);
        },

        onStatus(status) {
            if (status === "connected") {
                showNotice(
                    "Gerçek zamanlı bağlantı aktif.",
                    "success"
                );
            } else if (status === "disconnected") {
                showNotice(
                    "Gerçek zamanlı bağlantı kesildi. Yeniden bağlanılıyor.",
                    "warning"
                );
            } else if (status === "error") {
                console.warn("WebSocket bağlantı hatası.");
            }
        },
    });
}

async function initializeApplication() {
    try {
        await loadPartials([
            { target: "#sidebar-slot", file: "sidebar.html" },
            { target: "#header-slot", file: "header.html" },
            { target: "#overview-slot", file: "overview.html" },
            { target: "#device-form-slot", file: "device-form.html" },
            { target: "#assistant-slot", file: "assistant.html" },
            { target: "#footer-slot", file: "footer.html" },
        ]);

        initializeNavigation();
        initializeRefreshButton();
        initializeDeviceForm();
        await initializeAssistant();

        window.addEventListener("devices:refresh", () => {
            void loadDashboard();
        });

        initializeRealtimeUpdates();
        await loadDashboard();
    } catch (error) {
        console.error("Uygulama başlatılamadı:", error);

        const notice = document.getElementById("notice");

        if (notice) {
            notice.hidden = false;
            notice.textContent =
                "Arayüz yüklenemedi. HTML parçalarını ve uygulama loglarını kontrol et.";
            notice.classList.add("error");
        }
    }
}

window.addEventListener("beforeunload", disconnectWebSocket);

void initializeApplication();
