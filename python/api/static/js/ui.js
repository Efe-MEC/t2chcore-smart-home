
const $ = (id) => document.getElementById(id);

export function showNotice(message, type = "success") {
    const notice = $("notice");

    if (!notice) {
        console.info("[UNO Q]", message);
        return;
    }

    notice.textContent = message;
    notice.classList.remove("success", "error", "warning");

    const safeType = ["success", "error", "warning"].includes(type)
        ? type
        : "success";

    notice.classList.add(safeType);
    notice.hidden = false;
    notice.setAttribute("role", safeType === "error" ? "alert" : "status");
}

export function updateConnectionStatus(health) {
    const mqttConnected = health?.mqtt === true;

    for (const indicator of [
        { dot: $("health-dot"), text: $("health-text") },
        { dot: $("header-health-dot"), text: $("header-health-text") },
    ]) {
        if (indicator.dot) {
            indicator.dot.classList.toggle("online", mqttConnected);
        }

        if (indicator.text) {
            indicator.text.textContent = mqttConnected
                ? "API ve MQTT bağlı"
                : "MQTT bağlantısı yok";
        }
    }

    const mqttValue = $("mqtt-value");

    if (mqttValue) {
        mqttValue.textContent = mqttConnected ? "Bağlı" : "Bağlı değil";
    }
}

export function updateLastUpdated() {
    const element = $("last-updated");

    if (element) {
        element.textContent =
            "Son güncelleme: " +
            new Date().toLocaleTimeString("tr-TR");
    }
}

export function setButtonLoading(
    button,
    loading,
    loadingText = "İşleniyor..."
) {
    if (!button) return;

    if (loading) {
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent.trim();
        }

        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.textContent = loadingText;
        return;
    }

    button.disabled = false;
    button.removeAttribute("aria-busy");

    if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
        delete button.dataset.originalText;
    }
}
