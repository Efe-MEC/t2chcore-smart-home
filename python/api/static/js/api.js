const API_BASE = "/api";

async function request(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers
        }
    });

    if (!response.ok) {
        const detail = await response.text();
        throw new Error(
            `API request failed (${response.status}): ${detail || response.statusText}`
        );
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

export async function getDashboardData() {
    const [health, deviceData] = await Promise.all([
        request("/health"),
        request("/devices")
    ]);

    return {
        health,
        devices: deviceData.devices ?? []
    };
}

export async function getDevices() {
    const result = await request("/devices");
    return result.devices ?? [];
}

export async function createDevice(device) {
    return request("/devices", {
        method: "POST",
        body: JSON.stringify(device)
    });
}

export async function deleteDevice(deviceId) {
    return request(`/devices/${encodeURIComponent(deviceId)}`, {
        method: "DELETE"
    });
}

export async function sendDeviceCommand(deviceId, state) {
    return request(`/devices/${encodeURIComponent(deviceId)}/command`, {
        method: "POST",
        body: JSON.stringify({ state })
    });
}

export async function getAIHealth() {
    return request("/ai/health");
}

export async function sendAIMessage({ message, history = [] }) {
    return request("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message, history })
    });
}
