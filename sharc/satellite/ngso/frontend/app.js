const viewer = new Cesium.Viewer("cesiumContainer", {
    timeline: false,
    animation: false,
    shouldAnimate: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    selectionIndicator: false,
    navigationHelpButton: false,
});

viewer.scene.globe.enableLighting = true;
viewer.scene.globe.depthTestAgainstTerrain = false;
viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(-55, -15, 2_600_000),
});

const profileSelect = document.getElementById("profileSelect");
const reloadBtn = document.getElementById("reloadBtn");
const playBtn = document.getElementById("playBtn");
const frameSlider = document.getElementById("frameSlider");
const frameInfo = document.getElementById("frameInfo");
const activeCount = document.getElementById("activeCount");
const coverageInfo = document.getElementById("coverageInfo");
const timeInfo = document.getElementById("timeInfo");
const statusText = document.getElementById("statusText");

let simulation = null;
let currentFrameIndex = 0;
let isPlaying = false;
let timerId = null;
let satelliteEntities = new Map();
let footprintEntities = [];
let stationEntity = null;
let brazilEntities = [];

function setStatus(message) {
    statusText.textContent = message;
}

function satelliteColor(isActive) {
    return isActive ? Cesium.Color.LIME.withAlpha(0.95) : Cesium.Color.CYAN.withAlpha(0.9);
}

function footprintColor(index) {
    const palette = [
        Cesium.Color.CYAN.withAlpha(0.85),
        Cesium.Color.ORANGE.withAlpha(0.8),
        Cesium.Color.YELLOW.withAlpha(0.8),
        Cesium.Color.SPRINGGREEN.withAlpha(0.8),
    ];
    return palette[index % palette.length];
}

async function loadSimulation(profile) {
    stopPlayback();
    setStatus(`Carregando perfil ${profile}...`);

    const response = await fetch(`/api/simulation?profile=${encodeURIComponent(profile)}`);
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `Falha ao carregar a simulação (${response.status})`);
    }

    simulation = await response.json();
    profileSelect.value = simulation.meta.profile;
    currentFrameIndex = 0;
    frameSlider.min = "0";
    frameSlider.max = String(Math.max(0, simulation.frames.length - 1));
    frameSlider.value = "0";

    buildStaticScene();
    buildSatelliteEntities();
    renderFrame(0);
    setStatus(`Perfil ${simulation.meta.profile} carregado com ${simulation.meta.frameCount} frames.`);
}

function buildStaticScene() {
    if (stationEntity) {
        viewer.entities.remove(stationEntity);
        stationEntity = null;
    }
    brazilEntities.forEach((entity) => viewer.entities.remove(entity));
    brazilEntities = [];

    const station = simulation.station;
    stationEntity = viewer.entities.add({
        id: "ground-station",
        position: Cesium.Cartesian3.fromDegrees(station.lon, station.lat, station.altKm * 1000),
        point: {
            pixelSize: 10,
            color: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
        },
        label: {
            text: "Estação base",
            font: "13px Segoe UI",
            pixelOffset: new Cesium.Cartesian2(0, -18),
            fillColor: Cesium.Color.WHITE,
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(0.5),
        },
    });

    const geometry = simulation.brazilGeoJson;
    const polygons = geometry.type === "MultiPolygon"
        ? geometry.coordinates
        : [geometry.coordinates];

    polygons.forEach((polygon, index) => {
        const outerRing = polygon[0];
        brazilEntities.push(viewer.entities.add({
            id: `brazil-outline-${index}`,
            polygon: {
                hierarchy: Cesium.Cartesian3.fromDegreesArray(
                    outerRing.flatMap(([lon, lat]) => [lon, lat])
                ),
                material: Cesium.Color.WHITE.withAlpha(0.06),
                outline: true,
                outlineColor: Cesium.Color.WHITE.withAlpha(0.5),
                perPositionHeight: false,
            },
        }));
    });
}

function buildSatelliteEntities() {
    satelliteEntities.forEach((entity) => viewer.entities.remove(entity));
    satelliteEntities = new Map();

    const firstFrame = simulation.frames[0];
    firstFrame.satellites.forEach((satellite) => {
        const entity = viewer.entities.add({
            id: satellite.id,
            position: Cesium.Cartesian3.fromDegrees(
                satellite.lon,
                satellite.lat,
                satellite.altKm * 1000
            ),
            point: {
                pixelSize: 7,
                color: satelliteColor(satellite.active),
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 1,
            },
            label: {
                text: satellite.id,
                font: "12px Segoe UI",
                show: false,
            },
        });
        satelliteEntities.set(satellite.id, entity);
    });
}

function clearFootprints() {
    footprintEntities.forEach((entity) => viewer.entities.remove(entity));
    footprintEntities = [];
}

function renderFrame(frameIndex) {
    if (!simulation) {
        return;
    }

    const frame = simulation.frames[frameIndex];
    currentFrameIndex = frameIndex;
    frameSlider.value = String(frameIndex);

    frame.satellites.forEach((satellite) => {
        const entity = satelliteEntities.get(satellite.id);
        if (!entity) {
            return;
        }

        entity.position = Cesium.Cartesian3.fromDegrees(
            satellite.lon,
            satellite.lat,
            satellite.altKm * 1000
        );
        entity.point.color = satelliteColor(satellite.active);
        entity.point.pixelSize = satellite.active ? 9 : 6;
    });

    clearFootprints();
    frame.footprints.forEach((footprint, index) => {
        footprintEntities.push(
            viewer.entities.add({
                polyline: {
                    positions: Cesium.Cartesian3.fromDegreesArrayHeights(
                        footprint.ring.flatMap(([lon, lat, height]) => [lon, lat, height])
                    ),
                    width: 2.5,
                    material: footprintColor(index),
                    clampToGround: false,
                },
            })
        );
    });

    frameInfo.textContent = `${frameIndex + 1} / ${simulation.frames.length}`;
    activeCount.textContent = String(frame.activeSatelliteCount);
    coverageInfo.textContent = `${frame.coveragePercent.toFixed(1)}%`;
    timeInfo.textContent = `${frame.timeSeconds.toFixed(0)} s`;
}

function stopPlayback() {
    isPlaying = false;
    playBtn.textContent = "Play";
    if (timerId !== null) {
        clearInterval(timerId);
        timerId = null;
    }
}

function startPlayback() {
    if (!simulation) {
        return;
    }
    stopPlayback();
    isPlaying = true;
    playBtn.textContent = "Pause";
    const delayMs = Math.max(100, simulation.meta.intervalSeconds * 20);
    timerId = setInterval(() => {
        const nextFrame = (currentFrameIndex + 1) % simulation.frames.length;
        renderFrame(nextFrame);
    }, delayMs);
}

playBtn.addEventListener("click", () => {
    if (isPlaying) {
        stopPlayback();
    } else {
        startPlayback();
    }
});

reloadBtn.addEventListener("click", async () => {
    try {
        await loadSimulation(profileSelect.value);
    } catch (error) {
        setStatus(error.message);
        console.error(error);
    }
});

frameSlider.addEventListener("input", (event) => {
    stopPlayback();
    renderFrame(Number(event.target.value));
});

async function init() {
    try {
        await loadSimulation(profileSelect.value);
    } catch (error) {
        setStatus(error.message);
        console.error(error);
    }
}

init();
