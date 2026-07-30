Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJlNGFjZjdmZC05N2ZhLTQzY2YtYmVjNC1iZjM4YzA4MWQ2OWYiLCJpZCI6NDE5NTczLCJpYXQiOjE3NzY0MjkyMDJ9.U2I_2yVRqORG1AmQSXtJPBXTfn6PK0fpie_PXFOXr6g";

let brazilPolygons = []; 
let brMinLon = 180, brMaxLon = -180, brMinLat = 90, brMaxLat = -90;

function initBrazilPolygon() {
    const geometry = simulation.brazilGeoJson;

    brazilPolygons = [];
    brMinLon = 180;
    brMaxLon = -180;
    brMinLat = 90;
    brMaxLat = -90;

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
viewer.scene.pickTranslucentDepth = true;

viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(-55, -15, 2_600_000),
});

const hud = document.getElementById("hud");
const hudDrawerToggle = document.getElementById("hudDrawerToggle");
const profileSelect = document.getElementById("profileSelect");
const footprintModeSelect = document.getElementById("footprintModeSelect");
const footprintModeHelp = document.getElementById("footprintModeHelp");
const scenarioSelect = document.getElementById("scenarioSelect");
const scenarioHelp = document.getElementById("scenarioHelp");
const mitigationToggleBtn = document.getElementById("mitigationToggleBtn");
const mitigationHelp = document.getElementById("mitigationHelp");
const azimuthToggleBtn = document.getElementById("azimuthToggleBtn");
const ueDensitySlider = document.getElementById("ueDensitySlider");
const ueDensityInfo = document.getElementById("ueDensityInfo");
const reloadBtn = document.getElementById("reloadBtn");
const playBtn = document.getElementById("playBtn");
const captureBtn = document.getElementById("captureBtn");
const frameSlider = document.getElementById("frameSlider");
const frameInfo = document.getElementById("frameInfo");
const activeCount = document.getElementById("activeCount");
const coverageInfo = document.getElementById("coverageInfo");
const footprintInfo = document.getElementById("footprintInfo");
const timeInfo = document.getElementById("timeInfo");
const statusText = document.getElementById("statusText");
const cellTooltip = document.getElementById("cellTooltip");
let interferenceLegend = document.getElementById("interferenceLegend");

const globalGridEntities = new Map(); 
const globalGridCells = new Map();
let footprintAssignmentCache = new Map();
const activeCellsThisFrame = []; 
const activeCellEntitySet = new Set();
const conePool = []; 
let antenna7dbPreviewEntities = [];

let simulation = null;
let currentFrameIndex = 0;
let isPlaying = false;
let timerId = null;
let satelliteEntities = new Map();
let footprintEntities = [];
let stationEntity = null;
let azimuthVectorEntity = null;
let brazilEntities = [];
let ueEntities = [];
let activeConesCount = 0; 
let activeAntenna7dbPreviewCount = 0;
let currentLinkBudgetScale = null;
let mitigationEnabled = true;
let scenarioWasSelectedByUser = false;
let showAzimuthVector = true;
let ueMaxPerCell = Number(ueDensitySlider?.value || 2);

// Variáveis preenchidas pelo Backend
let GLOBAL_HEX_RADIUS_KM = null; 
let GUARDBAND_HEX_COUNT = null; 
let ANTENNA_GAIN_HIGH = null; 
let ANTENNA_GAIN_LOW = null;  
let POWER_BACKOFF_DB = null;
let MINIMUM_SERVICE_ANGLE_DEG = null;
let ANTENNA_7DB_RADIUS_KM = null;
let ANTENNA_7DB_HIGH_ANGLE_DEG = null;
let ANTENNA_7DB_LOW_ANGLE_DEG = null;
let FOOTPRINT_3DB_RADIUS_KM = null;
let FOOTPRINT_7DB_RADIUS_KM = null;
let SERVICE_FOOTPRINT_DIAMETER_KM = null;
let INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM = null;
let INTERFERENCE_PATH_FOOTPRINT_DIAMETER_KM = null;
let SHARC_INTERFERENCE_PATH_MIN_ELEVATION_DEG = null;
let SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG = null;
let ENABLE_COCHANNEL = false;
let ENABLE_ADJACENT_CHANNEL = false;
let IMT_FREQUENCY_MHZ = null;
let IMT_BANDWIDTH_MHZ = null;
let IMT_CONDUCTED_POWER_DBM = null;
let IMT_BS_OHMIC_LOSS_DB = null;
let IMT_ADJACENT_CH_EMISSIONS = "OFF";
let IMT_ADJACENT_CH_LEAK_RATIO_DB = null;
let SINGLE_EARTH_STATION_GAIN_DB = null;
let SINGLE_EARTH_STATION_FREQUENCY_MHZ = null;
let SINGLE_EARTH_STATION_BANDWIDTH_MHZ = null;
let SINGLE_EARTH_STATION_ADJACENT_CH_RECEPTION = "OFF";
let SINGLE_EARTH_STATION_ADJACENT_CH_SELECTIVITY_DB = null;
let POLARIZATION_LOSS_DB = null;
let ANTENNA_SYSTEM4_HIGH = null;
let ANTENNA_SYSTEM4_LOW = null;
let lastAntenna7dbMaxBeamRadiusKm = 0;
const EARTH_RADIUS_KM = 6371.0;
const FOOTPRINT_MODE_SHARC = "sharc_service_grid";
const FOOTPRINT_MODE_7DB_FIRST = "antenna_7db_first";
const FOOTPRINT_MODE_SHARC_INTERFERENCE_MASK = "sharc_interference_mask";
const FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK = "sharc_interference_link_budget";
const MAX_INTERFERENCE_CANDIDATE_SATELLITES = 72;
const SCENARIO_PARAM_FILES = {
    sa: "sharc/campaigns/02_DC_MSS_to_FS 2/input/dc_mss_to_fs_SouthAmerica_Sys3_340km_FS20m_LF20_EZ0km_Azi90deg.yaml",
    brarg: "sharc/campaigns/02_DC_MSS_to_FS 2/output/output_dc_mss_to_fs_BR_AR_Paraguay_Sys3_340km_FS20m_LF20_M0km_Azi90deg_2026-07-02_01/dc_mss_to_fs_BR_AR_Paraguay_Sys3_340km_FS20m_LF20_M0km_Azi90deg.yaml",
};
const SCENARIO_LABELS = {
    sa: "SA",
    brarg: "BR/ARG",
};
const INACTIVE_SATELLITE_PIXEL_SIZE = 3.5;
const ACTIVE_SATELLITE_PIXEL_SIZE = 10;
const UE_MAX_POINTS = Number.POSITIVE_INFINITY;
const UE_COLOR = Cesium.Color.fromBytes(255, 245, 92, 245);
const UE_SCALE_BY_DISTANCE = new Cesium.NearFarScalar(600_000, 1.0, 7_500_000, 0.12);
const UE_TRANSLUCENCY_BY_DISTANCE = new Cesium.NearFarScalar(600_000, 0.95, 7_500_000, 0.18);
const DEFAULT_BS_AZIMUTH_DEG = 90;
const BS_AZIMUTH_VECTOR_LENGTH_KM = 420;
const ANTENNA_7DB_SECTOR_STEP_DB = 2;
const ANTENNA_7DB_SECTOR_COLORS = [
    Cesium.Color.fromBytes(126, 211, 33, 185),
    Cesium.Color.fromBytes(242, 205, 59, 185),
    Cesium.Color.fromBytes(245, 166, 35, 185),
    Cesium.Color.fromBytes(208, 76, 45, 185),
];
const SHARC_INTERFERENCE_COLORS = [
    Cesium.Color.fromBytes(26, 83, 255, 175),
    Cesium.Color.fromBytes(0, 196, 190, 180),
    Cesium.Color.fromBytes(126, 211, 33, 185),
    Cesium.Color.fromBytes(245, 166, 35, 190),
    Cesium.Color.fromBytes(215, 25, 28, 195),
];
const SHARC_LINK_BUDGET_COLORS = [
    { css: "#16324f", color: Cesium.Color.fromBytes(22, 50, 79, 185) },
    { css: "#2f728f", color: Cesium.Color.fromBytes(47, 114, 143, 185) },
    { css: "#d6a547", color: Cesium.Color.fromBytes(214, 165, 71, 190) },
    { css: "#b9473b", color: Cesium.Color.fromBytes(185, 71, 59, 200) },
];
const PRESENTATION_CONE_FACES = 18;
const PRESENTATION_CONE_MAX_SATELLITES = 220;
const PRESENTATION_CONE_MATERIAL = Cesium.Color.fromBytes(255, 184, 74, 14);
const PRESENTATION_CONE_OUTLINE = Cesium.Color.fromBytes(255, 232, 151, 42);
const PRESENTATION_STATION_GRID_RADIUS_KM = 180;

function serviceAreaCountryNames() {
    return simulation?.meta?.serviceAreaCountryNames || [];
}

function isBrArgServiceArea() {
    const names = serviceAreaCountryNames().map((name) => name.toLowerCase());
    return names.includes("brazil") && names.includes("argentina") && names.length <= 3;
}

function isSouthAmericaServiceArea() {
    return !isBrArgServiceArea() && serviceAreaCountryNames().length > 2;
}

function selectedScenario() {
    return scenarioSelect?.value || "sa";
}

function selectedScenarioParamFile() {
    return SCENARIO_PARAM_FILES[selectedScenario()] || SCENARIO_PARAM_FILES.sa;
}

function isBrArgScenario() {
    return selectedScenario() === "brarg" || isBrArgServiceArea();
}

function isSouthAmericaScenario() {
    return selectedScenario() === "sa" || isSouthAmericaServiceArea();
}

function powerBackoffMitigationApplies() {
    return mitigationEnabled && isBrArgScenario();
}

function exclusionZoneMitigationApplies() {
    return mitigationEnabled && isSouthAmericaScenario() && !isBrArgScenario();
}

function shouldExcludeCellByMitigation(cell) {
    return exclusionZoneMitigationApplies() && Boolean(cell?.isNearStation);
}

function exclusionZoneGridStyle() {
    return {
        material: Cesium.Color.WHITE.withAlpha(0.0),
        outlineColor: Cesium.Color.WHITE.withAlpha(0.96),
    };
}

function updateMitigationControls() {
    const scenario = selectedScenario();
    const method = scenario === "brarg" ? "power back-off nas celulas de fronteira" : "zona de exclusao ao redor da estacao";

    if (scenarioHelp) {
        scenarioHelp.textContent = scenario === "brarg"
            ? "Usa o cenario BR/ARG do campaign 02_DC_MSS_to_FS."
            : "Usa o cenario South America do campaign 02_DC_MSS_to_FS.";
    }

    if (mitigationToggleBtn) {
        mitigationToggleBtn.textContent = mitigationEnabled ? "Ativada" : "Desativada";
        mitigationToggleBtn.classList.toggle("is-active", mitigationEnabled);
        mitigationToggleBtn.title = `${mitigationEnabled ? "Desativa" : "Ativa"} ${method}.`;
    }

    if (mitigationHelp) {
        mitigationHelp.textContent = mitigationEnabled
            ? `Mitigacao ativa: ${method}.`
            : `Mitigacao desligada: ${method} ignorado.`;
    }
}

function updateAzimuthToggleControl() {
    if (!azimuthToggleBtn) return;

    azimuthToggleBtn.textContent = showAzimuthVector ? "Vetor ativo" : "Vetor oculto";
    azimuthToggleBtn.classList.toggle("is-active", showAzimuthVector);
    azimuthToggleBtn.title = showAzimuthVector
        ? "Ocultar vetor de azimute da antena FS/BS."
        : "Mostrar vetor de azimute da antena FS/BS.";
}

function updateUeDensityControl() {
    if (ueDensityInfo) {
        ueDensityInfo.textContent = String(ueMaxPerCell);
    }
}

function distanceKmBetween(lon1, lat1, lon2, lat2) {
    const toRad = Math.PI / 180;
    const dLat = (lat2 - lat1) * toRad;
    const dLon = (lon2 - lon1) * toRad;
    const a = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

function isNearPresentationStation(cell) {
    if (!isSouthAmericaScenario() || !simulation?.station) {
        return false;
    }

    return distanceKmBetween(
        cell.lon,
        cell.lat,
        simulation.station.lon,
        simulation.station.lat
    ) <= PRESENTATION_STATION_GRID_RADIUS_KM;
}

function gridCellStyle(isBorder, isNearStation, { showPowerBackoffBorder = true } = {}) {
    if (isBrArgScenario() && isBorder && showPowerBackoffBorder) {
        return {
            material: Cesium.Color.WHITE.withAlpha(0.34),
            outlineColor: Cesium.Color.WHITE.withAlpha(0.95),
        };
    }

    if (exclusionZoneMitigationApplies() && isNearStation) {
        return {
            material: Cesium.Color.RED.withAlpha(0.22),
            outlineColor: Cesium.Color.RED.withAlpha(0.95),
        };
    }

    return {
        material: Cesium.Color.ORANGE.withAlpha(0.16),
        outlineColor: Cesium.Color.ORANGE.withAlpha(0.58),
    };
}

function preBuildGrid() {
    globalGridEntities.forEach((entity) => viewer.entities.remove(entity));
    globalGridEntities.clear();
    globalGridCells.clear();
    activeCellsThisFrame.length = 0;
    activeCellEntitySet.clear();

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
        const limit = Math.max(1, Math.ceil(Number(GUARDBAND_HEX_COUNT) || 0));
        
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

        const isNearStation = isNearPresentationStation(cell);
        const style = gridCellStyle(isBorder, isNearStation);

        const entity = viewer.entities.add({
            show: false, 
            polygon: {
                hierarchy: new Cesium.PolygonHierarchy(
                    createHexagon(cell.lon, cell.lat, GLOBAL_HEX_RADIUS_KM)
                ),
                material: style.material,
                outline: true,
                outlineColor: style.outlineColor,
                height: 0,
            }
        });
        entity.gridCellKey = key;
        entity.gridCellIsBorder = isBorder;
        entity.gridCellNearStation = isNearStation;
        globalGridEntities.set(key, entity);
        globalGridCells.set(key, {
            lon: cell.lon,
            lat: cell.lat,
            isBorder,
            isNearStation,
        });
    });
    console.log(`Grade de ${globalGridEntities.size} células pré-construída com sucesso.`);
}

function baseGridMaterial(isBorder, { showPowerBackoffBorder = true } = {}) {
    return gridCellStyle(isBorder, false, { showPowerBackoffBorder }).material;
}

function resetGridCellEntity(entity) {
    entity.show = false;
    const style = gridCellStyle(entity.gridCellIsBorder, entity.gridCellNearStation, {
        showPowerBackoffBorder: powerBackoffMitigationApplies(),
    });
    entity.polygon.material = style.material;
    entity.polygon.outlineColor = style.outlineColor;
    entity.gridCellSatelliteId = undefined;
    entity.gridCellElevationDeg = undefined;
    entity.gridCellElevationThresholdDeg = undefined;
    entity.gridCellInterferenceDbm = undefined;
    entity.gridCellCouplingLossDb = undefined;
    entity.gridCellTxGainDb = undefined;
    entity.gridCellRxGainDb = undefined;
    entity.gridCellPowerBackoffDb = undefined;
    entity.gridCellEffectivePowerDbm = undefined;
    entity.gridCellScenarioTxPowerDbm = undefined;
    entity.gridCellPathLossDb = undefined;
    entity.gridCellDistanceKm = undefined;
    entity.gridCellExcludedZone = undefined;
}

function applyFixedGridAssignment(entity, assignment) {
    const details = typeof assignment === "object" && assignment !== null
        ? assignment
        : { satelliteId: assignment };
    const isServiceGridMode = footprintModeSelect.value === FOOTPRINT_MODE_SHARC;
    const style = gridCellStyle(
        entity.gridCellIsBorder,
        entity.gridCellNearStation,
        { showPowerBackoffBorder: isServiceGridMode && powerBackoffMitigationApplies() }
    );
    const excludedStyle = details.isExcludedZone ? exclusionZoneGridStyle() : null;
    entity.polygon.material = excludedStyle?.material || details.heatmapColor || style.material;
    entity.polygon.outlineColor = excludedStyle?.outlineColor || style.outlineColor;
    entity.gridCellSatelliteId = details.satelliteId;
    entity.gridCellElevationDeg = details.elevationDeg;
    entity.gridCellElevationThresholdDeg = details.elevationThresholdDeg;
    entity.gridCellInterferenceDbm = details.interferenceDbm;
    entity.gridCellCouplingLossDb = details.couplingLossDb;
    entity.gridCellTxGainDb = details.txGainDb;
    entity.gridCellRxGainDb = details.rxGainDb;
    entity.gridCellPowerBackoffDb = details.powerBackoffDb;
    entity.gridCellEffectivePowerDbm = details.effectivePowerDbm;
    entity.gridCellScenarioTxPowerDbm = details.scenarioTxPowerDbm;
    entity.gridCellPathLossDb = details.pathLossDb;
    entity.gridCellDistanceKm = details.distanceKm;
    entity.gridCellExcludedZone = Boolean(details.isExcludedZone);
}

function setStatus(message) {
    statusText.textContent = message;
}

function satelliteColor(isActive) {
    return isActive ? Cesium.Color.fromBytes(0, 255, 0, 255) : Cesium.Color.CYAN.withAlpha(0.58);
}

function hideCellTooltip() {
    cellTooltip.style.display = "none";
    cellTooltip.setAttribute("aria-hidden", "true");
}

function isAntenna7dbPreviewMode() {
    return footprintModeSelect.value === FOOTPRINT_MODE_7DB_FIRST;
}

function isSharcInterferenceMode() {
    return footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_MASK
        || footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK;
}

function isDynamicFootprintMode() {
    return isAntenna7dbPreviewMode();
}

function isPresentationProfile() {
    return simulation?.meta?.profile === "presentation";
}

function formatKm(value) {
    return Number.isFinite(value) ? `${value.toFixed(1)} km` : "km indisponivel";
}

function getFootprintModeDescription(mode = footprintModeSelect.value) {
    const serviceAngle = Number.isFinite(MINIMUM_SERVICE_ANGLE_DEG)
        ? `${MINIMUM_SERVICE_ANGLE_DEG.toFixed(1)}°`
        : "minimum_service_angle";
    const activeElevation = Number.isFinite(SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG)
        ? `${SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG.toFixed(1)}°`
        : "minimum_elevation_from_es";

    if (mode === FOOTPRINT_MODE_7DB_FIRST) {
        return "Preview do primeiro satelite: divide o feixe por perda de ganho de antena em setores de 2 dB e mantem a contagem de hexagonos para comparar com o footprint 7 dB.";
    }
    if (mode === FOOTPRINT_MODE_SHARC_INTERFERENCE_MASK) {
        return `Mascara de interferencia: mostra celulas elegiveis por visibilidade usando elevacao >= ${activeElevation}, separada da grade de servico.`;
    }
    if (mode === FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK) {
        return "Link budget de interferencia: estima intensidade por celula com ganho S.1528, perda de espaco livre, perdas do cenario e potencia configurada.";
    }
    return `Grade de servico SHARC: mostra celulas na area de servico que poderiam ser atendidas por satelite com elevacao >= ${serviceAngle}.`;
}

function updateFootprintModeHelp() {
    const description = getFootprintModeDescription();
    if (footprintModeHelp) {
        footprintModeHelp.textContent = description;
    }
    footprintModeSelect.title = description;
    updateInterferenceLegend();
}

function ensureInterferenceLegend() {
    if (!interferenceLegend) {
        interferenceLegend = document.createElement("aside");
        interferenceLegend.id = "interferenceLegend";
        interferenceLegend.className = "legend-panel";
        interferenceLegend.setAttribute("aria-hidden", "true");
        document.body.appendChild(interferenceLegend);
    }

    Object.assign(interferenceLegend.style, {
        position: "fixed",
        top: "18px",
        right: "18px",
        left: "auto",
        bottom: "auto",
        zIndex: "2147483647",
        width: "260px",
        pointerEvents: "none",
    });

    return interferenceLegend;
}

function updateInterferenceLegend(scale = currentLinkBudgetScale) {
    const legend = ensureInterferenceLegend();

    if (footprintModeSelect.value !== FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK) {
        legend.classList.remove("is-visible");
        legend.style.display = "none";
        legend.setAttribute("aria-hidden", "true");
        return;
    }

    const sectors = scale?.length ? scale : buildDefaultLinkBudgetScale();
    legend.innerHTML = `
        <div class="legend-title">Link budget recebido</div>
        ${sectors.map((sector) => `
            <div class="legend-row" style="display:flex;align-items:center;gap:10px;padding:4px 0;color:white;font-size:13px;line-height:1.2;">
                <span style="display:inline-block;flex:0 0 auto;width:22px;height:13px;border-radius:3px;background-color:${sector.css};border:1px solid rgba(255,255,255,0.45);box-shadow:0 0 8px rgba(0,0,0,0.35);"></span>
                <span style="display:inline-block;white-space:nowrap;">${sector.label}</span>
            </div>
        `).join("")}
    `;
    legend.classList.add("is-visible");
    legend.style.display = "block";
    legend.style.visibility = "visible";
    legend.style.opacity = "1";
    legend.setAttribute("aria-hidden", "false");
}

function showCellTooltip(position, entity) {
    if (entity.gridCellExcludedZone) {
        const elevationText = Number.isFinite(entity.gridCellElevationDeg)
            ? `${entity.gridCellElevationDeg.toFixed(2)}Â°`
            : "indisponivel";
        const distanceText = Number.isFinite(entity.gridCellDistanceKm)
            ? `${entity.gridCellDistanceKm.toFixed(1)} km`
            : "dentro da zona";

        cellTooltip.innerHTML = `
            <div class="tooltip-title">Zona de exclusao</div>
            <div class="tooltip-row"><span>Estado</span><strong>Celula removida da grade ativa</strong></div>
            <div class="tooltip-row"><span>Satelite</span><strong>${entity.gridCellSatelliteId || "n/a"}</strong></div>
            <div class="tooltip-row"><span>Elevacao</span><strong>${elevationText}</strong></div>
            <div class="tooltip-row"><span>Distancia FS</span><strong>${distanceText}</strong></div>
        `;
        cellTooltip.style.left = `${Math.min(position.x + 16, window.innerWidth - 310)}px`;
        cellTooltip.style.top = `${Math.min(position.y + 16, window.innerHeight - 180)}px`;
        cellTooltip.style.display = "block";
        cellTooltip.setAttribute("aria-hidden", "false");
        setStatus("Zona de exclusao: celula visualizada sem preenchimento, mas removida da grade ativa do SHARC.");
        return;
    }

    if (Number.isFinite(entity.gridCellInterferenceDbm)) {
        const interferenceText = `${entity.gridCellInterferenceDbm.toFixed(1)} dBm`;
        const couplingText = Number.isFinite(entity.gridCellCouplingLossDb)
            ? `${entity.gridCellCouplingLossDb.toFixed(1)} dB`
            : "indisponível";
        const elevationText = Number.isFinite(entity.gridCellElevationDeg)
            ? `${entity.gridCellElevationDeg.toFixed(2)}°`
            : "indisponível";
        const txGainText = Number.isFinite(entity.gridCellTxGainDb)
            ? `${entity.gridCellTxGainDb.toFixed(1)} dBi`
            : "indisponível";
        const rxGainText = Number.isFinite(entity.gridCellRxGainDb)
            ? `${entity.gridCellRxGainDb.toFixed(1)} dBi`
            : "indisponível";
        const pathLossText = Number.isFinite(entity.gridCellPathLossDb)
            ? `${entity.gridCellPathLossDb.toFixed(1)} dB`
            : "indisponível";
        const powerBackoffText = Number.isFinite(entity.gridCellPowerBackoffDb)
            ? `${entity.gridCellPowerBackoffDb.toFixed(1)} dB`
            : "indisponível";
        const effectivePowerText = Number.isFinite(entity.gridCellEffectivePowerDbm)
            ? `${entity.gridCellEffectivePowerDbm.toFixed(1)} dBm`
            : "indisponível";
        const scenarioPowerText = Number.isFinite(entity.gridCellScenarioTxPowerDbm)
            ? `${entity.gridCellScenarioTxPowerDbm.toFixed(1)} dBm`
            : "indisponível";
        const distanceText = Number.isFinite(entity.gridCellDistanceKm)
            ? `${entity.gridCellDistanceKm.toFixed(1)} km`
            : "indisponível";

        cellTooltip.innerHTML = `
            <div class="tooltip-title">SHARC link budget</div>
            <div class="tooltip-row"><span>Interferência</span><strong>${interferenceText}</strong></div>
            <div class="tooltip-row"><span>Satélite dominante</span><strong>${entity.gridCellSatelliteId || "n/a"}</strong></div>
            <div class="tooltip-row"><span>Elevação</span><strong>${elevationText}</strong></div>
            <div class="tooltip-row"><span>G_tx MSS</span><strong>${txGainText}</strong></div>
            <div class="tooltip-row"><span>G_rx ES</span><strong>${rxGainText}</strong></div>
            <div class="tooltip-row"><span>Power back-off</span><strong>${powerBackoffText}</strong></div>
            <div class="tooltip-row"><span>Potência efetiva</span><strong>${effectivePowerText}</strong></div>
            <div class="tooltip-row"><span>Potência cenário</span><strong>${scenarioPowerText}</strong></div>
            <div class="tooltip-row"><span>Path loss</span><strong>${pathLossText}</strong></div>
            <div class="tooltip-row"><span>Coupling loss</span><strong>${couplingText}</strong></div>
            <div class="tooltip-row"><span>Distância</span><strong>${distanceText}</strong></div>
        `;
        cellTooltip.style.left = `${Math.min(position.x + 16, window.innerWidth - 310)}px`;
        cellTooltip.style.top = `${Math.min(position.y + 16, window.innerHeight - 270)}px`;
        cellTooltip.style.display = "block";
        cellTooltip.setAttribute("aria-hidden", "false");
        setStatus(`Interferência: ${interferenceText} | ${entity.gridCellSatelliteId || "satélite"}`);
        return;
    }

    if (Number.isFinite(entity.gridCellElevationDeg)) {
        const elevationText = `${entity.gridCellElevationDeg.toFixed(2)}°`;
        const thresholdText = Number.isFinite(entity.gridCellElevationThresholdDeg)
            ? `${entity.gridCellElevationThresholdDeg.toFixed(1)}°`
            : "indisponível";

        cellTooltip.innerHTML = `
            <div class="tooltip-title">SHARC máscara</div>
            <div class="tooltip-row"><span>Satélite dominante</span><strong>${entity.gridCellSatelliteId || "n/a"}</strong></div>
            <div class="tooltip-row"><span>Elevação</span><strong>${elevationText}</strong></div>
            <div class="tooltip-row"><span>Limiar do cenário</span><strong>${thresholdText}</strong></div>
            <div class="tooltip-row"><span>Critério</span><strong>caminho ativo</strong></div>
        `;
        cellTooltip.style.left = `${Math.min(position.x + 16, window.innerWidth - 310)}px`;
        cellTooltip.style.top = `${Math.min(position.y + 16, window.innerHeight - 160)}px`;
        cellTooltip.style.display = "block";
        cellTooltip.setAttribute("aria-hidden", "false");
        setStatus(`Máscara SHARC: elevação ${elevationText}`);
        return;
    }

    if (Number.isFinite(entity.gridCellGainDb)) {
        const gainText = `${entity.gridCellGainDb.toFixed(1)} dBi`;
        const gainDropText = Number.isFinite(entity.gridCellGainDropDb)
            ? `${entity.gridCellGainDropDb.toFixed(1)} dB`
            : "indisponível";
        const angleText = Number.isFinite(entity.gridCellOffAxisAngleDeg)
            ? `${entity.gridCellOffAxisAngleDeg.toFixed(2)}°`
            : "indisponível";
        const distanceText = Number.isFinite(entity.gridCellDistanceKm)
            ? `${entity.gridCellDistanceKm.toFixed(1)} km`
            : "indisponível";
        const footprintText = Number.isFinite(entity.gridCellFootprintDiameterKm)
            ? `${entity.gridCellFootprintDiameterKm.toFixed(1)} km`
            : "indisponível";
        const sectorText = entity.gridCellGainSector || "indisponível";
        const beamRadiusText = Number.isFinite(entity.gridCellBeamRadiusKm)
            ? `${entity.gridCellBeamRadiusKm.toFixed(1)} km`
            : "indisponível";
        const message = `Ganho: ${gainText} | Queda: ${gainDropText} | Ângulo off-axis: ${angleText}`;

        cellTooltip.innerHTML = `
            <div class="tooltip-title">Célula 7 dB</div>
            <div class="tooltip-row"><span>Ganho</span><strong>${gainText}</strong></div>
            <div class="tooltip-row"><span>Setor</span><strong>${sectorText}</strong></div>
            <div class="tooltip-row"><span>Queda relativa</span><strong>${gainDropText}</strong></div>
            <div class="tooltip-row"><span>Ângulo off-axis</span><strong>${angleText}</strong></div>
            <div class="tooltip-row"><span>Raio do hex</span><strong>${beamRadiusText}</strong></div>
            <div class="tooltip-row"><span>Distância ao nadir</span><strong>${distanceText}</strong></div>
            <div class="tooltip-row"><span>Footprint total</span><strong>${footprintText}</strong></div>
        `;
        cellTooltip.style.left = `${Math.min(position.x + 16, window.innerWidth - 310)}px`;
        cellTooltip.style.top = `${Math.min(position.y + 16, window.innerHeight - 180)}px`;
        cellTooltip.style.display = "block";
        cellTooltip.setAttribute("aria-hidden", "false");
        setStatus(message);
        return;
    }

    const isPowerBackoffCell = powerBackoffMitigationApplies() && Boolean(entity.gridCellIsBorder);
    const gain = isPowerBackoffCell ? ANTENNA_GAIN_LOW : ANTENNA_GAIN_HIGH;
    const gainText = Number.isFinite(gain) ? `${gain.toFixed(1)} dBi` : "indisponível";
    const message = isPowerBackoffCell
        ? `Ganho: ${gainText} | Power back-off aplicado na fronteira`
        : `Ganho: ${gainText}`;

    cellTooltip.innerHTML = isPowerBackoffCell
        ? `<strong>Ganho:</strong> ${gainText}\nPower back-off aplicado na fronteira`
        : `<strong>Ganho:</strong> ${gainText}`;
    cellTooltip.style.left = `${position.x + 14}px`;
    cellTooltip.style.top = `${position.y + 14}px`;
    cellTooltip.style.display = "block";
    cellTooltip.setAttribute("aria-hidden", "false");
    setStatus(message);
}

function getActiveCellEntityFromPick(position) {
    const picks = viewer.scene.drillPick(position);
    const picked = picks.find((candidate) => (
        candidate
        && candidate.id
        && candidate.id.gridCellKey
        && activeCellEntitySet.has(candidate.id)
    ));

    return picked && picked.id;
}

function getLonLatFromScreenPosition(position) {
    const ray = viewer.camera.getPickRay(position);
    const cartesian = ray && viewer.scene.globe.pick(ray, viewer.scene);
    const fallbackCartesian = cartesian || viewer.camera.pickEllipsoid(
        position,
        viewer.scene.globe.ellipsoid
    );
    if (!fallbackCartesian) return null;

    const cartographic = Cesium.Cartographic.fromCartesian(fallbackCartesian);
    return {
        lon: Cesium.Math.toDegrees(cartographic.longitude),
        lat: Cesium.Math.toDegrees(cartographic.latitude),
    };
}

function approximateDistanceKm(a, b) {
    const latMean = ((a.lat + b.lat) / 2) * Math.PI / 180;
    const dx = (a.lon - b.lon) * 111 * Math.cos(latMean);
    const dy = (a.lat - b.lat) * 111;
    return Math.sqrt(dx * dx + dy * dy);
}

function greatCircleDistanceKm(a, b) {
    const lat1 = a.lat * Math.PI / 180;
    const lat2 = b.lat * Math.PI / 180;
    const dLat = lat2 - lat1;
    const dLon = (b.lon - a.lon) * Math.PI / 180;
    const hav = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;

    return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(Math.min(1, hav)));
}

function destinationFromOffsetKm(origin, eastKm, northKm) {
    const distanceKm = Math.sqrt(eastKm * eastKm + northKm * northKm);
    if (distanceKm === 0) return { lon: origin.lon, lat: origin.lat };

    const angularDistance = distanceKm / EARTH_RADIUS_KM;
    const bearing = Math.atan2(eastKm, northKm);
    const lat1 = origin.lat * Math.PI / 180;
    const lon1 = origin.lon * Math.PI / 180;
    const lat2 = Math.asin(
        Math.sin(lat1) * Math.cos(angularDistance)
        + Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearing)
    );
    const lon2 = lon1 + Math.atan2(
        Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(lat1),
        Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2)
    );

    return {
        lon: ((lon2 * 180 / Math.PI + 540) % 360) - 180,
        lat: lat2 * 180 / Math.PI,
    };
}

function destinationFromAzimuthKm(origin, azimuthDeg, distanceKm) {
    // SHARC usa o plano local ENU com azimute 0 deg no eixo +x (leste)
    // e 90 deg no eixo +y (norte). Esta conversao replica essa convencao.
    const azimuthRad = azimuthDeg * Math.PI / 180;
    return destinationFromOffsetKm(
        origin,
        Math.cos(azimuthRad) * distanceKm,
        Math.sin(azimuthRad) * distanceKm
    );
}

function updateAzimuthVector() {
    if (!simulation?.station) return;

    const station = simulation.station;
    const azimuthDeg = Number.isFinite(simulation.meta?.bsAzimuthDeg)
        ? simulation.meta.bsAzimuthDeg
        : DEFAULT_BS_AZIMUTH_DEG;
    const endPoint = destinationFromAzimuthKm(station, azimuthDeg, BS_AZIMUTH_VECTOR_LENGTH_KM);
    const positions = Cesium.Cartesian3.fromDegreesArrayHeights([
        station.lon,
        station.lat,
        Math.max(20, station.altKm * 1000 + 20),
        endPoint.lon,
        endPoint.lat,
        20,
    ]);

    if (!azimuthVectorEntity) {
        azimuthVectorEntity = viewer.entities.add({
            id: "bs-azimuth-vector",
            position: Cesium.Cartesian3.fromDegrees(endPoint.lon, endPoint.lat, 20),
            polyline: {
                positions,
                width: 10,
                material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.RED.withAlpha(0.92)),
                clampToGround: false,
            },
            label: {
                text: `Az ${azimuthDeg.toFixed(0)} deg`,
                font: "bold 13px Segoe UI",
                fillColor: Cesium.Color.RED,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 3,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                showBackground: true,
                backgroundColor: Cesium.Color.BLACK.withAlpha(0.65),
                pixelOffset: new Cesium.Cartesian2(0, -14),
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
        });
    } else {
        azimuthVectorEntity.polyline.positions = positions;
        azimuthVectorEntity.position = Cesium.Cartesian3.fromDegrees(endPoint.lon, endPoint.lat, 20);
        azimuthVectorEntity.label.text = `Az ${azimuthDeg.toFixed(0)} deg`;
    }

    azimuthVectorEntity.show = showAzimuthVector;
    updateAzimuthToggleControl();
}

function hashString(value) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index++) {
        hash ^= value.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
}

function randomUnit(seed) {
    const value = Math.sin(seed * 12.9898) * 43758.5453;
    return value - Math.floor(value);
}

function hideUnusedUeEntities(startIndex) {
    for (let index = startIndex; index < ueEntities.length; index++) {
        if (ueEntities[index]) ueEntities[index].show = false;
    }
}

function renderRandomUesForActiveCells() {
    let ueIndex = 0;
    const jitterRadiusKm = Math.max(1, GLOBAL_HEX_RADIUS_KM * 0.45);

    for (const entity of activeCellsThisFrame) {
        if (ueIndex >= UE_MAX_POINTS) break;
        if (!entity?.gridCellKey) continue;

        const cell = globalGridCells.get(entity.gridCellKey);
        if (!cell || shouldExcludeCellByMitigation(cell)) continue;

        const seed = hashString(`${selectedScenario()}:${entity.gridCellKey}`);
        const density = Math.max(1, Math.min(5, Math.round(ueMaxPerCell)));
        const extraProbability = Math.min(0.95, 0.18 + Math.max(0, density - 2) * 0.18);
        const rawExtraCount = Math.floor(randomUnit(seed) * density);
        const ueCount = density === 1
            ? 1
            : 1 + Math.min(density - 1, randomUnit(seed + 53) < extraProbability ? rawExtraCount : 0);

        for (let cellUeIndex = 0; cellUeIndex < ueCount; cellUeIndex++) {
            if (ueIndex >= UE_MAX_POINTS) break;

            const ueSeed = seed + 97 * (cellUeIndex + 1);
            const angle = randomUnit(ueSeed + 17) * 2 * Math.PI;
            const distanceKm = Math.sqrt(randomUnit(ueSeed + 31)) * jitterRadiusKm;
            const point = destinationFromOffsetKm(
                cell,
                Math.cos(angle) * distanceKm,
                Math.sin(angle) * distanceKm
            );

            let ueEntity = ueEntities[ueIndex];
            const position = Cesium.Cartesian3.fromDegrees(point.lon, point.lat, 35);

            if (!ueEntity) {
                ueEntity = viewer.entities.add({
                    position,
                    point: {
                        pixelSize: 8.0,
                        color: UE_COLOR,
                        outlineColor: Cesium.Color.BLACK.withAlpha(0.7),
                        outlineWidth: 1.0,
                        scaleByDistance: UE_SCALE_BY_DISTANCE,
                        translucencyByDistance: UE_TRANSLUCENCY_BY_DISTANCE,
                        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                    },
                });
                ueEntities.push(ueEntity);
            } else {
                ueEntity.position = position;
                ueEntity.point.scaleByDistance = UE_SCALE_BY_DISTANCE;
                ueEntity.point.translucencyByDistance = UE_TRANSLUCENCY_BY_DISTANCE;
            }

            ueEntity.show = true;
            ueIndex += 1;
        }
    }

    hideUnusedUeEntities(ueIndex);
}

function lonLatToVectorKm(point, radiusKm = EARTH_RADIUS_KM) {
    const lat = point.lat * Math.PI / 180;
    const lon = point.lon * Math.PI / 180;
    return {
        x: radiusKm * Math.cos(lat) * Math.cos(lon),
        y: radiusKm * Math.cos(lat) * Math.sin(lon),
        z: radiusKm * Math.sin(lat),
    };
}

function vectorToLonLat(vector) {
    const radius = Math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z);
    return {
        lon: Math.atan2(vector.y, vector.x) * 180 / Math.PI,
        lat: Math.asin(vector.z / radius) * 180 / Math.PI,
    };
}

function dotVector(a, b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

function crossVector(a, b) {
    return {
        x: a.y * b.z - a.z * b.y,
        y: a.z * b.x - a.x * b.z,
        z: a.x * b.y - a.y * b.x,
    };
}

function scaleVector(vector, scale) {
    return {
        x: vector.x * scale,
        y: vector.y * scale,
        z: vector.z * scale,
    };
}

function addVector(a, b) {
    return {
        x: a.x + b.x,
        y: a.y + b.y,
        z: a.z + b.z,
    };
}

function subtractVector(a, b) {
    return {
        x: a.x - b.x,
        y: a.y - b.y,
        z: a.z - b.z,
    };
}

function normalizeVector(vector) {
    const norm = Math.sqrt(dotVector(vector, vector));
    return scaleVector(vector, 1 / norm);
}

function tangentBasis(axis) {
    let reference = { x: 0, y: 0, z: 1 };
    if (Math.abs(dotVector(axis, reference)) > 0.95) {
        reference = { x: 0, y: 1, z: 0 };
    }

    const tangent1 = normalizeVector(crossVector(axis, reference));
    const tangent2 = normalizeVector(crossVector(axis, tangent1));
    return { tangent1, tangent2 };
}

function raySphereIntersection(origin, direction, radiusKm = EARTH_RADIUS_KM) {
    const b = 2 * dotVector(origin, direction);
    const c = dotVector(origin, origin) - radiusKm * radiusKm;
    const discriminant = b * b - 4 * c;
    if (discriminant < 0) return null;

    const root = Math.sqrt(discriminant);
    const candidates = [(-b - root) / 2, (-b + root) / 2].filter((value) => value > 0);
    if (candidates.length === 0) return null;

    return addVector(origin, scaleVector(direction, Math.min(...candidates)));
}

function calculate7dbBeamRadiusKm(satellite, center) {
    const halfAngleDeg = Math.max(ANTENNA_7DB_HIGH_ANGLE_DEG, ANTENNA_7DB_LOW_ANGLE_DEG);
    const halfAngleRad = halfAngleDeg * Math.PI / 180;
    const satVector = lonLatToVectorKm(
        { lon: satellite.lon, lat: satellite.lat },
        EARTH_RADIUS_KM + satellite.altKm
    );
    const centerVector = lonLatToVectorKm(center);
    const axis = normalizeVector(subtractVector(centerVector, satVector));
    const { tangent1, tangent2 } = tangentBasis(axis);
    let maxRadiusKm = 0;
    const samples = 8;

    for (let i = 0; i < samples; i++) {
        const angle = i * 2 * Math.PI / samples;
        const direction = normalizeVector(addVector(
            scaleVector(axis, Math.cos(halfAngleRad)),
            addVector(
                scaleVector(tangent1, Math.sin(halfAngleRad) * Math.cos(angle)),
                scaleVector(tangent2, Math.sin(halfAngleRad) * Math.sin(angle))
            )
        ));
        const edgeVector = raySphereIntersection(satVector, direction);
        if (!edgeVector) continue;

        const edgePoint = vectorToLonLat(edgeVector);
        maxRadiusKm = Math.max(maxRadiusKm, greatCircleDistanceKm(center, edgePoint));
    }

    return maxRadiusKm || GLOBAL_HEX_RADIUS_KM;
}

function getActiveCellEntityFromGeography(position) {
    const lonLat = getLonLatFromScreenPosition(position);
    if (!lonLat) return null;

    let closestEntity = null;
    let closestDistanceKm = Number.POSITIVE_INFINITY;
    activeCellEntitySet.forEach((entity) => {
        const cell = globalGridCells.get(entity.gridCellKey) || (
            Number.isFinite(entity.gridCellLon) && Number.isFinite(entity.gridCellLat)
                ? { lon: entity.gridCellLon, lat: entity.gridCellLat }
                : null
        );
        if (!cell) return;

        const distanceKm = approximateDistanceKm(lonLat, cell);
        if (distanceKm < closestDistanceKm) {
            closestDistanceKm = distanceKm;
            closestEntity = entity;
        }
    });

    const maxDistanceKm = closestEntity?.gridCellRadiusKm || GLOBAL_HEX_RADIUS_KM;
    return closestDistanceKm <= maxDistanceKm * 1.25 ? closestEntity : null;
}

function getActiveCellEntityAt(position) {
    return getActiveCellEntityFromPick(position) || getActiveCellEntityFromGeography(position);
}

function updateFootprintInfo() {
    if (!simulation) return;

    if (isAntenna7dbPreviewMode()) {
        footprintInfo.textContent = `7 dB: footprint ${formatKm(SERVICE_FOOTPRINT_DIAMETER_KM)} | ${lastAntenna7dbMaxBeamRadiusKm.toFixed(1)} km celula`;
        return;
    }

    if (footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_MASK) {
        footprintInfo.textContent = `${formatKm(INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM)} max. | mascara elev. >= ${SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG.toFixed(1)}°`;
        return;
    }

    if (footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK) {
        footprintInfo.textContent = `${formatKm(INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM)} max. | link budget`;
        return;
    }

    footprintInfo.textContent = `${formatKm(SERVICE_FOOTPRINT_DIAMETER_KM)} max.`;
}

function focusFirstSatelliteFootprint() {
    if (!simulation || !isAntenna7dbPreviewMode()) return;

    const satellite = simulation.frames[currentFrameIndex]?.satellites?.[0];
    if (!satellite) return;

    viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(satellite.lon, satellite.lat, 2_600_000),
        duration: 0.8,
    });
}

function applyPresentationCamera() {
    if (!isPresentationProfile()) return;

    viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(-57.5, -23.0, 4_300_000),
        orientation: {
            heading: Cesium.Math.toRadians(8),
            pitch: Cesium.Math.toRadians(-47),
            roll: 0,
        },
    });
}

function canvasPositionFromPointerEvent(event) {
    const rect = viewer.scene.canvas.getBoundingClientRect();
    return new Cesium.Cartesian2(
        event.clientX - rect.left,
        event.clientY - rect.top
    );
}

function tooltipPositionFromPointerEvent(event) {
    return {
        x: event.clientX,
        y: event.clientY,
    };
}

function handleCellPointer(event, { hideWhenEmpty = true } = {}) {
    const canvasPosition = canvasPositionFromPointerEvent(event);
    const entity = getActiveCellEntityAt(canvasPosition);

    if (!entity) {
        if (hideWhenEmpty) hideCellTooltip();
        return false;
    }

    showCellTooltip(tooltipPositionFromPointerEvent(event), entity);
    return true;
}

async function loadSimulation(profile) {
    stopPlayback();
    updateMitigationControls();
    setStatus(`Carregando perfil ${profile} (${SCENARIO_LABELS[selectedScenario()]})...`);

    if (window.location.protocol === "file:") {
        throw new Error("Abra o simulador pelo servidor da API: http://127.0.0.1:8000?profile=presentation");
    }

    const pageParams = new URLSearchParams(window.location.search);
    const apiParams = new URLSearchParams({ profile });
    const paramFile = scenarioWasSelectedByUser ? null : pageParams.get("param_file");
    if (paramFile || scenarioWasSelectedByUser) {
        apiParams.set("param_file", paramFile || selectedScenarioParamFile());
    }

    const response = await fetch(`/api/simulation?${apiParams.toString()}`);
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `Falha ao carregar a simulação (${response.status})`);
    }

    simulation = await response.json();
    footprintAssignmentCache = new Map();
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
    POWER_BACKOFF_DB = simulation.meta.powerBackoffDb
        ?? (ANTENNA_GAIN_HIGH - ANTENNA_GAIN_LOW);
    MINIMUM_SERVICE_ANGLE_DEG = simulation.meta.minimumServiceAngleDeg;
    ANTENNA_7DB_RADIUS_KM = simulation.meta.antenna7dbRadiusKm;
    ANTENNA_7DB_HIGH_ANGLE_DEG = simulation.meta.antenna7dbHighAngleDeg;
    ANTENNA_7DB_LOW_ANGLE_DEG = simulation.meta.antenna7dbLowAngleDeg;
    FOOTPRINT_3DB_RADIUS_KM = simulation.meta.footprint3dbRadiusKm;
    FOOTPRINT_7DB_RADIUS_KM = simulation.meta.footprint7dbRadiusKm;
    SERVICE_FOOTPRINT_DIAMETER_KM = simulation.meta.serviceFootprintDiameterKm
        ?? simulation.meta.footprintDiameterKm;
    INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM = simulation.meta.interferenceActiveFootprintDiameterKm
        ?? simulation.meta.footprintDiameterKm;
    INTERFERENCE_PATH_FOOTPRINT_DIAMETER_KM = simulation.meta.interferencePathFootprintDiameterKm
        ?? INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM;
    SHARC_INTERFERENCE_PATH_MIN_ELEVATION_DEG = simulation.meta.sharcInterferencePathMinElevationDeg;
    SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG = simulation.meta.sharcInterferenceActiveMinElevationDeg;
    ENABLE_COCHANNEL = Boolean(simulation.meta.enableCochannel);
    ENABLE_ADJACENT_CHANNEL = Boolean(simulation.meta.enableAdjacentChannel);
    IMT_FREQUENCY_MHZ = simulation.meta.imtFrequencyMHz;
    IMT_BANDWIDTH_MHZ = simulation.meta.imtBandwidthMHz;
    IMT_CONDUCTED_POWER_DBM = simulation.meta.imtConductedPowerDbm;
    IMT_BS_OHMIC_LOSS_DB = simulation.meta.imtBsOhmicLossDb;
    IMT_ADJACENT_CH_EMISSIONS = simulation.meta.imtAdjacentChEmissions || "OFF";
    IMT_ADJACENT_CH_LEAK_RATIO_DB = simulation.meta.imtAdjacentChLeakRatioDb;
    SINGLE_EARTH_STATION_GAIN_DB = simulation.meta.singleEarthStationGainDb;
    SINGLE_EARTH_STATION_FREQUENCY_MHZ = simulation.meta.singleEarthStationFrequencyMHz;
    SINGLE_EARTH_STATION_BANDWIDTH_MHZ = simulation.meta.singleEarthStationBandwidthMHz;
    SINGLE_EARTH_STATION_ADJACENT_CH_RECEPTION = simulation.meta.singleEarthStationAdjacentChReception || "OFF";
    SINGLE_EARTH_STATION_ADJACENT_CH_SELECTIVITY_DB = simulation.meta.singleEarthStationAdjacentChSelectivityDb;
    POLARIZATION_LOSS_DB = simulation.meta.polarizationLossDb;
    ANTENNA_SYSTEM4_HIGH = simulation.meta.antennaSystem4High;
    ANTENNA_SYSTEM4_LOW = simulation.meta.antennaSystem4Low;
    updateFootprintModeHelp();
    updateFootprintInfo();
    updateMitigationControls();

    console.log(`Configurações carregadas: Raio = ${GLOBAL_HEX_RADIUS_KM}km, Guardband = ${GUARDBAND_HEX_COUNT} hexs`);

    buildStaticScene();
    buildSatelliteEntities();
    preBuildGrid();
    renderFrame(0);
    applyPresentationCamera();
    setStatus(`Perfil ${simulation.meta.profile} carregado em ${SCENARIO_LABELS[selectedScenario()]} com ${simulation.meta.frameCount} frames.`);
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
            text: "Estação FS",
            font: "13px Segoe UI",
            pixelOffset: new Cesium.Cartesian2(0, -18),
            fillColor: Cesium.Color.WHITE.withAlpha(1.0),
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(1.0),
            disableDepthTestDistance: Number.POSITIVE_INFINITY 
        },
    });

    updateAzimuthVector();

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
                pixelSize: satellite.active ? ACTIVE_SATELLITE_PIXEL_SIZE : INACTIVE_SATELLITE_PIXEL_SIZE,
                color: satelliteColor(satellite.active),
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 1,
            },
            label: {
                text: satellite.id,
                font: "12px Segoe UI",
                show: false,
                horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                verticalOrigin: Cesium.VerticalOrigin.TOP,
            },
        });
        satelliteEntities.set(satellite.id, entity);
    });
}

function calculateSatelliteElevationDeg(cell, satellite) {
    const earthLat = cell.lat * Math.PI / 180;
    const satLat = satellite.lat * Math.PI / 180;
    const earthLon = cell.lon * Math.PI / 180;
    const satLon = satellite.lon * Math.PI / 180;
    const gamma = Math.acos(Math.min(1, Math.max(-1,
        Math.cos(earthLat) * Math.cos(satLat) * Math.cos(satLon - earthLon)
        + Math.sin(earthLat) * Math.sin(satLat)
    )));
    const satRadius = EARTH_RADIUS_KM + satellite.altKm;
    const slant = Math.sqrt(
        satRadius ** 2
        + EARTH_RADIUS_KM ** 2
        - 2 * satRadius * EARTH_RADIUS_KM * Math.cos(gamma)
    );
    const elevationRad = Math.acos(Math.min(1, Math.max(-1,
        (slant ** 2 + EARTH_RADIUS_KM ** 2 - satRadius ** 2)
        / (2 * slant * EARTH_RADIUS_KM)
    ))) - Math.PI / 2;

    return elevationRad * 180 / Math.PI;
}

function assignGridCellsToSatellites(frame) {
    const assignedCells = new Map();
    const satBeamCounts = new Map();

    globalGridCells.forEach((cell, key) => {
        let bestSatellite = null;
        let bestElevation = Number.NEGATIVE_INFINITY;

        frame.satellites.forEach((satellite) => {
            const elevation = calculateSatelliteElevationDeg(cell, satellite);
            if (elevation > bestElevation) {
                bestElevation = elevation;
                bestSatellite = satellite;
            }
        });

        if (bestSatellite && bestElevation >= MINIMUM_SERVICE_ANGLE_DEG) {
            const isExcludedZone = shouldExcludeCellByMitigation(cell);
            assignedCells.set(key, isExcludedZone
                ? {
                    satelliteId: bestSatellite.id,
                    lon: cell.lon,
                    lat: cell.lat,
                    elevationDeg: bestElevation,
                    elevationThresholdDeg: MINIMUM_SERVICE_ANGLE_DEG,
                    distanceKm: distanceKmBetween(cell.lon, cell.lat, simulation.station.lon, simulation.station.lat),
                    isExcludedZone: true,
                }
                : bestSatellite.id
            );

            if (!isExcludedZone) {
                satBeamCounts.set(
                    bestSatellite.id,
                    (satBeamCounts.get(bestSatellite.id) || 0) + 1
                );
            }
        }
    });

    return { assignedCells, satBeamCounts };
}

function calculateOffAxisAngleDeg(satellite, center) {
    const satVector = lonLatToVectorKm(
        { lon: satellite.lon, lat: satellite.lat },
        EARTH_RADIUS_KM + satellite.altKm
    );
    const nadirVector = lonLatToVectorKm({ lon: satellite.lon, lat: satellite.lat });
    const centerVector = lonLatToVectorKm(center);
    const nadirDirection = normalizeVector(subtractVector(nadirVector, satVector));
    const centerDirection = normalizeVector(subtractVector(centerVector, satVector));
    const cosine = Math.min(1, Math.max(-1, dotVector(nadirDirection, centerDirection)));

    return Math.acos(cosine) * 180 / Math.PI;
}

function calculateSlantDistanceKm(cell, satellite) {
    const satVector = lonLatToVectorKm(
        { lon: satellite.lon, lat: satellite.lat },
        EARTH_RADIUS_KM + satellite.altKm
    );
    const cellVector = lonLatToVectorKm(cell);
    const delta = subtractVector(satVector, cellVector);

    return Math.sqrt(dotVector(delta, delta));
}

function calculateFreeSpaceLossDb(distanceKm, frequencyMHz) {
    return 32.45 + 20 * Math.log10(Math.max(distanceKm, 0.001))
        + 20 * Math.log10(Math.max(frequencyMHz, 0.001));
}

function calculateBandwidthOverlapMHz(freqAMHz, bandwidthAMHz, freqBMHz, bandwidthBMHz) {
    const minA = freqAMHz - bandwidthAMHz / 2;
    const maxA = freqAMHz + bandwidthAMHz / 2;
    const minB = freqBMHz - bandwidthBMHz / 2;
    const maxB = freqBMHz + bandwidthBMHz / 2;
    return Math.max(0, Math.min(maxA, maxB) - Math.max(minA, minB));
}

function linearPowerSumDbm(valuesDbm) {
    const linearSum = valuesDbm
        .filter(Number.isFinite)
        .reduce((sum, value) => sum + 10 ** (0.1 * value), 0);

    return linearSum > 0 ? 10 * Math.log10(linearSum) : Number.NEGATIVE_INFINITY;
}

function calculateScenarioTxPowerDbm(effectiveConductedPowerDbm) {
    const components = [];

    if (ENABLE_COCHANNEL) {
        components.push(effectiveConductedPowerDbm);
    }

    if (ENABLE_ADJACENT_CHANNEL && IMT_ADJACENT_CH_EMISSIONS === "ACLR") {
        const overlapMHz = calculateBandwidthOverlapMHz(
            IMT_FREQUENCY_MHZ,
            IMT_BANDWIDTH_MHZ,
            SINGLE_EARTH_STATION_FREQUENCY_MHZ,
            SINGLE_EARTH_STATION_BANDWIDTH_MHZ
        );
        const nonOverlapSystemBandwidthMHz = Math.max(
            0.001,
            SINGLE_EARTH_STATION_BANDWIDTH_MHZ - overlapMHz
        );
        const measurementBandwidthMHz = Math.max(0.001, IMT_BANDWIDTH_MHZ);
        const bandwidthScalingDb = 10 * Math.log10(
            nonOverlapSystemBandwidthMHz / measurementBandwidthMHz
        );

        components.push(
            effectiveConductedPowerDbm
            - (IMT_ADJACENT_CH_LEAK_RATIO_DB || 0)
            + bandwidthScalingDb
        );
    }

    if (
        ENABLE_ADJACENT_CHANNEL
        && SINGLE_EARTH_STATION_ADJACENT_CH_RECEPTION === "ACS"
        && Number.isFinite(SINGLE_EARTH_STATION_ADJACENT_CH_SELECTIVITY_DB)
    ) {
        const overlapMHz = calculateBandwidthOverlapMHz(
            IMT_FREQUENCY_MHZ,
            IMT_BANDWIDTH_MHZ,
            SINGLE_EARTH_STATION_FREQUENCY_MHZ,
            SINGLE_EARTH_STATION_BANDWIDTH_MHZ
        );
        const nonOverlapImtBandwidthMHz = Math.max(0.001, IMT_BANDWIDTH_MHZ - overlapMHz);
        const bandwidthScalingDb = 10 * Math.log10(
            nonOverlapImtBandwidthMHz / Math.max(0.001, IMT_BANDWIDTH_MHZ)
        );

        components.push(
            effectiveConductedPowerDbm
            + bandwidthScalingDb
            - SINGLE_EARTH_STATION_ADJACENT_CH_SELECTIVITY_DB
        );
    }

    return linearPowerSumDbm(components);
}

function calculateS1528System4GainDb(offAxisAngleDeg, elevationDeg) {
    const params = elevationDeg >= 50 ? ANTENNA_SYSTEM4_HIGH : ANTENNA_SYSTEM4_LOW;
    if (!params) return 0;

    const peakGain = params.gainDb;
    const sideLobe = params.nearSideLobeDb;
    const farSideLobe = params.farSideLobeDb;
    const psi = Math.abs(offAxisAngleDeg);
    const psiB = params.beamwidth3dbDeg / 2;
    const z = 1;
    const a = 2.58;
    const b = 6.32;
    const alpha = 1.5;
    const x = peakGain + sideLobe + 25 * Math.log10(b * psiB);
    const y = b * psiB * 10 ** (0.04 * (peakGain + sideLobe - farSideLobe));
    const backLobe = Math.max(0, 15 + sideLobe + 0.25 * peakGain + 5 * Math.log10(z));

    if (psi < a * psiB) return peakGain - 3 * (psi / psiB) ** alpha;
    if (psi <= 0.5 * b * psiB) return peakGain + sideLobe + 20 * Math.log10(z);
    if (psi <= b * psiB) return peakGain + sideLobe;
    if (psi <= y) return x - 25 * Math.log10(Math.max(psi, 0.001));
    if (psi <= 90) return farSideLobe;
    return backLobe;
}

function getInterferenceColor(value, minValue, maxValue) {
    const span = Math.max(0.1, maxValue - minValue);
    const normalized = Math.min(1, Math.max(0, (value - minValue) / span));
    const index = Math.min(
        SHARC_INTERFERENCE_COLORS.length - 1,
        Math.floor(normalized * SHARC_INTERFERENCE_COLORS.length)
    );

    return SHARC_INTERFERENCE_COLORS[index];
}

function formatDbm(value) {
    return `${value.toFixed(1)} dBm`;
}

function buildDefaultLinkBudgetScale() {
    const fixedRanges = [
        { minDbm: -Infinity, maxDbm: -165, label: "< -165.0 dBm" },
        { minDbm: -165, maxDbm: -155, label: "-165.0 dBm a -155.0 dBm" },
        { minDbm: -155, maxDbm: -145, label: "-155.0 dBm a -145.0 dBm" },
        { minDbm: -145, maxDbm: Infinity, label: "> -145.0 dBm" },
    ];

    return fixedRanges.map((range, index) => ({
        ...SHARC_LINK_BUDGET_COLORS[index],
        ...range,
    }));
}

function buildAdaptiveLinkBudgetScale(values) {
    return buildDefaultLinkBudgetScale();
}

function getLinkBudgetSector(valueDbm, scale = currentLinkBudgetScale) {
    const sectors = scale?.length ? scale : buildDefaultLinkBudgetScale();
    return sectors.find((sector, index) => (
        index === sectors.length - 1 || valueDbm <= sector.maxDbm
    )) || sectors[sectors.length - 1];
}

function approximateDistanceToBrazilKm(point) {
    const clampedLon = Math.max(brMinLon, Math.min(brMaxLon, point.lon));
    const clampedLat = Math.max(brMinLat, Math.min(brMaxLat, point.lat));
    return approximateDistanceKm(point, { lon: clampedLon, lat: clampedLat });
}

function candidateSatellitesForFootprint(frame, radiusKm) {
    if (!Number.isFinite(radiusKm) || radiusKm <= 0) return frame.satellites;

    const midLatRad = ((brMinLat + brMaxLat) / 2) * Math.PI / 180;
    const latMarginDeg = radiusKm / 111 + 3;
    const lonMarginDeg = radiusKm / (111 * Math.max(0.25, Math.cos(midLatRad))) + 3;
    const candidates = frame.satellites
        .filter((satellite) => (
            satellite.lat >= brMinLat - latMarginDeg
            && satellite.lat <= brMaxLat + latMarginDeg
            && satellite.lon >= brMinLon - lonMarginDeg
            && satellite.lon <= brMaxLon + lonMarginDeg
        ))
        .map((satellite) => ({
            satellite,
            distanceKm: approximateDistanceToBrazilKm(satellite),
        }))
        .filter(({ distanceKm }) => distanceKm <= radiusKm + 2 * GLOBAL_HEX_RADIUS_KM)
        .sort((a, b) => a.distanceKm - b.distanceKm)
        .slice(0, MAX_INTERFERENCE_CANDIDATE_SATELLITES)
        .map(({ satellite }) => satellite);

    if (candidates.length) return candidates;

    return frame.satellites
        .map((satellite) => ({
            satellite,
            distanceKm: approximateDistanceToBrazilKm(satellite),
        }))
        .sort((a, b) => a.distanceKm - b.distanceKm)
        .slice(0, MAX_INTERFERENCE_CANDIDATE_SATELLITES)
        .map(({ satellite }) => satellite);
}

function satelliteCanReachCellQuick(satellite, cell, radiusKm) {
    if (!Number.isFinite(radiusKm) || radiusKm <= 0) return true;

    return approximateDistanceKm(
        { lon: satellite.lon, lat: satellite.lat },
        cell
    ) <= radiusKm + GLOBAL_HEX_RADIUS_KM;
}

function assignSharcInterferenceMask(frame) {
    const assignedCells = new Map();
    const satBeamCounts = new Map();
    const thresholdDeg = SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG
        ?? SHARC_INTERFERENCE_PATH_MIN_ELEVATION_DEG
        ?? 0;
    const footprintRadiusKm = (INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM || 0) / 2;
    const candidateSatellites = candidateSatellitesForFootprint(frame, footprintRadiusKm);

    globalGridCells.forEach((cell, key) => {
        let bestSatellite = null;
        let bestElevation = Number.NEGATIVE_INFINITY;

        candidateSatellites.forEach((satellite) => {
            if (!satelliteCanReachCellQuick(satellite, cell, footprintRadiusKm)) return;
            const elevation = calculateSatelliteElevationDeg(cell, satellite);
            if (elevation > bestElevation) {
                bestElevation = elevation;
                bestSatellite = satellite;
            }
        });

        if (!bestSatellite || bestElevation < thresholdDeg) return;

        const isExcludedZone = shouldExcludeCellByMitigation(cell);
        if (!isExcludedZone) {
            satBeamCounts.set(
                bestSatellite.id,
                (satBeamCounts.get(bestSatellite.id) || 0) + 1
            );
        }
        assignedCells.set(key, {
            satelliteId: bestSatellite.id,
            lon: cell.lon,
            lat: cell.lat,
            radiusKm: GLOBAL_HEX_RADIUS_KM,
            elevationDeg: bestElevation,
            elevationThresholdDeg: thresholdDeg,
            distanceKm: isExcludedZone
                ? distanceKmBetween(cell.lon, cell.lat, simulation.station.lon, simulation.station.lat)
                : undefined,
            heatmapColor: isExcludedZone ? undefined : getInterferenceColor(bestElevation, thresholdDeg, 90),
            isExcludedZone,
        });
    });

    return { assignedCells, satBeamCounts };
}

function assignSharcInterferenceLinkBudget(frame) {
    const assignedCells = new Map();
    const satBeamCounts = new Map();
    const candidates = [];
    const thresholdDeg = SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG
        ?? SHARC_INTERFERENCE_PATH_MIN_ELEVATION_DEG
        ?? 0;
    const footprintRadiusKm = (INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM || 0) / 2;
    const candidateSatellites = candidateSatellitesForFootprint(frame, footprintRadiusKm);

    globalGridCells.forEach((cell, key) => {
        let best = null;

        candidateSatellites.forEach((satellite) => {
            if (!satelliteCanReachCellQuick(satellite, cell, footprintRadiusKm)) return;
            const elevationDeg = calculateSatelliteElevationDeg(cell, satellite);
            if (elevationDeg < thresholdDeg) return;

            const distanceKm = calculateSlantDistanceKm(cell, satellite);
            const offAxisAngleDeg = calculateOffAxisAngleDeg(satellite, cell);
            const txGainDb = calculateS1528System4GainDb(offAxisAngleDeg, elevationDeg);
            const rxGainDb = Number.isFinite(SINGLE_EARTH_STATION_GAIN_DB)
                ? SINGLE_EARTH_STATION_GAIN_DB
                : 0;
            const powerBackoffDb = powerBackoffMitigationApplies() && cell.isBorder && Number.isFinite(POWER_BACKOFF_DB)
                ? POWER_BACKOFF_DB
                : 0;
            const effectiveConductedPowerDbm = IMT_CONDUCTED_POWER_DBM - powerBackoffDb;
            const scenarioTxPowerDbm = calculateScenarioTxPowerDbm(effectiveConductedPowerDbm);
            if (!Number.isFinite(scenarioTxPowerDbm)) return;
            const pathLossDb = calculateFreeSpaceLossDb(distanceKm, IMT_FREQUENCY_MHZ);
            const couplingLossDb = pathLossDb - txGainDb - rxGainDb
                + (IMT_BS_OHMIC_LOSS_DB || 0)
                + (POLARIZATION_LOSS_DB || 0);
            const interferenceDbm = scenarioTxPowerDbm - couplingLossDb;

            if (!best || interferenceDbm > best.interferenceDbm) {
                best = {
                    satelliteId: satellite.id,
                    lon: cell.lon,
                    lat: cell.lat,
                    radiusKm: GLOBAL_HEX_RADIUS_KM,
                    elevationDeg,
                    elevationThresholdDeg: thresholdDeg,
                    distanceKm,
                    offAxisAngleDeg,
                    txGainDb,
                    rxGainDb,
                    powerBackoffDb,
                    effectivePowerDbm: effectiveConductedPowerDbm,
                    scenarioTxPowerDbm,
                    pathLossDb,
                    couplingLossDb,
                    interferenceDbm,
                };
            }
        });

        if (best) {
            if (shouldExcludeCellByMitigation(cell)) {
                assignedCells.set(key, {
                    ...best,
                    interferenceDbm: undefined,
                    couplingLossDb: undefined,
                    powerBackoffDb: undefined,
                    effectivePowerDbm: undefined,
                    scenarioTxPowerDbm: undefined,
                    pathLossDb: undefined,
                    distanceKm: distanceKmBetween(cell.lon, cell.lat, simulation.station.lon, simulation.station.lat),
                    isExcludedZone: true,
                });
                return;
            }

            candidates.push([key, best]);
            satBeamCounts.set(
                best.satelliteId,
                (satBeamCounts.get(best.satelliteId) || 0) + 1
            );
        }
    });

    const linkBudgetScale = buildAdaptiveLinkBudgetScale(
        candidates.map(([, candidate]) => candidate.interferenceDbm)
    );

    candidates.forEach(([key, candidate]) => {
        assignedCells.set(key, {
            ...candidate,
            heatmapColor: getLinkBudgetSector(candidate.interferenceDbm, linkBudgetScale).color,
        });
    });

    return { assignedCells, satBeamCounts, linkBudgetScale };
}

function calculateAntenna7dbGainDb(offAxisAngleDeg, maxOffAxisAngleDeg) {
    const peakGain = Number.isFinite(ANTENNA_GAIN_HIGH) ? ANTENNA_GAIN_HIGH : 0;
    if (!Number.isFinite(maxOffAxisAngleDeg) || maxOffAxisAngleDeg <= 0) {
        return { gainDb: peakGain, gainDropDb: 0 };
    }

    const normalizedAngle = Math.min(1, Math.max(0, offAxisAngleDeg / maxOffAxisAngleDeg));
    const gainDropDb = 7 * normalizedAngle * normalizedAngle;
    return {
        gainDb: peakGain - gainDropDb,
        gainDropDb,
    };
}

function getAntenna7dbSector(gainDropDb, beamRadiusKm) {
    const clampedDropDb = Math.min(7, Math.max(0, gainDropDb));
    const index = Math.min(
        ANTENNA_7DB_SECTOR_COLORS.length - 1,
        Math.floor(clampedDropDb / ANTENNA_7DB_SECTOR_STEP_DB)
    );
    const sectorStartDb = index * ANTENNA_7DB_SECTOR_STEP_DB;
    const sectorEndDb = Math.min(7, sectorStartDb + ANTENNA_7DB_SECTOR_STEP_DB);
    const representativeDropDb = (sectorStartDb + sectorEndDb) / 2;
    const normalizedSector = representativeDropDb / 7;

    return {
        color: ANTENNA_7DB_SECTOR_COLORS[index],
        label: `${sectorStartDb.toFixed(0)}-${sectorEndDb.toFixed(0)} dB`,
        radiusKm: beamRadiusKm * (0.92 + 0.16 * normalizedSector),
    };
}

function assignAntenna7dbFirstSatellite(frame) {
    const assignedCells = new Map();
    const satBeamCounts = new Map();
    const satellite = frame.satellites[0];
    const outerFootprintRadiusKm = SERVICE_FOOTPRINT_DIAMETER_KM / 2;

    if (!satellite || !Number.isFinite(outerFootprintRadiusKm)) {
        return { assignedCells, satBeamCounts, maxBeamRadiusKm: 0 };
    }

    const satelliteNadir = { lon: satellite.lon, lat: satellite.lat };
    const nominalBeamRadiusKm = calculate7dbBeamRadiusKm(satellite, satelliteNadir);
    const footprintEdge = destinationFromOffsetKm(satelliteNadir, outerFootprintRadiusKm, 0);
    const maxOffAxisAngleDeg = calculateOffAxisAngleDeg(satellite, footprintEdge);
    let maxDrawnBeamRadiusKm = 0;
    let previousCellRadiusKm = nominalBeamRadiusKm;
    let ringDistanceKm = 0;
    let ringIndex = 0;

    const addSectorCell = (key, center, centerDistanceKm, beamRadiusKm) => {
        const offAxisAngleDeg = calculateOffAxisAngleDeg(satellite, center);
        const { gainDb, gainDropDb } = calculateAntenna7dbGainDb(
            offAxisAngleDeg,
            maxOffAxisAngleDeg
        );
        const sector = getAntenna7dbSector(gainDropDb, beamRadiusKm);
        if (centerDistanceKm + sector.radiusKm > outerFootprintRadiusKm) return false;

        maxDrawnBeamRadiusKm = Math.max(maxDrawnBeamRadiusKm, sector.radiusKm);
        assignedCells.set(key, {
            satelliteId: satellite.id,
            lon: center.lon,
            lat: center.lat,
            radiusKm: sector.radiusKm,
            beamRadiusKm,
            gainDb,
            gainDropDb,
            gainSector: sector.label,
            offAxisAngleDeg,
            centerDistanceKm,
            footprintDiameterKm: SERVICE_FOOTPRINT_DIAMETER_KM,
            heatmapColor: sector.color,
            isAntenna7dbBorder: false,
        });
        return true;
    };

    addSectorCell("a7_0_0", satelliteNadir, 0, nominalBeamRadiusKm);

    while (ringDistanceKm < outerFootprintRadiusKm && ringIndex < 120) {
        ringIndex += 1;
        const probeDistanceKm = ringDistanceKm + Math.sqrt(3) * previousCellRadiusKm;
        const probeCenter = destinationFromOffsetKm(satelliteNadir, probeDistanceKm, 0);
        const probeBeamRadiusKm = calculate7dbBeamRadiusKm(satellite, probeCenter);
        const probeOffAxisAngleDeg = calculateOffAxisAngleDeg(satellite, probeCenter);
        const { gainDropDb: probeGainDropDb } = calculateAntenna7dbGainDb(
            probeOffAxisAngleDeg,
            maxOffAxisAngleDeg
        );
        const probeSector = getAntenna7dbSector(probeGainDropDb, probeBeamRadiusKm);
        const radialSpacingKm = Math.sqrt(3) * (previousCellRadiusKm + probeSector.radiusKm) / 2;

        ringDistanceKm += radialSpacingKm;
        if (ringDistanceKm + probeSector.radiusKm > outerFootprintRadiusKm) break;

        const tangentialSpacingKm = Math.sqrt(3) * probeSector.radiusKm;
        const cellsInRing = Math.max(
            6,
            Math.floor((2 * Math.PI * ringDistanceKm) / tangentialSpacingKm)
        );
        const angleOffset = ringIndex % 2 === 0 ? 0 : Math.PI / cellsInRing;

        for (let index = 0; index < cellsInRing; index++) {
            const angle = angleOffset + index * 2 * Math.PI / cellsInRing;
            const eastKm = ringDistanceKm * Math.cos(angle);
            const northKm = ringDistanceKm * Math.sin(angle);
            const center = destinationFromOffsetKm(satelliteNadir, eastKm, northKm);
            const centerDistanceKm = greatCircleDistanceKm(satelliteNadir, center);
            const beamRadiusKm = calculate7dbBeamRadiusKm(satellite, center);
            addSectorCell(`a7_${ringIndex}_${index}`, center, centerDistanceKm, beamRadiusKm);
        }

        previousCellRadiusKm = probeSector.radiusKm;
    }

    lastAntenna7dbMaxBeamRadiusKm = maxDrawnBeamRadiusKm;
    satBeamCounts.set(satellite.id, assignedCells.size);
    return { assignedCells, satBeamCounts, maxBeamRadiusKm: maxDrawnBeamRadiusKm };
}

function isFootprintBoundaryCell(key, assignedCells) {
    const [col, row] = key.split("_").map(Number);
    const neighborOffsets = [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
        [1, col % 2 === 0 ? -1 : 1],
        [-1, col % 2 === 0 ? -1 : 1],
    ];

    return neighborOffsets.some(([dCol, dRow]) => (
        !assignedCells.has(`${col + dCol}_${row + dRow}`)
    ));
}

function clearAntenna7dbPreviewEntities() {
    for (let index = 0; index < activeAntenna7dbPreviewCount; index++) {
        const entity = antenna7dbPreviewEntities[index];
        if (entity) entity.show = false;
    }
    activeAntenna7dbPreviewCount = 0;
}

function drawAntenna7dbPreviewCells(activeHexagonsMap) {
    activeHexagonsMap.forEach((assignment, key) => {
        const isAntenna7dbBorder = Boolean(assignment.isAntenna7dbBorder);
        const cellRadiusKm = assignment.radiusKm;
        const materialColor = assignment.heatmapColor || (
            isAntenna7dbBorder
                ? Cesium.Color.YELLOW.withAlpha(0.32)
                : Cesium.Color.ORANGE.withAlpha(0.28)
        );
        let entity = antenna7dbPreviewEntities[activeAntenna7dbPreviewCount];
        const hierarchy = new Cesium.PolygonHierarchy(
            createHexagon(assignment.lon, assignment.lat, cellRadiusKm)
        );

        if (!entity) {
            entity = viewer.entities.add({
                polygon: {
                    hierarchy,
                    material: materialColor,
                    outline: true,
                    outlineColor: Cesium.Color.ORANGE.withAlpha(0.85),
                    height: 0,
                },
            });
            antenna7dbPreviewEntities.push(entity);
        } else {
            entity.polygon.hierarchy = hierarchy;
            entity.polygon.material = materialColor;
            entity.polygon.outlineColor = Cesium.Color.ORANGE.withAlpha(0.85);
        }
        entity.show = true;
        entity.gridCellKey = key;
        entity.gridCellIsBorder = false;
        entity.isAntenna7dbBorder = isAntenna7dbBorder;
        entity.gridCellLon = assignment.lon;
        entity.gridCellLat = assignment.lat;
        entity.gridCellRadiusKm = cellRadiusKm;
        entity.gridCellBeamRadiusKm = assignment.beamRadiusKm;
        entity.gridCellGainDb = assignment.gainDb;
        entity.gridCellGainDropDb = assignment.gainDropDb;
        entity.gridCellGainSector = assignment.gainSector;
        entity.gridCellOffAxisAngleDeg = assignment.offAxisAngleDeg;
        entity.gridCellDistanceKm = assignment.centerDistanceKm;
        entity.gridCellFootprintDiameterKm = assignment.footprintDiameterKm;
        entity.gridCellSatelliteId = assignment.satelliteId;
        entity.gridCellElevationDeg = assignment.elevationDeg;
        entity.gridCellElevationThresholdDeg = assignment.elevationThresholdDeg;
        entity.gridCellInterferenceDbm = assignment.interferenceDbm;
        entity.gridCellCouplingLossDb = assignment.couplingLossDb;
        entity.gridCellTxGainDb = assignment.txGainDb;
        entity.gridCellRxGainDb = assignment.rxGainDb;
        entity.gridCellPowerBackoffDb = assignment.powerBackoffDb;
        entity.gridCellEffectivePowerDbm = assignment.effectivePowerDbm;
        entity.gridCellScenarioTxPowerDbm = assignment.scenarioTxPowerDbm;
        entity.gridCellPathLossDb = assignment.pathLossDb;
        if (Number.isFinite(assignment.distanceKm)) {
            entity.gridCellDistanceKm = assignment.distanceKm;
        }
        activeAntenna7dbPreviewCount += 1;
        activeCellEntitySet.add(entity);
    });
}

function getFootprintAssignment(frame, frameIndex) {
    const cacheKey = `${footprintModeSelect.value}:${selectedScenario()}:${mitigationEnabled ? "mit" : "raw"}:${frameIndex}`;
    if (footprintAssignmentCache.has(cacheKey)) {
        return footprintAssignmentCache.get(cacheKey);
    }

    let footprintAssignment;
    if (isAntenna7dbPreviewMode()) {
        footprintAssignment = assignAntenna7dbFirstSatellite(frame);
    } else if (footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_MASK) {
        footprintAssignment = assignSharcInterferenceMask(frame);
    } else if (footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK) {
        footprintAssignment = assignSharcInterferenceLinkBudget(frame);
    } else {
        footprintAssignment = assignGridCellsToSatellites(frame);
    }

    footprintAssignmentCache.set(cacheKey, footprintAssignment);
    return footprintAssignment;
}

function createHexagonLonLat(lon, lat, sizeKm) {
    const coords = [];
    const latFactor = 1 / 111;
    const lonFactor = 1 / (111 * Math.cos(lat * Math.PI / 180));

    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i;
        coords.push([
            lon + sizeKm * Math.cos(angle) * lonFactor,
            lat + sizeKm * Math.sin(angle) * latFactor,
            0,
        ]);
    }

    return coords;
}

function cross2d(origin, a, b) {
    return (a[0] - origin[0]) * (b[1] - origin[1])
        - (a[1] - origin[1]) * (b[0] - origin[0]);
}

function convexHullLonLat(points) {
    const unique = Array.from(
        new Map(points.map((point) => [`${point[0].toFixed(6)},${point[1].toFixed(6)}`, point])).values()
    ).sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));

    if (unique.length <= 1) {
        return unique;
    }

    const lower = [];
    unique.forEach((point) => {
        while (lower.length >= 2 && cross2d(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) {
            lower.pop();
        }
        lower.push(point);
    });

    const upper = [];
    [...unique].reverse().forEach((point) => {
        while (upper.length >= 2 && cross2d(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) {
            upper.pop();
        }
        upper.push(point);
    });

    lower.pop();
    upper.pop();
    return lower.concat(upper);
}

function createPresentationFootprintRing(footprint) {
    const gridPoints = Array.isArray(footprint.grid) ? footprint.grid : [];
    if (gridPoints.length === 0) {
        return [];
    }

    if (gridPoints.length === 1) {
        return createHexagonLonLat(gridPoints[0][0], gridPoints[0][1], GLOBAL_HEX_RADIUS_KM * 1.15);
    }

    const hull = convexHullLonLat(gridPoints);
    if (hull.length >= 3) {
        return hull.map(([lon, lat]) => [lon, lat, 0]);
    }

    const lon = gridPoints.reduce((sum, point) => sum + point[0], 0) / gridPoints.length;
    const lat = gridPoints.reduce((sum, point) => sum + point[1], 0) / gridPoints.length;
    return createHexagonLonLat(lon, lat, GLOBAL_HEX_RADIUS_KM * 1.15);
}

function drawPresentationFootprintCones(frame, satBeamCounts) {
    if (!isPresentationProfile()) return;

    let drawnSatellites = 0;
    for (const footprint of frame.footprints || []) {
        if (drawnSatellites >= PRESENTATION_CONE_MAX_SATELLITES) break;
        if (!footprint) continue;

        const satData = frame.satellites.find((satellite) => satellite.id === footprint.satelliteId);
        if (!satData) continue;

        const count = satBeamCounts.get(footprint.satelliteId) || footprint.cellCount || 0;
        if (count <= 0) continue;

        const satPos = Cesium.Cartesian3.fromDegrees(
            satData.lon,
            satData.lat,
            satData.altKm * 1000
        );

        const rings = Array.isArray(footprint.rings) && footprint.rings.length > 0
            ? footprint.rings
            : [createPresentationFootprintRing(footprint)];

        rings.forEach((ring) => {
            if (!Array.isArray(ring) || ring.length < 3) return;

            const uniqueRingLength = Math.max(3, ring.length - 1);
            const step = Math.max(1, Math.floor(uniqueRingLength / PRESENTATION_CONE_FACES));

            for (let i = 0; i < uniqueRingLength; i += step) {
                const p1 = ring[i];
                const p2 = ring[(i + step) % uniqueRingLength];
                if (!p1 || !p2) continue;

                const trianglePositions = [
                    satPos,
                    Cesium.Cartesian3.fromDegrees(p1[0], p1[1], 0),
                    Cesium.Cartesian3.fromDegrees(p2[0], p2[1], 0),
                ];

                let coneEntity = conePool[activeConesCount];
                if (!coneEntity) {
                    coneEntity = viewer.entities.add({
                        polygon: {
                            hierarchy: new Cesium.PolygonHierarchy(trianglePositions),
                            material: PRESENTATION_CONE_MATERIAL,
                            outline: true,
                            outlineColor: PRESENTATION_CONE_OUTLINE,
                            perPositionHeight: true,
                            closeTop: false,
                            closeBottom: false,
                        },
                        show: false,
                    });
                    conePool.push(coneEntity);
                }

                coneEntity.polygon.hierarchy = new Cesium.PolygonHierarchy(trianglePositions);
                coneEntity.polygon.material = PRESENTATION_CONE_MATERIAL;
                coneEntity.polygon.outlineColor = PRESENTATION_CONE_OUTLINE;
                coneEntity.show = true;
                activeConesCount++;
            }
        });

        drawnSatellites++;
    }
}

function renderFrame(frameIndex) {
    if (!simulation) return;

    const frame = simulation.frames[frameIndex];

    currentFrameIndex = frameIndex;
    frameSlider.value = String(frameIndex);

    viewer.entities.suspendEvents();

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
            : Cesium.Color.CYAN.withAlpha(0.58);

        entity.point.pixelSize = satellite.active ? ACTIVE_SATELLITE_PIXEL_SIZE : INACTIVE_SATELLITE_PIXEL_SIZE;
    });

    for (let i = 0; i < activeConesCount; i++) {
        if (conePool[i]) conePool[i].show = false;
    }
    activeConesCount = 0; 

    activeCellsThisFrame.forEach(entity => { if (entity) resetGridCellEntity(entity); });
    activeCellsThisFrame.length = 0;
    activeCellEntitySet.clear();
    clearAntenna7dbPreviewEntities();

    const footprintAssignment = getFootprintAssignment(frame, frameIndex);
    if (Number.isFinite(footprintAssignment.maxBeamRadiusKm)) {
        lastAntenna7dbMaxBeamRadiusKm = footprintAssignment.maxBeamRadiusKm;
    }
    currentLinkBudgetScale = footprintAssignment.linkBudgetScale || null;
    const activeHexagonsMap = footprintAssignment.assignedCells;
    const satBeamCounts = footprintAssignment.satBeamCounts;
    updateInterferenceLegend(currentLinkBudgetScale);
    if (isAntenna7dbPreviewMode()) {
        footprintInfo.textContent = `${activeHexagonsMap.size} hex | footprint ${formatKm(SERVICE_FOOTPRINT_DIAMETER_KM)} | celula ${lastAntenna7dbMaxBeamRadiusKm.toFixed(1)} km`;
    } else if (footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_MASK) {
        footprintInfo.textContent = `${formatKm(INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM)} max. | mascara elev. >= ${SHARC_INTERFERENCE_ACTIVE_MIN_ELEVATION_DEG.toFixed(1)}°`;
    } else if (footprintModeSelect.value === FOOTPRINT_MODE_SHARC_INTERFERENCE_LINK) {
        footprintInfo.textContent = `${formatKm(INTERFERENCE_ACTIVE_FOOTPRINT_DIAMETER_KM)} max. | link budget`;
    }
    const dxKm = GLOBAL_HEX_RADIUS_KM * 1.5;
    const dyKm = GLOBAL_HEX_RADIUS_KM * Math.sqrt(3);
    const processedRings = []; 

    drawPresentationFootprintCones(frame, satBeamCounts);

    if (false) {
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
    }

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

        if (count > 0) {
            entity.point.color = Cesium.Color.LIME.withAlpha(1.0);
            entity.point.pixelSize = ACTIVE_SATELLITE_PIXEL_SIZE;
            entity.label.text = `${satellite.id}\n${count} cel`;
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
            entity.label.horizontalOrigin = Cesium.HorizontalOrigin.CENTER;
            entity.label.verticalOrigin = Cesium.VerticalOrigin.TOP;
            entity.label.pixelOffset = new Cesium.Cartesian2(0, 14);
            entity.label.disableDepthTestDistance = Number.POSITIVE_INFINITY; 
        } else {
            entity.label.show = false;
            entity.point.color = Cesium.Color.CYAN.withAlpha(0.58);
            entity.point.pixelSize = INACTIVE_SATELLITE_PIXEL_SIZE;
        }

        if (isPresentationProfile()) {
            entity.label.show = false;
        }
    });

    if (isDynamicFootprintMode()) {
        drawAntenna7dbPreviewCells(activeHexagonsMap);
    } else {
        activeHexagonsMap.forEach((assignment, key) => {
            const entity = globalGridEntities.get(key);
            if (entity) {
                applyFixedGridAssignment(entity, assignment);
                entity.show = true;
                activeCellsThisFrame.push(entity);
                activeCellEntitySet.add(entity);
            }
        });
    }

    renderRandomUesForActiveCells();

    viewer.entities.resumeEvents(); 

    frameInfo.textContent = `${frameIndex + 1} / ${simulation.frames.length}`;
    activeCount.textContent = String(activeCountsList.length);
    coverageInfo.textContent = `${(100 * activeHexagonsMap.size / Math.max(1, globalGridCells.size)).toFixed(1)}%`;
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

if (captureBtn) {
    captureBtn.addEventListener("click", () => {
        document.body.classList.toggle("capture-mode");
        captureBtn.textContent = document.body.classList.contains("capture-mode") ? "HUD" : "Print";
        viewer.scene.requestRender();
    });
}

if (hudDrawerToggle && hud) {
    hudDrawerToggle.addEventListener("click", () => {
        const collapsed = hud.classList.toggle("is-collapsed");
        hudDrawerToggle.setAttribute("aria-label", collapsed ? "Abrir painel" : "Recolher painel");
        hudDrawerToggle.title = collapsed ? "Abrir painel" : "Recolher painel";
    });
}

if (scenarioSelect) {
    scenarioSelect.addEventListener("change", async () => {
        try {
            scenarioWasSelectedByUser = true;
            footprintAssignmentCache.clear();
            await loadSimulation(profileSelect.value);
        } catch (error) {
            setStatus(error.message);
            console.error(error);
        }
    });
}

if (mitigationToggleBtn) {
    mitigationToggleBtn.addEventListener("click", () => {
        mitigationEnabled = !mitigationEnabled;
        footprintAssignmentCache.clear();
        updateMitigationControls();
        activeCellsThisFrame.forEach(entity => { if (entity) resetGridCellEntity(entity); });
        activeCellsThisFrame.length = 0;
        activeCellEntitySet.clear();
        renderFrame(currentFrameIndex);
    });
}

if (azimuthToggleBtn) {
    azimuthToggleBtn.addEventListener("click", () => {
        showAzimuthVector = !showAzimuthVector;
        updateAzimuthVector();
        viewer.scene.requestRender();
    });
}

if (ueDensitySlider) {
    ueDensitySlider.addEventListener("input", (event) => {
        ueMaxPerCell = Number(event.target.value) || 1;
        updateUeDensityControl();
        renderRandomUesForActiveCells();
        viewer.scene.requestRender();
    });
    updateUeDensityControl();
}

reloadBtn.addEventListener("click", async () => {
    try {
        await loadSimulation(profileSelect.value);
    } catch (error) {
        setStatus(error.message);
        console.error(error);
    }
});

footprintModeSelect.addEventListener("change", () => {
    updateFootprintModeHelp();
    updateFootprintInfo();
    renderFrame(currentFrameIndex);
    focusFirstSatelliteFootprint();
});

viewer.scene.canvas.addEventListener("mousemove", (event) => {
    handleCellPointer(event);
});

viewer.scene.canvas.addEventListener("click", (event) => {
    const foundCell = handleCellPointer(event, { hideWhenEmpty: false });
    if (!foundCell) {
        setStatus("Nenhuma célula ativa selecionada.");
    }
});

frameSlider.addEventListener("input", (event) => {
    stopPlayback();
    renderFrame(Number(event.target.value));
});

async function init() {
    try {
        const pageParams = new URLSearchParams(window.location.search);
        const requestedProfile = pageParams.get("profile");
        if (requestedProfile) {
            profileSelect.value = requestedProfile;
        }
        const requestedScenario = pageParams.get("scenario");
        const requestedParamFile = pageParams.get("param_file") || "";
        if (requestedScenario && SCENARIO_PARAM_FILES[requestedScenario] && scenarioSelect) {
            scenarioSelect.value = requestedScenario;
            scenarioWasSelectedByUser = true;
        } else if (requestedParamFile.includes("BR_AR") && scenarioSelect) {
            scenarioSelect.value = "brarg";
        } else if (requestedParamFile.includes("SouthAmerica") && scenarioSelect) {
            scenarioSelect.value = "sa";
        }
        updateMitigationControls();
        updateAzimuthToggleControl();
        viewer.terrainProvider = await Cesium.createWorldTerrainAsync();
        viewer.imageryLayers.removeAll();
        const imagery = await Cesium.IonImageryProvider.fromAssetId(2);
        viewer.imageryLayers.addImageryProvider(imagery);
        await loadSimulation(profileSelect.value);
    } catch (error) {
        setStatus(error.message);
        console.error("ERRO NO INIT:", error);
    }
}

init();
