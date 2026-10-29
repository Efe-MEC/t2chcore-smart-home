
let socket = null;
let reconnectTimer = null;
let reconnectDelay = 1000;
let manuallyStopped = false;

const MAX_RECONNECT_DELAY = 30000;

export function connectWebSocket({
    onDevices,
    onStatus,
} = {}) {
    manuallyStopped = false;

    if (
        socket &&
        (
            socket.readyState === WebSocket.OPEN ||
            socket.readyState === WebSocket.CONNECTING
        )
    ) {
        return;
    }

    if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    const protocol = window.location.protocol === "https:"
        ? "wss:"
        : "ws:";

    socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

    socket.addEventListener("open", () => {
        reconnectDelay = 1000;
        onStatus?.("connected");
    });

    socket.addEventListener("message", (event) => {
        try {
            const message = JSON.parse(event.data);

            if (
                message.type === "devices" &&
                Array.isArray(message.devices)
            ) {
                onDevices?.(message.devices);
            }
        } catch (error) {
            console.error("WebSocket mesajı okunamadı:", error);
        }
    });

    socket.addEventListener("close", () => {
        onStatus?.("disconnected");

        if (!manuallyStopped) {
            scheduleReconnect({ onDevices, onStatus });
        }
    });

    socket.addEventListener("error", () => {
        onStatus?.("error");

        if (socket && socket.readyState !== WebSocket.CLOSED) {
            socket.close();
        }
    });
}

function scheduleReconnect(callbacks) {
    if (manuallyStopped || reconnectTimer !== null) return;

    const delay = reconnectDelay;

    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket(callbacks);
    }, delay);

    reconnectDelay = Math.min(
        reconnectDelay * 2,
        MAX_RECONNECT_DELAY
    );
}

export function disconnectWebSocket() {
    manuallyStopped = true;

    if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    if (socket) {
        socket.close();
        socket = null;
    }
}

export function isWebSocketConnected() {
    return socket?.readyState === WebSocket.OPEN;
}
