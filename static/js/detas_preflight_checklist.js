(function () {
    if (window.__DETAS_PREFLIGHT_CHECKLIST__) return;
    window.__DETAS_PREFLIGHT_CHECKLIST__ = true;

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

        return (
            t === "true" ||
            t === "1" ||
            t === "yes" ||
            t === "evet" ||
            t === "aktif" ||
            t === "bağlı" ||
            t === "bagli" ||
            t === "armed"
        );
    }

    function asNumber(value, fallback) {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function ensureStyle() {
        if (document.getElementById("detasPreflightStyle")) return;

        const style = document.createElement("style");
        style.id = "detasPreflightStyle";

        style.textContent = `
            .detas-preflight-card {
                margin-top: 16px;
                background: #1f2430;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 16px;
                color: #ffffff;
            }

            .detas-preflight-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
            }

            .detas-preflight-head h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 900;
                color: #ffffff;
            }

            .detas-preflight-badge {
                min-height: 30px;
                padding: 0 12px;
                border-radius: 999px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: 900;
                background: #252b38;
                color: #d8dde8;
                border: 1px solid rgba(255,255,255,0.10);
            }

            .detas-preflight-badge.ready {
                background: #198754;
                color: #ffffff;
                border-color: #198754;
            }

            .detas-preflight-badge.warn {
                background: #af1763;
                color: #ffffff;
                border-color: #af1763;
            }

            .detas-preflight-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
            }

            .detas-preflight-item {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px;
                min-height: 82px;
            }

            .detas-preflight-item span {
                display: block;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 800;
                margin-bottom: 8px;
            }

            .detas-preflight-item strong {
                display: block;
                color: #ffffff;
                font-size: 16px;
                font-weight: 900;
                font-variant-numeric: tabular-nums;
            }

            .detas-preflight-state {
                margin-top: 8px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 24px;
                padding: 0 9px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 900;
                background: #252b38;
                color: #d8dde8;
            }

            .detas-preflight-state.ok {
                background: #198754;
                color: #ffffff;
            }

            .detas-preflight-state.warn {
                background: #af1763;
                color: #ffffff;
            }

            .detas-preflight-note {
                display: none !important;
            }

            @media (max-width: 1100px) {
                .detas-preflight-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }

            @media (max-width: 560px) {
                .detas-preflight-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function findTarget() {
        return document.getElementById("overviewSection") ||
               document.querySelector(".page.active") ||
               document.querySelector("main") ||
               document.body;
    }

    function ensureCard() {
        let card = document.getElementById("detasPreflightCard");

        if (card) return card;

        const target = findTarget();

        card = document.createElement("div");
        card.id = "detasPreflightCard";
        card.className = "detas-preflight-card";

        card.innerHTML = `
            <div class="detas-preflight-head">
                <h3>Uçuşa Hazırlık Kontrolü</h3>
                <div id="detasPreflightBadge" class="detas-preflight-badge">KONTROL EDİLİYOR</div>
            </div>

            <div class="detas-preflight-grid">
                <div class="detas-preflight-item">
                    <span>Cube bağlantısı</span>
                    <strong id="pfCube">-</strong>
                    <div id="pfCubeState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>ARM durumu</span>
                    <strong id="pfArm">-</strong>
                    <div id="pfArmState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>Uçuş modu</span>
                    <strong id="pfMode">-</strong>
                    <div id="pfModeState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>İstasyon telemetrisi</span>
                    <strong id="pfTelemetry">-</strong>
                    <div id="pfTelemetryState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>Termal sensör</span>
                    <strong id="pfThermal">-</strong>
                    <div id="pfThermalState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>Batarya</span>
                    <strong id="pfBattery">-</strong>
                    <div id="pfBatteryState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>GPS</span>
                    <strong id="pfGps">-</strong>
                    <div id="pfGpsState" class="detas-preflight-state">-</div>
                </div>

                <div class="detas-preflight-item">
                    <span>Görev durumu</span>
                    <strong id="pfMission">-</strong>
                    <div id="pfMissionState" class="detas-preflight-state">-</div>
                </div>
            </div>

            <div id="pfNote" class="detas-preflight-note">
                Sistem durumu okunuyor.
            </div>
        `;

        const pageTitle = target.querySelector(".page-title");
        if (pageTitle && pageTitle.nextSibling) {
            pageTitle.parentNode.insertBefore(card, pageTitle.nextSibling);
        } else {
            target.prepend(card);
        }

        return card;
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function setState(id, ok, okText, warnText) {
        const el = document.getElementById(id);
        if (!el) return;

        el.className = ok ? "detas-preflight-state ok" : "detas-preflight-state warn";
        el.textContent = ok ? okText : warnText;
    }

    async function updateCard() {
        ensureCard();

        try {
            const res = await fetch("/data", { cache: "no-store" });
            const data = await res.json();

            const cubeConnected = asBool(getValue(data, ["cube_connected", "mavlink_connected"], false));
            const armed = asBool(getValue(data, ["cube_armed", "armed", "is_armed"], false));
            const mode = String(getValue(data, ["cube_mode", "mode"], "-"));
            const telemetryConnected = asBool(getValue(data, ["telemetry_connected", "station_connected"], false));
            const thermalConnected = asBool(getValue(data, ["thermal_connected"], false));
            const batteryVoltage = asNumber(getValue(data, ["cube_battery_voltage", "battery_voltage", "voltage"], NaN), NaN);
            const gpsFix = getValue(data, ["cube_gps_fix", "gps_fix"], "-");
            const satellites = getValue(data, ["cube_satellites", "satellites"], "-");
            const mission = String(getValue(data, ["mission_status", "auto_mission_status"], "BEKLEMEDE"));

            const modeReady = (
                mode.toUpperCase().includes("STABILIZE") ||
                mode.toUpperCase().includes("ALT_HOLD") ||
                mode.toUpperCase().includes("LOITER")
            );

            const batteryKnown = Number.isFinite(batteryVoltage);
            const batteryOk = !batteryKnown || batteryVoltage >= 13.5;

            const gpsText = gpsFix + " / " + satellites + " uydu";
            const gpsOk = String(gpsFix).includes("3") || Number(satellites) >= 6;

            setText("pfCube", cubeConnected ? "Bağlı" : "Yok");
            setState("pfCubeState", cubeConnected, "Hazır", "Kontrol et");

            setText("pfArm", armed ? "ARMED" : "DISARMED");
            setState("pfArmState", true, armed ? "Görev aktif" : "Güvenli", "Kontrol et");

            setText("pfMode", mode);
            setState("pfModeState", modeReady, "Uygun", "Mod kontrol");

            setText("pfTelemetry", telemetryConnected ? "Bağlı" : "Yok");
            setState("pfTelemetryState", telemetryConnected, "Veri geliyor", "İstasyon yok");

            setText("pfThermal", thermalConnected ? "Bağlı" : "Yok");
            setState("pfThermalState", thermalConnected, "Hazır", "Sensör yok");

            setText("pfBattery", batteryKnown ? batteryVoltage.toFixed(2) + " V" : "-");
            setState("pfBatteryState", batteryOk, batteryKnown ? "Uygun" : "Bilinmiyor", "Düşük");

            setText("pfGps", gpsText);
            setState("pfGpsState", gpsOk, "Fix var", "GPS bekleniyor");

            setText("pfMission", mission);
            setState("pfMissionState", true, mission, "Kontrol et");

            const criticalReady = cubeConnected && telemetryConnected && modeReady && batteryOk;
            const badge = document.getElementById("detasPreflightBadge");

            if (badge) {
                badge.className = criticalReady ? "detas-preflight-badge ready" : "detas-preflight-badge warn";
                badge.textContent = criticalReady ? "SİSTEM HAZIR" : "KONTROL GEREKİYOR";
            }

            let note = "Kritik sistemler izleniyor. Pervaneler takılıysa tüm kontroller tamamlanmadan ARM denenmemeli.";

            if (criticalReady && !armed) {
                note = "Temel sistemler hazır. Deprem senaryosu veya manuel ARM için sistem beklemede.";
            }

            if (criticalReady && armed) {
                note = "Sistem ARM durumda. Görev akışı, kamera, termal ve telemetri verileri canlı izleniyor.";
            }

            if (!cubeConnected) {
                note = "Cube bağlantısı yok. MAVLink portu, güç ve bağlantı kontrol edilmeli.";
            }

            setText("pfNote", note);

        } catch (err) {
            console.log("[DETAS PREFLIGHT] veri alınamadı:", err);
        }
    }

    function init() {
        ensureStyle();
        ensureCard();

        updateCard();
        setInterval(updateCard, 1000);

        console.log("[DETAS PREFLIGHT] Uçuşa hazırlık kontrol kartı aktif.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
