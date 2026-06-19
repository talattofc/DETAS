(() => {
    "use strict";

    const POLL_MS = 700;
    const HISTORY_LIMIT = 60;
    const MAP_CENTER = [36.8969, 30.7133];
    const MAP_ZOOM = 14;
    const CAMERA_ZOOM_LEVELS = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10];

    const chart = {
        labels: [],
        movement: [],
        threshold: [],
    };

    let map = null;
    let droneMarker = null;
    let droneTimer = null;
    let selectedDetectionEventId = null;
    let detectionEventsRenderKey = "";
    let detectionEventMarkers = {};
    let cameraZoomIndex = 0;
    let lastValidCubeMode = "BILINMIYOR";
    let sliderTimer = null;
    let lastServoSent = null;
    let feedbackClasses = [];

    const $ = (id) => document.getElementById(id);
    const number = (value, fallback = 0) => {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    };

    function setText(id, value) {
        const el = $(id);
        if (el) el.textContent = value;
    }

    function setClass(id, className) {
        const el = $(id);
        if (el) el.className = className;
    }

    function toggleClass(id, className, enabled) {
        const el = $(id);
        if (el) el.classList.toggle(className, Boolean(enabled));
    }

    function postJson(url, payload = undefined) {
        const options = { method: "POST" };
        if (payload !== undefined) {
            options.headers = { "Content-Type": "application/json" };
            options.body = JSON.stringify(payload);
        }

        return fetch(url, options)
            .then((response) => response.json().catch(() => ({ ok: response.ok })));
    }

    function getJson(url) {
        return fetch(url, { cache: "no-store" })
            .then((response) => response.json());
    }

    function setupClock() {
        const render = () => {
            const now = new Date();
            setText("dateBox", now.toLocaleString("tr-TR", {
                day: "2-digit",
                month: "long",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            }));
        };

        render();
        setInterval(render, 30000);
    }

    function switchPage(targetId) {
        document.querySelectorAll(".page").forEach((page) => {
            page.classList.toggle("active", page.id === targetId);
        });

        document.querySelectorAll(".side-link").forEach((button) => {
            button.classList.toggle("active", button.dataset.target === targetId);
        });

        setTimeout(() => {
            if (map) map.invalidateSize();
            drawChart();
            window.dispatchEvent(new Event("resize"));
        }, 180);
    }

    function setupNavigation() {
        document.querySelectorAll(".side-link").forEach((button) => {
            button.addEventListener("click", () => switchPage(button.dataset.target));
        });
    }

    function metersToLatLng(center, eastMeters, northMeters) {
        const lat = center[0] + (northMeters / 111320);
        const lng = center[1] + (eastMeters / (111320 * Math.cos(center[0] * Math.PI / 180)));
        return [lat, lng];
    }

    function addRiskZone(center, radiusMeters, color, label, className) {
        const group = L.layerGroup().addTo(map);

        L.circle(center, {
            radius: radiusMeters,
            color,
            fillColor: color,
            fillOpacity: 0.18,
            weight: 2,
        }).addTo(group).bindTooltip(label, {
            permanent: true,
            direction: "center",
            className: `map-label ${className}`,
        });

        const slope = 0.55;
        const step = 35;

        for (let b = -radiusMeters; b <= radiusMeters; b += step) {
            const a = 1 + slope * slope;
            const bb = 2 * slope * b;
            const c = b * b - radiusMeters * radiusMeters;
            const disc = bb * bb - 4 * a * c;
            if (disc < 0) continue;

            const x1 = (-bb - Math.sqrt(disc)) / (2 * a);
            const x2 = (-bb + Math.sqrt(disc)) / (2 * a);
            const y1 = slope * x1 + b;
            const y2 = slope * x2 + b;

            L.polyline([
                metersToLatLng(center, x1, y1),
                metersToLatLng(center, x2, y2),
            ], {
                color,
                weight: 1.4,
                opacity: 0.7,
            }).addTo(group);
        }
    }

    function startDroneAnimation(routeCoords) {
        if (droneTimer) clearInterval(droneTimer);

        const icon = L.divIcon({
            className: "",
            html: "<div class=\"drone-marker\">UAV</div>",
            iconSize: [42, 26],
            iconAnchor: [21, 13],
        });

        droneMarker = L.marker(routeCoords[0], { icon })
            .addTo(map)
            .bindPopup("IHA Konumu");

        let segment = 0;
        let t = 0;

        droneTimer = setInterval(() => {
            if (!droneMarker || !map) return;

            const start = routeCoords[segment];
            const end = routeCoords[(segment + 1) % routeCoords.length];
            droneMarker.setLatLng([
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t,
            ]);

            t += 0.035;
            if (t >= 1) {
                t = 0;
                segment = (segment + 1) % routeCoords.length;
            }
        }, 120);
    }

    function initMap() {
        const mapEl = $("map");
        if (!mapEl || typeof L === "undefined") return;

        if (map) map.remove();

        const routeCoords = [
            [36.8969, 30.7133],
            [36.8955, 30.7070],
            [36.8910, 30.7015],
            [36.8875, 30.7065],
            [36.8898, 30.7165],
            [36.9005, 30.7190],
        ];

        const dangerCenter = [36.8928, 30.7085];
        const mediumCenter = [36.8898, 30.7165];
        const safeCenter = [36.9005, 30.7190];

        map = L.map("map", { zoomControl: true }).setView(MAP_CENTER, MAP_ZOOM);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "OpenStreetMap",
        }).addTo(map);

        const stationIcon = L.divIcon({
            className: "",
            html: "<div class=\"station-marker\"></div>",
            iconSize: [20, 20],
            iconAnchor: [10, 10],
        });

        L.marker(MAP_CENTER, { icon: stationIcon })
            .addTo(map)
            .bindPopup("<b>ADTİ İstasyonu</b><br>Aktif");

        L.polyline(routeCoords, {
            color: "#0DCAF0",
            weight: 5,
            opacity: 0.95,
            dashArray: "8,6",
        }).addTo(map).bindTooltip("IHA Rotasi", {
            permanent: true,
            direction: "center",
            className: "map-label route-label",
        });

        addRiskZone(dangerCenter, 155, "#AB2E3C", "Riskli Bolge", "danger-label");
        addRiskZone(mediumCenter, 170, "#FFC107", "Orta Risk", "medium-label");
        addRiskZone(safeCenter, 185, "#198754", "Guvenli Alan", "safe-label");
        startDroneAnimation(routeCoords);

        map.fitBounds(L.latLngBounds([
            MAP_CENTER,
            dangerCenter,
            mediumCenter,
            safeCenter,
            ...routeCoords,
        ]).pad(0.25));

        setTimeout(() => map.invalidateSize(), 400);
    }

    function setCamera(cameraId) {
        postJson(`/set_camera/${cameraId}`)
            .then((data) => {
                if (!data.ok) {
                    console.error("Kamera degistirilemedi:", data.error);
                    return;
                }

                ["cam0Btn", "cam1Btn"].forEach((id) => $(id)?.classList.remove("active"));
                $(`cam${cameraId}Btn`)?.classList.add("active");

                const feed = $("cameraFeed");
                if (feed) feed.src = `/video?t=${Date.now()}`;
            })
            .catch((err) => console.error("Kamera degistirme hatasi:", err));
    }

    function updateStats(data) {
        const deprem = number(data.deprem);
        const movement = number(data.movement);
        const threshold = number(data.threshold);
        const maxMovement = number(data.max_movement);
        const mute = number(data.mute);
        const thermalMax = number(data.thermal_max);
        const thermalMin = number(data.thermal_min);
        const hotspot = number(data.hotspot);

        setText("movementValue", movement.toFixed(2));
        setText("thresholdValue", threshold.toFixed(2));
        setText("maxMovementValue", maxMovement.toFixed(2));
        setText("muteValue", mute);
        setText("thermalMaxCard", `${thermalMax.toFixed(1)}°C`);
        setText("thermalMax", `${thermalMax.toFixed(1)}°C`);
        setText("thermalMin", `${thermalMin.toFixed(1)}°C`);
        setText("hotspotText", hotspot ? "Sicak nokta algilandi" : "Sicak nokta yok");

        if (deprem === 1) {
            setText("eqStatusText", "ALARM");
            setText("eqStatusSmall", "Deprem / sarsinti algilandi");
            setText("systemStatus", "Alarm");
        } else {
            setText("eqStatusText", "NORMAL");
            setText("eqStatusSmall", "Sarsinti yok");
            setText("systemStatus", "Aktif");
        }

        toggleClass("eqCard", "alarm-card", deprem === 1);

        const thermalBadge = $("thermalBadge");
        if (thermalBadge) {
            thermalBadge.textContent = hotspot ? "SICAK NOKTA" : (data.thermal_connected ? "NORMAL" : "BAGLANTI YOK");
            thermalBadge.className = `badge ${hotspot ? "danger" : data.thermal_connected ? "live" : "offline"}`;
        }

        setText("thermalHotspot", hotspot ? "VAR" : "YOK");
        const thermalHotspot = $("thermalHotspot");
        if (thermalHotspot) thermalHotspot.className = `operation-summary-value ${hotspot ? "bad" : "warn"}`;
    }

    function updateChart(data) {
        chart.labels.push(new Date().toLocaleTimeString("tr-TR"));
        chart.movement.push(number(data.movement));
        chart.threshold.push(number(data.threshold));

        while (chart.labels.length > HISTORY_LIMIT) {
            chart.labels.shift();
            chart.movement.shift();
            chart.threshold.shift();
        }

        drawChart();
    }

    function drawChart() {
        const canvas = $("movementChart");
        if (!canvas) return;

        const parent = canvas.parentElement;
        const width = Math.max(parent?.clientWidth || 500, 260);
        const height = Math.max(parent?.clientHeight || 300, 220);

        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = "#151923";
        ctx.fillRect(0, 0, width, height);

        const left = 44;
        const right = 18;
        const top = 20;
        const bottom = 36;
        const graphW = width - left - right;
        const graphH = height - top - bottom;
        const values = chart.movement.concat(chart.threshold);
        const maxVal = Math.max(1.5, Math.ceil(Math.max(...values, 1.5) * 1.3 * 10) / 10);

        ctx.strokeStyle = "rgba(255,255,255,0.08)";
        ctx.lineWidth = 1;
        ctx.font = "12px Arial";
        ctx.fillStyle = "#8B94A8";

        for (let i = 0; i <= 5; i += 1) {
            const y = top + (graphH / 5) * i;
            const value = maxVal - (maxVal / 5) * i;
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(width - right, y);
            ctx.stroke();
            ctx.fillText(value.toFixed(1), 8, y + 4);
        }

        function xAt(index) {
            if (chart.movement.length <= 1) return left;
            return left + (index / (chart.movement.length - 1)) * graphW;
        }

        function yAt(value) {
            return top + graphH - (value / maxVal) * graphH;
        }

        function line(points, color, dashed = false) {
            if (points.length < 2) return;

            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.setLineDash(dashed ? [7, 6] : []);

            points.forEach((value, index) => {
                const x = xAt(index);
                const y = yAt(value);
                if (index === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });

            ctx.stroke();
            ctx.setLineDash([]);
        }

        line(chart.threshold, "#0D6EFD", true);
        line(chart.movement, "#AB2E3C");

        ctx.font = "13px Arial";
        ctx.fillStyle = "#AB2E3C";
        ctx.fillRect(left, height - 18, 16, 4);
        ctx.fillStyle = "#F4F6FA";
        ctx.fillText("Hareket", left + 22, height - 13);
        ctx.fillStyle = "#0D6EFD";
        ctx.fillRect(left + 110, height - 18, 16, 4);
        ctx.fillStyle = "#F4F6FA";
        ctx.fillText("Esik", left + 132, height - 13);

        if (chart.movement.length === 0) {
            ctx.fillStyle = "#8B94A8";
            ctx.font = "bold 16px Arial";
            ctx.fillText("Grafik veri bekliyor...", left + 16, top + 42);
        }
    }

    function formatDetectionEngine(engine, hailoActive) {
        const raw = String(engine || "").trim();
        if (!raw) return hailoActive ? "AI HAT" : "Bekliyor";

        const parts = raw.split("+").filter(Boolean);
        const labels = parts.map((part) => {
            if (part.includes("detas_disaster_hailo8l")) return "ADTİ Afet HEF";
            if (part.includes("person_hailo8l")) return "İnsan HEF";
            if (part.includes("ready_hailo_coco")) return "Hazır Hailo";
            if (part.includes("detas_disaster_pt")) return "ADTİ Afet PT";
            if (part.includes("detas_disaster_onnx")) return "ADTİ Afet ONNX";
            if (part.includes("person_pt")) return "İnsan PT";
            if (part === "disabled") return "Devre Dışı";
            if (part === "error") return "Hata";
            return part;
        });

        return labels.join(" + ");
    }

    function updateDetections(data) {
        const count = number(data.detection_count);
        const detections = Array.isArray(data.detections) ? data.detections : [];
        const list = $("detectionsList");

        setText("detectedCount", count);
        setText("detectedCountDonut", count);
        setText("detectionEngine", formatDetectionEngine(data.detection_engine, data.hailo));

        if (!list) return;

        list.innerHTML = "";
        if (count === 0 || detections.length === 0) {
            const empty = document.createElement("div");
            empty.textContent = "Henuz nesne algilanmadi";
            list.appendChild(empty);
            return;
        }

        const counts = data.detection_count_by_class || {};
        Object.entries(counts).forEach(([className, classCount]) => {
            const summary = document.createElement("div");
            summary.className = "detection-summary-row";
            summary.textContent = `${className}: ${classCount}`;
            list.appendChild(summary);
        });

        detections.slice(0, 20).forEach((obj) => {
            const item = document.createElement("div");
            const name = obj.name || obj.label || "Nesne";
            const confidence = Number(obj.confidence ?? obj.score);
            const confidenceText = Number.isFinite(confidence) ? `%${(confidence * 100).toFixed(1)}` : "-";
            item.textContent = `${name} | Guven: ${confidenceText}`;
            list.appendChild(item);
        });
    }

    function formatPercent(value) {
        const parsed = number(value, NaN);
        return Number.isFinite(parsed) ? `%${parsed.toFixed(1)}` : "-";
    }

    function formatCoord(value) {
        if (value === null || value === undefined || value === "") return "Bilinmiyor";
        const parsed = number(value, NaN);
        return Number.isFinite(parsed) ? parsed.toFixed(6) : "Bilinmiyor";
    }

    function hasKnownGps(event) {
        return Boolean(event?.gps_known) && Number.isFinite(number(event.lat, NaN)) && Number.isFinite(number(event.lng, NaN));
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll("\"", "&quot;")
            .replaceAll("'", "&#039;");
    }

    function eventTitle(event) {
        return String(event?.label || event?.class_name || "Tespit").replaceAll("_", " ");
    }

    function renderDetectionEventDetail(event) {
        const detail = $("detectionEventDetail");
        if (!detail) return;

        detail.innerHTML = "";

        if (!event) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Bir tespit seçildiğinde fotoğraf ve konum burada görünür.";
            detail.appendChild(empty);
            return;
        }

        const title = document.createElement("strong");
        title.textContent = eventTitle(event);
        detail.appendChild(title);

        const meta = document.createElement("div");
        meta.className = "event-detail-grid";

        [
            ["Güven", formatPercent(event.confidence_percent)],
            ["Saat", event.time || "-"],
            ["Enlem", formatCoord(event.lat)],
            ["Boylam", formatCoord(event.lng)],
            ["GPS", event.gps_text || "Bilinmiyor"],
            ["Uydu", event.satellites ?? "-"],
        ].forEach(([label, value]) => {
            const row = document.createElement("p");
            const labelEl = document.createElement("span");
            const valueEl = document.createElement("b");
            labelEl.textContent = label;
            valueEl.textContent = value;
            row.append(labelEl, valueEl);
            meta.appendChild(row);
        });

        detail.appendChild(meta);

        if (event.snapshot_url) {
            const image = document.createElement("img");
            image.src = `${event.snapshot_url}?t=${Math.round(number(event.timestamp))}`;
            image.alt = `${eventTitle(event)} tespit fotoğrafı`;
            detail.appendChild(image);
        }
    }

    function selectDetectionEvent(event, shouldFocusMap = true) {
        if (!event) return;

        selectedDetectionEventId = event.id;
        document.querySelectorAll(".detection-event-item").forEach((item) => {
            item.classList.toggle("active", item.dataset.eventId === selectedDetectionEventId);
        });

        renderDetectionEventDetail(event);

        if (shouldFocusMap && map && hasKnownGps(event)) {
            const latLng = [number(event.lat), number(event.lng)];
            map.setView(latLng, Math.max(map.getZoom(), 16));
            detectionEventMarkers[event.id]?.openPopup();
        }
    }

    function updateDetectionEventMarkers(events) {
        if (!map || typeof L === "undefined") return;

        const activeIds = new Set(events.map((event) => event.id));

        Object.entries(detectionEventMarkers).forEach(([id, marker]) => {
            if (!activeIds.has(id)) {
                marker.remove();
                delete detectionEventMarkers[id];
            }
        });

        events.forEach((event) => {
            if (!hasKnownGps(event)) return;

            const latLng = [number(event.lat), number(event.lng)];
            const popup = `<b>${escapeHtml(eventTitle(event))}</b><br>${escapeHtml(formatPercent(event.confidence_percent))}<br>${escapeHtml(event.time || "")}`;

            if (!detectionEventMarkers[event.id]) {
                detectionEventMarkers[event.id] = L.circleMarker(latLng, {
                    radius: 9,
                    color: "#ffffff",
                    weight: 2,
                    fillColor: "#af1763",
                    fillOpacity: 0.9,
                })
                    .addTo(map)
                    .bindPopup(popup)
                    .on("click", () => selectDetectionEvent(event, false));
            } else {
                detectionEventMarkers[event.id]
                    .setLatLng(latLng)
                    .setPopupContent(popup);
            }
        });
    }

    function updateDetectionEvents(data) {
        const events = Array.isArray(data.detection_events) ? data.detection_events : [];
        const list = $("detectionEventsList");

        setText("aiEventsCount", events.length);
        const badge = $("aiEventsCount");
        if (badge) badge.className = `badge ${events.length ? "live" : "offline"}`;

        updateDetectionEventMarkers(events);

        if (!list) return;

        const eventKey = events.map((event) => `${event.id}:${event.confidence_percent}:${event.time}`).join("|");
        const previousScrollTop = list.scrollTop;
        const wasNearTop = previousScrollTop < 8;
        const hadSelectedEvent = Boolean(selectedDetectionEventId);

        if (events.length === 0) {
            selectedDetectionEventId = null;
            detectionEventsRenderKey = "";
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Henüz kritik tespit yok";
            list.innerHTML = "";
            list.appendChild(empty);
            renderDetectionEventDetail(null);
            return;
        }

        const selectedEvent = events.find((event) => event.id === selectedDetectionEventId) || events[0];
        selectedDetectionEventId = selectedEvent.id;

        if (eventKey === detectionEventsRenderKey) {
            document.querySelectorAll(".detection-event-item").forEach((item) => {
                item.classList.toggle("active", item.dataset.eventId === selectedDetectionEventId);
            });
            renderDetectionEventDetail(selectedEvent);
            return;
        }

        list.innerHTML = "";
        events.slice(0, 30).forEach((event) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "detection-event-item";
            item.dataset.eventId = event.id;

            const title = document.createElement("strong");
            title.textContent = eventTitle(event);

            const meta = document.createElement("span");
            meta.textContent = `${formatPercent(event.confidence_percent)} | ${event.time || "-"} | GPS: ${event.gps_text || "Bilinmiyor"}`;

            item.append(title, meta);
            item.addEventListener("click", () => selectDetectionEvent(event));
            item.classList.toggle("active", event.id === selectedDetectionEventId);
            list.appendChild(item);
        });

        detectionEventsRenderKey = eventKey;
        if (hadSelectedEvent && !wasNearTop) {
            list.scrollTop = Math.min(previousScrollTop, list.scrollHeight - list.clientHeight);
        }

        renderDetectionEventDetail(selectedEvent);
    }

    function updateLogs(data) {
        const list = $("logsList");
        const logs = Array.isArray(data.logs) ? data.logs : [];
        if (!list) return;

        list.innerHTML = "";
        if (logs.length === 0) {
            const empty = document.createElement("div");
            empty.textContent = "Log bekleniyor...";
            list.appendChild(empty);
            return;
        }

        logs.forEach((log) => {
            const item = document.createElement("div");
            item.textContent = String(log);
            list.appendChild(item);
        });
    }

    function thermalColor(value) {
        const v = Math.max(18, Math.min(45, number(value, 18)));
        const ratio = (v - 18) / 27;
        const hue = 220 - (220 * ratio);
        return `hsl(${hue}, 82%, 45%)`;
    }

    function updateThermal(data) {
        const grid = $("thermalGrid");
        const matrix = Array.isArray(data.thermal) ? data.thermal : [];
        const sensor = number(data.thermal_sensor_temp);
        const hotspot = number(data.hotspot);

        setText("thermalSensorTemp", `${sensor.toFixed(1)}°C`);
        setText("thermalHotspotText", hotspot ? "VAR" : "YOK");

        if (!grid) return;

        grid.innerHTML = "";
        const cells = matrix.flat().slice(0, 64);
        while (cells.length < 64) cells.push(0);

        cells.forEach((value) => {
            const cell = document.createElement("div");
            cell.className = "thermal-cell";
            cell.style.background = thermalColor(value);
            cell.textContent = `${number(value).toFixed(1)}°`;
            grid.appendChild(cell);
        });
    }

    function gpsFixText(fix) {
        const fixNo = number(fix);
        if (fixNo >= 6) return "RTK";
        if (fixNo >= 4) return "3D DGPS";
        if (fixNo === 3) return "3D";
        if (fixNo === 2) return "2D";
        return "YOK";
    }

    function formatDistanceCm(value) {
        const distance = Number(value);
        if (!Number.isFinite(distance) || distance <= 0) return "-";
        if (distance >= 100) return `${(distance / 100).toFixed(2)} m`;
        return `${distance.toFixed(0)} cm`;
    }

    function updateLandingProximity(data) {
        const level = String(data.landing_proximity_level || "unknown");
        const text = String(data.landing_proximity_text || "Bilinmiyor");
        const nearest = data.landing_nearest_distance_cm;
        const autoActive = Boolean(data.auto_landing_active);
        const autoStatus = String(data.auto_landing_status || "Kapalı");
        const autoSpeed = number(data.auto_landing_target_speed_mps, 0);
        const mz80Connected = Boolean(data.landing_mz80_connected);
        const mz80Detected = Boolean(data.landing_mz80_detected);
        const sharpConnected = Boolean(data.landing_sharp_connected);
        const sharpCm = data.landing_sharp_distance_cm;
        const sharpVoltage = Number(data.landing_sharp_voltage);

        const card = $("landingCard");
        if (card) {
            card.classList.remove("alarm-card", "warn-card", "safe-card");
            if (level === "danger") card.classList.add("alarm-card");
            else if (level === "warn") card.classList.add("warn-card");
            else if (level === "safe") card.classList.add("safe-card");
        }

        const displayText = level === "unknown" ? "BİLİNMİYOR" : text.toUpperCase();
        const distanceText = formatDistanceCm(nearest);
        setText("landingProximityText", displayText);
        setText("landingProximitySmall", distanceText === "-" ? "Sensör verisi bekleniyor" : `En yakın: ${distanceText}`);

        const mz80Text = !mz80Connected ? "Yok" : (mz80Detected ? "80 cm içinde" : "Serbest");
        const sharpText = !sharpConnected
            ? "Yok"
            : `${formatDistanceCm(sharpCm)}${Number.isFinite(sharpVoltage) && sharpVoltage > 0 ? ` / ${sharpVoltage.toFixed(2)}V` : ""}`;

        setText("landingMz80", mz80Text);
        setText("landingSharp", sharpText);
        setText("landingCubeStatus", displayText);
        setText("landingSummary", distanceText === "-" ? text : `${text} (${distanceText})`);
        setText("autoLandingStatus", autoStatus);
        setText("autoLandingSpeed", `${autoSpeed.toFixed(2)} m/s`);
        setText("landingAutoStatus", autoStatus);
        setText("landingAutoSpeed", `${autoSpeed.toFixed(2)} m/s`);

        const summary = $("landingSummary");
        if (summary) {
            summary.className = `operation-summary-value ${
                level === "danger" ? "bad" : level === "warn" ? "warn" : level === "safe" ? "ok" : "info"
            }`;
        }

        const autoStatusEl = $("autoLandingStatus");
        if (autoStatusEl) autoStatusEl.style.color = autoActive ? "var(--green)" : "var(--cyan)";
    }

    function updateCubePanel(data) {
        const connected = Boolean(data.cube_connected);
        const mode = String(data.cube_mode || "").trim();
        const armed = Boolean(data.cube_armed);
        const voltage = number(data.cube_battery_voltage);
        const current = number(data.cube_battery_current);

        if (mode && mode !== "-") lastValidCubeMode = mode;

        setText("connectionStatus", connected ? "Bagli" : "Baglanti Yok");
        setText("cubeConnectedText", connected ? "Bagli" : "Yok");
        setText("cubeMode", lastValidCubeMode);
        setText("cubeArmStatus", armed ? "ARMED" : "DISARMED");
        setText("cubeArmStatusMirror", armed ? "ARMED" : "DISARMED");
        setText("cubeBattery", voltage > 0 ? `${voltage.toFixed(2)}V / ${current.toFixed(1)}A` : "-");
        setText("cubeGps", gpsFixText(data.cube_gps_fix));
        setText("cubeSatellites", number(data.cube_satellites));
        setText("cubeAltitude", `${number(data.cube_altitude).toFixed(1)} m`);
        setText("cubeHeading", `${number(data.cube_heading).toFixed(0)}°`);
        setText("cubeThrottle", `${number(data.cube_throttle).toFixed(0)}%`);
        setText("cubeRoll", `${number(data.cube_roll).toFixed(1)}°`);
        setText("cubePitch", `${number(data.cube_pitch).toFixed(1)}°`);
        setText("cubeYaw", `${number(data.cube_yaw).toFixed(1)}°`);
        updateLandingProximity(data);

        const badge = $("cubeConnectionBadge");
        if (badge) {
            badge.textContent = connected ? "BAGLI" : "BAGLANTI YOK";
            badge.className = `cube-badge ${connected ? "online" : "offline"}`;
        }
    }

    function normalizeMissionStatus(status) {
        return String(status || "BEKLEMEDE").toUpperCase();
    }

    function updateMissionUI(statusText) {
        const status = statusText || "BEKLEMEDE";
        const normalized = normalizeMissionStatus(status);
        const badge = $("missionBadge");
        const currentBox = $("missionCurrentStatus");

        setText("missionStatusText", status);
        setText("missionStatusBox", status);

        document.querySelectorAll(".mission-step").forEach((step) => {
            step.classList.remove("active");
        });

        let badgeState = "waiting";
        let boxState = "state-waiting";
        const activate = (id) => $(id)?.classList.add("active");

        if (normalized.includes("DURDUR")) {
            badgeState = "stop";
            boxState = "state-stop";
            activate("step-stopped");
        } else if (normalized.includes("İNİŞ") || normalized.includes("INIS")) {
            badgeState = "active";
            boxState = "state-active";
            activate("step-earthquake");
            activate("step-arm");
            activate("step-takeoff");
            activate("step-active");
            activate("step-scan");
            activate("step-landing");
        } else if (normalized.includes("TARAMA")) {
            badgeState = "active";
            boxState = "state-active";
            activate("step-earthquake");
            activate("step-arm");
            activate("step-takeoff");
            activate("step-active");
            activate("step-scan");
        } else if (normalized.includes("KALKIŞ") || normalized.includes("KALKIS")) {
            badgeState = "active";
            boxState = "state-active";
            activate("step-earthquake");
            activate("step-arm");
            activate("step-takeoff");
        } else if (normalized.includes("GÖREVDE") || normalized.includes("GOREVDE")) {
            badgeState = "active";
            boxState = "state-active";
            activate("step-active");
        } else if (normalized.includes("DOĞRULAN") || normalized.includes("DOGRULAN")) {
            badgeState = "alert";
            boxState = "state-alert";
            activate("step-earthquake");
        } else if (normalized.includes("ARM")) {
            badgeState = "alert";
            boxState = "state-alert";
            activate("step-earthquake");
            activate("step-arm");
        } else if (normalized.includes("DEPREM")) {
            badgeState = "alert";
            boxState = "state-alert";
            activate("step-earthquake");
        } else {
            activate("step-waiting");
        }

        if (badge) {
            badge.textContent = status;
            badge.className = `mission-badge ${badgeState}`;
        }

        if (currentBox) {
            currentBox.classList.remove("state-waiting", "state-alert", "state-active", "state-stop");
            currentBox.classList.add(boxState);
        }
    }

    function updateOperationSummary(data) {
        const telemetryConnected = Boolean(data.telemetry_connected);
        const hotspot = number(data.hotspot);

        setText("telemetryStatus", telemetryConnected ? "Bagli" : "Yok");
        const telemetry = $("telemetryStatus");
        if (telemetry) telemetry.className = `operation-summary-value ${telemetryConnected ? "ok" : "bad"}`;

        const cube = $("cubeConnectedText");
        if (cube) cube.className = `operation-summary-value ${data.cube_connected ? "ok" : "bad"}`;

        const arm = $("cubeArmStatusMirror");
        if (arm) arm.className = `operation-summary-value ${data.cube_armed ? "ok" : "info"}`;

        const thermal = $("thermalHotspot");
        if (thermal) thermal.className = `operation-summary-value ${hotspot ? "bad" : "warn"}`;
    }

    function updatePanel() {
        fetch("/data", { cache: "no-store" })
            .then((response) => response.json())
            .then((data) => {
                updateStats(data);
                updateChart(data);
                updateDetections(data);
                updateDetectionEvents(data);
                updateLogs(data);
                updateThermal(data);
                updateCubePanel(data);
                updateMissionUI(data.mission_status);
                updateServoPanelFromData(data);
                updateOperationSummary(data);
            })
            .catch((err) => {
                console.warn("Panel veri hatasi:", err);
                setText("connectionStatus", "Veri Yok");
            });
    }

    function updateFeedbackStats() {
        getJson("/api/feedback/stats")
            .then((data) => {
                const stats = data.stats || {};
                setText("feedbackImageCount", stats.image_count ?? 0);
                setText("feedbackNegativeCount", stats.negative_count ?? 0);

                const box = $("feedbackClassStats");
                if (!box) return;

                const distribution = stats.class_distribution || {};
                box.innerHTML = "";
                const entries = Object.entries(distribution).filter(([, count]) => Number(count) > 0);
                if (entries.length === 0) {
                    const empty = document.createElement("div");
                    empty.textContent = "Henüz feedback yok";
                    box.appendChild(empty);
                    return;
                }

                entries.forEach(([name, count]) => {
                    const item = document.createElement("div");
                    item.textContent = `${name}: ${count}`;
                    box.appendChild(item);
                });
            })
            .catch((err) => console.warn("Feedback istatistik hatasi:", err));
    }

    function feedbackOptionsHtml(defaultValue = "none") {
        const options = [
            `<option value="none"${defaultValue === "none" ? " selected" : ""}>none / background / yanlış tespit</option>`,
        ];

        feedbackClasses.forEach((item) => {
            const selected = item.name === defaultValue ? " selected" : "";
            options.push(`<option value="${escapeHtml(item.name)}"${selected}>${escapeHtml(item.name)}</option>`);
        });

        return options.join("");
    }

    function feedbackDetectionText(detection) {
        const name = detection?.name || detection?.class_name || "Tespit";
        const confidence = Number(detection?.confidence ?? detection?.score);
        const confidenceText = Number.isFinite(confidence) ? `%${(confidence * 100).toFixed(1)}` : "-";
        const bbox = Array.isArray(detection?.bbox) ? detection.bbox.map((v) => Math.round(Number(v))).join(", ") : "-";
        return `${name} | ${confidenceText} | bbox: ${bbox}`;
    }

    function renderFeedbackRows(detections) {
        const box = $("feedbackDetectionRows");
        if (!box) return;

        box.innerHTML = "";
        if (!detections.length) {
            const row = document.createElement("div");
            row.className = "feedback-row";
            row.dataset.detectionId = "";
            row.innerHTML = `
                <div>
                    <strong>Tespit yok</strong>
                    <span>Bu kare background/negatif örnek olarak kaydedilecek.</span>
                </div>
                <select class="feedback-class-select">${feedbackOptionsHtml("none")}</select>
            `;
            box.appendChild(row);
            return;
        }

        detections.forEach((detection) => {
            const row = document.createElement("div");
            row.className = "feedback-row";
            row.dataset.detectionId = detection.id ?? "";
            row.innerHTML = `
                <div>
                    <strong>${escapeHtml(detection.name || detection.class_name || "Tespit")}</strong>
                    <span>${escapeHtml(feedbackDetectionText(detection))}</span>
                </div>
                <select class="feedback-class-select">${feedbackOptionsHtml("none")}</select>
            `;
            box.appendChild(row);
        });
    }

    function openFeedbackModal() {
        const modal = $("feedbackModal");
        const preview = $("feedbackPreviewImage");
        if (modal) {
            modal.classList.add("open");
            modal.setAttribute("aria-hidden", "false");
        }
        if (preview) preview.src = `/api/feedback/latest-frame?t=${Date.now()}`;
        setText("feedbackStatus", "Tespitler yükleniyor...");

        Promise.all([
            getJson("/api/feedback/classes"),
            getJson("/api/detections"),
        ])
            .then(([classesData, detectionsData]) => {
                feedbackClasses = Array.isArray(classesData.classes) ? classesData.classes : [];
                const detections = Array.isArray(detectionsData.detections) ? detectionsData.detections : [];
                renderFeedbackRows(detections);
                setText("feedbackStatus", detections.length ? "Seçimleri düzenle ve kaydet." : "Background olarak kaydedilebilir.");
            })
            .catch((err) => {
                console.error("Feedback modal hatasi:", err);
                feedbackClasses = [];
                renderFeedbackRows([]);
                setText("feedbackStatus", "Tespitler yüklenemedi; background olarak kaydedebilirsin.");
            });
    }

    function closeFeedbackModal() {
        const modal = $("feedbackModal");
        if (!modal) return;
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
    }

    function markAllFeedbackNone() {
        document.querySelectorAll(".feedback-class-select").forEach((select) => {
            select.value = "none";
        });
    }

    function submitFeedbackCapture() {
        const rows = Array.from(document.querySelectorAll(".feedback-row"));
        const annotations = rows
            .filter((row) => row.dataset.detectionId)
            .map((row) => ({
                detection_id: row.dataset.detectionId,
                true_class: row.querySelector(".feedback-class-select")?.value || "none",
            }));

        setText("feedbackStatus", "Kaydediliyor...");
        postJson("/api/feedback/capture", {
            annotations,
            note: "false_positive_or_corrected_sample",
        })
            .then((data) => {
                if (!data.ok) {
                    setText("feedbackStatus", data.error || "Kayit hatasi");
                    return;
                }

                setText("feedbackStatus", `Kaydedildi: ${data.id}`);
                updateFeedbackStats();
                setTimeout(closeFeedbackModal, 700);
            })
            .catch((err) => {
                console.error("Feedback kayit hatasi:", err);
                setText("feedbackStatus", "Kayit hatasi");
            });
    }

    function previewServoValue() {
        const slider = $("servoSlider");
        const value = $("servoValue");
        if (slider && value) value.textContent = slider.value;
    }

    function sendServoValue() {
        const slider = $("servoSlider");
        if (!slider) return;

        previewServoValue();
        clearTimeout(sliderTimer);

        sliderTimer = setTimeout(() => {
            const pwm = parseInt(slider.value, 10);
            if (lastServoSent !== null && Math.abs(lastServoSent - pwm) < 25) return;
            lastServoSent = pwm;

            postJson(`/servo/position/${pwm}`)
                .catch((err) => console.error("Servo PWM hatasi:", err));
        }, 250);
    }

    function updateServoPanelFromData(data) {
        const slider = $("servoSlider");
        const value = data.servo_pwm ?? data.single_servo_pwm ?? data.servo_pan;

        if (slider && value !== undefined && document.activeElement !== slider) {
            slider.value = value;
            previewServoValue();
        }

        const badge = $("servoScanBadge");
        if (badge) {
            const active = Boolean(data.servo_scan_active);
            badge.textContent = active ? "Tarıyor" : "Durdu";
            badge.className = `badge ${active ? "live" : "offline"}`;
        }
    }

    function bindSliders() {
        const slider = $("servoSlider");
        if (!slider) return;

        slider.addEventListener("input", previewServoValue);
        slider.addEventListener("change", sendServoValue);
        slider.addEventListener("pointerup", sendServoValue);
        slider.addEventListener("touchend", sendServoValue);
        previewServoValue();
    }

    function servoCommand(path, after) {
        postJson(path)
            .then((data) => {
                if (data && data.ok === false) console.error("Servo komut hatasi:", data.error || data.message);
                if (typeof after === "function") after();
            })
            .catch((err) => console.error("Servo komut hatasi:", err));
    }

    function servoCenter() {
        servoCommand("/servo/center", () => {
            const slider = $("servoSlider");
            if (slider) slider.value = 2400;
            previewServoValue();
        });
    }

    function servoStop() {
        servoCommand("/servo/stop");
    }

    function servoScan() {
        servoCommand("/servo/scan");
    }

    function applyCameraZoom() {
        const feed = $("cameraFeed");
        const resetButton = $("zoomResetBtn");
        if (!feed) return;

        const zoom = CAMERA_ZOOM_LEVELS[cameraZoomIndex];
        feed.style.transform = `scale(${zoom})`;
        feed.style.transformOrigin = "center center";
        if (resetButton) resetButton.textContent = `Zoom ${zoom.toFixed(2)}x`;
    }

    function cameraZoomIn() {
        cameraZoomIndex = Math.min(cameraZoomIndex + 1, CAMERA_ZOOM_LEVELS.length - 1);
        applyCameraZoom();
    }

    function cameraZoomOut() {
        cameraZoomIndex = Math.max(cameraZoomIndex - 1, 0);
        applyCameraZoom();
    }

    function cameraZoomReset() {
        cameraZoomIndex = 0;
        applyCameraZoom();
    }

    function toggleCameraZoom() {
        cameraZoomIndex = cameraZoomIndex === 0 ? 2 : 0;
        applyCameraZoom();
    }

    function missionArm() {
        postJson("/mission/arm").catch((err) => console.error("ARM hatasi:", err));
    }

    function missionStop() {
        postJson("/mission/stop").catch((err) => console.error("DISARM hatasi:", err));
    }

    function missionReset() {
        postJson("/mission/reset").catch((err) => console.error("Gorev reset hatasi:", err));
    }

    function missionMotorTest() {
        postJson("/mission/motor_test").catch((err) => console.error("Motor test hatasi:", err));
    }

    function landingStart() {
        postJson("/landing/start").catch((err) => console.error("Otomatik inis baslatma hatasi:", err));
    }

    function landingStop() {
        postJson("/landing/stop").catch((err) => console.error("Otomatik inis durdurma hatasi:", err));
    }

    function exposeGlobals() {
        Object.assign(window, {
            setCamera,
            switchPage,
            previewServoValue,
            sendServoValue,
            servoCenter,
            servoStop,
            servoScan,
            cameraZoomIn,
            cameraZoomOut,
            cameraZoomReset,
            toggleCameraZoom,
            missionArm,
            missionStop,
            missionReset,
            missionMotorTest,
            landingStart,
            landingStop,
            openFeedbackModal,
            closeFeedbackModal,
            markAllFeedbackNone,
            submitFeedbackCapture,
        });
    }

    function init() {
        exposeGlobals();
        setupClock();
        setupNavigation();
        bindSliders();
        initMap();
        applyCameraZoom();
        updateMissionUI("BEKLEMEDE");
        drawChart();
        updatePanel();
        updateFeedbackStats();
        setInterval(updatePanel, POLL_MS);
        setInterval(updateFeedbackStats, 5000);
        window.addEventListener("resize", drawChart);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
