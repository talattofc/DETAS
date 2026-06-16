
(function () {
    if (window.__DETAS_REMOVE_CAMERA_SCAN_PANEL__) return;
    window.__DETAS_REMOVE_CAMERA_SCAN_PANEL__ = true;

    function removeCameraScanPanel() {
        const el = document.getElementById("cameraScanPanel");
        if (el) {
            el.remove();
            console.log("[DETAS] cameraScanPanel silindi.");
        }
    }

    function start() {
        removeCameraScanPanel();

        const observer = new MutationObserver(function () {
            removeCameraScanPanel();
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        setInterval(removeCameraScanPanel, 500);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
