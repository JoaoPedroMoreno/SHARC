/* Optional, reproducible publication view. Campaign inputs remain untouched. */
(() => {
    if (new URLSearchParams(location.search).get("capture") !== "publication") return;
    const width = 3200;
    const mapHeight = 1648;
    const headerHeight = 112;
    const height = 2100;
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
        stationEntity.label.text = "Victim FS receiver";
        stationEntity.label.font = `bold ${48 * displayScale}px Segoe UI`;
        stationEntity.label.pixelOffset = new Cesium.Cartesian2(0, -84 * displayScale);
        stationEntity.label.backgroundColor = Cesium.Color.BLACK.withAlpha(0.80);
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
        ctx.lineWidth = 3;
        if (["active", "other", "fs"].includes(kind)) {
            ctx.beginPath();
            ctx.arc(x, y, kind === "other" ? 6 : 11, 0, Math.PI * 2);
            ctx.fillStyle = { active: "#00ff00", other: "#29b8bd", fs: "#ffffff" }[kind];
            ctx.fill();
            ctx.strokeStyle = "#26333b";
            ctx.stroke();
        } else {
            ctx.fillStyle = "#263d47";
            ctx.fillRect(x - 24, y - 22, 48, 44);
            ctx.beginPath();
            if (kind === "cone") {
                ctx.moveTo(x, y - 17);
                ctx.lineTo(x - 19, y + 15);
                ctx.lineTo(x + 19, y + 15);
            } else {
                for (let i = 0; i < 6; i++) {
                    const angle = Math.PI * i / 3;
                    const px = x + 18 * Math.cos(angle);
                    const py = y + 18 * Math.sin(angle);
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
                ["active", "Satellite serving displayed cells"],
                ["other", "Other displayed satellite"],
                ["fs", "Victim FS receiver"],
                ["nominal", "Nominal-power service cell"],
                ["mitigation", isBrArgScenario() ? "Border cell with power back-off" : "Excluded cell (no service)"],
                ["cone", "Service-footprint envelope (yellow)"],
            ];
            const footer = headerHeight + mapHeight;
            ctx.font = "30px Segoe UI";
            ctx.fillStyle = "#263d47";
            entries.forEach(([kind, label], index) => {
                const x = 72 + (index % 3) * 1050;
                const y = footer + 60 + Math.floor(index / 3) * 64;
                symbol(ctx, kind, x, y - 8);
                ctx.fillText(label, x + 40, y + 3);
            });
            ctx.font = "23px Segoe UI";
            ctx.fillStyle = "#526570";
            ctx.fillText("Orbital service-grid visualization. Yellow envelopes do not represent interference intensity.", 52, footer + 191);
            ctx.font = "20px Segoe UI";
            wrap(ctx, attributionText(), 52, footer + 235, width - 104, 27);
            download.href = output.toDataURL("image/png");
            download.download = isBrArgScenario() ? "mapa_power_backoff.png" : "mapa_zona_exclusao.png";
            download.hidden = false;
            download.textContent = "Download PNG";
            status.textContent = "PNG ready: 3200 x 2100";
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
