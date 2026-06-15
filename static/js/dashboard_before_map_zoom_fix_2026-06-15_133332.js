let chartLabels = [];
let movementData = [];
let thresholdData = [];
let lastValidCubeMode = "BILINMIYOR";
let map = null;
let droneMarker = null;
let droneAnimationInterval = null;

document.addEventListener("DOMContentLoaded", function () {
    injectMapCss();

    setText("dateBox", new Date().toLocaleDateString("tr-TR", {
        day: "numeric",
        month: "long",
        year: "numeric"
    }));

    try {
        initMapSafe();
    } catch (err) {
        console.error("Harita başlatma hatası:", err);
    }

    setupSidebarNavigation();
    drawCanvasChart();

    updatePanel();
    setInterval(updatePanel, 700);
});

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.innerText = value;
    }
}

function setClass(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.className = value;
    }
}

function addClass(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.add(value);
    }
}

function removeClass(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove(value);
    }
}

/* ========================= */
/* HARİTA CSS */
/* ========================= */

function injectMapCss() {
    const old = document.getElementById("detas-map-extra-css");
    if (old) old.remove();

    const style = document.createElement("style");
    style.id = "detas-map-extra-css";

    style.innerHTML = `
        .map-label {
            background: rgba(10, 18, 32, 0.92) !important;
            color: #fff !important;
            border: 1px solid rgba(255,255,255,0.16) !important;
            border-radius: 10px !important;
            padding: 6px 10px !important;
            font-size: 13px !important;
            font-weight: 900 !important;
            box-shadow: 0 6px 18px rgba(0,0,0,0.28) !important;
        }

        .leaflet-tooltip.map-label:before {
            display: none !important;
        }

        .route-label {
            color: #67e8f9 !important;
        }

        .danger-label {
            color: #f87171 !important;
        }

        .medium-label {
            color: #fbbf24 !important;
        }

        .safe-label {
            color: #4ade80 !important;
        }

        .station-marker {
            width: 20px;
            height: 20px;
            background: #0ea5e9;
            border: 3px solid #ffffff;
            border-radius: 50%;
            box-shadow: 0 0 0 7px rgba(14, 165, 233, 0.25);
        }

        .drone-marker {
            width: 36px;
            height: 36px;
            border-radius: 999px;
            background: linear-gradient(135deg, #0f172a, #0284c7);
            border: 2px solid white;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 18px;
            box-shadow: 0 8px 22px rgba(14, 165, 233, 0.45);
            animation: dronePulse 1.2s infinite ease-in-out;
        }

        @keyframes dronePulse {
            0% {
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.45);
            }
            50% {
                transform: scale(1.08);
                box-shadow: 0 0 0 10px rgba(14, 165, 233, 0.12);
            }
            100% {
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(14, 165, 233, 0);
            }
        }
    `;

    document.head.appendChild(style);
}

/* ========================= */
/* SIDEBAR */
/* ========================= */

function setupSidebarNavigation() {
    const navLinks = document.querySelectorAll(".nav-link");

    navLinks.forEach(link => {
        link.addEventListener("click", function () {
            navLinks.forEach(item => item.classList.remove("active"));
            this.classList.add("active");

            const targetId = this.getAttribute("data-target");
            const targetEl = document.getElementById(targetId);

            if (targetEl) {
                targetEl.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

                setTimeout(() => {
                    if (map) map.invalidateSize();
                }, 600);
            }
        });
    });
}

/* ========================= */
/* HARİTA */
/* ========================= */

function metersToLatLng(center, eastMeters, northMeters) {
    const lat = center[0];
    const lng = center[1];

    const newLat = lat + (northMeters / 111320);
    const newLng = lng + (eastMeters / (111320 * Math.cos(lat * Math.PI / 180)));

    return [newLat, newLng];
}

function addHatchedZone(center, radiusMeters, color, fillColor, label, labelClass) {
    const layerGroup = L.layerGroup().addTo(map);

    const circle = L.circle(center, {
        radius: radiusMeters,
        color: color,
        fillColor: fillColor,
        fillOpacity: 0.20,
        weight: 2
    }).addTo(layerGroup);

    circle.bindTooltip(label, {
        permanent: true,
        direction: "center",
        className: `map-label ${labelClass}`
    });

    const slope = 0.55;
    const step = 35;

    for (let b = -radiusMeters; b <= radiusMeters; b += step) {
        const A = 1 + slope * slope;
        const B = 2 * slope * b;
        const C = b * b - radiusMeters * radiusMeters;
        const disc = B * B - 4 * A * C;

        if (disc < 0) continue;

        const x1 = (-B - Math.sqrt(disc)) / (2 * A);
        const x2 = (-B + Math.sqrt(disc)) / (2 * A);

        const y1 = slope * x1 + b;
        const y2 = slope * x2 + b;

        const p1 = metersToLatLng(center, x1, y1);
        const p2 = metersToLatLng(center, x2, y2);

        L.polyline([p1, p2], {
            color: color,
            weight: 1.4,
            opacity: 0.75
        }).addTo(layerGroup);
    }

    return circle;
}

function startDroneAnimation(routeCoords) {
    if (droneAnimationInterval) {
        clearInterval(droneAnimationInterval);
        droneAnimationInterval = null;
    }

    const droneIcon = L.divIcon({
        className: "",
        html: `<div class="drone-marker">✈</div>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -18]
    });

    droneMarker = L.marker(routeCoords[0], {
        icon: droneIcon
    })
    .addTo(map)
    .bindPopup("İHA Konumu");

    let segment = 0;
    let t = 0;

    droneAnimationInterval = setInterval(() => {
        if (!droneMarker || !map) return;

        const start = routeCoords[segment];
        const end = routeCoords[(segment + 1) % routeCoords.length];

        const lat = start[0] + (end[0] - start[0]) * t;
        const lng = start[1] + (end[1] - start[1]) * t;

        droneMarker.setLatLng([lat, lng]);

        t += 0.035;

        if (t >= 1) {
            t = 0;
            segment = (segment + 1) % routeCoords.length;
        }
    }, 120);
}

function initMapSafe() {
    if (typeof L === "undefined") {
        console.warn("Leaflet yüklenemedi.");
        return;
    }

    const mapEl = document.getElementById("map");
    if (!mapEl) return;

    if (map) {
        map.remove();
        map = null;
    }

    if (droneAnimationInterval) {
        clearInterval(droneAnimationInterval);
        droneAnimationInterval = null;
    }

    const station = [36.8969, 30.7133];

    const routeCoords = [
        [36.8969, 30.7133],
        [36.8955, 30.7070],
        [36.8910, 30.7015],
        [36.8875, 30.7065],
        [36.8898, 30.7165],
        [36.9005, 30.7190]
    ];

    const dangerCenter = [36.8928, 30.7085];
    const mediumCenter = [36.8898, 30.7165];
    const safeCenter = [36.9005, 30.7190];

    map = L.map("map", {
        zoomControl: true
    }).setView(station, 14);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap"
    }).addTo(map);

    const stationIcon = L.divIcon({
        className: "",
        html: `<div class="station-marker"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
        popupAnchor: [0, -12]
    });

    L.marker(station, {
        icon: stationIcon
    })
    .addTo(map)
    .bindPopup(`
        <b>DETAS İstasyonu</b><br>
        Konum: Antalya Merkez<br>
        Durum: Aktif
    `);

    L.polyline(routeCoords, {
        color: "#06b6d4",
        weight: 5,
        opacity: 0.95,
        dashArray: "8,6"
    })
    .addTo(map)
    .bindTooltip("İHA Rotası", {
        permanent: true,
        direction: "center",
        className: "map-label route-label"
    });

    addHatchedZone(
        dangerCenter,
        155,
        "#dc2626",
        "#dc2626",
        "Riskli Bölge",
        "danger-label"
    );

    addHatchedZone(
        mediumCenter,
        170,
        "#f59e0b",
        "#f59e0b",
        "Orta Risk",
        "medium-label"
    );

    addHatchedZone(
        safeCenter,
        185,
        "#22c55e",
        "#22c55e",
        "Güvenli Alan",
        "safe-label"
    );

    startDroneAnimation(routeCoords);

    const bounds = L.latLngBounds([
        station,
        dangerCenter,
        mediumCenter,
        safeCenter,
        ...routeCoords
    ]);

    map.fitBounds(bounds.pad(0.25));

    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 500);
}

/* ========================= */
/* KAMERA */
/* ========================= */

function setCamera(cameraId) {
    fetch(`/set_camera/${cameraId}`, { method: "POST" })
        .then(response => response.json())
        .then(data => {
            if (!data.ok) {
                alert("Kamera değiştirilemedi: " + data.error);
                return;
            }

            const cam0Btn = document.getElementById("cam0Btn");
            const cam1Btn = document.getElementById("cam1Btn");

            if (cam0Btn && cam1Btn) {
                cam0Btn.classList.remove("active");
                cam1Btn.classList.remove("active");

                if (cameraId === 0) cam0Btn.classList.add("active");
                else cam1Btn.classList.add("active");
            }

            const cameraFeed = document.getElementById("cameraFeed");

            if (cameraFeed) {
                cameraFeed.src = `/video?t=${Date.now()}`;
            }
        })
        .catch(error => {
            console.error("Kamera değiştirme hatası:", error);
        });
}

/* ========================= */
/* İSTATİSTİKLER */
/* ========================= */

function updateStats(d) {
    const deprem = Number(d.deprem || 0);
    const movement = Number(d.movement || 0);
    const threshold = Number(d.threshold || 0);
    const maxMovement = Number(d.max_movement || 0);
    const mute = Number(d.mute || 0);
    const thermalMax = Number(d.thermal_max || 0);
    const thermalMin = Number(d.thermal_min || 0);
    const hotspot = Number(d.hotspot || 0);

    setText("movementValue", movement.toFixed(2));
    setText("thresholdValue", threshold.toFixed(2));
    setText("maxMovementValue", maxMovement.toFixed(2));
    setText("muteValue", mute);

    setText("thermalMaxCard", thermalMax.toFixed(1) + "°C");
    setText("thermalMax", thermalMax.toFixed(1) + "°C");
    setText("thermalMin", thermalMin.toFixed(1) + "°C");
    setText("hotspotText", hotspot ? "Sıcak nokta algılandı" : "Sıcak nokta yok");

    const missionStatus = d.mission_status || "BEKLEMEDE";

    setText("missionStatusBox", missionStatus);
    setText("missionBadge", missionStatus);

    if (deprem === 1) {
        setText("eqStatusText", "ALARM");
        setText("eqStatusSmall", "Deprem / sarsıntı algılandı");
        setClass("missionStatusBox", "mission alarm");
        addClass("eqCard", "alarm-card");
        setText("systemStatus", "Alarm");
    } else {
        setText("eqStatusText", "NORMAL");
        setText("eqStatusSmall", "Sarsıntı yok");
        setClass("missionStatusBox", "mission normal");
        removeClass("eqCard", "alarm-card");
        setText("systemStatus", "Aktif");
    }

    const thermalBadge = document.getElementById("thermalBadge");

    if (thermalBadge) {
        if (hotspot) {
            thermalBadge.innerText = "SICAK NOKTA";
            thermalBadge.style.background = "#fee2e2";
            thermalBadge.style.color = "#991b1b";
        } else {
            thermalBadge.innerText = d.thermal_connected ? "NORMAL" : "BAĞLANTI YOK";
            thermalBadge.style.background = d.thermal_connected ? "#dcfce7" : "#fee2e2";
            thermalBadge.style.color = d.thermal_connected ? "#166534" : "#991b1b";
        }
    }
}

/* ========================= */
/* GRAFİK */
/* ========================= */

function updateChart(d) {
    const movement = Number(d.movement || 0);
    const threshold = Number(d.threshold || 0);

    chartLabels.push(new Date().toLocaleTimeString("tr-TR"));
    movementData.push(movement);
    thresholdData.push(threshold);

    if (chartLabels.length > 60) {
        chartLabels.shift();
        movementData.shift();
        thresholdData.shift();
    }

    drawCanvasChart();
}

function drawCanvasChart() {
    const canvas = document.getElementById("movementChart");
    if (!canvas) return;

    const parent = canvas.parentElement;
    const width = parent ? parent.clientWidth : 500;
    const height = parent ? parent.clientHeight : 300;

    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);

    const left = 45;
    const right = 15;
    const top = 20;
    const bottom = 35;

    const graphW = width - left - right;
    const graphH = height - top - bottom;

    const allValues = movementData.concat(thresholdData);
    let maxVal = Math.max(...allValues, 1.5);
    maxVal = Math.ceil(maxVal * 1.3 * 10) / 10;

    ctx.strokeStyle = "#d8dee9";
    ctx.lineWidth = 1;
    ctx.font = "12px Arial";
    ctx.fillStyle = "#64748b";

    for (let i = 0; i <= 5; i++) {
        const y = top + (graphH / 5) * i;
        const value = maxVal - (maxVal / 5) * i;

        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(width - right, y);
        ctx.stroke();

        ctx.fillText(value.toFixed(1), 8, y + 4);
    }

    ctx.strokeStyle = "#94a3b8";
    ctx.beginPath();
    ctx.moveTo(left, top);
    ctx.lineTo(left, height - bottom);
    ctx.lineTo(width - right, height - bottom);
    ctx.stroke();

    function getX(index) {
        if (movementData.length <= 1) return left;
        return left + (index / (movementData.length - 1)) * graphW;
    }

    function getY(value) {
        return top + graphH - (value / maxVal) * graphH;
    }

    function drawLine(data, color, dashed) {
        if (data.length < 2) return;

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.setLineDash(dashed ? [8, 6] : []);

        data.forEach((value, index) => {
            const x = getX(index);
            const y = getY(value);

            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });

        ctx.stroke();
        ctx.setLineDash([]);
    }

    drawLine(thresholdData, "#2563eb", true);
    drawLine(movementData, "#ef4444", false);

    if (movementData.length > 0) {
        const lastIndex = movementData.length - 1;
        const x = getX(lastIndex);
        const y = getY(movementData[lastIndex]);

        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#111827";
        ctx.font = "bold 13px Arial";
        ctx.fillText("M: " + movementData[lastIndex].toFixed(2), Math.max(50, x - 70), y - 12);
    }

    ctx.font = "13px Arial";

    ctx.fillStyle = "#ef4444";
    ctx.fillRect(left, height - 18, 16, 4);
    ctx.fillStyle = "#111827";
    ctx.fillText("Hareket", left + 22, height - 13);

    ctx.fillStyle = "#2563eb";
    ctx.fillRect(left + 105, height - 18, 16, 4);
    ctx.fillStyle = "#111827";
    ctx.fillText("Eşik", left + 127, height - 13);

    if (movementData.length === 0) {
        ctx.fillStyle = "#64748b";
        ctx.font = "bold 16px Arial";
        ctx.fillText("Grafik veri bekliyor...", left + 20, top + 40);
    }
}

/* ========================= */
/* YOLO */
/* ========================= */

function updateDetections(d) {
    const count = Number(d.detection_count || 0);
    const detections = d.detections || [];

    setText("detectedCount", count);
    setText("detectedCountDonut", count);

    const detectionsList = document.getElementById("detectionsList");

    if (!detectionsList) return;

    detectionsList.innerHTML = "";

    if (count === 0) {
        detectionsList.innerHTML = "<div>Henüz nesne algılanmadı</div>";
        return;
    }

    detections.forEach(obj => {
        const item = document.createElement("div");
        item.innerText = `${obj.name} | Güven: ${obj.confidence}`;
        detectionsList.appendChild(item);
    });
}

/* ========================= */
/* LOGLAR */
/* ========================= */

function fixTurkish(text) {
    if (typeof text !== "string") return text;

    return text
        .replace(/Ã¼/g, "ü")
        .replace(/Ãœ/g, "Ü")
        .replace(/Ã¶/g, "ö")
        .replace(/Ã–/g, "Ö")
        .replace(/Ã§/g, "ç")
        .replace(/Ã‡/g, "Ç")
        .replace(/ÄŸ/g, "ğ")
        .replace(/Äž/g, "Ğ")
        .replace(/ÅŸ/g, "ş")
        .replace(/Åž/g, "Ş")
        .replace(/Ä±/g, "ı")
        .replace(/Ä°/g, "İ");
}

function updateLogs(d) {
    const logs = d.logs || [];
    const logsList = document.getElementById("logsList");

    if (!logsList) return;

    logsList.innerHTML = "";

    if (logs.length === 0) {
        logsList.innerHTML = "<div>Log bekleniyor...</div>";
        return;
    }

    logs.slice(0, 12).forEach(log => {
        const item = document.createElement("div");
        item.innerText = fixTurkish(log);
        logsList.appendChild(item);
    });
}

/* ========================= */
/* TERMAL */
/* ========================= */

function updateThermal(d) {
    const grid = document.getElementById("thermalGrid");
    if (!grid) return;

    grid.innerHTML = "";

    const thermal = d.thermal || [];
    const minT = Number(d.thermal_min || 0);
    const maxT = Number(d.thermal_max || 0);

    if (!thermal.length) {
        grid.innerHTML = "<div>Termal veri yok</div>";
        return;
    }

    thermal.forEach(row => {
        row.forEach(temp => {
            const cell = document.createElement("div");
            cell.className = "thermal-cell";

            let ratio = 0;

            if (maxT > minT) {
                ratio = (temp - minT) / (maxT - minT);
            }

            const r = Math.floor(255 * ratio);
            const b = Math.floor(255 * (1 - ratio));
            const g = Math.floor(110 * (1 - Math.abs(ratio - 0.5)));

            cell.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
            cell.innerText = Number(temp).toFixed(1);

            grid.appendChild(cell);
        });
    });
}

/* ========================= */
/* CUBE MAVLINK */
/* ========================= */

function gpsFixText(fix) {
    const value = Number(fix);

    if (value === 0) return "Yok";
    if (value === 1) return "No Fix";
    if (value === 2) return "2D Fix";
    if (value === 3) return "3D Fix";
    if (value === 4) return "DGPS";
    if (value === 5) return "RTK Float";
    if (value === 6) return "RTK Fixed";

    return "Bilinmiyor";
}

function updateCubePanel(d) {
    const badge = document.getElementById("cubeConnectionBadge");

    if (badge) {
        if (d.cube_connected) {
            badge.textContent = "BAĞLI";
            badge.classList.remove("offline");
            badge.classList.add("online");
        } else {
            badge.textContent = "BAĞLANTI YOK";
            badge.classList.remove("online");
            badge.classList.add("offline");
        }
    }

    let modeText = d.cube_mode || "-";
    
    if (modeText.startsWith("Mode(")) {
        modeText = lastValidCubeMode !== "BILINMIYOR" ? lastValidCubeMode : "MAVLink Bağlı";
    } else if (modeText !== "-" && modeText !== "BILINMIYOR") {
        lastValidCubeMode = modeText;
    }
    
    setText("cubeMode", modeText);
    setText("cubeArmStatus", d.cube_arm_status || "-");

    const voltage = Number(d.cube_battery_voltage || 0);
    setText("cubeBattery", voltage > 1 ? `${voltage.toFixed(2)} V` : "USB / düşük");

    setText("cubeGps", gpsFixText(d.cube_gps_fix));
    setText("cubeSatellites", `${d.cube_satellites ?? 0}`);
    setText("cubeAltitude", `${Number(d.cube_altitude || 0).toFixed(1)} m`);
    setText("cubeHeading", `${d.cube_heading ?? 0}°`);
    setText("cubeThrottle", `${d.cube_throttle ?? 0}%`);

    setText("cubeRoll", `${Number(d.cube_roll || 0).toFixed(1)}°`);
    setText("cubePitch", `${Number(d.cube_pitch || 0).toFixed(1)}°`);
    setText("cubeYaw", `${Number(d.cube_yaw || 0).toFixed(1)}°`);
}

/* ========================= */
/* ANA UPDATE */
/* ========================= */

function updatePanel() {
    fetch("/data?v=" + Date.now())
        .then(response => response.json())
        .then(d => {
            updateStats(d);
            updateChart(d);
            updateDetections(d);
            updateLogs(d);
            updateThermal(d);
            updateCubePanel(d);
            updateServoPanelFromData(d);
        })
        .catch(err => {
            console.error("Panel veri hatası:", err);
        });
}

window.addEventListener("resize", function () {
    drawCanvasChart();

    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 300);
});



/* ============================= */
/* PAN-TILT SERVO WEB KONTROL */
/* ============================= */

function previewServoValue(type) {
    if (type === "pan") {
        const slider = document.getElementById("panSlider");
        const value = document.getElementById("panValue");

        if (slider && value) {
            value.innerText = slider.value;
        }
    }

    if (type === "tilt") {
        const slider = document.getElementById("tiltSlider");
        const value = document.getElementById("tiltValue");

        if (slider && value) {
            value.innerText = slider.value;
        }
    }
}

function sendServoValue(type) {
    let slider = null;
    let endpoint = "";

    if (type === "pan") {
        slider = document.getElementById("panSlider");
        if (!slider) return;
        endpoint = `/servo/pan/${slider.value}`;
    }

    if (type === "tilt") {
        slider = document.getElementById("tiltSlider");
        if (!slider) return;
        endpoint = `/servo/tilt/${slider.value}`;
    }

    if (endpoint === "") {
        return;
    }

    fetch(endpoint, {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        if (!data.ok) {
            console.error("Servo komut hatası:", data.message);
        }
    })
    .catch(error => {
        console.error("Servo gönderme hatası:", error);
    });
}

function servoCenter() {
    fetch("/servo/center", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            const panSlider = document.getElementById("panSlider");
            const tiltSlider = document.getElementById("tiltSlider");

            if (panSlider) panSlider.value = 1300;
            if (tiltSlider) tiltSlider.value = 1500;

            previewServoValue("pan");
            previewServoValue("tilt");
        }
    })
    .catch(error => {
        console.error("Merkeze alma hatası:", error);
    });
}

function servoScan() {
    fetch("/servo/scan", {
        method: "POST"
    })
    .catch(error => {
        console.error("Tarama hatası:", error);
    });
}

function servoLeft() {
    fetch("/servo/left", {
        method: "POST"
    })
    .then(() => {
        const panSlider = document.getElementById("panSlider");
        if (panSlider) panSlider.value = 450;
        previewServoValue("pan");
    });
}

function servoRight() {
    fetch("/servo/right", {
        method: "POST"
    })
    .then(() => {
        const panSlider = document.getElementById("panSlider");
        if (panSlider) panSlider.value = 2500;
        previewServoValue("pan");
    });
}

function servoUp() {
    fetch("/servo/up", {
        method: "POST"
    })
    .then(() => {
        const tiltSlider = document.getElementById("tiltSlider");
        if (tiltSlider) tiltSlider.value = 2000;
        previewServoValue("tilt");
    });
}

function servoDown() {
    fetch("/servo/down", {
        method: "POST"
    })
    .then(() => {
        const tiltSlider = document.getElementById("tiltSlider");
        if (tiltSlider) tiltSlider.value = 650;
        previewServoValue("tilt");
    });
}

function updateServoPanelFromData(d) {
    const panSlider = document.getElementById("panSlider");
    const tiltSlider = document.getElementById("tiltSlider");

    if (panSlider && d.servo_pan !== undefined && document.activeElement !== panSlider) {
        panSlider.value = d.servo_pan;
        previewServoValue("pan");
    }

    if (tiltSlider && d.servo_tilt !== undefined && document.activeElement !== tiltSlider) {
        tiltSlider.value = d.servo_tilt;
        previewServoValue("tilt");
    }
}



/* ============================= */
/* YAVAŞ PAN-TILT TARAMA MODLARI */
/* ============================= */

function servoScanPanSlow() {
    fetch("/servo/scan_pan_slow", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        console.log("Sağ-sol tarama başlatıldı:", data);
    })
    .catch(error => {
        console.error("Sağ-sol tarama hatası:", error);
    });
}

function servoScanTiltSlow() {
    fetch("/servo/scan_tilt_slow", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        console.log("Yukarı-aşağı tarama başlatıldı:", data);
    })
    .catch(error => {
        console.error("Yukarı-aşağı tarama hatası:", error);
    });
}

function servoScanFullSlow() {
    fetch("/servo/scan_full_slow", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        console.log("Tam tarama başlatıldı:", data);
    })
    .catch(error => {
        console.error("Tam tarama hatası:", error);
    });
}



/* ============================= */
/* KAMERA ZOOM KONTROL */
/* ============================= */

let cameraZoomActive = false;

function toggleCameraZoom() {
    const cameraFeed = document.getElementById("cameraFeed");
    const zoomBtn = document.getElementById("zoomBtn");

    if (!cameraFeed) {
        return;
    }

    cameraZoomActive = !cameraZoomActive;

    if (cameraZoomActive) {
        cameraFeed.classList.add("camera-zoomed");

        if (zoomBtn) {
            zoomBtn.innerText = "Zoom Kapat";
            zoomBtn.classList.add("active");
        }
    } else {
        cameraFeed.classList.remove("camera-zoomed");

        if (zoomBtn) {
            zoomBtn.innerText = "Zoom Aç";
            zoomBtn.classList.remove("active");
        }
    }
}



/* ============================= */
/* KAMERA KADEMELİ ZOOM */
/* Sadece kamera görüntüsü zoomlanır */
/* ============================= */

let cameraZoomIndex = 0;
const cameraZoomLevels = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10];

function applyCameraZoom() {
    const cameraFeed = document.getElementById("cameraFeed");
    const resetBtn = document.getElementById("zoomResetBtn");

    if (!cameraFeed) {
        return;
    }

    const zoom = cameraZoomLevels[cameraZoomIndex];
    cameraFeed.style.transform = `scale(${zoom})`;

    if (resetBtn) {
        const zoom = cameraZoomLevels[cameraZoomIndex];
        resetBtn.innerText = `Zoom ${zoom.toFixed(2)}x`;
    }
}

function cameraZoomIn() {
    if (cameraZoomIndex < cameraZoomLevels.length - 1) {
        cameraZoomIndex += 1;
    }

    applyCameraZoom();
}

function cameraZoomOut() {
    if (cameraZoomIndex > 0) {
        cameraZoomIndex -= 1;
    }

    applyCameraZoom();
}

function cameraZoomReset() {
    cameraZoomIndex = 0;
    applyCameraZoom();
}

/* Eski buton varsa boşa düşmesin diye uyumluluk */
function toggleCameraZoom() {
    if (cameraZoomIndex === 0) {
        cameraZoomIndex = 2;
    } else {
        cameraZoomIndex = 0;
    }

    applyCameraZoom();
}



/* ============================= */
/* SERVO TARAMA DURDUR */
/* ============================= */

function servoStop() {
    fetch("/servo/stop", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        console.log("Servo tarama durduruldu:", data);
    })
    .catch(error => {
        console.error("Servo durdurma hatası:", error);
    });
}

/* Eski Zoom Aç butonu varsa uyumluluk */
function toggleCameraZoom() {
    if (detasCameraZoomIndex === 0) {
        detasCameraZoomIndex = 3;
    } else {
        detasCameraZoomIndex = 0;
    }

    applyCameraZoom();
}

function detasEnsureZoomButtons() {
    const buttonsBox = document.querySelector(".camera-buttons");
    if (!buttonsBox) return;

    const oldZoomBtn = document.getElementById("zoomBtn");
    if (oldZoomBtn) {
        oldZoomBtn.remove();
    }

    if (!document.getElementById("zoomOutBtn")) {
        const btn = document.createElement("button");
        btn.id = "zoomOutBtn";
        btn.className = "camera-btn zoom-btn";
        btn.innerText = "Zoom -";
        btn.onclick = cameraZoomOut;
        buttonsBox.appendChild(btn);
    }

    if (!document.getElementById("zoomResetBtn")) {
        const btn = document.createElement("button");
        btn.id = "zoomResetBtn";
        btn.className = "camera-btn zoom-btn";
        btn.innerText = "Zoom 1.00x";
        btn.onclick = cameraZoomReset;
        buttonsBox.appendChild(btn);
    }

    if (!document.getElementById("zoomInBtn")) {
        const btn = document.createElement("button");
        btn.id = "zoomInBtn";
        btn.className = "camera-btn zoom-btn";
        btn.innerText = "Zoom +";
        btn.onclick = cameraZoomIn;
        buttonsBox.appendChild(btn);
    }
}

function detasCreateScanButtonsIfMissing(container) {
    const existing = document.querySelector(".scan-mode-buttons");
    if (existing) return existing;

    const title = document.createElement("div");
    title.className = "servo-mode-title";
    title.innerText = "Tarama Modları";
    container.appendChild(title);

    const box = document.createElement("div");
    box.className = "servo-buttons scan-mode-buttons";

    box.innerHTML = `
        <button onclick="servoCenter()">Merkeze Al</button>
        <button onclick="servoStop()" class="servo-stop-btn">Taramayı Durdur</button>
        <button onclick="servoScanPanSlow()">Sağ-Sol Tarama</button>
        <button onclick="servoScanTiltSlow()">Yukarı-Aşağı Tarama</button>
        <button onclick="servoScanFullSlow()">Tam Tarama</button>
    `;

    container.appendChild(box);
    return box;
}

function detasMoveScanModesToCameraBlank() {
    const cameraPanel = document.querySelector(".camera-panel");
    if (!cameraPanel) return;

    let scanPanel = document.getElementById("cameraScanPanel");

    if (!scanPanel) {
        scanPanel = document.createElement("div");
        scanPanel.id = "cameraScanPanel";
        scanPanel.className = "camera-scan-panel";

        const header = document.createElement("div");
        header.className = "camera-scan-header";
        header.innerHTML = `
            <div>
                <h2>Tarama Modları</h2>
                <p>Kamera pan-tilt otomatik tarama kontrolleri</p>
            </div>
            <span>Aktif</span>
        `;

        scanPanel.appendChild(header);
    }

    const oldTitle = document.querySelector(".servo-mode-title");
    const oldButtons = document.querySelector(".scan-mode-buttons");

    if (oldTitle && oldTitle.parentElement !== scanPanel) {
        oldTitle.remove();
    }

    if (oldButtons && oldButtons.parentElement !== scanPanel) {
        scanPanel.appendChild(oldButtons);
    } else if (!oldButtons) {
        detasCreateScanButtonsIfMissing(scanPanel);
    }

    const detections =
        document.getElementById("detectionsList") ||
        document.querySelector(".detections-list") ||
        document.querySelector(".detection-list");

    if (detections && detections.parentElement === cameraPanel) {
        detections.insertAdjacentElement("afterend", scanPanel);
    } else {
        cameraPanel.appendChild(scanPanel);
    }
}

function detasFixScanButtonClasses() {
    const box = document.querySelector(".camera-scan-panel .scan-mode-buttons");
    if (!box) return;

    const buttons = box.querySelectorAll("button");

    buttons.forEach((btn, index) => {
        btn.classList.add("scan-fixed-btn");

        const text = btn.innerText.trim();

        if (text.includes("Durdur")) btn.classList.add("servo-stop-btn");
        if (text.includes("Sağ-Sol")) btn.classList.add("pan-scan-btn");
        if (text.includes("Yukarı")) btn.classList.add("tilt-scan-btn");
        if (text.includes("Tam")) btn.classList.add("full-scan-btn");
        if (text.includes("Merkeze")) btn.classList.add("center-scan-btn");
    });
}

function detasFinalLayoutInit() {
    detasEnsureCameraViewport();
    detasEnsureZoomButtons();
    detasMoveScanModesToCameraBlank();
    detasFixScanButtonClasses();
    applyCameraZoom();
}

document.addEventListener("DOMContentLoaded", function () {
    setTimeout(detasFinalLayoutInit, 300);
    setTimeout(detasFinalLayoutInit, 1200);
});

/* =====================================================
   DETAS MISSION ARM / STOP CONTROL
   ===================================================== */

function missionStop() {
    fetch("/mission/stop", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        console.log("Motor durdur:", data);
    })
    .catch(error => {
        console.error("Motor durdurma hatası:", error);
    });
}

function missionReset() {
    fetch("/mission/reset", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        console.log("Görev sıfırlandı:", data);
    })
    .catch(error => {
        console.error("Görev sıfırlama hatası:", error);
    });
}




/* =====================================================
   DETAS SLIDER SERVO FIX
   Slider komut spamini keser, sadece bırakınca gönderir
   ===================================================== */

let detasSliderTimerPan = null;
let detasSliderTimerTilt = null;
let detasLastSentPan = null;
let detasLastSentTilt = null;

function detasSendSliderCommand(type, pwm) {
    pwm = parseInt(pwm);

    if (type === "pan") {
        if (detasLastSentPan !== null && Math.abs(detasLastSentPan - pwm) < 25) {
            return;
        }

        detasLastSentPan = pwm;

        fetch("/servo/pan/" + pwm, {
            method: "POST"
        })
        .then(r => r.json())
        .then(data => console.log("PAN slider:", data))
        .catch(err => console.error("PAN slider hata:", err));
    }

    if (type === "tilt") {
        if (detasLastSentTilt !== null && Math.abs(detasLastSentTilt - pwm) < 25) {
            return;
        }

        detasLastSentTilt = pwm;

        fetch("/servo/tilt/" + pwm, {
            method: "POST"
        })
        .then(r => r.json())
        .then(data => console.log("TILT slider:", data))
        .catch(err => console.error("TILT slider hata:", err));
    }
}

/* Eski inline onchange bunu çağırdığı için güvenli şekilde override ediyoruz */
function sendServoValue(type) {
    if (type === "pan") {
        const slider = document.getElementById("panSlider");
        const value = document.getElementById("panValue");
        if (!slider) return;

        if (value) value.innerText = slider.value;

        clearTimeout(detasSliderTimerPan);
        detasSliderTimerPan = setTimeout(() => {
            detasSendSliderCommand("pan", slider.value);
        }, 350);
    }

    if (type === "tilt") {
        const slider = document.getElementById("tiltSlider");
        const value = document.getElementById("tiltValue");
        if (!slider) return;

        if (value) value.innerText = slider.value;

        clearTimeout(detasSliderTimerTilt);
        detasSliderTimerTilt = setTimeout(() => {
            detasSendSliderCommand("tilt", slider.value);
        }, 350);
    }
}

window.addEventListener("DOMContentLoaded", function () {
    const panSlider = document.getElementById("panSlider");
    const tiltSlider = document.getElementById("tiltSlider");

    if (panSlider) {
        panSlider.step = "25";

        panSlider.oninput = function () {
            previewServoValue("pan");
        };

        panSlider.onchange = function () {
            sendServoValue("pan");
        };

        panSlider.addEventListener("pointerup", function () {
            sendServoValue("pan");
        });

        panSlider.addEventListener("touchend", function () {
            sendServoValue("pan");
        });
    }

    if (tiltSlider) {
        tiltSlider.step = "25";

        tiltSlider.oninput = function () {
            previewServoValue("tilt");
        };

        tiltSlider.onchange = function () {
            sendServoValue("tilt");
        };

        tiltSlider.addEventListener("pointerup", function () {
            sendServoValue("tilt");
        });

        tiltSlider.addEventListener("touchend", function () {
            sendServoValue("tilt");
        });
    }
});


/* ===== DETAS MISSION UI JS START ===== */

function detasClearMissionSteps() {
    document.querySelectorAll(".mission-step").forEach(function(step) {
        step.classList.remove("active");
    });
}

function detasSetMissionStep(id) {
    var el = document.getElementById(id);
    if (el) {
        el.classList.add("active");
    }
}

function detasNormalizeMissionStatus(statusText) {
    return String(statusText || "BEKLEMEDE").toUpperCase();
}

function updateMissionUI(statusText) {
    var status = statusText || "BEKLEMEDE";
    var s = detasNormalizeMissionStatus(status);

    var missionText = document.getElementById("missionStatusText");
    var missionBadge = document.getElementById("missionBadge");
    var currentBox = document.getElementById("missionCurrentStatus");
    var legacyBox = document.getElementById("missionStatusBox");

    if (missionText) {
        missionText.textContent = status;
    }

    if (legacyBox) {
        legacyBox.textContent = status;
    }

    if (missionBadge) {
        missionBadge.textContent = status;
        missionBadge.className = "mission-badge";
    }

    if (currentBox) {
        currentBox.classList.remove("state-waiting", "state-alert", "state-active", "state-stop");
    }

    detasClearMissionSteps();

    var badgeState = "waiting";
    var boxState = "state-waiting";

    if (s.includes("DURDUR")) {
        badgeState = "stop";
        boxState = "state-stop";
        detasSetMissionStep("step-stopped");
    }
    else if (s.includes("MOTOR HAZIR")) {
        badgeState = "active";
        boxState = "state-active";
        detasSetMissionStep("step-active");
        detasSetMissionStep("step-motor-ready");
    }
    else if (s.includes("GÖREVDE") || s.includes("GOREVDE")) {
        badgeState = "active";
        boxState = "state-active";
        detasSetMissionStep("step-active");
    }
    else if (s.includes("ARM")) {
        badgeState = "alert";
        boxState = "state-alert";
        detasSetMissionStep("step-earthquake");
        detasSetMissionStep("step-arm");
    }
    else if (s.includes("DEPREM")) {
        badgeState = "alert";
        boxState = "state-alert";
        detasSetMissionStep("step-earthquake");
    }
    else {
        badgeState = "waiting";
        boxState = "state-waiting";
        detasSetMissionStep("step-waiting");
    }

    if (missionBadge) {
        missionBadge.classList.add(badgeState);
    }

    if (currentBox) {
        currentBox.classList.add(boxState);
    }
}

/* Motor test fonksiyonu yoksa ekle */
if (typeof window.missionMotorTest !== "function") {
    window.missionMotorTest = function() {
        fetch("/mission/motor_test", { method: "POST" })
            .then(function(r) { return r.json(); })
            .then(function(data) { console.log("Motor test:", data); })
            .catch(function(err) { console.error("Motor test hata:", err); });
    };
}

/* Eski dashboard kodundan bağımsız olarak görev durumunu canlı takip eder */
function detasMissionUIPoll() {
    fetch("/data")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var status = data.mission_status || data.missionStatus || data.mission || "BEKLEMEDE";
            updateMissionUI(status);
        })
        .catch(function(err) {
            console.warn("Mission UI poll hata:", err);
        });
}

window.addEventListener("DOMContentLoaded", function() {
    updateMissionUI("BEKLEMEDE");
    detasMissionUIPoll();
    setInterval(detasMissionUIPoll, 1000);
});

/* ===== DETAS MISSION UI JS END ===== */





/* ===== DETAS DUPLICATE SCAN PANEL GUARD START ===== */
window.addEventListener("DOMContentLoaded", function () {
    setTimeout(function () {
        const cameraPage = document.getElementById("cameraSection");
        if (!cameraPage) return;

        const scanPanels = Array.from(document.querySelectorAll(".scan-panel"));

        scanPanels.forEach(function(panel) {
            const insideCameraSide = panel.closest(".camera-side");
            const insideCameraPage = panel.closest("#cameraSection");

            // Yeni tasarımda doğru Tarama Modları sadece cameraSection > camera-side içinde olmalı.
            if (!insideCameraSide || !insideCameraPage) {
                panel.remove();
            }
        });
    }, 500);
});
/* ===== DETAS DUPLICATE SCAN PANEL GUARD END ===== */
