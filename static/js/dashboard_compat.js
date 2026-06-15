/* =========================================================
   DETAS DASHBOARD COMPAT FIX
   Mevcut dashboard.js bozulsa bile ana butonlar ve veri güncelleme çalışır.
   ========================================================= */

(function () {
    if (window.__DETAS_COMPAT_LOADED__) return;
    window.__DETAS_COMPAT_LOADED__ = true;

    function $(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const el = $(id);
        if (el && value !== undefined && value !== null) {
            el.textContent = value;
        }
    }

    function number(value, digits = 2) {
        const n = Number(value);
        if (!Number.isFinite(n)) return "0.00";
        return n.toFixed(digits);
    }

    function get(data, keys, fallback = null) {
        for (const key of keys) {
            if (data && data[key] !== undefined && data[key] !== null) {
                return data[key];
            }
        }
        return fallback;
    }

    function post(url) {
        return fetch(url, { method: "POST" })
            .then(r => r.json())
            .catch(err => {
                console.error("POST hata:", url, err);
                return { ok: false, error: String(err) };
            });
    }

    /* ------------------------------
       Görev / motor butonları
    ------------------------------ */

    window.missionArm = function () {
        post("/mission/arm").then(data => console.log("ARM:", data));
    };

    window.missionStop = function () {
        post("/mission/stop").then(data => console.log("STOP:", data));
    };

    window.missionReset = function () {
        post("/mission/reset").then(data => console.log("RESET:", data));
    };

    window.missionMotorTest = function () {
        post("/mission/motor_test").then(data => console.log("MOTOR TEST:", data));
    };

    /* ------------------------------
       Servo butonları
    ------------------------------ */

    window.previewServoValue = function (axis) {
        if (axis === "pan") {
            const slider = $("panSlider");
            const label = $("panValue");
            if (slider && label) label.textContent = slider.value;
        }

        if (axis === "tilt") {
            const slider = $("tiltSlider");
            const label = $("tiltValue");
            if (slider && label) label.textContent = slider.value;
        }
    };

    window.sendServoValue = function (axis) {
        if (axis === "pan") {
            const slider = $("panSlider");
            if (!slider) return;
            post("/servo/pan/" + parseInt(slider.value));
        }

        if (axis === "tilt") {
            const slider = $("tiltSlider");
            if (!slider) return;
            post("/servo/tilt/" + parseInt(slider.value));
        }
    };

    window.servoCenter = function () {
        post("/servo/center");
    };

    window.servoStop = function () {
        post("/servo/stop");
    };

    window.servoLeft = function () {
        const slider = $("panSlider");
        const label = $("panValue");
        if (slider) slider.value = 450;
        if (label) label.textContent = "450";
        post("/servo/left");
    };

    window.servoRight = function () {
        const slider = $("panSlider");
        const label = $("panValue");
        if (slider) slider.value = 2500;
        if (label) label.textContent = "2500";
        post("/servo/right");
    };

    window.servoUp = function () {
        const slider = $("tiltSlider");
        const label = $("tiltValue");
        if (slider) slider.value = 2000;
        if (label) label.textContent = "2000";
        post("/servo/up");
    };

    window.servoDown = function () {
        const slider = $("tiltSlider");
        const label = $("tiltValue");
        if (slider) slider.value = 650;
        if (label) label.textContent = "650";
        post("/servo/down");
    };

    window.servoScanPanSlow = function () {
        post("/servo/scan_pan_slow");
    };

    window.servoScanTiltSlow = function () {
        post("/servo/scan_tilt_slow");
    };

    window.servoScanFullSlow = function () {
        post("/servo/scan_full_slow");
    };

    /* ------------------------------
       Kamera / zoom
    ------------------------------ */

    let detasZoom = 1;

    function applyZoom() {
        const img = $("cameraFeed");
        const btn = $("zoomResetBtn");

        if (img) {
            img.style.transform = "scale(" + detasZoom + ")";
            img.style.transformOrigin = "center center";
        }

        if (btn) {
            btn.textContent = "Zoom " + detasZoom.toFixed(2) + "x";
        }
    }

    window.cameraZoomIn = function () {
        detasZoom = Math.min(10, detasZoom + 0.25);
        applyZoom();
    };

    window.cameraZoomOut = function () {
        detasZoom = Math.max(1, detasZoom - 0.25);
        applyZoom();
    };

    window.cameraZoomReset = function () {
        detasZoom = 1;
        applyZoom();
    };

    if (typeof window.setCamera !== "function") {
        window.setCamera = function (cameraId) {
            const endpoints = [
                "/camera/" + cameraId,
                "/set_camera/" + cameraId,
                "/camera/select/" + cameraId
            ];

            let index = 0;

            function tryNext() {
                if (index >= endpoints.length) {
                    console.warn("Kamera endpoint bulunamadı.");
                    return;
                }

                fetch(endpoints[index], { method: "POST" })
                    .then(r => {
                        if (!r.ok) throw new Error("HTTP " + r.status);
                        return r.json().catch(() => ({}));
                    })
                    .then(data => {
                        console.log("Kamera değişti:", data);
                        const feed = $("cameraFeed");
                        if (feed) feed.src = "/video?t=" + Date.now();
                    })
                    .catch(() => {
                        index += 1;
                        tryNext();
                    });
            }

            tryNext();

            const cam0 = $("cam0Btn");
            const cam1 = $("cam1Btn");

            if (cam0 && cam1) {
                cam0.classList.toggle("active", cameraId === 0);
                cam1.classList.toggle("active", cameraId === 1);
            }
        };
    }

    /* ------------------------------
       Görev durumu görseli
    ------------------------------ */

    function clearMissionSteps() {
        document.querySelectorAll(".mission-step").forEach(step => {
            step.classList.remove("active");
        });
    }

    function setMissionStep(id) {
        const el = $(id);
        if (el) el.classList.add("active");
    }

    window.updateMissionUI = function (statusText) {
        const status = String(statusText || "BEKLEMEDE");
        const upper = status.toUpperCase();

        setText("missionStatusText", status);
        setText("missionStatusBox", status);
        setText("missionBadge", status);

        const badge = $("missionBadge");
        const box = $("missionCurrentStatus");

        if (badge) {
            badge.className = "mission-badge";
        }

        if (box) {
            box.classList.remove("state-waiting", "state-alert", "state-active", "state-stop");
        }

        clearMissionSteps();

        if (upper.includes("DURDUR")) {
            if (badge) badge.classList.add("stop");
            if (box) box.classList.add("state-stop");
            setMissionStep("step-stopped");
        } else if (upper.includes("MOTOR HAZIR")) {
            if (badge) badge.classList.add("active");
            if (box) box.classList.add("state-active");
            setMissionStep("step-active");
            setMissionStep("step-motor-ready");
        } else if (upper.includes("GÖREVDE") || upper.includes("GOREVDE")) {
            if (badge) badge.classList.add("active");
            if (box) box.classList.add("state-active");
            setMissionStep("step-active");
        } else if (upper.includes("ARM")) {
            if (badge) badge.classList.add("alert");
            if (box) box.classList.add("state-alert");
            setMissionStep("step-earthquake");
            setMissionStep("step-arm");
        } else if (upper.includes("DEPREM")) {
            if (badge) badge.classList.add("alert");
            if (box) box.classList.add("state-alert");
            setMissionStep("step-earthquake");
        } else {
            if (badge) badge.classList.add("waiting");
            if (box) box.classList.add("state-waiting");
            setMissionStep("step-waiting");
        }
    };

    /* ------------------------------
       Temel veri güncelleme
    ------------------------------ */

    function updateDetections(detections) {
        const box = $("detectionsList");
        if (!box || !Array.isArray(detections)) return;

        if (detections.length === 0) {
            box.innerHTML = "<div>Henüz nesne algılanmadı</div>";
            return;
        }

        box.innerHTML = detections.slice(0, 8).map(item => {
            if (typeof item === "string") {
                return "<div>" + item + "</div>";
            }

            const label = item.label || item.name || item.class || "nesne";
            const conf = item.confidence || item.score || item.conf || "";

            return "<div>" + label + (conf ? " | Güven: " + conf : "") + "</div>";
        }).join("");
    }

    function updateLogs(logs) {
        const box = $("logsList");
        if (!box || !Array.isArray(logs)) return;

        if (logs.length === 0) {
            box.innerHTML = "<div>Log bekleniyor...</div>";
            return;
        }

        box.innerHTML = logs.slice(0, 60).map(line => {
            return "<div>" + String(line) + "</div>";
        }).join("");
    }

    function updateThermalGrid(matrix) {
        const grid = $("thermalGrid");
        if (!grid || !Array.isArray(matrix)) return;

        const flat = Array.isArray(matrix[0]) ? matrix.flat() : matrix;
        if (!flat.length) return;

        const min = Math.min(...flat.map(Number));
        const max = Math.max(...flat.map(Number));
        const range = Math.max(1, max - min);

        grid.innerHTML = flat.slice(0, 64).map(v => {
            const n = Number(v);
            const ratio = (n - min) / range;
            let bg = "#1d4ed8";

            if (ratio > 0.75) bg = "#ef4444";
            else if (ratio > 0.55) bg = "#f97316";
            else if (ratio > 0.35) bg = "#eab308";
            else if (ratio > 0.15) bg = "#2563eb";

            return '<div class="thermal-cell" style="background:' + bg + '">' + n.toFixed(1) + "</div>";
        }).join("");
    }

    function updateBasicUI(data) {
        const movement = get(data, ["movement", "hareket"], 0);
        const maxMovement = get(data, ["max_movement", "maxMovement"], 0);
        const threshold = get(data, ["threshold", "esik"], 0);
        const deprem = get(data, ["deprem", "earthquake"], 0);

        const detected = get(data, ["detected_count", "detection_count", "detectedCount"], 0);

        const thermalMax = get(data, ["thermal_max", "thermalMax"], 0);
        const thermalMin = get(data, ["thermal_min", "thermalMin"], 0);
        const thermalSensor = get(data, ["thermal_sensor_temp", "thermalSensorTemp"], 0);

        setText("movementValue", number(movement, 2));
        setText("maxMovementValue", number(maxMovement, 2));
        setText("thresholdValue", number(threshold, 2));
        setText("muteValue", get(data, ["mute"], 0));
        setText("detectedCount", detected);
        setText("detectedCountDonut", detected);

        setText("thermalMaxCard", number(thermalMax, 1) + "°C");
        setText("thermalMax", number(thermalMax, 1) + "°C");
        setText("thermalMin", number(thermalMin, 1) + "°C");
        setText("thermalSensorTemp", number(thermalSensor, 1) + "°C");

        const quakeActive = Number(deprem) === 1 || Number(movement) >= Number(threshold);
        setText("eqStatusText", quakeActive ? "DEPREM ALGILANDI" : "NORMAL");
        setText("eqStatusSmall", quakeActive ? "Eşik değeri aşıldı" : "Sarsıntı yok");

        const telemetryConnected = get(data, ["telemetry_connected"], true);
        setText("telemetryStatus", telemetryConnected ? "Bağlı" : "Yok");
        setText("telemetryPacketCount", get(data, ["telemetry_packet_count", "packet_count"], 0));

        const cubeConnected = get(data, ["cube_connected"], false);
        const cubeArmed = get(data, ["cube_armed"], false);

        setText("cubeConnectedText", cubeConnected ? "Bağlı" : "Yok");
        setText("cubeMode", get(data, ["cube_mode"], "-"));
        setText("cubeArmStatus", cubeArmed ? "ARMED" : "DISARMED");
        setText("cubeArmStatusMirror", cubeArmed ? "ARMED" : "DISARMED");

        const batt = get(data, ["cube_battery_voltage", "battery_voltage"], null);
        if (batt !== null) setText("cubeBattery", number(batt, 2) + " V");

        setText("cubeGps", get(data, ["cube_gps_fix", "gps_fix"], "-"));
        setText("cubeSatellites", get(data, ["cube_satellites", "satellites"], "-"));
        setText("cubeAltitude", number(get(data, ["cube_altitude", "altitude"], 0), 1) + " m");
        setText("cubeHeading", number(get(data, ["cube_heading", "heading"], 0), 0) + "°");
        setText("cubeThrottle", number(get(data, ["cube_throttle", "throttle"], 0), 0) + "%");
        setText("cubeRoll", number(get(data, ["cube_roll", "roll"], 0), 1) + "°");
        setText("cubePitch", number(get(data, ["cube_pitch", "pitch"], 0), 1) + "°");
        setText("cubeYaw", number(get(data, ["cube_yaw", "yaw"], 0), 1) + "°");

        const conn = $("cubeConnectionBadge");
        if (conn) {
            conn.textContent = cubeConnected ? "BAĞLI" : "BAĞLANTI YOK";
            conn.classList.toggle("offline", !cubeConnected);
        }

        const globalConn = cubeConnected || telemetryConnected;
        setText("connectionStatus", globalConn ? "Bağlı" : "Yok");

        const missionStatus = get(data, ["mission_status", "missionStatus"], "BEKLEMEDE");
        updateMissionUI(missionStatus);

        updateDetections(get(data, ["detections"], []));
        updateLogs(get(data, ["logs"], []));
        updateThermalGrid(get(data, ["thermal_matrix", "thermal_grid", "thermal"], null));
    }

    function pollData() {
        fetch("/data")
            .then(r => r.json())
            .then(updateBasicUI)
            .catch(err => console.warn("DETAS veri okuma hatası:", err));
    }

    window.addEventListener("DOMContentLoaded", function () {
        console.log("DETAS compat JS aktif.");

        applyZoom();
        pollData();
        setInterval(pollData, 1000);
    });
})();
