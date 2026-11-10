/* Optional, reproducible publication view. Campaign inputs remain untouched. */
(() => {
    if (new URLSearchParams(location.search).get("capture") !== "publication") return;
    const width = 3200;
    const mapHeight = 1648;
    const headerHeight = 112;
    const attributionHeight = 80;
    const height = headerHeight + mapHeight + attributionHeight;
    document.body.classList.add("publication-mode");
    const panel = document.createElement("section");
    panel.className = "publication-caption";
    panel.innerHTML = `<h2 id="publicationTitle">Preparing capture</h2>
        <p>Same orbital frame and camera for both mitigation scenarios.</p>
        <div class="publication-actions">
          <button type="button" id="publicationExport" disabled>Generate PNG</button>
          <a id="publicationDownload" hidden>Download PNG</a>
          <span id="publicationStatus" class="publication-status">Loading simulation...</span>
        </div>`;
    document.body.appendChild(panel);
    const button = document.getElementById("publicationExport");
    const status = document.getElementById("publicationStatus");
    const download = document.getElementById("publicationDownload");

    function heading() {
        return isBrArgScenario() ? "Conditional power back-off" : "Exclusion zone";
    }

    function prepare() {
        stopPlayback();
        showAzimuthVector = false;
        updateAzimuthVector();
        ueEntities.forEach(entity => { entity.show = false; });
        viewer.scene.globe.enableLighting = false;
        viewer.scene.fog.enabled = false;
        viewer.scene.postProcessStages.fxaa.enabled = true;
        viewer.scene.globe.maximumScreenSpaceError = 1;
        viewer.resolutionScale = width / viewer.scene.canvas.clientWidth;
        viewer.resize();
        const displayScale = viewer.scene.canvas.clientWidth / width;
        stationEntity.label.show = false;
        stationEntity.point.pixelSize = 36 * displayScale;
        stationEntity.point.outlineWidth = 8 * displayScale;
        satelliteEntities.forEach(entity => {
            const size = entity.point.pixelSize.getValue(viewer.clock.currentTime);
            entity.point.pixelSize = (size > 5 ? 24 : 8) * displayScale;
            entity.point.outlineWidth = 4 * displayScale;
        });
        viewer.camera.lookAt(
            Cesium.Cartesian3.fromDegrees(-56.8, -25.0, 0),
            new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-82), 3_550_000)
        );
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
        viewer.scene.requestRender();
        document.getElementById("publicationTitle").textContent = heading();
        status.textContent = "Waiting for map tiles...";
        button.disabled = false;
        viewer.scene.globe.tileLoadProgressEvent.addEventListener(pending => {
            status.textContent = pending ? `Loading map tiles: ${pending}` : "Ready to capture";
        });
    }

    function wrap(ctx, value, x, y, maxWidth, lineHeight) {
        let line = "";
        for (const word of value.split(/\s+/)) {
            const next = line ? `${line} ${word}` : word;
            if (line && ctx.measureText(next).width > maxWidth) {
                ctx.fillText(line, x, y);
                y += lineHeight;
                line = word;
            } else line = next;
        }
        if (line) ctx.fillText(line, x, y);
        return y + lineHeight;
    }

    function symbol(ctx, kind, x, y) {
        ctx.save();
        ctx.lineWidth = 4;
        if (["active", "other", "fs"].includes(kind)) {
            ctx.beginPath();
            ctx.arc(x, y, kind === "other" ? 9 : kind === "fs" ? 18 : 15, 0, Math.PI * 2);
            ctx.fillStyle = { active: "#00ff00", other: "#29b8bd", fs: "#ffffff" }[kind];
            ctx.fill();
            ctx.strokeStyle = "#071219";
            ctx.stroke();
        } else {
            ctx.beginPath();
            if (kind === "cone") {
                ctx.moveTo(x, y - 25);
                ctx.lineTo(x - 27, y + 21);
                ctx.lineTo(x + 27, y + 21);
            } else {
                for (let i = 0; i < 6; i++) {
                    const angle = Math.PI * i / 3;
                    const px = x + 25 * Math.cos(angle);
                    const py = y + 25 * Math.sin(angle);
                    if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
                }
            }
            ctx.closePath();
            ctx.fillStyle = kind === "nominal" ? "rgba(255,165,0,.16)"
                : kind === "cone" ? "rgba(255,184,74,.12)"
                : isBrArgScenario() ? "rgba(255,255,255,.34)" : "rgba(255,255,255,0)";
            ctx.fill();
            ctx.strokeStyle = kind === "nominal" ? "#ffa500" : kind === "cone" ? "#ffe897" : "#ffffff";
            ctx.stroke();
        }
        ctx.restore();
    }

    function attributionText() {
        const credits = Array.from(document.querySelectorAll(".cesium-credit-lightbox li"))
            .map(node => node.textContent.trim()).filter(Boolean);
        return `Cesium ion / Bing Maps. ${[...new Set(credits)].join(" | ")}`;
    }

    async function exportPng() {
        button.disabled = true;
        status.textContent = "Rendering high-resolution PNG...";
        try {
            // Read pixels inside postRender so the WebGL buffer is still valid.
            const image = await new Promise(resolve => {
                const remove = viewer.scene.postRender.addEventListener(() => {
                    remove();
                    const copy = document.createElement("canvas");
                    copy.width = width;
                    copy.height = mapHeight;
                    copy.getContext("2d").drawImage(viewer.scene.canvas, 0, 0, width, mapHeight);
                    resolve(copy);
                });
                viewer.scene.requestRender();
            });
            const output = document.createElement("canvas");
            output.width = width;
            output.height = height;
            const ctx = output.getContext("2d");
            ctx.fillStyle = "white";
            ctx.fillRect(0, 0, width, height);
            ctx.drawImage(image, 0, headerHeight);
            ctx.fillStyle = "#263d47";
            ctx.font = "600 44px Segoe UI";
            ctx.fillText(heading(), 52, 55);
            ctx.font = "27px Segoe UI";
            ctx.fillStyle = "#526570";
            ctx.fillText(isBrArgScenario() ? "Brazil / Argentina service area" : "Regional South American service area", 54, 91);
            ctx.textAlign = "right";
            ctx.fillText(`System 3 | ${Math.round(simulation.frames[0].satellites[0].altKm)} km | Frame ${currentFrameIndex + 1}`, width - 52, 62);
            ctx.textAlign = "left";

            const entries = [
                ["active", "Serving satellite"],
                ["other", "Other satellite"],
                ["fs", "FS receiver"],
                ["nominal", "Nominal-power cell"],
                ["mitigation", isBrArgScenario() ? "Power back-off cell" : "Excluded cell"],
                ["cone", "Service footprint"],
            ];
            const footer = headerHeight + mapHeight;
            const legendWidth = 820;
            const rowHeight = 76;
            const legendHeight = entries.length * rowHeight + 56;
            const legendX = width - legendWidth - 40;
            const legendY = footer - legendHeight - 40;
            ctx.fillStyle = "rgba(8, 23, 33, 0.9)";
            ctx.fillRect(legendX, legendY, legendWidth, legendHeight);
            ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
            ctx.lineWidth = 2;
            ctx.strokeRect(legendX, legendY, legendWidth, legendHeight);
            ctx.font = "500 56px Segoe UI";
            ctx.fillStyle = "#ffffff";
            ctx.textBaseline = "middle";
            entries.forEach(([kind, label], index) => {
                const y = legendY + 28 + rowHeight * (index + 0.5);
                symbol(ctx, kind, legendX + 60, y);
                ctx.fillText(label, legendX + 110, y);
            });
            ctx.textBaseline = "alphabetic";
            ctx.fillStyle = "#526570";
            ctx.font = "20px Segoe UI";
            wrap(ctx, attributionText(), 40, footer + 30, width - 80, 27);
            download.href = output.toDataURL("image/png");
            download.download = isBrArgScenario() ? "mapa_power_backoff.png" : "mapa_zona_exclusao.png";
            download.hidden = false;
            download.textContent = "Download PNG";
            status.textContent = `PNG ready: ${width} x ${height}`;
        } catch (error) {
            status.textContent = `Capture failed: ${error.message}`;
        } finally {
            button.disabled = false;
        }
    }
    button.addEventListener("click", exportPng);
    window.addEventListener("ngso:simulation-loaded", prepare);
    if (simulation) prepare();
})();
