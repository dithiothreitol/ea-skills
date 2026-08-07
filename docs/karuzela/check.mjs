import { chromium } from 'playwright';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';
const here = dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
await page.goto(pathToFileURL(join(here, 'slides.html')).href, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
const rows = await page.evaluate(() => [...document.querySelectorAll('.slide')].map(s => {
  const c = s.querySelector('.content');
  const foot = s.querySelector('.foot');
  const sp = s.querySelector('.spacer');
  return { id: s.id, contentH: c.scrollHeight, boxH: c.clientHeight,
           slack: sp ? Math.round(sp.getBoundingClientRect().height) : -1,
           footTop: Math.round(foot.getBoundingClientRect().top - s.getBoundingClientRect().top) };
}));
for (const r of rows) {
  const over = r.contentH - r.boxH;
  const flag = over > 0 ? 'PRZEPELNIENIE +' + over : (r.slack > 420 ? 'PUSTO ' + r.slack + 'px' : 'ok');
  console.log(`${r.id}  tresc ${String(r.contentH).padStart(4)} / ${r.boxH}  luz ${String(r.slack).padStart(4)}  stopka@${r.footTop}  ${flag}`);
}
await browser.close();
