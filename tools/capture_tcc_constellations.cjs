/* Isolated Cesium captures. No simulator frontend or campaign files are edited. */
const {chromium} = require('C:/Users/joaop/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'figuras');
const data = path.join(out, 'tcc_constellations_capture');
// Reuse the viewer's configured imagery credentials without exporting them.
const auth = fs.readFileSync(path.join(root, 'sharc/satellite/ngso/frontend/app.js'), 'utf8').split('\n')[0];
const html = `<!doctype html><meta charset="utf-8">
<script src="https://cesium.com/downloads/cesiumjs/releases/1.120/Build/Cesium/Cesium.js"></script>
<link rel="stylesheet" href="https://cesium.com/downloads/cesiumjs/releases/1.120/Build/Cesium/Widgets/widgets.css">
<style>html,body,#globe{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}
.cesium-widget,.cesium-widget canvas{background:transparent!important}
.cesium-viewer-bottom,.cesium-viewer-toolbar,.cesium-viewer-fullscreenContainer{display:none!important}</style>
<div id="globe"></div><script>${auth}
const viewer = new Cesium.Viewer('globe', {
 animation:false, timeline:false, baseLayerPicker:false, geocoder:false,
 homeButton:false, infoBox:false, selectionIndicator:false, navigationHelpButton:false,
 fullscreenButton:false, shouldAnimate:false, requestRenderMode:false,
 contextOptions:{webgl:{alpha:true,preserveDrawingBuffer:true}}
});
viewer.scene.backgroundColor=Cesium.Color.TRANSPARENT;
viewer.scene.skyBox.show=false;viewer.scene.sun.show=false;viewer.scene.moon.show=false;
viewer.scene.globe.enableLighting=false;viewer.scene.skyAtmosphere.show=false;
viewer.scene.globe.showGroundAtmosphere=false;
viewer.scene.globe.depthTestAgainstTerrain=true;
viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-55,-10,18500000),
 orientation:{heading:0,pitch:-Math.PI/2,roll:0}});
viewer.camera.frustum.fov=Cesium.Math.toRadians(35);
const dots=viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
window.loadOrbit=async function(altitude){
 const payload=await (await fetch('/orbit_'+altitude+'km.json')).json();dots.removeAll();
 for(const [lon,lat,alt] of payload.satellites){dots.add({
  position:Cesium.Cartesian3.fromDegrees(lon,lat,alt*1000),pixelSize:6,
  color:Cesium.Color.fromCssColorString('#f39234'),
  outlineColor:Cesium.Color.fromCssColorString('#834018'),outlineWidth:.35,
  disableDepthTestDistance:0});}
 viewer.scene.requestRender();return {count:dots.length,altitude:payload.altitude_km,
  planes:payload.orbital_parameters.n_planes,perPlane:payload.orbital_parameters.sats_per_plane,
  inclination:payload.orbital_parameters.inclination_deg};
};
</script>`;

(async()=>{
 const server=http.createServer((req,res)=>{
  const route=new URL(req.url,'http://localhost').pathname;
  if(route==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);return;}
  if(!/^\/orbit_(340|525)km\.json$/.test(route)){res.writeHead(404).end();return;}
  res.writeHead(200,{'Content-Type':'application/json'});res.end(fs.readFileSync(path.join(data,route.slice(1))));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try{
  browser=await chromium.launch({headless:true,channel:'chrome'});
  const page=await browser.newPage({viewport:{width:1200,height:1200},deviceScaleFactor:2.5});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:'+server.address().port,{waitUntil:'load',timeout:120000});
  await page.waitForFunction(()=>typeof window.loadOrbit==='function',{}, {timeout:120000});
  const report={sourceAdapter:'tmp/pbo_presentation_review/system3_capture.js',
    noServiceLayers:true,transparentBackground:true,satelliteSymbolPixels:6,
    sameCamera:true,orbitalFrameSeconds:0,views:[],errors};
  for(const altitude of [340,525]){
   const meta=await page.evaluate(alt=>window.loadOrbit(alt),altitude);
   await page.waitForFunction(()=>viewer.scene.globe.tilesLoaded,{}, {timeout:180000});
   await page.waitForTimeout(5000);
   const canvas=await page.evaluate(()=>({width:viewer.canvas.width,height:viewer.canvas.height,
      imageryLayers:viewer.imageryLayers.length,tilesLoaded:viewer.scene.globe.tilesLoaded,
      credits:[...new Set([...document.querySelectorAll('.cesium-credit-lightbox li')].map(n=>n.textContent.trim()))]}));
   if(meta.count!==(altitude===340?5280:3360))throw Error('Wrong constellation count');
   await page.screenshot({path:path.join(out,`fig_constelacao_${altitude}km.png`),omitBackground:true});
   report.views.push({...meta,...canvas});console.log(JSON.stringify({altitude,count:meta.count,tilesLoaded:canvas.tilesLoaded}));
  }
  await page.evaluate(()=>viewer.destroy());await page.close();
  const panels=await browser.newPage({viewport:{width:2440,height:1315},deviceScaleFactor:2.5});
  const images=[340,525].map(alt=>'data:image/png;base64,'+fs.readFileSync(path.join(out,`fig_constelacao_${alt}km.png`)).toString('base64'));
  await panels.setContent(`<!doctype html><meta charset="utf-8"><style>
   html,body{margin:0;background:transparent;font-family:Arial,sans-serif;color:#46525a}
   main{display:flex;gap:40px}section{width:1200px;text-align:center}img{width:1200px;height:1200px;display:block}
   .label{font-size:36px;font-weight:600;margin-top:0;color:#39789c}.details{font-size:29px;margin-top:12px}
   </style><main><section><img src="${images[0]}"><div class="label">(a) 340 km</div>
   <div class="details">48 planos × 110 satélites = 5 280 satélites</div></section>
   <section><img src="${images[1]}"><div class="label">(b) 525 km</div>
   <div class="details">28 planos × 120 satélites = 3 360 satélites</div></section></main>`);
  await panels.evaluate(()=>Promise.all([...document.images].map(im=>im.decode())));
  await panels.screenshot({path:path.join(out,'fig_constelacoes_dc_mss_imt.png'),omitBackground:true});
  // White preview for chat; the publication PNG above keeps its alpha channel.
  await panels.evaluate(()=>document.body.style.background='white');
  await panels.screenshot({path:path.join(out,'fig_constelacoes_dc_mss_imt_preview.png'),scale:'css'});
  fs.writeFileSync(path.join(data,'validation.json'),JSON.stringify(report,null,2));
  fs.writeFileSync(path.join(data,'notas.txt'),
   'Constelações de 340 km (5280 satélites) e 525 km (3360 satélites), ambas com inclinação de 53 graus.\n'+
   'OrbitModel original do SHARC, t=0; não são snapshots de resultados da campanha.\n'+
   'Satélites laranjas: símbolos sem escala física e sem codificação de atividade ou PBO.\n'+
   'A Terra oculta os satélites no lado oposto. Mesma câmera e escala nos dois painéis.\n'+
   'Fonte cartográfica: Cesium ion / Bing Maps. Créditos completos: '+report.views.map(v=>v.credits.join(' | ')).join('\n')+'\n');
 }finally{if(browser)await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
