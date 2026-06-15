(function () {
    if (window.__DETAS_SERVO_SLIDER_REBUILD_FIXED__) return;
    window.__DETAS_SERVO_SLIDER_REBUILD_FIXED__ = true;

    const PAN_MIN = 800;
    const PAN_MAX = 2200;
    const PAN_CENTER = 1500;
    const PAN_STEP = 100;

    const TILT_MIN = 650;
    const TILT_MAX = 2000;
    const TILT_CENTER = 1300;
    const TILT_STEP = 120;

    let panPwm = PAN_CENTER;
    let tiltPwm = TILT_CENTER;

    let panTimer = null;
    let tiltTimer = null;

    function clamp(value, min, max, fallback) {
        value = parseInt(value, 10);
        if (Number.isNaN(value)) value = fallback;
        if (value < min) value = min;
        if (value > max) value = max;
        return value;
    }

    function findPanel() {
        const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4"));

        for (const h of headings) {
            const text = (h.textContent || "").toLowerCase();

            if (
                text.includes("pan-tilt") ||
                text.includes("pan tilt") ||
                text.includes("kamera kontrol")
            ) {
                let el = h.parentElement;

                while (el && el !== document.body) {
                    if (
                        el.classList.contains("panel") ||
                        el.classList.contains("servo-box") ||
                        el.classList.contains("camera-panel") ||
                        el.classList.contains("camera-side")
                    ) {
                        return el;
                    }

                    el = el.parentElement;
                }

                return h.parentElement;
            }
        }

        return null;
    }

    async function send(path) {
        console.log("[DETAS SERVO SLIDER]", path);

        try {
            const res = await fetch(path, {
                method: "POST",
                cache: "no-store"
            });

            const text = await res.text();
            console.log("[DETAS SERVO SLIDER] cevap:", text);

            return res.ok;
        } catch (err) {
            console.log("[DETAS SERVO SLIDER] hata:", err);
            return false;
        }
    }

    function sendPan(value) {
        panPwm = clamp(value, PAN_MIN, PAN_MAX, PAN_CENTER);

        const slider = document.getElementById("detasPanSlider");
        const box = document.getElementById("detasPanValue");

        if (slider) slider.value = panPwm;
        if (box) box.textContent = panPwm;

        clearTimeout(panTimer);
        panTimer = setTimeout(function () {
            send("/servo/pan/" + panPwm);
        }, 120);
    }

    function sendTilt(value) {
        tiltPwm = clamp(value, TILT_MIN, TILT_MAX, TILT_CENTER);

        const slider = document.getElementById("detasTiltSlider");
        const box = document.getElementById("detasTiltValue");

        if (slider) slider.value = tiltPwm;
        if (box) box.textContent = tiltPwm;

        clearTimeout(tiltTimer);
        tiltTimer = setTimeout(function () {
            send("/servo/tilt/" + tiltPwm);
        }, 120);
    }

    function build(panel) {
        panel.innerHTML = `
            <div class="detas-servo-card">
                <div class="detas-servo-head">
                    <h3>Pan-Tilt Kamera Kontrol</h3>
                    <span>Canlı PWM kontrol</span>
                </div>

                <div class="detas-servo-control">
                    <div class="detas-servo-row-title">
                        <span>PAN / Sağ-Sol</span>
                        <strong id="detasPanValue">${PAN_CENTER}</strong>
                    </div>

                    <input
                        id="detasPanSlider"
                        class="detas-servo-slider"
                        type="range"
                        min="${PAN_MIN}"
                        max="${PAN_MAX}"
                        step="10"
                        value="${PAN_CENTER}"
                    >

                    <div class="detas-servo-actions">
                        <button id="detasPanLeft">Sol</button>
                        <button id="detasPanCenter">Merkez</button>
                        <button id="detasPanRight">Sağ</button>
                    </div>
                </div>

                <div class="detas-servo-control">
                    <div class="detas-servo-row-title">
                        <span>TILT / Yukarı-Aşağı</span>
                        <strong id="detasTiltValue">${TILT_CENTER}</strong>
                    </div>

                    <input
                        id="detasTiltSlider"
                        class="detas-servo-slider"
                        type="range"
                        min="${TILT_MIN}"
                        max="${TILT_MAX}"
                        step="10"
                        value="${TILT_CENTER}"
                    >

                    <div class="detas-servo-actions">
                        <button id="detasTiltDown">Aşağı</button>
                        <button id="detasTiltCenter">Merkez</button>
                        <button id="detasTiltUp">Yukarı</button>
                    </div>
                </div>
            </div>
        `;

        bind();
    }

    function bind() {
        const panSlider = document.getElementById("detasPanSlider");
        const tiltSlider = document.getElementById("detasTiltSlider");

        if (panSlider) {
            panSlider.oninput = function () {
                panPwm = clamp(panSlider.value, PAN_MIN, PAN_MAX, PAN_CENTER);
                document.getElementById("detasPanValue").textContent = panPwm;

                clearTimeout(panTimer);
                panTimer = setTimeout(function () {
                    send("/servo/pan/" + panPwm);
                }, 120);
            };
        }

        if (tiltSlider) {
            tiltSlider.oninput = function () {
                tiltPwm = clamp(tiltSlider.value, TILT_MIN, TILT_MAX, TILT_CENTER);
                document.getElementById("detasTiltValue").textContent = tiltPwm;

                clearTimeout(tiltTimer);
                tiltTimer = setTimeout(function () {
                    send("/servo/tilt/" + tiltPwm);
                }, 120);
            };
        }

        document.getElementById("detasPanLeft").onclick = function () {
            sendPan(panPwm - PAN_STEP);
        };

        document.getElementById("detasPanCenter").onclick = function () {
            sendPan(PAN_CENTER);
        };

        document.getElementById("detasPanRight").onclick = function () {
            sendPan(panPwm + PAN_STEP);
        };

        document.getElementById("detasTiltDown").onclick = function () {
            sendTilt(TILT_MIN);
        };

        document.getElementById("detasTiltCenter").onclick = function () {
            sendTilt(TILT_CENTER);
        };

        document.getElementById("detasTiltUp").onclick = function () {
            sendTilt(TILT_MAX);
        };
    }

    function addStyle() {
        if (document.getElementById("detasServoSliderStyle")) return;

        const style = document.createElement("style");
        style.id = "detasServoSliderStyle";

        style.textContent = `
            .detas-servo-card {
                width: 100%;
            }

            .detas-servo-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
            }

            .detas-servo-head h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 900;
                color: #ffffff;
            }

            .detas-servo-head span {
                font-size: 12px;
                font-weight: 800;
                color: #94a3b8;
            }

            .detas-servo-control {
                background: #151923;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 14px;
                margin-top: 14px;
            }

            .detas-servo-row-title {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }

            .detas-servo-row-title span {
                font-size: 15px;
                font-weight: 900;
                color: #ffffff;
            }

            .detas-servo-row-title strong {
                font-size: 17px;
                font-weight: 900;
                color: #00d9ff;
                font-variant-numeric: tabular-nums;
            }

            .detas-servo-slider {
                width: 100%;
                height: 8px;
                accent-color: #c2186a;
                cursor: pointer;
            }

            .detas-servo-actions {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 8px;
                margin-top: 14px;
            }

            .detas-servo-actions button {
                height: 44px;
                border-radius: 9px;
                border: 1px solid rgba(255,255,255,0.10);
                background: #252b38;
                color: #ffffff;
                font-size: 14px;
                font-weight: 900;
                cursor: pointer;
            }

            .detas-servo-actions button:hover {
                background: #303849;
            }
        `;

        document.head.appendChild(style);
    }

    function init() {
        addStyle();

        const panel = findPanel();

        if (!panel) {
            console.log("[DETAS SERVO SLIDER] Pan-Tilt panel bulunamadı.");
            return;
        }

        build(panel);

        console.log("[DETAS SERVO SLIDER] Düzeltilmiş slider web panel içine yüklendi.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
