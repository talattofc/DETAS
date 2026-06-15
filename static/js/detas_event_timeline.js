(function () {
    if (window.__DETAS_EVENT_TIMELINE__) return;
    window.__DETAS_EVENT_TIMELINE__ = true;

    const STORAGE_KEY = "detas_event_timeline_v1";
    const MAX_EVENTS = 40;

    let lastQuake = false;
    let lastArmed = null;
    let lastMission = "";
    let lastDetection = 0;
    let lastThermalHot = false;

    function nowText() {
        const d = new Date();
        return d.toLocaleTimeString("tr-TR", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    }

    function getEvents() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        } catch (e) {
            return [];
        }
    }

    function saveEvents(events) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(0, MAX_EVENTS)));
    }

    function addEvent(type, title, detail) {
        const events = getEvents();

        const last = events[0];

        if (last && last.title === title && last.detail === detail) {
            return;
        }

        events.unshift({
            time: nowText(),
            type,
            title,
            detail
        });

        saveEvents(events);
        renderEvents();
    }

    function getValue(data, keys, fallback) {
        for (const key of keys) {
            if (data && data[key] !== undefined && data[key] !== null && data[key] !== "") {
                return data[key];
            }
        }
        return fallback;
    }

    function asBool(value) {
        if (typeof value === "boolean") return value;
        if (typeof value === "number") return value > 0;

        const t = String(value || "").toLowerCase();
        return t === "true" || t === "1" || t === "armed" || t === "aktif" || t === "bağlı" || t === "bagli";
    }

    function asNumber(value, fallback) {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function ensureStyle() {
        if (document.getElementById("detasTimelineStyle")) return;

        const style = document.createElement("style");
        style.id = "detasTimelineStyle";

        style.textContent = `
            .detas-timeline-card {
                margin-top: 16px;
                background: #1f2430;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 16px;
                color: #ffffff;
            }

            .detas-timeline-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
            }

            .detas-timeline-head h3 {
                margin: 0;
                color: #ffffff;
                font-size: 18px;
                font-weight: 900;
            }

            .detas-timeline-head button {
                border: 1px solid rgba(255,255,255,0.12);
                background: #252b38;
                color: #ffffff;
                border-radius: 8px;
                height: 34px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 900;
                cursor: pointer;
            }

            .detas-timeline-list {
                display: flex;
                flex-direction: column;
                gap: 8px;
                max-height: 340px;
                overflow-y: auto;
            }

            .detas-timeline-item {
                display: grid;
                grid-template-columns: 76px 12px 1fr;
                gap: 10px;
                align-items: start;
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 10px;
            }

            .detas-timeline-time {
                color: #94a3b8;
                font-size: 12px;
                font-weight: 900;
                font-variant-numeric: tabular-nums;
                padding-top: 2px;
            }

            .detas-timeline-dot {
                width: 10px;
                height: 10px;
                border-radius: 999px;
                margin-top: 4px;
                background: #64748b;
            }

            .detas-timeline-dot.quake {
                background: #af1763;
            }

            .detas-timeline-dot.arm {
                background: #198754;
            }

            .detas-timeline-dot.warn {
                background: #ffc107;
            }

            .detas-timeline-dot.info {
                background: #00d9ff;
            }

            .detas-timeline-body strong {
                display: block;
                color: #ffffff;
                font-size: 14px;
                font-weight: 900;
                line-height: 1.2;
            }

            .detas-timeline-body span {
                display: block;
                color: #d8dde8;
                font-size: 12px;
                font-weight: 700;
                line-height: 1.35;
                margin-top: 4px;
            }

            .detas-timeline-empty {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 14px;
                color: #94a3b8;
                font-size: 13px;
                font-weight: 800;
            }
        `;

        document.head.appendChild(style);
    }

    function findTargetSection() {
        return document.getElementById("logsSection") ||
               document.getElementById("overviewSection") ||
               document.querySelector(".page.active") ||
               document.querySelector("main") ||
               document.body;
    }

    function ensureCard() {
        let card = document.getElementById("detasTimelineCard");

        if (card) return card;

        const target = findTargetSection();

        card = document.createElement("div");
        card.id = "detasTimelineCard";
        card.className = "detas-timeline-card";

        card.innerHTML = `
            <div class="detas-timeline-head">
                <h3>Görev Olay Geçmişi</h3>
                <button id="detasClearTimeline">Temizle</button>
            </div>

            <div id="detasTimelineList" class="detas-timeline-list"></div>
        `;

        target.prepend(card);

        const clearBtn = document.getElementById("detasClearTimeline");

        if (clearBtn) {
            clearBtn.onclick = function () {
                localStorage.removeItem(STORAGE_KEY);
                renderEvents();
            };
        }

        return card;
    }

    function renderEvents() {
        const list = document.getElementById("detasTimelineList");
        if (!list) return;

        const events = getEvents();

        if (events.length === 0) {
            list.innerHTML = `
                <div class="detas-timeline-empty">
                    Henüz görev olayı yok. Deprem senaryosu tetiklendiğinde olaylar burada görünecek.
                </div>
            `;
            return;
        }

        list.innerHTML = events.map(function (ev) {
            return `
                <div class="detas-timeline-item">
                    <div class="detas-timeline-time">${ev.time}</div>
                    <div class="detas-timeline-dot ${ev.type}"></div>
                    <div class="detas-timeline-body">
                        <strong>${ev.title}</strong>
                        <span>${ev.detail}</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    async function pollData() {
        try {
            const res = await fetch("/data", { cache: "no-store" });
            const data = await res.json();

            const movement = asNumber(getValue(data, ["movement"], 0), 0);
            const threshold = asNumber(getValue(data, ["threshold"], 1.5), 1.5);
            const quake = movement >= threshold;

            const armed = asBool(getValue(data, ["cube_armed", "armed", "is_armed"], false));
            const mission = String(getValue(data, ["mission_status", "auto_mission_status"], "BEKLEMEDE"));
            const detection = asNumber(getValue(data, ["detection_count", "detected_count", "detections_count"], 0), 0);
            const thermalMax = asNumber(getValue(data, ["thermal_max", "thermalMax", "thermal_maximum"], NaN), NaN);
            const thermalHot = Number.isFinite(thermalMax) && thermalMax >= 32;

            if (quake && !lastQuake) {
                addEvent(
                    "quake",
                    "Deprem algılandı",
                    "Sarsıntı değeri " + movement.toFixed(2) + " eşiği geçti. Eşik: " + threshold.toFixed(2)
                );
            }

            if (!quake && lastQuake) {
                addEvent(
                    "info",
                    "Deprem sinyali normale döndü",
                    "Sarsıntı değeri tekrar eşik altına indi."
                );
            }

            if (lastArmed !== null && armed !== lastArmed) {
                if (armed) {
                    addEvent("arm", "ARM oldu", "Orange Cube görev için hazır durumda.");
                } else {
                    addEvent("warn", "DISARM oldu", "Motorlar güvenli duruma geçti.");
                }
            }

            if (mission !== lastMission && lastMission !== "") {
                addEvent("info", "Görev durumu değişti", lastMission + " → " + mission);
            }

            if (detection > lastDetection) {
                addEvent("info", "AI tespiti güncellendi", "Tespit sayısı: " + detection);
            }

            if (thermalHot && !lastThermalHot) {
                addEvent("warn", "Termal sıcak nokta olasılığı", "Termal maksimum: " + thermalMax.toFixed(1) + "°C");
            }

            lastQuake = quake;
            lastArmed = armed;
            lastMission = mission;
            lastDetection = detection;
            lastThermalHot = thermalHot;

        } catch (err) {
            console.log("[DETAS TIMELINE] veri alınamadı:", err);
        }
    }

    function init() {
        ensureStyle();
        ensureCard();
        renderEvents();

        pollData();
        setInterval(pollData, 1000);

        console.log("[DETAS TIMELINE] Görev olay geçmişi aktif.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
