/**
 * Render karuzeli LinkedIn: slides.html -> 10 x PNG 1080x1350 (@2x) + jeden PDF.
 *
 *   npm install          (raz, w tym katalogu)
 *   node render.mjs
 *
 * Poprawka tekstu = edycja slides.html + ponowny render. Nic nie jest wypalane
 * w bitmapie, wiec literowka nie kosztuje nowej grafiki.
 *
 * Fonty sa lokalne (fonts/), wiec render nie zalezy od sieci -- tak jak reszta
 * tego repozytorium, gdzie nawet xml.xsd jest zawendorowany po to, zeby bramka
 * dzialala offline.
 */
import { chromium } from 'playwright';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync } from 'node:fs';

const here = dirname(fileURLToPath(import.meta.url));
const SRC = pathToFileURL(join(here, 'slides.html')).href;
const OUT = join(here, 'out');
mkdirSync(OUT, { recursive: true });

const IDS = ['s01', 's02', 's03', 's04', 's05', 's06', 's07', 's08', 's09', 's10', 's11'];

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1080, height: 1350 },
  deviceScaleFactor: 2,
});
await page.goto(SRC, { waitUntil: 'networkidle', timeout: 45000 });
await page.evaluate(() => document.fonts.ready);

// 1) PNG per slajd -- post wieloobrazkowy.
for (let i = 0; i < IDS.length; i++) {
  const file = String(i + 1).padStart(2, '0') + '.png';
  await page.locator('#' + IDS[i]).screenshot({ path: join(OUT, file) });
  console.log('PNG  ' + file);
}

// 2) Jeden PDF -- post dokumentowy (karuzela na LinkedIn). @page w CSS daje
//    jeden slajd na strone.
await page.pdf({
  path: join(OUT, 'karuzela.pdf'),
  width: '1080px',
  height: '1350px',
  printBackground: true,
  preferCSSPageSize: true,
});
console.log('PDF  karuzela.pdf');

await browser.close();
console.log('\nGotowe -> ' + OUT);
