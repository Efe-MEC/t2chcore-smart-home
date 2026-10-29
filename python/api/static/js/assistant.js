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
    const micButton = document.querySelector("#ai-mic-button");
    const voiceToggle = document.querySelector("#ai-voice-toggle");
    const voiceStatus = document.querySelector("#ai-voice-status");

    if (!form || !input || !messages) {
        console.error("Asistan başlatılamadı: HTML elemanları bulunamadı.");
        return;
    }

    initialized = true;

    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    let recognition = null;
    let isListening = false;
    let voiceEnabled = true;

    function setVoiceStatus(message, isError = false) {
        if (!voiceStatus) return;

        voiceStatus.textContent = message;
        voiceStatus.hidden = !message;
        voiceStatus.classList.toggle("is-error", isError);
    }

    function updateMicButton() {
        if (!micButton) return;

        micButton.textContent = isListening
            ? "⏹ Dinlemeyi durdur"
            : "🎙 Konuş";

        micButton.setAttribute("aria-pressed", String(isListening));
        micButton.classList.toggle("is-listening", isListening);
    }

    function updateVoiceButton() {
        if (!voiceToggle) return;

        voiceToggle.textContent = voiceEnabled
            ? "🔊 Sesli yanıt açık"
            : "🔇 Sesli yanıt kapalı";

        voiceToggle.setAttribute("aria-pressed", String(voiceEnabled));
    }

    function speakAnswer(text) {
        if (!voiceEnabled || !("speechSynthesis" in window)) return;

        // Önceki seslendirme sürüyorsa yeni yanıtla değiştir.
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "tr-TR";
        utterance.rate = 1;
        utterance.pitch = 1;

        window.speechSynthesis.speak(utterance);
    }

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = "tr-TR";
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            isListening = true;
            updateMicButton();
            setVoiceStatus("Dinliyorum. Türkçe komutunu söyle.");
        };

        recognition.onresult = (event) => {
            const transcript = event.results?.[0]?.[0]?.transcript?.trim();

            if (!transcript) {
                setVoiceStatus("Konuşma algılanamadı. Tekrar deneyebilirsin.", true);
                return;
            }

            input.value = transcript;
            setVoiceStatus(`Algılanan komut: ${transcript}`);

            // Tanınan metni mevcut sohbet akışına gönder.
            form.requestSubmit();
        };

        recognition.onerror = (event) => {
            console.error("Ses tanıma hatası:", event.error);

            const messagesByError = {
                "not-allowed": "Mikrofon izni verilmedi. Tarayıcı izinlerini kontrol et.",
                "service-not-allowed": "Tarayıcı ses tanıma servisine izin vermiyor.",
                "no-speech": "Ses algılanmadı. Mikrofonuna konuşup tekrar dene.",
                "audio-capture": "Mikrofon bulunamadı veya kullanılamıyor.",
                "network": "Ses tanıma servisi için ağ bağlantısını kontrol et.",
                "language-not-supported": "Tarayıcı Türkçe ses tanımayı desteklemiyor."
            };

            setVoiceStatus(
                messagesByError[event.error] ||
                    `Ses tanıma hatası: ${event.error}`,
                true
            );
        };

        recognition.onend = () => {
            isListening = false;
            updateMicButton();
        };
    } else if (micButton) {
        micButton.disabled = true;
        micButton.title = "Bu tarayıcı Web Speech API ses tanımayı desteklemiyor.";
    }

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

        if (isError) message.classList.add("is-error");

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

            speakAnswer(answer);
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

    if (micButton && recognition) {
        micButton.addEventListener("click", () => {
            if (isSending) return;

            if (isListening) {
                recognition.stop();
                return;
            }

            if (!window.isSecureContext) {
                setVoiceStatus(
                    "Tarayıcı mikrofon erişimi için güvenli bağlantı isteyebilir. HTTPS veya localhost üzerinden deneyin.",
                    true
                );
            }

            try {
                recognition.start();
            } catch (error) {
                console.error("Mikrofon başlatılamadı:", error);
                setVoiceStatus(
                    "Mikrofon başlatılamadı. Tarayıcı iznini ve bağlantıyı kontrol et.",
                    true
                );
            }
        });
    }

    if (voiceToggle) {
        voiceToggle.addEventListener("click", () => {
            voiceEnabled = !voiceEnabled;

            if (!voiceEnabled && "speechSynthesis" in window) {
                window.speechSynthesis.cancel();
            }

            updateVoiceButton();
            setVoiceStatus(
                voiceEnabled ? "Sesli yanıt etkin." : "Sesli yanıt kapatıldı."
            );
        });
    }

    updateMicButton();
    updateVoiceButton();

    if (!("speechSynthesis" in window)) {
        if (voiceToggle) voiceToggle.disabled = true;
        setVoiceStatus("Bu tarayıcı sesli yanıt özelliğini desteklemiyor.", true);
    }

    await updateAIStatus();
}
