Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJlNGFjZjdmZC05N2ZhLTQzY2YtYmVjNC1iZjM4YzA4MWQ2OWYiLCJpZCI6NDE5NTczLCJpYXQiOjE3NzY0MjkyMDJ9.U2I_2yVRqORG1AmQSXtJPBXTfn6PK0fpie_PXFOXr6g";

let brazilPolygon = null;

function initBrazilPolygon() {
    const geometry = simulation.brazilGeoJson;

    const coords = geometry.type === "MultiPolygon"
        ? geometry.coordinates[0][0]
        : geometry.coordinates[0];

    brazilPolygon = coords;
}

// Cria hexagonos para representar o grid de elegibilidade dentro do footprint levando em consideração a curvatura da Terra e a variação de distância com a latitude
function createHexagon(lon, lat, sizeKm) {

    const coords = [];

    const latFactor = 1 / 111;
    const lonFactor = 1 / (111 * Math.cos(lat * Math.PI / 180));

    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i;

        const dLat = sizeKm * Math.sin(angle) * latFactor;
        const dLon = sizeKm * Math.cos(angle) * lonFactor;

        coords.push(
            lon + dLon,
            lat + dLat
        );
    }

    return Cesium.Cartesian3.fromDegreesArray(coords);
}

// algoritmo simples (ray casting)
function isPointInPolygon(lon, lat, polygon) {
    let inside = false;

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i][0], yi = polygon[i][1];
        const xj = polygon[j][0], yj = polygon[j][1];

        const intersect =
            ((yi > lat) !== (yj > lat)) &&
            (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi);

        if (intersect) inside = !inside;
    }

    return inside;
}

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
    return isActive ? Cesium.Color.fromBytes(0, 255, 0, 255) : Cesium.Color.CYAN.withAlpha(0.9);
}

function footprintColor(index) {
    const palette = [
        Cesium.Color.CYAN.withAlpha(0.85),
        Cesium.Color.ORANGE.withAlpha(0.03),
        Cesium.Color.YELLOW.withAlpha(0.03),
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
    initBrazilPolygon();
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
            fillColor: Cesium.Color.WHITE.withAlpha(1.5),
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(1.0),
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
                material: Cesium.Color.YELLOW.withAlpha(0.03),
                outline: true,
                outlineColor: Cesium.Color.YELLOW.withAlpha(0.03),
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
    if (!simulation) return;

    const frame = simulation.frames[frameIndex];

    const beamRadiusKm = simulation.meta.beamRadiusKm || 50; // valor padrão de 50km caso não venha do backend
    const beamRadiusDeg = beamRadiusKm / 111; // Aproximação: 1 grau ~ 111 km na superfície da Terra

    console.log("Beam radius (km):", beamRadiusKm); // Log para verificar o valor do beam radius
    console.log("FRAME:", frameIndex);
    console.log("footprints:", frame.footprints);

    currentFrameIndex = frameIndex;
    frameSlider.value = String(frameIndex);

    // ================================
    // SATÉLITES
    // ================================
    frame.satellites.forEach((satellite) => {
        const entity = satelliteEntities.get(satellite.id);
        if (!entity) return;

        entity.position = Cesium.Cartesian3.fromDegrees(
            satellite.lon,
            satellite.lat,
            satellite.altKm * 1000
        );

        // Verde forte para ativo, ciano para inativo
        entity.point.color = satellite.active
            ? Cesium.Color.LIME.withAlpha(1.0)
            : Cesium.Color.CYAN.withAlpha(0.9);

        entity.point.pixelSize = satellite.active ? 10 : 6;
    });

    // ================================
    // LIMPAR FOOTPRINTS ANTIGOS
    // ================================
    clearFootprints();

    // ================================
    // FOOTPRINT + CONE
    // ================================
    frame.footprints.forEach((footprint) => {

        if (!footprint || !footprint.rings) return;

        const satEntity = satelliteEntities.get(footprint.satelliteId);
        if (!satEntity) return;

        const satPos = satEntity.position.getValue(Cesium.JulianDate.now());
        if (!satPos) return;


        // ITERA EM TODOS OS RINGS
        footprint.rings.forEach((ring) => {

            if (!ring || ring.length < 3) return;

            // ================================
            // BASE DO FOOTPRINT
            // ================================
            const polygonPositions = ring.flatMap(([lon, lat]) => [lon, lat]);

            footprintEntities.push(
                viewer.entities.add({
                    polygon: {
                        hierarchy: new Cesium.PolygonHierarchy(
                            Cesium.Cartesian3.fromDegreesArray(polygonPositions)
                        ),
                        material: Cesium.Color.ORANGE.withAlpha(0.03),
                        height: 0,
                    }
                })
            );

            // ================================
            // CONE (TRIÂNGULOS)
            // ================================
            for (let i = 0; i < ring.length - 1; i++) {

                const p1 = ring[i];
                const p2 = ring[i + 1];

                const trianglePositions = [
                    satPos,
                    Cesium.Cartesian3.fromDegrees(p1[0], p1[1], 0),
                    Cesium.Cartesian3.fromDegrees(p2[0], p2[1], 0),
                ];

                footprintEntities.push(
                    viewer.entities.add({
                        polygon: {
                            hierarchy: new Cesium.PolygonHierarchy(trianglePositions),
                            material: Cesium.Color.ORANGE.withAlpha(0.05),
                            perPositionHeight: true,
                        }
                    })
                );
            }

        });

    });

    // ================================
    // HUD
    // ================================
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
        console.log("INIT START");

        // Terrain (async)
        viewer.terrainProvider = await Cesium.createWorldTerrainAsync();

        // Imagery (sync!)
        viewer.imageryLayers.removeAll();

        const imagery = await Cesium.IonImageryProvider.fromAssetId(2);
        viewer.imageryLayers.addImageryProvider(imagery);

        console.log("IMAGERY OK");

        // SIMULAÇÃO
        await loadSimulation(profileSelect.value);

        console.log("SIMULATION OK");

    } catch (error) {
        console.error("ERRO NO INIT:", error);
    }
}

init();
