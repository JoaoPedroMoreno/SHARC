const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("C:/Users/joaop/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const assets = "C:/GitHub/SHARC/sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets/v3";
(async () => {
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    const names = ["itu_pbo_overview_brazil.png", "itu_pbo_zoom_border.png"];
    const images = names.map(name => {
      const src = "data:image/png;base64," + fs.readFileSync(path.join(assets, name)).toString("base64");
      return '<img alt="' + name + '" src="' + src + '">';
    }).join("");
    await page.setContent('<!doctype html><html><head><style>body{margin:0;background:white}.preview{display:flex;gap:40px;align-items:center;justify-content:center;width:1920px;height:1080px}.preview img{width:876px;height:876px;object-fit:contain}</style></head><body><main class="preview">' + images + '</main></body></html>');
    await page.locator("img").evaluateAll(imgs => Promise.all(imgs.map(img => img.decode())));
    await page.screenshot({ path: "C:/GitHub/SHARC/tmp/pbo_presentation_review/slide_pair_v3.png" });
    console.log(await page.locator("img").evaluateAll(imgs => imgs.map(img => ({
      name: img.alt, naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight,
      displayedWidth: img.getBoundingClientRect().width, complete: img.complete
    }))));
  } finally {
    await browser.close();
  }
})().catch(err => { console.error(err); process.exit(1); });

