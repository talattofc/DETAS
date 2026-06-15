(function () {
    if (window.__DETAS_SERVO_PANEL_SAFE_FINAL__) return;
    window.__DETAS_SERVO_PANEL_SAFE_FINAL__ = true;

    const PAN_MIN = 800;
    const PAN_MAX = 2200;
    const PAN_CENTER = 1500;
    const PAN_STEP = 120;

    const TILT_MIN = 800;
    const TILT_MAX = 1800;
    const TILT_CENTER = 1300;
    const TILT_STEP = 100;

    let panPwm = PAN_CENTER;
    let tiltPwm = TILT_CENTER;

    function log(msg) {
        console.log("[DETAS SERVO FIX]", msg);
    }

    function norm(text) {
        return (text || "")
            .toLowerCase()
            .replace(/ı/g, "i")
            .replace(/ğ/g, "g")
            .replace(/ü/g, "u")
            .replace(/ş/g, "s")
            .replace(/ö/g, "o")
            .replace(/ç/g, "c")
            .replace(/\s+/g, " ")
            .trim();
    }

    function clamp(v, min, max, fallback) {
        v = parseInt(v);

        if (Number.isNaN(v)) v = fallback;
        if (v < min) v = min;
        if (v > max) v = max;

        return v;
    }

    function getSlider(axis) {
        const sliders = Array.from(document.querySelectorAll('input[type="range"]'));

        if (axis === "pan") {
            return document.getElementById("panSlider") ||
                   document.getElementById("servoPan") ||
                   sliders[0] ||
                   null;
        }

        if (axis === "tilt") {
            return document.getElementById("tiltSlider") ||
                   document.getElementById("servoTilt") ||
                   sliders[1] ||
                   null;
        }

        return null;
    }

    function getServoBox(axis) {
        const slider = getSlider(axis);
        if (!slider) return null;

        let el = slider.parentElement;

        while (el && el !== document.body) {
            if (el.querySelectorAll('input[type="range"]').length >= 1 &&
                el.querySelectorAll("button").length >= 3) {
                return el;
            }

            el = el.parentElement;
        }

        return null;
    }

    function setNumberInBox(axis, value) {
        const box = getServoBox(axis);
        if (!box) return;

        const nodes = Array.from(box.querySelectorAll("*"));

        for (const el of nodes) {
            if (el.children.length > 0) continue;
            if (el.tagName.toLowerCase() === "button") continue;

            const t = (el.textContent || "").trim();

            if (/^\d{3,4}$/.test(t)) {
                el.textContent = value;
                return;
            }
        }
    }

    function setKnownIds(ids, value) {
        ids.forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        });
    }

    function updatePanUI(value) {
        panPwm = clamp(value, PAN_MIN, PAN_MAX, PAN_CENTER);

        const s = getSlider("pan");
        if (s) {
            s.min = PAN_MIN;
            s.max = PAN_MAX;
            s.step = 10;
            s.value = panPwm;
        }

        setKnownIds(["panValue", "panPwm", "servoPanValue"], panPwm);
        setNumberInBox("pan", panPwm);
    }

    function updateTiltUI(value) {
        tiltPwm = clamp(value, TILT_MIN, TILT_MAX, TILT_CENTER);

        const s = getSlider("tilt");
        if (s) {
            s.min = TILT_MIN;
            s.max = TILT_MAX;
            s.step = 10;
            s.value = tiltPwm;
        }

        setKnownIds(["tiltValue", "tiltPwm", "servoTiltValue"], tiltPwm);
        setNumberInBox("tilt", tiltPwm);
    }

    async function send(path) {
        log("İstek gönderiliyor: " + path);

        try {
            const res = await fetch(path, {
                method: "POST",
                cache: "no-store"
            });

            const text = await res.text();
            log("Cevap: " + text);

            return res.ok;
        } catch (e) {
            log("Hata: " + e);
            return false;
        }
    }

    function sendPan(value) {
        value = clamp(value, PAN_MIN, PAN_MAX, PAN_CENTER);
        updatePanUI(value);
        return send("/servo/pan/" + value);
    }

    function sendTilt(value) {
        value = clamp(value, TILT_MIN, TILT_MAX, TILT_CENTER);
        updateTiltUI(value);
        return send("/servo/tilt/" + value);
    }

    window.previewServoValue = function (axis, value) {
        if (axis === "pan") updatePanUI(value);
        if (axis === "tilt") updateTiltUI(value);
    };

    window.sendServoValue = function (axis) {
        if (axis === "pan") {
            const s = getSlider("pan");
            return sendPan(s ? s.value : panPwm);
        }

        if (axis === "tilt") {
            const s = getSlider("tilt");
            return sendTilt(s ? s.value : tiltPwm);
        }
    };

    window.servoLeft = function () {
        return sendPan(panPwm - PAN_STEP);
    };

    window.servoRight = function () {
        return sendPan(panPwm + PAN_STEP);
    };

    window.servoUp = function () {
        return sendTilt(tiltPwm + TILT_STEP);
    };

    window.servoDown = function () {
        return sendTilt(tiltPwm - TILT_STEP);
    };

    window.servoCenter = function () {
        updatePanUI(PAN_CENTER);
        updateTiltUI(TILT_CENTER);
        return send("/servo/center");
    };

    window.servoStop = function () {
        return send("/servo/stop");
    };

    window.scanPanSlow = function () {
        return send("/servo/scan_pan_slow");
    };

    window.scanTiltSlow = function () {
        return send("/servo/scan_tilt_slow");
    };

    window.scanFullSlow = function () {
        return send("/servo/scan_full_slow");
    };

    window.scanStop = function () {
        return send("/servo/stop");
    };

    function bindSliders() {
        const pan = getSlider("pan");
        const tilt = getSlider("tilt");

        if (pan) {
            pan.min = PAN_MIN;
            pan.max = PAN_MAX;
            pan.step = 10;

            updatePanUI(clamp(pan.value || PAN_CENTER, PAN_MIN, PAN_MAX, PAN_CENTER));

            pan.oninput = function () {
                updatePanUI(pan.value);
            };

            pan.onchange = function () {
                sendPan(pan.value);
            };
        }

        if (tilt) {
            tilt.min = TILT_MIN;
            tilt.max = TILT_MAX;
            tilt.step = 10;

            updateTiltUI(clamp(tilt.value || TILT_CENTER, TILT_MIN, TILT_MAX, TILT_CENTER));

            tilt.oninput = function () {
                updateTiltUI(tilt.value);
            };

            tilt.onchange = function () {
                sendTilt(tilt.value);
            };
        }
    }

    function bindServoButtons() {
        const panBox = getServoBox("pan");
        const tiltBox = getServoBox("tilt");

        if (panBox) {
            Array.from(panBox.querySelectorAll("button")).forEach(function (btn) {
                const text = norm(btn.textContent);

                if (text === "sol") {
                    btn.onclick = function (e) {
                        e.preventDefault();
                        sendPan(panPwm - PAN_STEP);
                        return false;
                    };
                }

                if (text === "sag") {
                    btn.onclick = function (e) {
                        e.preventDefault();
                        sendPan(panPwm + PAN_STEP);
                        return false;
                    };
                }

                if (text === "merkez") {
                    btn.onclick = function (e) {
                        e.preventDefault();
                        sendPan(PAN_CENTER);
                        return false;
                    };
                }
            });
        }

        if (tiltBox) {
            const buttons = Array.from(tiltBox.querySelectorAll("button"));

            if (buttons.length >= 3) {
                buttons[0].textContent = "Aşağı";
                buttons[1].textContent = "Merkez";
                buttons[2].textContent = "Yukarı";

                buttons[0].onclick = function (e) {
                    e.preventDefault();
                    sendTilt(tiltPwm - TILT_STEP);
                    return false;
                };

                buttons[1].onclick = function (e) {
                    e.preventDefault();
                    sendTilt(TILT_CENTER);
                    return false;
                };

                buttons[2].onclick = function (e) {
                    e.preventDefault();
                    sendTilt(tiltPwm + TILT_STEP);
                    return false;
                };
            }
        }
    }

    function bindScanButtons() {
        Array.from(document.querySelectorAll("button")).forEach(function (btn) {
            const text = norm(btn.textContent);

            if (text === "merkeze al") {
                btn.onclick = function (e) {
                    e.preventDefault();
                    window.servoCenter();
                    return false;
                };
            }

            if (text === "taramayi durdur") {
                btn.onclick = function (e) {
                    e.preventDefault();
                    window.scanStop();
                    return false;
                };
            }

            if (text === "sag-sol tarama") {
                btn.onclick = function (e) {
                    e.preventDefault();
                    window.scanPanSlow();
                    return false;
                };
            }

            if (text === "yukari-asagi tarama") {
                btn.onclick = function (e) {
                    e.preventDefault();
                    window.scanTiltSlow();
                    return false;
                };
            }

            if (text === "tam tarama") {
                btn.onclick = function (e) {
                    e.preventDefault();
                    window.scanFullSlow();
                    return false;
                };
            }
        });
    }

    function init() {
        bindSliders();
        bindServoButtons();
        bindScanButtons();

        log("Safe final aktif. PAN 800-2200, TILT 800-1800, butonlar adımlı.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
