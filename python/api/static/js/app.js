const $ = (id) => document.getElementById(id);

let refreshInProgress = false;
let socket = null;
let reconnectTimer = null;
let reconnectDelay = 1000;
let manuallyRefreshing = false;

function createElement(tag, className = "", text = "") {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    element.textContent = text;
    return element;
}

function showNotice(message, isError = false) {
    const notice = $("notice");
    notice.textContent = message;
    notice.classList.toggle("error", isError);
}

function renderDevices(devices) {
    const container = $("device-list");
    container.replaceChildren();

    $("device-count").textContent = devices.length;

    $("online-count").textContent = devices.filter(
        (device) => device.online === true
    ).length;

    if (devices.length === 0) {
        container.append(
            createElement("div", "panel empty-state", "Henüz kayıtlı cihaz yok.")
        );
        return;
    }

    for (const device of devices) {
        const card = createElement("article", "panel device-card");
        const top = createElement("div", "device-top");

        const icon = createElement(
            "div",
            "device-icon",
            device.type === "light" ? "💡" : "◈"
        );

        const identity = createElement("div");
        identity.append(
            createElement("div", "device-name", device.name || device.id),
            createElement(
                "div",
                "device-room",
                (device.room || "Genel").replaceAll("-", " ")
            )
        );

        const status = createElement("div", "device-status");
        const dot = createElement(
            "span",
            "status-dot" + (device.online === true ? " online" : "")
        );

        status.append(
            dot,
            createElement(
                "div",
                "device-room",
                device.online === true ? "Çevrimiçi" : "Çevrimdışı"
            )
        );

        top.append(icon, identity, status);
        card.append(top);

        const state = String(device.state ?? "unknown").toUpperCase();

        card.append(
            createElement(
                "div",
                "device-state " + (state === "ON" ? "on" : "off"),
                state
            )
        );

        card.append(
            createElement(
                "p",
                "device-hint",
                device.online === true
                    ? "Cihazdan bağlantı bildirimi alınmış."
                    : "Son bilinen durum. Fiziksel cihaz bağlantısı doğrulanmadı."
            )
        );

        const actions = createElement("div", "device-actions");

        for (const desiredState of ["ON", "OFF"]) {
            const button = createElement(
                "button",
                "button" + (desiredState === "ON" ? " button-primary" : ""),
                desiredState === "ON" ? "Aç" : "Kapat"
            );

            button.addEventListener("click", () => {
                sendCommand(device.id, desiredState, button);
            });

            actions.append(button);
        }

        card.append(actions);
        container.append(card);
    }
}

function updateLastUpdated() {
    $("last-updated").textContent =
        "Son güncelleme: " + new Date().toLocaleTimeString("tr-TR");
}

function applyDeviceUpdate(devices) {
    renderDevices(Array.isArray(devices) ? devices : []);
    updateLastUpdated();
}

async function loadDashboard() {
    if (refreshInProgress) {
        return;
    }

    refreshInProgress = true;

    try {
        const [healthResponse, devicesResponse] = await Promise.all([
            fetch("/api/health", { cache: "no-store" }),
            fetch("/api/devices", { cache: "no-store" })
        ]);

        if (!healthResponse.ok || !devicesResponse.ok) {
            throw new Error("API yanıt vermedi.");
        }

        const health = await healthResponse.json();
        const data = await devicesResponse.json();

        $("health-dot").classList.toggle("online", health.mqtt === true);

        $("health-text").textContent =
            health.mqtt === true ? "API ve MQTT bağlı" : "MQTT bağlantısı yok";

        $("mqtt-value").textContent =
            health.mqtt === true ? "Bağlı" : "Bağlı değil";

        applyDeviceUpdate(data.devices);

        if (health.mqtt === true) {
            showNotice(
                socket && socket.readyState === WebSocket.OPEN
                    ? "Sistem çalışıyor. Gerçek zamanlı bağlantı aktif."
                    : "MQTT bağlı. Gerçek zamanlı bağlantı kuruluyor."
            );
        } else {
            showNotice("API çalışıyor ancak MQTT bağlantısı yok.", true);
        }
    } catch (error) {
        $("health-dot").classList.remove("online");
        $("health-text").textContent = "API bağlantısı yok";
        $("mqtt-value").textContent = "Bilinmiyor";

        showNotice(
            "Dashboard API'ye ulaşamıyor. Uygulama loglarını kontrol et.",
            true
        );
    } finally {
        refreshInProgress = false;
        manuallyRefreshing = false;
    }
}

function connectWebSocket() {
    if (
        socket &&
        (socket.readyState === WebSocket.OPEN ||
         socket.readyState === WebSocket.CONNECTING)
    ) {
        return;
    }

    if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws`;

    socket = new WebSocket(url);

    socket.addEventListener("open", () => {
        reconnectDelay = 1000;

        if (!manuallyRefreshing) {
            showNotice("Gerçek zamanlı bağlantı aktif.");
        }

        loadDashboard();
    });

    socket.addEventListener("message", (event) => {
        try {
            const message = JSON.parse(event.data);

            if (message.type === "devices") {
                applyDeviceUpdate(message.devices);
            }
        } catch (error) {
            console.error("WebSocket mesajı okunamadı:", error);
        }
    });

    socket.addEventListener("close", () => {
        if (!manuallyRefreshing) {
            showNotice(
                "Gerçek zamanlı bağlantı kesildi. Yeniden bağlanılıyor.",
                true
            );
        }

        scheduleReconnect();
    });

    socket.addEventListener("error", () => {
        socket.close();
    });
}

function scheduleReconnect() {
    if (reconnectTimer !== null) {
        return;
    }

    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
    }, reconnectDelay);

    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
}

async function sendCommand(deviceId, state, button) {
    button.disabled = true;

    try {
        const response = await fetch(
            "/api/devices/" + encodeURIComponent(deviceId) + "/command",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ state })
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Komut gönderilemedi.");
        }

        showNotice(
            `${deviceId} için ${state} komutu MQTT'ye gönderildi. ` +
            "Fiziksel cihazın komutu uygulaması henüz doğrulanmadı."
        );
    } catch (error) {
        showNotice(error.message || "Komut gönderilemedi.", true);
    } finally {
        button.disabled = false;
    }
}

$("refresh-button").addEventListener("click", () => {
    manuallyRefreshing = true;
    loadDashboard();
    connectWebSocket();
});

loadDashboard();
connectWebSocket();
