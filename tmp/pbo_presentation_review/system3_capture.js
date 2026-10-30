"use strict";

(async function prepareCapture() {
    const status = document.createElement('div');
    status.id = 'system3-state';
    status.textContent = 'Preparando geometria...';
    document.body.append(status);

    const ready = setInterval(() => {
        if (!simulation?.frames?.length || !satelliteEntities.size) return;
        clearInterval(ready);
        stopPlayback();
        viewer.entities.values.forEach(entity => { entity.show = false; });
        satelliteEntities.forEach(entity => {
            entity.show = true;
            entity.point.pixelSize = 3.5;
            entity.point.color = Cesium.Color.fromCssColorString('#f39234');
            entity.point.outlineColor = Cesium.Color.fromCssColorString('#834018');
            entity.point.outlineWidth = 0.35;
            if (entity.label) entity.label.show = false;
        });
        viewer.scene.backgroundColor = Cesium.Color.WHITE;
        viewer.scene.skyBox.show = false;
        viewer.scene.sun.show = false;
        viewer.scene.moon.show = false;
        viewer.scene.globe.enableLighting = false;
        viewer.scene.skyAtmosphere.show = true;
        viewer.camera.setView({destination: Cesium.Cartesian3.fromDegrees(-55, -10, 18500000),
            orientation: {heading: 0, pitch: -Math.PI / 2, roll: 0}});
        viewer.resize();
        viewer.scene.requestRender();
        status.textContent = '';
        document.body.dataset.captureReady = 'true';
    }, 300);
})();
