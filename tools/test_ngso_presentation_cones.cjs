const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../sharc/satellite/ngso/frontend/app.js'), 'utf8');
const start = source.indexOf('function drawPresentationFootprintCones(');
const end = source.indexOf('\nfunction renderFrame(', start);
assert.ok(start >= 0 && end > start);
const drawSource = source.slice(start, end);

function drawWithCounts(counts, presentation = true) {
    const scene = {
        isPresentationProfile: () => presentation,
        PRESENTATION_CONE_MAX_SATELLITES: 10,
        PRESENTATION_CONE_FACES: 3,
        PRESENTATION_CONE_MATERIAL: 'yellow',
        PRESENTATION_CONE_OUTLINE: 'yellow',
        conePool: [],
        activeConesCount: 0,
        Cesium: {
            Cartesian3: { fromDegrees: (...coordinates) => coordinates },
            PolygonHierarchy: function (positions) { this.positions = positions; },
        },
        viewer: { entities: { add: entity => entity } },
    };
    vm.createContext(scene);
    vm.runInContext(drawSource, scene);
    scene.drawPresentationFootprintCones({
        satellites: [{ id: 'sat-1', lon: -55, lat: -25, altKm: 340 }],
        footprints: [{
            satelliteId: 'sat-1',
            cellCount: 12,
            rings: [[[-55, -25], [-54, -25], [-55, -24], [-55, -25]]],
        }],
    }, counts);
    return scene;
}

test('no cone for an unassigned satellite despite a backend footprint', () => {
    assert.equal(drawWithCounts(new Map()).activeConesCount, 0);
});

test('no cone when the current assignment explicitly has zero cells', () => {
    assert.equal(drawWithCounts(new Map([['sat-1', 0]])).activeConesCount, 0);
});

test('a serving satellite retains its visible yellow cone', () => {
    const scene = drawWithCounts(new Map([['sat-1', 3]]));
    assert.equal(scene.activeConesCount, 3);
    assert.ok(scene.conePool.every(entity => entity.show));
});

test('other visual profiles remain unaffected', () => {
    assert.equal(drawWithCounts(new Map([['sat-1', 3]]), false).activeConesCount, 0);
});
