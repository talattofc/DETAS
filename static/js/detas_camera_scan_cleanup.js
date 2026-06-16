(function () {
    if (window.__DETAS_CAMERA_SCAN_CLEANUP__) return;
    window.__DETAS_CAMERA_SCAN_CLEANUP__ = true;

    function looksLikeOldScanBlock(el) {
        if (!el) return false;

        const text = (el.textContent || "").trim();

        const hasOldTitle = text.includes("Tarama Modları");
        const hasOldButtons =
            text.includes("Merkeze Al") ||
            text.includes("Sağ-Sol Tarama") ||
            text.includes("Yukarı-Aşağı Tarama") ||
            text.includes("Tam Tarama") ||
            text.includes("Kamera pan-tilt otomatik tarama kontrolleri");

        const hasButtons = el.querySelectorAll && el.querySelectorAll("button").length >= 2;

        return hasOldTitle && hasOldButtons && hasButtons;
    }

    function findBestOldScanContainer(startEl) {
        let node = startEl;
        let best = null;

        for (let i = 0; i < 8; i++) {
            if (!node) break;

            if (looksLikeOldScanBlock(node)) {
                const rect = node.getBoundingClientRect();

                if (rect.width > 250 && rect.height > 80) {
                    best = node;
                }
            }

            node = node.parentElement;
        }

        return best;
    }

    function cleanupCameraBottomScan() {
        const cameraSection = document.getElementById("cameraSection");
        if (!cameraSection) return false;

        const side = cameraSection.querySelector(".camera-side");

        const candidates = Array.from(cameraSection.querySelectorAll("*")).filter(function (el) {
            const text = (el.textContent || "").trim();

            if (!text.includes("Tarama Modları")) return false;

            // Sağ paneldeki temiz servo/tarama kısmına dokunma
            if (side && side.contains(el)) return false;

            return true;
        });

        let removed = 0;

        candidates.forEach(function (el) {
            const container = findBestOldScanContainer(el);

            if (!container) return;
            if (side && side.contains(container)) return;

            container.remove();
            removed++;
        });

        if (removed > 0) {
            console.log("[DETAS] Canlı kamera altındaki eski Tarama Modları bloğu silindi:", removed);
        }

        return removed > 0;
    }

    function init() {
        let tries = 0;

        const timer = setInterval(function () {
            tries++;

            const ok = cleanupCameraBottomScan();

            if (ok || tries > 20) {
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
