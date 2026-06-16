(function () {
    if (window.__DETAS_CAMERA_SERVO_FIXED__) return;
    window.__DETAS_CAMERA_SERVO_FIXED__ = true;

    const MIN_PWM = 1250;
    const MAX_PWM = 2600;
    const CENTER_PWM = 2400;
    const STEP_BUTTON = 100;
    const STEP_SLIDER = 50;

    let currentPWM = CENTER_PWM;

    function clamp(v) {
        v = parseInt(v || CENTER_PWM);

        if (v < MIN_PWM) v = MIN_PWM;
        if (v > MAX_PWM) v = MAX_PWM;

        return v;
    }

    async function call(url) {
        try {
            let r = await fetch(url, { method: "POST", cache: "no-store" });
            if (r.ok) return true;
        } catch (e) {}

        try {
            let r = await fetch(url, { method: "GET", cache: "no-store" });
            return r.ok;
        } catch (e) {}

        return false;
    }

    function ensureStyle() {
        if (document.getElementById("detasCameraServoFixedStyle")) return;

        const style = document.createElement("style");
        style.id = "detasCameraServoFixedStyle";

        style.textContent = `
            .detas-clean-servo-panel {
                background: #1f2430;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 16px;
                color: #fff;
                margin-bottom: 18px;
            }

            .detas-clean-servo-panel h3 {
                margin: 0 0 14px 0;
                font-size: 18px;
                font-weight: 900;
            }

            .detas-clean-servo-box {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 14px;
            }

            .detas-clean-servo-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-bottom: 12px;
            }

            .detas-clean-servo-row strong {
                font-size: 15px;
                font-weight: 900;
            }

            #detasCleanServoValue {
                color: #00d9ff;
                font-size: 18px;
                font-weight: 900;
                font-variant-numeric: tabular-nums;
            }

            #detasCleanServoSlider {
                width: 100%;
                accent-color: #c01776;
                cursor: pointer;
            }

            .detas-clean-servo-buttons {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 8px;
                margin-top: 14px;
            }

            .detas-clean-scan-buttons {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }

            .detas-clean-servo-buttons button,
            .detas-clean-scan-buttons button {
                height: 42px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.12);
                background: #252b38;
                color: white;
                font-weight: 900;
                cursor: pointer;
            }

            .detas-clean-servo-buttons button:hover,
            .detas-clean-scan-buttons button:hover {
                background: #303849;
            }

            .detas-clean-scan-start {
                background: #198754 !important;
            }

            .detas-clean-scan-stop {
                background: #b02a37 !important;
            }

            .detas-clean-scan-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-bottom: 14px;
            }

            .detas-clean-scan-head h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 900;
            }

            .detas-clean-scan-badge {
                background: #198754;
                color: white;
                border-radius: 999px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 900;
            }
        `;

        document.head.appendChild(style);
    }

    function removeOldCameraScanPanels(cameraSection, side) {
        cameraSection.querySelectorAll(".scan-panel").forEach(function (el) {
            if (!side.contains(el)) {
                el.remove();
            }
        });
    }

    function removeOldSideServoPanels(side) {
        Array.from(side.children).forEach(function (el) {
            const text = (el.textContent || "").trim();

            const isOldServo =
                text.includes("Pan-Tilt Kamera Kontrol") ||
                text.includes("Yukarı-Aşağı Servo Kontrol") ||
                text.includes("PAN / Sağ-Sol") ||
                text.includes("TILT / Yukarı-Aşağı");

            const isOldScan =
                text.includes("Tarama Modları") ||
                text.includes("Tarama Modu") ||
                text.includes("Tam Tarama") ||
                text.includes("Sağ-Sol Tarama") ||
                text.includes("Yukarı-Aşağı Tarama");

            if (el.id === "detasCleanServoPanel") return;
            if (el.id === "detasCleanScanPanel") return;

            if (isOldServo || isOldScan) {
                el.remove();
            }
        });
    }

    function makeServoPanel() {
        const panel = document.createElement("div");
        panel.id = "detasCleanServoPanel";
        panel.className = "detas-clean-servo-panel";

        panel.innerHTML = `
            <h3>Yukarı-Aşağı Servo Kontrol</h3>

            <div class="detas-clean-servo-box">
                <div class="detas-clean-servo-row">
                    <strong>Kamera Açısı / AUX1</strong>
                    <span id="detasCleanServoValue">${CENTER_PWM}</span>
                </div>

                <input
                    id="detasCleanServoSlider"
                    type="range"
                    min="${MIN_PWM}"
                    max="${MAX_PWM}"
                    step="${STEP_SLIDER}"
                    value="${CENTER_PWM}"
                >

                <div class="detas-clean-servo-buttons">
                    <button id="detasCleanServoDown">Aşağı</button>
                    <button id="detasCleanServoCenter">Merkez</button>
                    <button id="detasCleanServoUp">Yukarı</button>
                </div>
            </div>
        `;

        return panel;
    }

    function makeScanPanel() {
        const panel = document.createElement("div");
        panel.id = "detasCleanScanPanel";
        panel.className = "detas-clean-servo-panel";

        panel.innerHTML = `
            <div class="detas-clean-scan-head">
                <h3>Tarama Modu</h3>
                <span class="detas-clean-scan-badge">1400 ↔ 2400</span>
            </div>

            <div class="detas-clean-scan-buttons">
                <button id="detasCleanScanStart" class="detas-clean-scan-start">Taramayı Başlat</button>
                <button id="detasCleanScanStop" class="detas-clean-scan-stop">Taramayı Durdur</button>
            </div>
        `;

        return panel;
    }

    function bindServoEvents() {
        const slider = document.getElementById("detasCleanServoSlider");
        const value = document.getElementById("detasCleanServoValue");

        if (!slider || !value) return;

        function update(v) {
            currentPWM = clamp(v);
            slider.value = String(currentPWM);
            value.textContent = String(currentPWM);
        }

        function send(v) {
            update(v);
            call("/servo/single/" + currentPWM);
        }

        slider.addEventListener("input", function () {
            update(slider.value);
        });

        slider.addEventListener("change", function () {
            send(slider.value);
        });

        document.getElementById("detasCleanServoDown").onclick = function () {
            send(currentPWM - STEP_BUTTON);
        };

        document.getElementById("detasCleanServoCenter").onclick = function () {
            send(CENTER_PWM);
        };

        document.getElementById("detasCleanServoUp").onclick = function () {
            send(currentPWM + STEP_BUTTON);
        };

        update(CENTER_PWM);
    }

    function bindScanEvents() {
        const start = document.getElementById("detasCleanScanStart");
        const stop = document.getElementById("detasCleanScanStop");

        if (start) {
            start.onclick = function () {
                call("/servo/scan_single");
            };
        }

        if (stop) {
            stop.onclick = function () {
                call("/servo/stop_single");
            };
        }
    }

    function apply() {
        const cameraSection = document.getElementById("cameraSection");
        if (!cameraSection) return false;

        const side = cameraSection.querySelector(".camera-side");
        if (!side) return false;

        ensureStyle();

        removeOldCameraScanPanels(cameraSection, side);
        removeOldSideServoPanels(side);

        if (!document.getElementById("detasCleanServoPanel")) {
            side.appendChild(makeServoPanel());
        }

        if (!document.getElementById("detasCleanScanPanel")) {
            side.appendChild(makeScanPanel());
        }

        bindServoEvents();
        bindScanEvents();

        console.log("[DETAS] Kamera sayfası servo paneli temiz kuruldu.");

        return true;
    }

    function init() {
        let tries = 0;

        const timer = setInterval(function () {
            tries++;

            if (apply() || tries > 30) {
                clearInterval(timer);
            }
        }, 300);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
