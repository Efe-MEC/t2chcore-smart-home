import { sendAIMessage, getAIHealth } from "./api.js";
import { showNotice } from "./ui.js";

let initialized = false;
let conversationHistory = [];
let isSending = false;

export async function initializeAssistant() {
    if (initialized) return;

    const form = document.querySelector("#ai-chat-form");
    const input = document.querySelector("#ai-message-input");
    const messages = document.querySelector("#chat-messages");
    const sendButton = document.querySelector("#ai-send-button");

    if (!form || !input || !messages) {
        console.error("Asistan başlatılamadı: HTML elemanları bulunamadı.", {
            form: !!form,
            input: !!input,
            messages: !!messages
        });
        return;
    }

    initialized = true;

    async function updateAIStatus() {
        try {
            const result = await getAIHealth();

            if (result?.status !== "ok") {
                console.warn("Yerel yapay zekâ servisi hazır görünmüyor.");
            }
        } catch (error) {
            console.error("AI sağlık kontrolü başarısız:", error);
        }
    }

    function appendMessage(role, text, isError = false) {
        const message = document.createElement("div");
        message.className = `chat-message ${role}`;

        if (isError) {
            message.classList.add("is-error");
        }

        const label = document.createElement("div");
        label.className = "chat-message-label";
        label.textContent = role === "user" ? "Sen" : "UNO Q Asistan";

        const content = document.createElement("div");
        content.className = "chat-message-content";
        content.textContent = text;

        message.append(label, content);
        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;

        return message;
    }

    function setSending(sending) {
        isSending = sending;
        input.disabled = sending;

        if (sendButton) {
            sendButton.disabled = sending;
            sendButton.setAttribute("aria-busy", String(sending));
            sendButton.firstChild.textContent = sending
                ? "Yanıt bekleniyor… "
                : "Gönder ";
        }
    }

    async function handleSubmit(event) {
        event.preventDefault();

        if (isSending) return;

        const message = input.value.trim();
        if (!message) {
            input.focus();
            return;
        }

        appendMessage("user", message);
        input.value = "";
        setSending(true);

        const pendingMessage = appendMessage("assistant", "Düşünüyorum…");

        try {
            const response = await sendAIMessage({
                message,
                history: conversationHistory
            });

            const answer =
                typeof response?.answer === "string" && response.answer.trim()
                    ? response.answer.trim()
                    : "Asistandan boş bir yanıt geldi.";

            pendingMessage.querySelector(".chat-message-content").textContent =
                answer;

            conversationHistory.push(
                { role: "user", content: message },
                { role: "assistant", content: answer }
            );

            if (conversationHistory.length > 20) {
                conversationHistory = conversationHistory.slice(-20);
            }
        } catch (error) {
            console.error("AI mesaj isteği başarısız:", error);

            pendingMessage.classList.add("is-error");
            pendingMessage.querySelector(".chat-message-content").textContent =
                "Mesaj gönderilemedi. API ve yerel model bağlantısını kontrol et.";

            showNotice("Yapay zekâ yanıt veremedi.", "error");
        } finally {
            setSending(false);
            input.focus();
        }
    }

    form.addEventListener("submit", handleSubmit);

    await updateAIStatus();
}
