(function () {
    if (window.__DETAS_CAMERA_THERMAL_MISSION__) return;
    window.__DETAS_CAMERA_THERMAL_MISSION__ = true;

    function getValue(data, keys, fallback) {
        for (const key of keys) {
            if (data && data[key] !== undefined && data[key] !== null && data[key] !== "") {
                return data[key];
            }
        }
        return fallback;
    }

    function asNumber(value, fallback) {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function asBool(value) {
        if (typeof value === "boolean") return value;
        if (typeof value === "number") return value > 0;

        const t = String(value || "").toLowerCase();
        return t === "true" || t === "1" || t === "armed" || t === "aktif" || t === "bağlı" || t === "bagli";
    }

    function ensureStyle() {
        if (document.getElementById("detasCameraThermalMissionStyle")) return;

        const style = document.createElement("style");
        style.id = "detasCameraThermalMissionStyle";

        style.textContent = `
            .detas-mission-analysis-card {
                margin-top: 16px;
                background: #1f2430;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 16px;
                color: #ffffff;
            }

            .detas-mission-analysis-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
            }

            .detas-mission-analysis-head h3 {
                margin: 0;
                color: #ffffff;
                font-size: 18px;
                font-weight: 900;
            }

            .detas-analysis-badge {
                min-height: 30px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0 12px;
                border-radius: 999px;
                background: #252b38;
                border: 1px solid rgba(255,255,255,0.10);
                color: #d8dde8;
                font-size: 12px;
                font-weight: 900;
            }

            .detas-analysis-badge.active {
                background: #198754;
                border-color: #198754;
                color: #ffffff;
            }

            .detas-analysis-badge.alert {
                background: #af1763;
                border-color: #af1763;
                color: #ffffff;
            }

            .detas-analysis-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
            }

            .detas-analysis-item {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px;
                min-height: 74px;
            }

            .detas-analysis-item span {
                display: block;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 800;
                margin-bottom: 8px;
            }

            .detas-analysis-item strong {
                display: block;
                color: #00d9ff;
                font-size: 20px;
                font-weight: 900;
                font-variant-numeric: tabular-nums;
            }

            .detas-analysis-note {
                margin-top: 12px;
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px;
                color: #d8dde8;
                font-size: 13px;
                font-weight: 700;
                line-height: 1.4;
            }

            @media (max-width: 900px) {
                .detas-analysis-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }

            @media (max-width: 520px) {
                .detas-analysis-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function ensureCard() {
        const cameraSection = document.getElementById("cameraSection");

        if (!cameraSection) return null;

        let card = document.getElementById("detasMissionAnalysisCard");

        if (!card) {
            card = document.createElement("div");
            card.id = "detasMissionAnalysisCard";
            card.className = "detas-mission-analysis-card";

            card.innerHTML = `
                <div class="detas-mission-analysis-head">
                    <h3>Görev Analiz Özeti</h3>
                    <div id="detasAnalysisBadge" class="detas-analysis-badge">BEKLEMEDE</div>
                </div>

                <div class="detas-analysis-grid">
                    <div class="detas-analysis-item">
                        <span>AI tespit sayısı</span>
                        <strong id="detasAnalysisDetection">0</strong>
                    </div>

                    <div class="detas-analysis-item">
                        <span>Termal maksimum</span>
                        <strong id="detasAnalysisThermalMax">-</strong>
                    </div>

                    <div class="detas-analysis-item">
                        <span>Sıcak nokta</span>
                        <strong id="detasAnalysisHotspot">Yok</strong>
                    </div>

                    <div class="detas-analysis-item">
                        <span>ARM durumu</span>
                        <strong id="detasAnalysisArm">DISARMED</strong>
                    </div>
                </div>

                <div id="detasAnalysisNote" class="detas-analysis-note">
                    Sistem beklemede. Deprem algılandığında kamera ve termal veriler görev analizi için izlenecek.
                </div>
            `;

            cameraSection.appendChild(card);
        }

        return card;
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    async function updateCard() {
        const card = ensureCard();
        if (!card) return;

        try {
            const res = await fetch("/data", { cache: "no-store" });
            const data = await res.json();

            const mission = String(getValue(data, ["mission_status", "auto_mission_status"], "BEKLEMEDE"));
            const armed = asBool(getValue(data, ["cube_armed", "armed", "is_armed"], false));

            const detectionCount = asNumber(
                getValue(data, ["detection_count", "detected_count", "detections_count"], 0),
                0
            );

            const thermalMax = asNumber(
                getValue(data, ["thermal_max", "thermalMax", "thermal_maximum"], NaN),
                NaN
            );

            const hotspot = getValue(data, ["hotspot", "thermal_hotspot"], null);

            const movement = asNumber(getValue(data, ["movement"], 0), 0);
            const threshold = asNumber(getValue(data, ["threshold"], 1.5), 1.5);

            const badge = document.getElementById("detasAnalysisBadge");
            let badgeText = "BEKLEMEDE";
            let badgeClass = "detas-analysis-badge";

            if (movement >= threshold) {
                badgeText = "DEPREM ALGILANDI";
                badgeClass += " alert";
            } else if (mission.toUpperCase().includes("GÖREV") || armed) {
                badgeText = "GÖREVDE";
                badgeClass += " active";
            }

            if (badge) {
                badge.textContent = badgeText;
                badge.className = badgeClass;
            }

            setText("detasAnalysisDetection", detectionCount);
            setText("detasAnalysisThermalMax", Number.isFinite(thermalMax) ? thermalMax.toFixed(1) + "°C" : "-");
            setText("detasAnalysisArm", armed ? "ARMED" : "DISARMED");

            if (hotspot && typeof hotspot === "object") {
                setText("detasAnalysisHotspot", "Var");
            } else if (Number.isFinite(thermalMax) && thermalMax >= 32) {
                setText("detasAnalysisHotspot", "Olası");
            } else {
                setText("detasAnalysisHotspot", "Yok");
            }

            let note = "Sistem beklemede. Deprem algılandığında kamera ve termal veriler görev analizi için izlenecek.";

            if (movement >= threshold) {
                note = "Deprem algılandı. Sistem ARM durumuna geçtiğinde kamera ve termal veriler aktif görev analizi için takip edilir.";
            }

            if (armed) {
                note = "Görev aktif. Kamera görüntüsü, AI tespitleri ve termal maksimum değerleri canlı olarak izleniyor.";
            }

            if (detectionCount > 0) {
                note = "AI HAT görüntü analizinde nesne tespiti var. Termal veri ile birlikte operatör değerlendirmesi yapılmalı.";
            }

            setText("detasAnalysisNote", note);

        } catch (err) {
            console.log("[DETAS ANALYSIS] veri alınamadı:", err);
        }
    }

    function init() {
        ensureStyle();
        ensureCard();
        updateCard();
        setInterval(updateCard, 1000);

        console.log("[DETAS ANALYSIS] Kamera + termal görev analiz kartı aktif.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
