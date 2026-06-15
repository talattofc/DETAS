(function () {
    if (window.__DETAS_MISSION_MAP_OVERLAY__) return;
    window.__DETAS_MISSION_MAP_OVERLAY__ = true;

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
        if (document.getElementById("detasMissionMapStyle")) return;

        const style = document.createElement("style");
        style.id = "detasMissionMapStyle";
        style.textContent = `
            #map {
                position: relative !important;
            }

            .detas-map-overlay {
                position: absolute;
                left: 18px;
                top: 18px;
                z-index: 700;
                width: 310px;
                max-width: calc(100% - 36px);
                background: rgba(18, 23, 34, 0.94);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 14px;
                padding: 14px;
                color: #ffffff;
                backdrop-filter: blur(8px);
                box-shadow: none;
                pointer-events: auto;
            }

            .detas-map-overlay h3 {
                margin: 0 0 10px 0;
                font-size: 17px;
                line-height: 1.2;
                font-weight: 900;
                color: #ffffff;
            }

            .detas-map-status {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 30px;
                padding: 0 12px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 900;
                margin-bottom: 12px;
                background: #252b38;
                color: #d8dde8;
                border: 1px solid rgba(255,255,255,0.10);
            }

            .detas-map-status.active {
                background: #198754;
                color: #ffffff;
                border-color: #198754;
            }

            .detas-map-status.alert {
                background: #af1763;
                color: #ffffff;
                border-color: #af1763;
            }

            .detas-map-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }

            .detas-map-item {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 9px 10px;
            }

            .detas-map-item span {
                display: block;
                font-size: 11px;
                font-weight: 800;
                color: #94a3b8;
                margin-bottom: 5px;
            }

            .detas-map-item strong {
                display: block;
                font-size: 14px;
                font-weight: 900;
                color: #00d9ff;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .detas-map-marker-center {
                position: absolute;
                left: 50%;
                top: 50%;
                z-index: 690;
                width: 22px;
                height: 22px;
                transform: translate(-50%, -50%);
                border-radius: 50%;
                background: #af1763;
                border: 3px solid #ffffff;
                box-shadow: 0 0 0 8px rgba(175, 23, 99, 0.18);
                pointer-events: none;
            }

            .detas-map-marker-label {
                position: absolute;
                left: 50%;
                top: calc(50% + 22px);
                transform: translateX(-50%);
                z-index: 690;
                background: rgba(18,23,34,0.92);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 900;
                pointer-events: none;
                white-space: nowrap;
            }
        `;

        document.head.appendChild(style);
    }

    function ensureOverlay() {
        const map = document.getElementById("map");

        if (!map) {
            return null;
        }

        let overlay = document.getElementById("detasMapOverlay");

        if (!overlay) {
            overlay = document.createElement("div");
            overlay.id = "detasMapOverlay";
            overlay.className = "detas-map-overlay";

            overlay.innerHTML = `
                <h3>Görev Haritası</h3>
                <div id="detasMapStatus" class="detas-map-status">BEKLEMEDE</div>

                <div class="detas-map-grid">
                    <div class="detas-map-item">
                        <span>Görev durumu</span>
                        <strong id="detasMapMission">-</strong>
                    </div>

                    <div class="detas-map-item">
                        <span>ARM</span>
                        <strong id="detasMapArm">-</strong>
                    </div>

                    <div class="detas-map-item">
                        <span>Sarsıntı</span>
                        <strong id="detasMapMovement">-</strong>
                    </div>

                    <div class="detas-map-item">
                        <span>Eşik</span>
                        <strong id="detasMapThreshold">-</strong>
                    </div>

                    <div class="detas-map-item">
                        <span>Enlem</span>
                        <strong id="detasMapLat">GPS bekleniyor</strong>
                    </div>

                    <div class="detas-map-item">
                        <span>Boylam</span>
                        <strong id="detasMapLng">GPS bekleniyor</strong>
                    </div>
                </div>
            `;

            map.appendChild(overlay);
        }

        if (!document.getElementById("detasMapMarkerCenter")) {
            const marker = document.createElement("div");
            marker.id = "detasMapMarkerCenter";
            marker.className = "detas-map-marker-center";
            map.appendChild(marker);
        }

        if (!document.getElementById("detasMapMarkerLabel")) {
            const label = document.createElement("div");
            label.id = "detasMapMarkerLabel";
            label.className = "detas-map-marker-label";
            label.textContent = "Görev noktası";
            map.appendChild(label);
        }

        return overlay;
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    async function updateOverlay() {
        const overlay = ensureOverlay();
        if (!overlay) return;

        try {
            const res = await fetch("/data", { cache: "no-store" });
            const data = await res.json();

            const mission = getValue(data, ["mission_status", "auto_mission_status"], "BEKLEMEDE");
            const armed = asBool(getValue(data, ["cube_armed", "armed", "is_armed"], false));
            const movement = asNumber(getValue(data, ["movement", "max_movement"], 0), 0);
            const threshold = asNumber(getValue(data, ["threshold"], 1.5), 1.5);

            const lat = getValue(data, ["cube_lat", "cube_latitude", "gps_lat", "lat", "latitude"], null);
            const lng = getValue(data, ["cube_lng", "cube_lon", "cube_longitude", "gps_lng", "gps_lon", "lng", "lon", "longitude"], null);

            const status = document.getElementById("detasMapStatus");

            let statusText = "BEKLEMEDE";
            let statusClass = "detas-map-status";

            if (String(mission).toUpperCase().includes("GÖREV")) {
                statusText = "GÖREVDE";
                statusClass += " active";
            }

            if (movement >= threshold) {
                statusText = "DEPREM ALGILANDI";
                statusClass += " alert";
            }

            if (status) {
                status.textContent = statusText;
                status.className = statusClass;
            }

            setText("detasMapMission", mission);
            setText("detasMapArm", armed ? "ARMED" : "DISARMED");
            setText("detasMapMovement", movement.toFixed(2));
            setText("detasMapThreshold", threshold.toFixed(2));

            if (lat !== null && lng !== null) {
                setText("detasMapLat", Number(lat).toFixed(6));
                setText("detasMapLng", Number(lng).toFixed(6));
            } else {
                setText("detasMapLat", "GPS bekleniyor");
                setText("detasMapLng", "GPS bekleniyor");
            }

        } catch (err) {
            console.log("[DETAS MAP OVERLAY] veri alınamadı:", err);
        }
    }

    function init() {
        ensureStyle();
        ensureOverlay();
        updateOverlay();
        setInterval(updateOverlay, 1000);

        console.log("[DETAS MAP OVERLAY] Görev haritası bilgi kartı aktif.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
