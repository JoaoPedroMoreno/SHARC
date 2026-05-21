Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJlNGFjZjdmZC05N2ZhLTQzY2YtYmVjNC1iZjM4YzA4MWQ2OWYiLCJpZCI6NDE5NTczLCJpYXQiOjE3NzY0MjkyMDJ9.U2I_2yVRqORG1AmQSXtJPBXTfn6PK0fpie_PXFOXr6g";

let brazilPolygons = []; 
let brMinLon = 180, brMaxLon = -180, brMinLat = 90, brMaxLat = -90;

function initBrazilPolygon() {
    const geometry = simulation.brazilGeoJson;

    if (geometry.type === "MultiPolygon") {
        brazilPolygons = geometry.coordinates.map(poly => poly[0]);
    } else {
        brazilPolygons = [geometry.coordinates[0]];
    }

    brazilPolygons.forEach(poly => {
        poly.forEach(([lon, lat]) => {
            if (lon < brMinLon) brMinLon = lon;
            if (lon > brMaxLon) brMaxLon = lon;
            if (lat < brMinLat) brMinLat = lat;
            if (lat > brMaxLat) brMaxLat = lat;
        });
    });
}

function isPointInBrazil(lon, lat) {
    if (lon < brMinLon || lon > brMaxLon || lat < brMinLat || lat > brMaxLat) return false;
    return brazilPolygons.some(poly => isPointInPolygon(lon, lat, poly));
}

function createHexagon(lon, lat, sizeKm) {
    const coords = [];
    const latFactor = 1 / 111;
    const lonFactor = 1 / (111 * Math.cos(lat * Math.PI / 180));

    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i;
        const dLat = sizeKm * Math.sin(angle) * latFactor;
        const dLon = sizeKm * Math.cos(angle) * lonFactor;
        coords.push(lon + dLon, lat + dLat);
    }
    return Cesium.Cartesian3.fromDegreesArray(coords);
}

function isPointInPolygon(lon, lat, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i][0], yi = polygon[i][1];
        const xj = polygon[j][0], yj = polygon[j][1];
        const intersect = ((yi > lat) !== (yj > lat)) && (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi);
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
    requestRenderMode: false,
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
const footprintInfo = document.getElementById("footprintInfo");
const timeInfo = document.getElementById("timeInfo");
const statusText = document.getElementById("statusText");

const globalGridEntities = new Map(); 
const activeCellsThisFrame = []; 
const conePool = []; 

let simulation = null;
let currentFrameIndex = 0;
let isPlaying = false;
let timerId = null;
let satelliteEntities = new Map();
let footprintEntities = [];
let stationEntity = null;
let brazilEntities = [];
let activeConesCount = 0; 

// Variáveis preenchidas pelo Backend
let GLOBAL_HEX_RADIUS_KM = null; 
let GUARDBAND_HEX_COUNT = null; 
let ANTENNA_GAIN_HIGH = null; 
let ANTENNA_GAIN_LOW = null;  

function preBuildGrid() {
    const dxKm = GLOBAL_HEX_RADIUS_KM * 1.5;
    const dyKm = GLOBAL_HEX_RADIUS_KM * Math.sqrt(3);
    const lonFactor = 111 * Math.cos(0); 

    const minLon = -85, maxLon = -30, minLat = -60, maxLat = 15;

    const minCol = Math.floor((minLon * lonFactor) / dxKm);
    const maxCol = Math.ceil((maxLon * lonFactor) / dxKm);
    const minRow = Math.floor((minLat * 111) / dyKm);
    const maxRow = Math.ceil((maxLat * 111) / dyKm);

    const tempBrazilCells = new Map();

    for (let col = minCol; col <= maxCol; col++) {
        for (let row = minRow; row <= maxRow; row++) {
            const offsetX = col * dxKm;
            const offsetY = (row + (col % 2 !== 0 ? 0.5 : 0)) * dyKm; 
            const centerLon = offsetX / lonFactor;
            const centerLat = offsetY / 111;

            if (isPointInBrazil(centerLon, centerLat)) {
                tempBrazilCells.set(`${col}_${row}`, { lon: centerLon, lat: centerLat, col: col, row: row });
            }
        }
    }

    tempBrazilCells.forEach((cell, key) => {
        let isBorder = false;
        const limit = GUARDBAND_HEX_COUNT;
        
        for (let dCol = -limit; dCol <= limit; dCol++) {
            for (let dRow = -limit; dRow <= limit; dRow++) {
                if (Math.abs(dCol) + Math.abs(dRow) <= Math.ceil(limit * 1.33)) {
                    const neighborKey = `${cell.col + dCol}_${cell.row + dRow}`;
                    if (!tempBrazilCells.has(neighborKey)) {
                        isBorder = true;
                        break;
                    }
                }
            }
            if (isBorder) break;
        }

        const entity = viewer.entities.add({
            show: false, 
            polygon: {
                hierarchy: new Cesium.PolygonHierarchy(
                    createHexagon(cell.lon, cell.lat, GLOBAL_HEX_RADIUS_KM)
                ),
                material: isBorder ? Cesium.Color.WHITE.withAlpha(0.6) : Cesium.Color.ORANGE.withAlpha(0.2),
                outline: true,
                outlineColor: isBorder ? Cesium.Color.WHITE : Cesium.Color.ORANGE,
                height: 0,
            }
        });
        globalGridEntities.set(key, entity);
    });
    console.log(`Grade de ${globalGridEntities.size} células pré-construída com sucesso.`);
}

function setStatus(message) {
    statusText.textContent = message;
}

function satelliteColor(isActive) {
    return isActive ? Cesium.Color.fromBytes(0, 255, 0, 255) : Cesium.Color.CYAN.withAlpha(0.9);
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
    
    // Ler as variáveis passadas pelo backend (com valores default caso falte algo no Python)
    GLOBAL_HEX_RADIUS_KM = simulation.meta.beamRadiuskm;
    GUARDBAND_HEX_COUNT = simulation.meta.guardbandHexCount;
    ANTENNA_GAIN_HIGH = simulation.meta.antennaGainHigh;
    ANTENNA_GAIN_LOW = simulation.meta.antennaGainLow;
    footprintInfo.textContent = `${simulation.meta.footprintDiameterKm.toFixed(1)} km`;

    console.log(`Configurações carregadas: Raio = ${GLOBAL_HEX_RADIUS_KM}km, Guardband = ${GUARDBAND_HEX_COUNT} hexs`);

    buildStaticScene();
    buildSatelliteEntities();
    preBuildGrid();
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
            disableDepthTestDistance: Number.POSITIVE_INFINITY 
        },
        label: {
            text: "Estação base",
            font: "13px Segoe UI",
            pixelOffset: new Cesium.Cartesian2(0, -18),
            fillColor: Cesium.Color.WHITE.withAlpha(1.0),
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(1.0),
            disableDepthTestDistance: Number.POSITIVE_INFINITY 
        },
    });

    brazilPolygons.forEach((poly, index) => {
        brazilEntities.push(viewer.entities.add({
            id: `brazil-outline-${index}`,
            polygon: {
                hierarchy: Cesium.Cartesian3.fromDegreesArray(
                    poly.flatMap(([lon, lat]) => [lon, lat])
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

function renderFrame(frameIndex) {
    if (!simulation) return;

    const frame = simulation.frames[frameIndex];

    currentFrameIndex = frameIndex;
    frameSlider.value = String(frameIndex);

    frame.satellites.forEach((satellite) => {
        const entity = satelliteEntities.get(satellite.id);
        if (!entity) return;

        entity.position = Cesium.Cartesian3.fromDegrees(
            satellite.lon,
            satellite.lat,
            satellite.altKm * 1000
        );

        entity.point.color = satellite.active
            ? Cesium.Color.LIME.withAlpha(1.0)
            : Cesium.Color.CYAN.withAlpha(0.9);

        entity.point.pixelSize = satellite.active ? 10 : 6;
    });

    for (let i = 0; i < activeConesCount; i++) {
        if (conePool[i]) conePool[i].show = false;
    }
    activeConesCount = 0; 

    activeCellsThisFrame.forEach(entity => { if (entity) entity.show = false; });
    activeCellsThisFrame.length = 0;

    const dxKm = GLOBAL_HEX_RADIUS_KM * 1.5;
    const dyKm = GLOBAL_HEX_RADIUS_KM * Math.sqrt(3);

    const activeHexagonsMap = new Map();
    const processedRings = []; 
    const satBeamCounts = new Map(); 

    frame.footprints.forEach((footprint) => {
        if (!footprint || !footprint.rings) return;

        const satData = frame.satellites.find(s => s.id === footprint.satelliteId);
        if (!satData) return;
        const satPos = Cesium.Cartesian3.fromDegrees(satData.lon, satData.lat, satData.altKm * 1000);

        let currentSatCount = 0;

        footprint.rings.forEach((ring) => {
            if (!ring || ring.length < 3) return;

            let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
            ring.forEach(([lon, lat]) => {
                if (lon < minLon) minLon = lon;
                if (lon > maxLon) maxLon = lon;
                if (lat < minLat) minLat = lat;
                if (lat > maxLat) maxLat = lat;
            });

            const lonFactor = 111 * Math.cos(0); 

            const minCol = Math.floor((minLon * lonFactor) / dxKm);
            const maxCol = Math.ceil((maxLon * lonFactor) / dxKm);
            const minRow = Math.floor((minLat * 111) / dyKm);
            const maxRow = Math.ceil((maxLat * 111) / dyKm);

            // Variável nova: Conta se ESTE anel iluminou algo
            let ringHexCount = 0; 

            for (let col = minCol; col <= maxCol; col++) {
                for (let row = minRow; row <= maxRow; row++) {
                    
                    const offsetX = col * dxKm;
                    const offsetY = (row + (col % 2 !== 0 ? 0.5 : 0)) * dyKm; 

                    const centerLon = offsetX / lonFactor;
                    const centerLat = offsetY / 111;

                    const cellKey = `${col}_${row}`;

                    if (isPointInPolygon(centerLon, centerLat, ring) && isPointInBrazil(centerLon, centerLat)) {
                        if (!activeHexagonsMap.has(cellKey)) {
                            activeHexagonsMap.set(cellKey, true); 
                            currentSatCount++; 
                            ringHexCount++; // Incrementa se achou hexágono válido
                        }
                    }
                }
            }

            // A MÁGICA AQUI: Só desenha o cone 3D se iluminou > 0 hexágonos!
            if (ringHexCount > 0) {
                const numFaces = 12; 
                const step = Math.max(1, Math.floor(ring.length / numFaces)); 

                for (let i = 0; i < ring.length; i += step) {
                    const p1 = ring[i];
                    const nextIdx = (i + step) % ring.length; 
                    const p2 = ring[nextIdx];

                    let isOverlapping = false;
                    for (let prevRing of processedRings) {
                        if (isPointInPolygon(p1[0], p1[1], prevRing) || isPointInPolygon(p2[0], p2[1], prevRing)) {
                            isOverlapping = true;
                            break;
                        }
                    }

                    if (isOverlapping) continue;

                    const trianglePositions = [
                        satPos,
                        Cesium.Cartesian3.fromDegrees(p1[0], p1[1], 0),
                        Cesium.Cartesian3.fromDegrees(p2[0], p2[1], 0),
                    ];

                    let coneEntity;
                    if (activeConesCount < conePool.length) {
                        coneEntity = conePool[activeConesCount];
                    } else {
                        coneEntity = viewer.entities.add({
                            polygon: {
                                hierarchy: new Cesium.PolygonHierarchy(trianglePositions),
                                material: Cesium.Color.ORANGE.withAlpha(0.04),
                                perPositionHeight: true,
                            },
                            show: false
                        });
                        conePool.push(coneEntity);
                    }

                    coneEntity.polygon.hierarchy = new Cesium.PolygonHierarchy(trianglePositions);
                    coneEntity.show = true;
                    
                    activeConesCount++;
                }
                
                // Marca a área como processada
                processedRings.push(ring);
            }
        });

        satBeamCounts.set(footprint.satelliteId, currentSatCount);
    });

    // ==========================================
    // 4. HEATMAP ESTATÍSTICO (AUTO-AJUSTÁVEL)
    // Sem "números mágicos" - Baseado na distribuição real do tráfego!
    // ==========================================
    
    // Extrai todas as contagens de beams maiores que zero para análise estatística
    const activeCountsList = [];
    satBeamCounts.forEach(count => {
        if (count > 0) activeCountsList.push(count);
    });

    let avgBeams = 0;
    let thresholdRed = 1; // Fallback seguro
    let thresholdYellow = 1;

    // Calcula a Média e o limite Superior (Top 20% mais carregados)
    if (activeCountsList.length > 0) {
        // Ordena do menor para o maior
        activeCountsList.sort((a, b) => a - b);
        
        // Calcula a média da rede
        const sum = activeCountsList.reduce((acc, val) => acc + val, 0);
        avgBeams = sum / activeCountsList.length;

        // Pega o valor de corte para os 20% mais altos (Pico de tráfego)
        const top20PercentIndex = Math.floor(activeCountsList.length * 0.80);
        
        // Se a rede for muito homogênea (todos com carga parecida), a média dita a regra
        thresholdYellow = avgBeams;
        thresholdRed = activeCountsList[top20PercentIndex];

        // Se o valor máximo for muito próximo da média, força um distanciamento visual
        if (thresholdRed <= avgBeams) {
            thresholdRed = avgBeams * 1.5; 
        }
    }

    // Aplica as cores baseadas no desempenho global da rede neste milissegundo
    frame.satellites.forEach((satellite) => {
        const entity = satelliteEntities.get(satellite.id);
        if (!entity) return;

        const count = satBeamCounts.get(satellite.id) || 0;

        if (satellite.active) {
            entity.label.text = String(count);
            entity.label.show = true;
            entity.label.font = "bold 15px monospace";
            
            // O Satélite ganha cor baseado no quão acima da média ele está
            if (count >= thresholdRed && count > 0) {
                entity.label.fillColor = Cesium.Color.RED;    // Alerta: Top 20% da carga da rede
            } else if (count > thresholdYellow && count > 0) {
                entity.label.fillColor = Cesium.Color.YELLOW; // Atenção: Acima da Média
            } else {
                entity.label.fillColor = Cesium.Color.LIME;   // Normal: Abaixo da Média
            }

            entity.label.style = Cesium.LabelStyle.FILL_AND_OUTLINE;
            entity.label.outlineColor = Cesium.Color.BLACK;
            entity.label.outlineWidth = 3;
            entity.label.pixelOffset = new Cesium.Cartesian2(0, -22); 
            entity.label.disableDepthTestDistance = Number.POSITIVE_INFINITY; 
        } else {
            entity.label.show = false;
        }
    });

    viewer.entities.suspendEvents(); 

    activeHexagonsMap.forEach((_, key) => {
        const entity = globalGridEntities.get(key);
        if (entity) {
            entity.show = true;
            activeCellsThisFrame.push(entity); 
        }
    });

    viewer.entities.resumeEvents(); 

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
    if (!simulation) return;
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
    if (isPlaying) stopPlayback();
    else startPlayback();
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
        viewer.terrainProvider = await Cesium.createWorldTerrainAsync();
        viewer.imageryLayers.removeAll();
        const imagery = await Cesium.IonImageryProvider.fromAssetId(2);
        viewer.imageryLayers.addImageryProvider(imagery);
        await loadSimulation(profileSelect.value);
    } catch (error) {
        console.error("ERRO NO INIT:", error);
    }
}

init();
