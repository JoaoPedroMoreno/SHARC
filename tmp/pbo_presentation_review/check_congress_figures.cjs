const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("C:/Users/joaop/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

const assets = "C:/GitHub/SHARC/sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets/v4";
const previews = "C:/GitHub/SHARC/tmp/pbo_presentation_review";
const names = ["cover_pbo_selective.png", "sharc_monte_carlo_methodology.png"];

(async () => {
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  try {
    for (const width of [1920, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: width * 9 / 16 }, deviceScaleFactor: 1 });
      for (const name of names) {
        const src = "data:image/png;base64," + fs.readFileSync(path.join(assets, name)).toString("base64");
        await page.setContent(`<!doctype html><html><head><style>body{margin:0;background:white}img{display:block;width:100vw;height:100vh;object-fit:contain}</style></head><body><img alt="${name}" src="${src}"></body></html>`);
        await page.locator("img").evaluate(img => img.decode());
        const state = await page.locator("img").evaluate(img => ({
          file: img.alt, source: [img.naturalWidth, img.naturalHeight],
          displayed: [img.width, img.height], complete: img.complete
        }));
        if (!state.complete || state.source[0] !== 3200 || state.source[1] !== 1800) throw new Error(JSON.stringify(state));
        await page.screenshot({ path: path.join(previews, `${path.parse(name).name}_${width}.png`) });
        console.log(state);
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
