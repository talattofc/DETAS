(function () {
    if (window.__SERVO_RIGHT_CLEAN__) return;
    window.__SERVO_RIGHT_CLEAN__ = true;

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

    async function post(url) {
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
        if (document.getElementById("servoRightCleanStyle")) return;

        const style = document.createElement("style");
        style.id = "servoRightCleanStyle";

        style.textContent = `
            #servoRightCleanPanel,
            #servoRightScanPanel {
                background: #1f2430;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 16px;
                color: #ffffff;
                margin-bottom: 18px;
            }

            #servoRightCleanPanel h3,
            #servoRightScanPanel h3 {
                margin: 0 0 14px 0;
                font-size: 18px;
                font-weight: 900;
                color: #ffffff;
            }

            .servo-clean-box {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 14px;
            }

            .servo-clean-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-bottom: 12px;
            }

            .servo-clean-row strong {
                font-size: 15px;
                font-weight: 900;
                color: #ffffff;
            }

            #servoRightValue {
                color: #00d9ff;
                font-size: 18px;
                font-weight: 900;
                font-variant-numeric: tabular-nums;
            }

            #servoRightSlider {
                width: 100%;
                accent-color: #c01776;
                cursor: pointer;
            }

            .servo-clean-buttons {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 8px;
                margin-top: 14px;
            }

            .servo-scan-buttons {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }

            .servo-clean-buttons button,
            .servo-scan-buttons button {
                height: 42px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.12);
                background: #252b38;
                color: #ffffff;
                font-weight: 900;
                cursor: pointer;
            }

            .servo-clean-buttons button:hover,
            .servo-scan-buttons button:hover {
                background: #303849;
            }

            .servo-scan-start {
                background: #198754 !important;
            }

            .servo-scan-stop {
                background: #b02a37 !important;
            }

            .servo-scan-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-bottom: 14px;
            }

            .servo-scan-head h3 {
                margin: 0 !important;
            }

            .servo-scan-badge {
                background: #198754;
                color: #ffffff;
                border-radius: 999px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 900;
            }
        `;

        document.head.appendChild(style);
    }

    function removeOldServoCards(side) {
        Array.from(side.children).forEach(function (child) {
            const text = (child.textContent || "").trim();

            const isOldServo =
                text.includes("Pan-Tilt Kamera Kontrol") ||
                text.includes("PAN / Sağ-Sol") ||
                text.includes("TILT / Yukarı-Aşağı");

            const isOldScan =
                text.includes("Tarama Modları") ||
                text.includes("Sağ-Sol Tarama") ||
                text.includes("Yukarı-Aşağı Tarama") ||
                text.includes("Tam Tarama");

            if (isOldServo || isOldScan) {
                child.remove();
            }
        });
    }

    function createServoPanel() {
        const panel = document.createElement("div");
        panel.id = "servoRightCleanPanel";

        panel.innerHTML = `
            <h3>Yukarı-Aşağı Servo Kontrol</h3>

            <div class="servo-clean-box">
                <div class="servo-clean-row">
                    <strong>Kamera Açısı / AUX1</strong>
                    <span id="servoRightValue">${CENTER_PWM}</span>
                </div>

                <input
                    id="servoRightSlider"
                    type="range"
                    min="${MIN_PWM}"
                    max="${MAX_PWM}"
                    step="${STEP_SLIDER}"
                    value="${CENTER_PWM}"
                >

                <div class="servo-clean-buttons">
                    <button id="servoRightDown">Aşağı</button>
                    <button id="servoRightCenter">Merkez</button>
                    <button id="servoRightUp">Yukarı</button>
                </div>
            </div>
        `;

        return panel;
    }

    function createScanPanel() {
        const panel = document.createElement("div");
        panel.id = "servoRightScanPanel";

        panel.innerHTML = `
            <div class="servo-scan-head">
                <h3>Tarama Modu</h3>
                <span class="servo-scan-badge">1400 ↔ 2400</span>
            </div>

            <div class="servo-scan-buttons">
                <button id="servoRightScanStart" class="servo-scan-start">Taramayı Başlat</button>
                <button id="servoRightScanStop" class="servo-scan-stop">Taramayı Durdur</button>
            </div>
        `;

        return panel;
    }

    function bindServo() {
        const slider = document.getElementById("servoRightSlider");
        const value = document.getElementById("servoRightValue");

        if (!slider || !value) return;

        function update(v) {
            currentPWM = clamp(v);
            slider.value = String(currentPWM);
            value.textContent = String(currentPWM);
        }

        function send(v) {
            update(v);
            post("/servo/single/" + currentPWM);
        }

        slider.addEventListener("input", function () {
            update(slider.value);
        });

        slider.addEventListener("change", function () {
            send(slider.value);
        });

        document.getElementById("servoRightDown").onclick = function () {
            send(currentPWM - STEP_BUTTON);
        };

        document.getElementById("servoRightCenter").onclick = function () {
            send(CENTER_PWM);
        };

        document.getElementById("servoRightUp").onclick = function () {
            send(currentPWM + STEP_BUTTON);
        };

        update(CENTER_PWM);
    }

    function bindScan() {
        const start = document.getElementById("servoRightScanStart");
        const stop = document.getElementById("servoRightScanStop");

        if (start) {
            start.onclick = function () {
                post("/servo/scan_single");
            };
        }

        if (stop) {
            stop.onclick = function () {
                post("/servo/stop_single");
            };
        }
    }

    function apply() {
        const cameraSection = document.getElementById("cameraSection");
        if (!cameraSection) return false;

        const side = cameraSection.querySelector(".camera-side");
        if (!side) return false;

        ensureStyle();

        removeOldServoCards(side);

        if (!document.getElementById("servoRightCleanPanel")) {
            side.appendChild(createServoPanel());
        }

        if (!document.getElementById("servoRightScanPanel")) {
            side.appendChild(createScanPanel());
        }

        bindServo();
        bindScan();

        console.log("[DETAS] Sağ servo paneli temiz kuruldu.");
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
