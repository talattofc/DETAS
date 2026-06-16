(function () {
    if (window.__DETAS_SPACING_FIX__) return;
    window.__DETAS_SPACING_FIX__ = true;

    function applySpacingFix() {
        if (document.getElementById("detasSpacingFixStyle")) return;

        const style = document.createElement("style");
        style.id = "detasSpacingFixStyle";

        style.textContent = `
            /* Uçuşa Hazırlık kartı ile alt bloklar arasına nefes payı */
            .detas-preflight-card {
                margin-bottom: 28px !important;
            }

            /* Genel Bakış içinde üst karttan sonra gelen ana grid biraz aşağı insin */
            #overviewSection .detas-preflight-card + * {
                margin-top: 24px !important;
            }

            /* Görev Durumu ve Sarsıntı Grafiği satırı üstten yapışmasın */
            #overviewSection .overview-grid,
            #overviewSection .dashboard-grid,
            #overviewSection .main-grid,
            #overviewSection .content-grid {
                row-gap: 24px !important;
                column-gap: 18px !important;
            }

            /* Görev Durumu kartı üst boşluğu */
            .mission-card {
                margin-top: 0 !important;
            }

            /* Genel panel aralıklarını biraz rahatlat */
            .panel {
                margin-bottom: 18px;
            }
        `;

        document.head.appendChild(style);
        console.log("[DETAS SPACING] Kart aralıkları düzeltildi.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", applySpacingFix);
    } else {
        applySpacingFix();
    }
})();
