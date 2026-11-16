const {chromium} = require('C:/Users/joaop/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname,'..');
(async()=>{
    const server = http.createServer((req,res)=>{
        const target=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
        if(!target.startsWith(root+path.sep)) {res.writeHead(403).end();return;}
        fs.readFile(target,(error,body)=>{
            if(error){res.writeHead(404).end();return;}
            const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css','.json':'application/json'};
            res.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream'}).end(body);
        });
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    let browser;
    try {
        browser = await chromium.launch({headless:true,channel:'chrome'});
        const page = await browser.newPage({viewport:{width:3200,height:2200},deviceScaleFactor:1});
        await page.goto(`http://127.0.0.1:${server.address().port}/tools/tcc_geography.html`,{waitUntil:'domcontentloaded',timeout:90000});
        await page.waitForFunction(()=>window.geographyReady || window.geographyError,{},{timeout:180000});
        const error = await page.evaluate(()=>window.geographyError);
        if(error) throw new Error(error);
        await page.waitForFunction(()=>geographyViewers.every(v=>v.scene.globe.tilesLoaded),{},{timeout:180000});
        await page.waitForFunction(()=>geographyViewers.every(v=>v.dataSourceDisplay.ready),{},{timeout:180000});
        await page.waitForTimeout(6000);
        await page.screenshot({path:path.join(root,'figuras/fig_cenario_geografico.png')});
        const report = await page.evaluate(()=>({errors:captureErrors,canvases:geographyViewers.map(v=>({
            width:v.scene.canvas.width,height:v.scene.canvas.height,tilesLoaded:v.scene.globe.tilesLoaded,
            imageryLayers:v.imageryLayers.length,entities:v.entities.values.length})),
            orbitalOverlays:[...document.querySelectorAll('canvas[data-serving]')].map(c=>({serving:Number(c.dataset.serving),cones:Number(c.dataset.cones)})),
            credits:document.getElementById('credits').textContent}));
        fs.writeFileSync(path.join(root,'figuras/fig_cenario_geografico_validation.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify(report));
        await page.evaluate(()=>geographyViewers.forEach(v=>v.destroy()));
        await page.close();
    } finally {
        server.closeAllConnections();
        server.close();
        if(browser) await browser.close({reason:'Figure exported'});
    }
})().catch(e=>{console.error(e);process.exitCode=1;});
