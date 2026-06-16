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
    let cameraZoomIndex = 0;
    let lastValidCubeMode = "BILINMIYOR";
    let sliderTimer = null;
    let lastServoSent = null;

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

    function postJson(url) {
        return fetch(url, { method: "POST" })
            .then((response) => response.json().catch(() => ({ ok: response.ok })));
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
            .bindPopup("<b>DETAS Istasyonu</b><br>Durum: Aktif");

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

    function updateDetections(data) {
        const count = number(data.detection_count);
        const detections = Array.isArray(data.detections) ? data.detections : [];
        const list = $("detectionsList");

        setText("detectedCount", count);
        setText("detectedCountDonut", count);

        if (!list) return;

        list.innerHTML = "";
        if (count === 0 || detections.length === 0) {
            const empty = document.createElement("div");
            empty.textContent = "Henuz nesne algilanmadi";
            list.appendChild(empty);
            return;
        }

        detections.slice(0, 20).forEach((obj) => {
            const item = document.createElement("div");
            const name = obj.name || obj.label || "Nesne";
            const confidence = obj.confidence ?? obj.score ?? "-";
            item.textContent = `${name} | Guven: ${confidence}`;
            list.appendChild(item);
        });
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
        } else if (normalized.includes("MOTOR HAZIR")) {
            badgeState = "active";
            boxState = "state-active";
            activate("step-active");
            activate("step-motor-ready");
        } else if (normalized.includes("GÖREVDE") || normalized.includes("GOREVDE")) {
            badgeState = "active";
            boxState = "state-active";
            activate("step-active");
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
        setInterval(updatePanel, POLL_MS);
        window.addEventListener("resize", drawChart);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
