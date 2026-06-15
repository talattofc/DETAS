(function () {
    if (window.__DETAS_MISSION_REPORT_EXPORT__) return;
    window.__DETAS_MISSION_REPORT_EXPORT__ = true;

    const STORAGE_KEY = "detas_event_timeline_v1";

    function nowFileName() {
        const d = new Date();
        const pad = n => String(n).padStart(2, "0");

        return (
            d.getFullYear() + "-" +
            pad(d.getMonth() + 1) + "-" +
            pad(d.getDate()) + "_" +
            pad(d.getHours()) + "-" +
            pad(d.getMinutes()) + "-" +
            pad(d.getSeconds())
        );
    }

    function getEvents() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        } catch (e) {
            return [];
        }
    }

    async function getLiveData() {
        try {
            const res = await fetch("/data", { cache: "no-store" });
            return await res.json();
        } catch (e) {
            return {};
        }
    }

    function downloadFile(filename, content, type) {
        const blob = new Blob([content], { type: type });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        setTimeout(function () {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 200);
    }

    function cleanValue(value) {
        if (value === undefined || value === null || value === "") return "-";

        if (typeof value === "object") {
            try {
                return JSON.stringify(value);
            } catch (e) {
                return String(value);
            }
        }

        return String(value);
    }

    function buildTextReport(events, data) {
        const lines = [];

        lines.push("DETAS GÖREV RAPORU");
        lines.push("Oluşturulma zamanı: " + new Date().toLocaleString("tr-TR"));
        lines.push("");

        lines.push("ANLIK SİSTEM DURUMU");
        lines.push("Görev durumu: " + cleanValue(data.mission_status || data.auto_mission_status));
        lines.push("ARM durumu: " + cleanValue(data.cube_armed || data.armed || data.is_armed));
        lines.push("Cube modu: " + cleanValue(data.cube_mode));
        lines.push("Sarsıntı değeri: " + cleanValue(data.movement));
        lines.push("Eşik değeri: " + cleanValue(data.threshold));
        lines.push("AI tespit sayısı: " + cleanValue(data.detection_count || data.detected_count));
        lines.push("Termal maksimum: " + cleanValue(data.thermal_max));
        lines.push("Termal minimum: " + cleanValue(data.thermal_min));
        lines.push("GPS fix: " + cleanValue(data.cube_gps_fix || data.gps_fix));
        lines.push("Uydu sayısı: " + cleanValue(data.cube_satellites || data.satellites));
        lines.push("");

        lines.push("GÖREV OLAY GEÇMİŞİ");

        if (!events.length) {
            lines.push("Kayıtlı olay yok.");
        } else {
            events.slice().reverse().forEach(function (ev, index) {
                lines.push("");
                lines.push((index + 1) + ". Olay");
                lines.push("Saat: " + cleanValue(ev.time));
                lines.push("Tür: " + cleanValue(ev.type));
                lines.push("Başlık: " + cleanValue(ev.title));
                lines.push("Detay: " + cleanValue(ev.detail));
            });
        }

        lines.push("");
        lines.push("Rapor sonu.");

        return lines.join("\n");
    }

    async function exportTxt() {
        const events = getEvents();
        const data = await getLiveData();

        const text = buildTextReport(events, data);
        downloadFile("DETAS_gorev_raporu_" + nowFileName() + ".txt", text, "text/plain;charset=utf-8");
    }

    async function exportJson() {
        const events = getEvents();
        const data = await getLiveData();

        const report = {
            project: "DETAS",
            generated_at: new Date().toISOString(),
            generated_at_tr: new Date().toLocaleString("tr-TR"),
            live_data: data,
            events: events
        };

        downloadFile(
            "DETAS_gorev_raporu_" + nowFileName() + ".json",
            JSON.stringify(report, null, 2),
            "application/json;charset=utf-8"
        );
    }

    function ensureStyle() {
        if (document.getElementById("detasReportExportStyle")) return;

        const style = document.createElement("style");
        style.id = "detasReportExportStyle";
        style.textContent = `
            .detas-report-actions {
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            }

            .detas-report-actions button {
                border: 1px solid rgba(255,255,255,0.12);
                background: #252b38;
                color: #ffffff;
                border-radius: 8px;
                height: 34px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 900;
                cursor: pointer;
            }

            .detas-report-actions button:hover {
                background: #303849;
            }
        `;

        document.head.appendChild(style);
    }

    function addButtons() {
        ensureStyle();

        const timelineHead = document.querySelector(".detas-timeline-head");

        if (!timelineHead) {
            console.log("[DETAS REPORT] Olay geçmişi kartı bulunamadı.");
            return;
        }

        if (document.getElementById("detasExportTxt")) return;

        const oldClear = document.getElementById("detasClearTimeline");

        const box = document.createElement("div");
        box.className = "detas-report-actions";

        box.innerHTML = `
            <button id="detasExportTxt">TXT indir</button>
            <button id="detasExportJson">JSON indir</button>
        `;

        if (oldClear) {
            box.appendChild(oldClear);
        }

        timelineHead.appendChild(box);

        document.getElementById("detasExportTxt").onclick = exportTxt;
        document.getElementById("detasExportJson").onclick = exportJson;

        console.log("[DETAS REPORT] Görev raporu indirme aktif.");
    }

    function init() {
        addButtons();

        let tries = 0;
        const timer = setInterval(function () {
            tries++;
            addButtons();

            if (document.getElementById("detasExportTxt") || tries > 10) {
                clearInterval(timer);
            }
        }, 500);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
