/* Isolated geographic export using the NGSO viewer's Cesium version and imagery. */
(async () => {
    const app = await (await fetch('/sharc/satellite/ngso/frontend/app.js')).text();
    Cesium.Ion.defaultAccessToken = app.match(/defaultAccessToken\s*=\s*"([^"]+)"/)[1];
    const data = await (await fetch('/figuras/tcc_geography_data.json')).json();
    const C = Cesium.Color;
    // A georeferenced overlay avoids asynchronous polygon tessellation during export.
    const overlay = document.createElement('canvas');
    overlay.width = 3072; overlay.height = 4096;
    const ctx = overlay.getContext('2d');
    const extent = [-83,-57,-32,14];
    const project = ([lon,lat]) => [(lon-extent[0])/(extent[2]-extent[0])*overlay.width,
        (extent[3]-lat)/(extent[3]-extent[1])*overlay.height];
    for (const feature of data.countries.features) {
        const {name,service} = feature.properties;
        if (!service && name !== 'Paraguay') continue;
        const polygons = feature.geometry.type==='Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
        ctx.beginPath();
        for (const polygon of polygons) for (const ring of polygon) {
            ring.forEach((coord,i) => { const [x,y]=project(coord); i ? ctx.lineTo(x,y) : ctx.moveTo(x,y); });
            ctx.closePath();
        }
        ctx.fillStyle = service ? 'rgba(231,171,54,.10)' : 'rgba(181,208,223,.25)';
        ctx.fill('evenodd');
        ctx.strokeStyle = name==='Paraguay' ? '#ffffff' : 'rgba(250,206,114,.85)';
        ctx.lineWidth = name==='Paraguay' ? 5 : 2;
        ctx.stroke();
    }
    // Clip the hexagonal visual mesh at country borders, especially Paraguay.
    ctx.save();
    ctx.beginPath();
    for(const f of data.countries.features.filter(f=>f.properties.service)) {
        const polygons=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates;
        for(const polygon of polygons) for(const ring of polygon) {
            ring.forEach((coord,i)=>{const [x,y]=project(coord);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
            ctx.closePath();
        }
    }
    ctx.clip('evenodd');
    ctx.beginPath();
    for(const [lon,lat] of data.cells) {
        for(let i=0;i<6;i++) {
            const a=i*Math.PI/3;
            const p=project([lon+data.beam_radius_km*Math.cos(a)/(111*Math.cos(lat*Math.PI/180)),
                lat+data.beam_radius_km*Math.sin(a)/111]);
            i?ctx.lineTo(...p):ctx.moveTo(...p);
        }
        ctx.closePath();
    }
    ctx.fillStyle='rgba(255,165,0,.10)';ctx.fill();
    ctx.lineWidth=1.1;ctx.strokeStyle='rgba(255,180,40,.85)';ctx.stroke();
    ctx.restore();
    const overlayUrl = overlay.toDataURL('image/png');
    const viewers = [];
    window.captureErrors = [];
    for (const [id, bounds] of [['main', [-83,-57,-32,14]], ['detail', [-65,-29,-52,-18]]]) {
        const viewer = new Cesium.Viewer(id, {timeline:false, animation:false, baseLayerPicker:false,
            geocoder:false, homeButton:false, infoBox:false, selectionIndicator:false,
            navigationHelpButton:false, sceneModePicker:false, fullscreenButton:false,
            requestRenderMode:false, sceneMode:Cesium.SceneMode.SCENE3D});
        viewers.push(viewer);
        viewer.scene.globe.enableLighting = false;
        viewer.scene.fog.enabled = false;
        viewer.scene.globe.maximumScreenSpaceError = 1;
        viewer.scene.postProcessStages.fxaa.enabled = true;
        viewer.scene.renderError.addEventListener((scene,error) => window.captureErrors.push(String(error)));
        const coverage = await Cesium.SingleTileImageryProvider.fromUrl(overlayUrl, {
            rectangle:Cesium.Rectangle.fromDegrees(...extent)});
        viewer.imageryLayers.addImageryProvider(coverage);
        function label(value,lon,lat,size=36) {
            const node=document.createElement('div');
            node.textContent=value;
            Object.assign(node.style,{position:'absolute',zIndex:2,pointerEvents:'none',
                whiteSpace:'pre',color:'white',font:`${size}px Arial`,transform:'translate(-50%,-50%)',
                textShadow:'-2px -2px 2px #10222d,2px -2px 2px #10222d,-2px 2px 2px #10222d,2px 2px 2px #10222d'});
            document.getElementById(id).appendChild(node);
            viewer.scene.postRender.addEventListener(()=>{
                const p=Cesium.SceneTransforms.worldToWindowCoordinates(viewer.scene,Cesium.Cartesian3.fromDegrees(lon,lat));
                if(p){node.style.left=p.x+'px';node.style.top=p.y+'px';}
            });
        }
        const marker = viewer.entities.add({position:Cesium.Cartesian3.fromDegrees(data.station.lon,data.station.lat),
            point:{pixelSize:id==='main'?24:30,color:C.WHITE,outlineColor:C.BLACK,outlineWidth:5,
                disableDepthTestDistance:Infinity}});
        if (id === 'main') {
            [['BRASIL',-49,-12],['ARGENTINA',-65,-38],['CHILE',-74,-31],['BOLÍVIA',-65,-17],
             ['PERU',-76,-10],['EQUADOR',-80,-2],['COLÔMBIA',-73,5],['VENEZUELA',-65,8],
             ['URUGUAI',-55,-34],['PARAGUAI',-59,-23],['GUIANA',-61,4],['SURINAME',-53,6]]
                .forEach(item => label(...item,30));
        } else {
            [['PARAGUAI',-59,-23],['BRASIL',-54,-21],['ARGENTINA',-62,-27.2],['BOLÍVIA',-63,-19]]
                .forEach(item => label(...item,38));
            label('Receptor FS\nCiudad del Este',-56.6,-26.25,34);
        }
        viewer.camera.setView({destination:Cesium.Rectangle.fromDegrees(...bounds)});
        const layer=document.createElement('canvas');
        Object.assign(layer.style,{position:'absolute',inset:0,pointerEvents:'none',zIndex:1});
        layer.width=viewer.scene.canvas.clientWidth;layer.height=viewer.scene.canvas.clientHeight;
        document.getElementById(id).appendChild(layer);
        const lc=layer.getContext('2d');
        const screen=(lon,lat,alt=0)=>Cesium.SceneTransforms.worldToWindowCoordinates(viewer.scene,
            Cesium.Cartesian3.fromDegrees(lon,lat,alt*1000));
        let painted=false;
        viewer.scene.postRender.addEventListener(()=>{
            if(painted)return;
            painted=true;
            lc.clearRect(0,0,layer.width,layer.height);
            const visible=data.satellites.map(s=>({s,p:screen(s.lon,s.lat,s.altKm)}))
                .filter(({p})=>p&&p.x>0&&p.x<layer.width&&p.y>0&&p.y<layer.height);
            const cones=visible.filter(({s})=>s.ring.length>=4)
                .sort((a,b)=>b.s.count-a.s.count).slice(0,10);
            for(const {s,p} of cones) {
                const ring=s.ring.slice(0,-1).map(([lon,lat])=>screen(lon,lat));
                const step=Math.max(1,Math.floor(ring.length/3));
                for(let i=0;i<ring.length;i+=step) {
                    const a=ring[i],b=ring[(i+step)%ring.length];if(!a||!b)continue;
                    lc.beginPath();lc.moveTo(p.x,p.y);lc.lineTo(a.x,a.y);lc.lineTo(b.x,b.y);lc.closePath();
                    lc.fillStyle='rgba(255,218,113,.09)';lc.fill();
                    lc.strokeStyle='rgba(255,225,143,.35)';lc.lineWidth=1.3;lc.stroke();
                }
            }
            for(const {s,p} of visible.sort((a,b)=>a.s.count-b.s.count)) {
                lc.beginPath();lc.arc(p.x,p.y,s.count?(id==='main'?6.5:11):3,0,Math.PI*2);
                lc.fillStyle=s.count?'#00ff00':'#29b8bd';lc.fill();
                lc.strokeStyle='#071219';lc.lineWidth=s.count?2.5:1.5;lc.stroke();
            }
            const fs=screen(data.station.lon,data.station.lat);
            lc.beginPath();lc.arc(fs.x,fs.y,id==='main'?12:15,0,Math.PI*2);
            lc.fillStyle='white';lc.fill();lc.strokeStyle='#071219';lc.lineWidth=5;lc.stroke();
            layer.dataset.serving=visible.filter(({s})=>s.count>0).length;
            layer.dataset.cones=cones.length;
        });
        viewer.scene.requestRender();
    }
    window.geographyViewers = viewers;
    function credits() {
        const nodes = [...document.querySelectorAll('.cesium-credit-lightbox li')];
        const values = [...new Set(nodes.map(n=>n.textContent.trim()).filter(Boolean))];
        document.getElementById('credits').textContent = 'Cesium ion / Bing Maps | Natural Earth. '+values.join(' | ');
    }
    credits();
    viewers.forEach(v=>v.scene.globe.tileLoadProgressEvent.addEventListener(credits));
    window.geographyReady = true;
})().catch(error => { window.geographyError = String(error); });
