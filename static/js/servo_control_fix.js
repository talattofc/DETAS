(function () {
    if (window.__DETAS_SERVO_CONTROL_FIX__) return;
    window.__DETAS_SERVO_CONTROL_FIX__ = true;

    let lastPan = 1300;
    let lastTilt = 1500;
    let debounceTimer = null;

    function api(path) {
        return fetch(path, { method: "POST" })
            .then(function (res) {
                if (res.ok) return res;
                return fetch(path, { method: "GET" });
            })
            .catch(function () {
                return fetch(path, { method: "GET" });
            });
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function findSliders() {
        const sliders = Array.from(document.querySelectorAll('input[type="range"]'));

        let panSlider =
            document.getElementById("panSlider") ||
            document.getElementById("servoPan") ||
            sliders[0];

        let tiltSlider =
            document.getElementById("tiltSlider") ||
            document.getElementById("servoTilt") ||
            sliders[1];

        return { panSlider, tiltSlider };
    }

    function updateSliderVisuals() {
        const { panSlider, tiltSlider } = findSliders();

        if (panSlider) {
            lastPan = parseInt(panSlider.value || lastPan);
            setText("panValue", lastPan);
            const panTexts = Array.from(document.querySelectorAll("*")).filter(e => e.textContent && e.textContent.trim() === String(lastPan));
        }

        if (tiltSlider) {
            lastTilt = parseInt(tiltSlider.value || lastTilt);
            setText("tiltValue", lastTilt);
        }
    }

    function sendPan(value) {
        value = parseInt(value);
        lastPan = value;
        setText("panValue", value);

        const { panSlider } = findSliders();
        if (panSlider) panSlider.value = value;

        return api("/servo/pan/" + value);
    }

    function sendTilt(value) {
        value = parseInt(value);
        lastTilt = value;
        setText("tiltValue", value);

        const { tiltSlider } = findSliders();
        if (tiltSlider) tiltSlider.value = value;

        return api("/servo/tilt/" + value);
    }

    function debounceSend(axis, value) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            if (axis === "pan") sendPan(value);
            if (axis === "tilt") sendTilt(value);
        }, 120);
    }

    window.previewServoValue = function (axis, value) {
        if (axis === "pan") {
            lastPan = parseInt(value);
            setText("panValue", lastPan);
        }

        if (axis === "tilt") {
            lastTilt = parseInt(value);
            setText("tiltValue", lastTilt);
        }
    };

    window.sendServoValue = function (axis) {
        const { panSlider, tiltSlider } = findSliders();

        if (axis === "pan" && panSlider) {
            return sendPan(panSlider.value);
        }

        if (axis === "tilt" && tiltSlider) {
            return sendTilt(tiltSlider.value);
        }
    };

    window.servoLeft = function () {
        return sendPan(1200);
    };

    window.servoRight = function () {
        return sendPan(1900);
    };

    window.servoUp = function () {
        return sendTilt(1200);
    };

    window.servoDown = function () {
        return sendTilt(1800);
    };

    window.servoCenter = function () {
        lastPan = 1500;
        lastTilt = 1500;

        const { panSlider, tiltSlider } = findSliders();
        if (panSlider) panSlider.value = 1500;
        if (tiltSlider) tiltSlider.value = 1500;

        setText("panValue", 1500);
        setText("tiltValue", 1500);

        return api("/servo/center");
    };

    window.servoStop = function () {
        return api("/servo/stop");
    };

    window.scanPanSlow = function () {
        return api("/servo/scan_pan_slow");
    };

    window.scanTiltSlow = function () {
        return api("/servo/scan_tilt_slow");
    };

    window.scanFullSlow = function () {
        return api("/servo/scan_full_slow");
    };

    window.scanStop = function () {
        return api("/servo/stop");
    };

    function bindButtonByText(text, fn) {
        const buttons = Array.from(document.querySelectorAll("button"));
        buttons.forEach(function (btn) {
            const clean = (btn.textContent || "").replace(/\s+/g, " ").trim();

            if (clean === text) {
                btn.onclick = function (e) {
                    e.preventDefault();
                    fn();
                };
            }
        });
    }

    function bindControls() {
        const { panSlider, tiltSlider } = findSliders();

        if (panSlider) {
            panSlider.min = panSlider.min || 1000;
            panSlider.max = panSlider.max || 2000;
            panSlider.step = panSlider.step || 10;

            panSlider.addEventListener("input", function () {
                lastPan = parseInt(panSlider.value);
                setText("panValue", lastPan);
                debounceSend("pan", lastPan);
            });
        }

        if (tiltSlider) {
            tiltSlider.min = tiltSlider.min || 1000;
            tiltSlider.max = tiltSlider.max || 2000;
            tiltSlider.step = tiltSlider.step || 10;

            tiltSlider.addEventListener("input", function () {
                lastTilt = parseInt(tiltSlider.value);
                setText("tiltValue", lastTilt);
                debounceSend("tilt", lastTilt);
            });
        }

        bindButtonByText("Sol", window.servoLeft);
        bindButtonByText("Merkez", window.servoCenter);
        bindButtonByText("Sağ", window.servoRight);

        bindButtonByText("Yukarı", window.servoUp);
        bindButtonByText("Aşağı", window.servoDown);

        bindButtonByText("Merkeze Al", window.servoCenter);
        bindButtonByText("Taramayı Durdur", window.scanStop);
        bindButtonByText("Sağ-Sol Tarama", window.scanPanSlow);
        bindButtonByText("Yukarı-Aşağı Tarama", window.scanTiltSlow);
        bindButtonByText("Tam Tarama", window.scanFullSlow);

        updateSliderVisuals();

        console.log("DETAS servo control fix aktif.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindControls);
    } else {
        bindControls();
    }
})();
