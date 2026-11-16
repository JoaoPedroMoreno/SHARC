/* Two camera captures of the ORIGINAL NGSO scene, composed without redrawing it. */
const {chromium}=require('C:/Users/joaop/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const frontend=path.join(root,'sharc/satellite/ngso/frontend');
const out=path.join(root,'figuras/tcc_geographic_capture');
(async()=>{
    const server=http.createServer((req,res)=>{
        const route=new URL(req.url,'http://localhost').pathname;
        const target=route==='/api/simulation'?path.join(out,'original_backend_frame.json')
            :path.resolve(frontend,'.'+(route==='/'?'/index.html':decodeURIComponent(route)));
        if(route!=='/api/simulation'&&!target.startsWith(frontend+path.sep)){res.writeHead(403).end();return;}
        fs.readFile(target,(err,body)=>{
            if(err){res.writeHead(404).end();return;}
            const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css','.json':'application/json'};
            res.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream'}).end(body);
        });
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    let browser;
    try {
        browser=await chromium.launch({headless:true,channel:'chrome'});
        let captures=[], report, views;
        if(process.argv.includes('--layout-only')) {
            report=JSON.parse(fs.readFileSync(path.join(root,'figuras/fig_cenario_geografico_validation.json'),'utf8'));
            views=report.views;
            captures=views.map(view=>({...view,dataUrl:'data:image/png;base64,'+
                fs.readFileSync(path.join(out,`native_${view.name}.png`)).toString('base64')}));
        } else {
        const page=await browser.newPage({viewport:{width:1600,height:920},deviceScaleFactor:2});
        page.on('pageerror',e=>console.error(String(e)));
        await page.goto(`http://127.0.0.1:${server.address().port}/?profile=presentation&capture=publication&lang=pt`,{waitUntil:'domcontentloaded',timeout:90000});
        await page.waitForFunction(()=>typeof simulation!=='undefined'&&simulation&&globalGridCells.size>0,{},{timeout:180000});
        await page.evaluate(()=>document.getElementById('mitigationToggleBtn').click());
        await page.addStyleTag({content:`
            html,body{margin:0!important;padding:0!important;width:100vw;height:100vh;overflow:hidden;}
            #cesiumContainer{position:absolute!important;inset:0!important;width:100vw!important;height:100vh!important;margin:0!important;}
            .hud,.publication-caption,.cell-tooltip,#interferenceLegend,.cesium-viewer-toolbar,.cesium-viewer-bottom{display:none!important;}
            .capture-label{position:absolute;z-index:5;pointer-events:none;color:white;font:15px Arial;white-space:pre;text-align:center;transform:translate(-50%,-50%);text-shadow:-1px -1px 2px #10222d,1px 1px 2px #10222d;}
        `});
        views=[
            {name:'continent',width:1040,height:1060,bounds:[-83,-57,-32,14],labels:[
                ['BRASIL',-49,-12],['ARGENTINA',-65,-38],['CHILE',-74,-31],['BOLÍVIA',-65,-17],
                ['PERU',-76,-10],['EQUADOR',-80,-2],['COLÔMBIA',-73,5],['VENEZUELA',-65,8],
                ['URUGUAI',-55,-34],['PARAGUAI',-59,-23],['GUIANA',-61,4],['SURINAME',-53,6]]},
            {name:'paraguay',width:540,height:615,bounds:[-65,-29,-52,-18],labels:[
                ['PARAGUAI',-59,-23],['BRASIL',-54,-21],['ARGENTINA',-62,-27.2],['BOLÍVIA',-61.5,-19],
                ['Receptor FS\nCiudad del Este',-56.8,-26.25]]},
        ];
        const originalFov=await page.evaluate(()=>viewer.camera.frustum.fov);
        for(const view of views) {
            await page.setViewportSize({width:view.width,height:view.height});
            await page.evaluate(({bounds,originalFov})=>{
                document.querySelectorAll('.capture-label').forEach(n=>n.remove());
                stopPlayback();viewer.resolutionScale=1;viewer.resize();
                viewer.camera.frustum.xOffset=0;
                viewer.camera.frustum.fov=originalFov;
                viewer.camera.setView({destination:Cesium.Rectangle.fromDegrees(...bounds)});
                viewer.scene.requestRender();
            },{...view,originalFov});
            if(view.name==='continent') {
                // Extend the original camera to the right without moving or stretching the map.
                const lens=await page.evaluate(()=>({fovy:viewer.camera.frustum.fovy,near:viewer.camera.frustum.near}));
                await page.setViewportSize({width:2160,height:view.height});
                await page.evaluate(({fovy,near,height})=>{
                    viewer.resize();
                    const frustum=viewer.camera.frustum;
                    frustum.aspectRatio=2160/height;
                    frustum.fov=2*Math.atan(Math.tan(fovy/2)*frustum.aspectRatio);
                    frustum.xOffset=0;
                    viewer.scene.requestRender();
                },{...lens,height:view.height});
                view.width=1600;
            }
            await page.waitForFunction(()=>viewer.scene.globe.tilesLoaded,{},{timeout:180000});
            await page.waitForTimeout(7000);
            await page.evaluate(({labels,name})=>{
                for(const [label,lon,lat] of labels) {
                    const p=Cesium.SceneTransforms.worldToWindowCoordinates(viewer.scene,Cesium.Cartesian3.fromDegrees(lon,lat));
                    const el=document.createElement('div');el.className='capture-label';el.textContent=label;
                    el.style.left=p.x+'px';el.style.top=p.y+'px';el.style.fontSize=name==='continent'?'15px':'18px';
                    document.body.appendChild(el);
                }
            },view);
            const filename=path.join(out,`native_${view.name}.png`);
            await page.screenshot({path:filename,...(view.name==='continent'
                ?{clip:{x:560,y:0,width:1600,height:1060}}:{})});
            captures.push({name:view.name,width:view.width,height:view.height,bounds:view.bounds,
                dataUrl:'data:image/png;base64,'+fs.readFileSync(filename).toString('base64')});
        }
        report=await page.evaluate(()=>({nativeViewer:true,gridCells:globalGridCells.size,
            activeCones:activeConesCount,mitigationEnabled,station:simulation.station,
            gridCenters:Array.from(globalGridCells.values()).map(c=>[c.lon,c.lat]),
            countries:simulation.meta.serviceAreaCountryNames,
            tileLoadingComplete:viewer.scene.globe.tilesLoaded,
            credits:[...new Set([...document.querySelectorAll('.cesium-credit-lightbox li')].map(n=>n.textContent.trim()).filter(Boolean))]}));
        if(report.mitigationEnabled||report.activeCones===0)throw Error('Native scene not ready');
        await page.evaluate(()=>viewer.destroy());await page.close();
        }

        // External tangents connect the selected region to the larger circular lens.
        const small={x:507,y:559,r:93}, large={x:1322,y:310,r:260};
        const dx=large.x-small.x,dy=large.y-small.y,d=Math.hypot(dx,dy);
        const k=(small.r-large.r)/d,h=Math.sqrt(1-k*k);
        const normals=[1,-1].map(sign=>({x:k*dx/d-sign*h*dy/d,y:k*dy/d+sign*h*dx/d}));
        const tangent=(circle,n)=>`${circle.x+circle.r*n.x},${circle.y+circle.r*n.y}`;
        const tube=[tangent(small,normals[0]),tangent(large,normals[0]),
            tangent(large,normals[1]),tangent(small,normals[1])].join(' ');
        const layout=await browser.newPage({viewport:{width:1600,height:1060},deviceScaleFactor:2});
        await layout.setContent(`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><style>
            *{box-sizing:border-box}body{margin:0;background:#071923;color:white;font-family:Arial,sans-serif}
            .main{position:absolute;left:0;top:0;width:1600px;height:1060px}
            .lens{position:absolute;left:1062px;top:50px;width:520px;height:520px;overflow:hidden;border-radius:50%;border:2px solid #526b7c;box-shadow:0 0 0 5px white,0 0 0 6px #afbdc7;z-index:3}
            .detail{position:absolute;left:0;top:-36px;width:516px;height:auto}
            .connector{position:absolute;inset:0;pointer-events:none;z-index:2}
            .legend{position:absolute;left:1062px;top:632px;width:520px;padding:24px;font-size:20px;line-height:1.25;background:rgba(7,23,33,.9);border:1px solid rgba(226,238,246,.55);z-index:4}
            .row{display:flex;align-items:center;gap:17px;margin:0 0 23px}
            .icon{width:27px;flex:0 0 27px;display:flex;justify-content:center}
            .dot{display:block;width:17px;height:17px;border-radius:50%;border:2px solid #142632;background:#00ff00}
            .other{width:9px;height:9px;background:#29b8bd}.fs{background:white;width:21px;height:21px}
            .hex{font:37px Arial;line-height:24px;color:#e9a626}
            .zone{width:27px;height:21px;border:1px solid #bdced9;background:#c0d5e138}
            .frequency{font-size:17px;color:#d0dce4;margin-top:25px}
            </style><img class="main" alt="América do Sul" src="${captures[0].dataUrl}">
            <svg class="connector" width="1600" height="1060" viewBox="0 0 1600 1060" aria-hidden="true">
              <defs><mask id="outside-selection"><rect width="1600" height="1060" fill="white"/>
                <circle cx="${small.x}" cy="${small.y}" r="${small.r}" fill="black"/>
              </mask></defs>
              <polygon points="${tube}" fill="#d9e7ef" fill-opacity=".09" mask="url(#outside-selection)"/>
              ${normals.map(n=>`<polyline points="${tangent(small,n)} ${tangent(large,n)}" fill="none" stroke="#e5edf2" stroke-width="2.4"/>
                <polyline points="${tangent(small,n)} ${tangent(large,n)}" fill="none" stroke="#657d8e" stroke-opacity=".75" stroke-width=".9"/>`).join('')}
              <circle cx="${small.x}" cy="${small.y}" r="${small.r}" fill="none" stroke="#edf3f7" stroke-width="2.5"/>
              <circle cx="${small.x}" cy="${small.y}" r="${small.r+2}" fill="none" stroke="#526b7c" stroke-width=".8"/>
            </svg>
            <div class="lens"><img class="detail" alt="Ampliação do Paraguai" src="${captures[1].dataUrl}"></div>
            <aside class="legend">
              <div class="row"><span class="icon"><i class="dot"></i></span>Satélite em serviço</div>
              <div class="row"><span class="icon"><i class="dot other"></i></span>Outro satélite</div>
              <div class="row"><span class="icon hex">&#x2B21;</span>Célula de serviço DC-MSS-IMT</div>
              <div class="row"><span class="icon"><i class="dot fs"></i></span>Receptor FS</div>
              <div class="row"><span class="icon"><i class="zone"></i></span>Paraguai: sem atendimento<br>DC-MSS-IMT</div>
              <div class="frequency">Frequência compartilhada: 2 155 MHz</div>
            </aside></html>`);
        await layout.evaluate(()=>Promise.all([...document.images].map(im=>im.decode())));
        await layout.screenshot({path:path.join(root,'figuras/fig_cenario_geografico.png')});
        await layout.screenshot({path:path.join(root,'figuras/fig_cenario_geografico_preview.png'),scale:'css'});
        const textFits=await layout.locator('.legend').evaluate(el=>el.scrollWidth<=el.clientWidth);
        if(!textFits)throw Error('Legend overflow');
        report.views=views.map(({name,width,height,bounds})=>({name,width,height,bounds}));
        report.composition={width:3200,height:2120,legendFits:textFits,lens:{small,large},
            footer:false,fullBleedNativeBackground:true,legendStyle:'dark translucent panel',creditsRetainedInNotes:true,nativeImagesUnmodified:true};
        fs.writeFileSync(path.join(out,'map_attribution.txt'),
            'Cesium ion / Bing Maps | Natural Earth. '+report.credits.join(' | ')+'\n');
        fs.writeFileSync(path.join(root,'figuras/fig_cenario_geografico_validation.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify({...report,gridCenters:report.gridCenters.length}));
        await layout.close();
    } finally {server.closeAllConnections();server.close();if(browser)await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
