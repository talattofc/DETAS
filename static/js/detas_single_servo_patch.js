(function () {
    if (window.__DETAS_CAMERA_SINGLE_SERVO_FINAL__) return;
    window.__DETAS_CAMERA_SINGLE_SERVO_FINAL__ = true;

    const MIN_PWM = 1250;
    const MAX_PWM = 2600;
    const CENTER_PWM = 2400;
    const DOWN_PWM = 1400;
    const BUTTON_STEP = 100;
    const SLIDER_STEP = 50;

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
            if (!r.ok) {
                await fetch(url, { method: "GET", cache: "no-store" });
            }
        } catch (e) {
            try {
                await fetch(url, { method: "GET", cache: "no-store" });
            } catch (_) {}
        }
    }

    function findSmallestPanel(root, keyword) {
        const items = Array.from(root.querySelectorAll(".panel, .card, div"));
        let best = null;

        for (const el of items) {
            const text = (el.textContent || "").trim();

            if (!text.includes(keyword)) continue;

            const rect = el.getBoundingClientRect();
            if (rect.width < 180 || rect.height < 80) continue;

            if (!best) {
                best = el;
                continue;
            }

            const b = best.getBoundingClientRect();

            if ((rect.width * rect.height) < (b.width * b.height)) {
                best = el;
            }
        }

        return best;
    }

    function removeOldScanPanels(cameraSection) {
        const panels = Array.from(cameraSection.querySelectorAll(".scan-panel, .panel, .card, div"));

        for (const el of panels) {
            if (el.id === "detasCleanSingleScanPanel") continue;
            if (el.id === "detasCleanSingleServoPanel") continue;

            const text = (el.textContent || "").trim();

            const isScan =
                text.includes("Tarama Modları") ||
                text.includes("Tarama Modu") ||
                (
                    text.includes("Merkeze Al") &&
                    text.includes("Taramayı Durdur") &&
                    text.includes("Tam Tarama")
                );

            if (!isScan) continue;

            const rect = el.getBoundingClientRect();

            if (rect.width > 150 && rect.height > 70) {
                el.remove();
            }
        }
    }

    function ensureStyle() {
        if (document.getElementById("detasSingleServoFinalStyle")) return;

        const style = document.createElement("style");
        style.id = "detasSingleServoFinalStyle";
        style.textContent = `
            #detasCleanSingleServoPanel,
            #detasCleanSingleScanPanel {
                background: #1f2430;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 16px;
                color: #fff;
                margin-bottom: 18px;
            }

            #detasCleanSingleServoPanel h3,
            #detasCleanSingleScanPanel h3 {
                margin: 0 0 14px 0;
                font-size: 18px;
                font-weight: 900;
            }

            .detas-servo-box {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 14px;
            }

            .detas-servo-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
                gap: 10px;
            }

            .detas-servo-row strong {
                font-size: 15px;
                font-weight: 900;
            }

            #detasSingleServoValue {
                color: #00d9ff;
                font-size: 18px;
                font-weight: 900;
                font-variant-numeric: tabular-nums;
            }

            #detasSingleServoSlider {
                width: 100%;
                accent-color: #c01776;
                cursor: pointer;
            }

            .detas-servo-buttons,
            .detas-scan-buttons {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 8px;
                margin-top: 14px;
            }

            .detas-scan-buttons {
                grid-template-columns: 1fr 1fr;
            }

            .detas-servo-buttons button,
            .detas-scan-buttons button {
                height: 42px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.12);
                background: #252b38;
                color: white;
                font-weight: 900;
                cursor: pointer;
            }

            .detas-servo-buttons button:hover,
            .detas-scan-buttons button:hover {
                background: #303849;
            }

            .detas-scan-start {
                background: #198754 !important;
            }

            .detas-scan-stop {
                background: #b02a37 !important;
            }

            .detas-scan-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-bottom: 14px;
            }

            .detas-scan-head h3 {
                margin: 0 !important;
            }

            .detas-scan-badge {
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

    function buildServoPanel(servoPanel) {
        servoPanel.id = "detasCleanSingleServoPanel";

        servoPanel.innerHTML = `
            <h3>Yukarı-Aşağı Servo Kontrol</h3>

            <div class="detas-servo-box">
                <div class="detas-servo-row">
                    <strong>Kamera Açısı / AUX1</strong>
                    <span id="detasSingleServoValue">${CENTER_PWM}</span>
                </div>

                <input
                    id="detasSingleServoSlider"
                    type="range"
                    min="${MIN_PWM}"
                    max="${MAX_PWM}"
                    step="${SLIDER_STEP}"
                    value="${CENTER_PWM}"
                >

                <div class="detas-servo-buttons">
                    <button id="detasServoDownBtn">Aşağı</button>
                    <button id="detasServoCenterBtn">Merkez</button>
                    <button id="detasServoUpBtn">Yukarı</button>
                </div>
            </div>
        `;

        const valueEl = document.getElementById("detasSingleServoValue");
        const slider = document.getElementById("detasSingleServoSlider");

        function update(v) {
            currentPWM = clamp(v);
            slider.value = String(currentPWM);
            valueEl.textContent = String(currentPWM);
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

        document.getElementById("detasServoDownBtn").onclick = function () {
            send(currentPWM - BUTTON_STEP);
        };

        document.getElementById("detasServoCenterBtn").onclick = function () {
            send(CENTER_PWM);
        };

        document.getElementById("detasServoUpBtn").onclick = function () {
            send(currentPWM + BUTTON_STEP);
        };

        update(CENTER_PWM);
    }

    function buildScanPanel(servoPanel) {
        let scanPanel = document.getElementById("detasCleanSingleScanPanel");

        if (!scanPanel) {
            scanPanel = document.createElement("div");
            scanPanel.id = "detasCleanSingleScanPanel";
            servoPanel.insertAdjacentElement("afterend", scanPanel);
        }

        scanPanel.innerHTML = `
            <div class="detas-scan-head">
                <h3>Tarama Modu</h3>
                <span class="detas-scan-badge">1400 ↔ 2400</span>
            </div>

            <div class="detas-scan-buttons">
                <button class="detas-scan-start" id="detasScanStartBtn">Taramayı Başlat</button>
                <button class="detas-scan-stop" id="detasScanStopBtn">Taramayı Durdur</button>
            </div>
        `;

        document.getElementById("detasScanStartBtn").onclick = function () {
            post("/servo/scan_single");
        };

        document.getElementById("detasScanStopBtn").onclick = function () {
            post("/servo/stop_single");
        };
    }

    function apply() {
        const cameraSection = document.getElementById("cameraSection");
        if (!cameraSection) return false;

        const side = cameraSection.querySelector(".camera-side");
        if (!side) return false;

        ensureStyle();

        let servoPanel =
            document.getElementById("detasCleanSingleServoPanel") ||
            findSmallestPanel(side, "Pan-Tilt Kamera Kontrol") ||
            findSmallestPanel(side, "Yukarı-Aşağı Servo Kontrol");

        if (!servoPanel) return false;

        removeOldScanPanels(cameraSection);
        buildServoPanel(servoPanel);
        buildScanPanel(servoPanel);

        console.log("[DETAS SERVO] Kamera sayfası tek servo paneli temizlendi.");
        return true;
    }

    function init() {
        let tries = 0;

        const timer = setInterval(function () {
            tries++;

            if (apply() || tries > 25) {
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
