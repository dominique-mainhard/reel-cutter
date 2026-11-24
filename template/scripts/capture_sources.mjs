// Real screenshots of the sources a reel cites (studies, news, laws), cropped to the part that matters.
// Usage (from the project root): node scripts/capture_sources.mjs <out dir> <jobs.json>
// Needs puppeteer-core in the project (npm i puppeteer-core@23.11.1) and Google Chrome installed.
//
// jobs.json = [{name, url, find | selector, highlight?, translate?, top?, up?, width?, dpr?, pad?, wait?}]
//   find:      text the block must contain (the deepest element containing it is captured)
//   selector:  CSS selector instead of find (e.g. "h1")
//   up:        climb N parents from the match (headline + date + byline)
//   highlight: exact text inside the block to mark in yellow (works across Google Translate's <font> pieces)
//   translate: target language ("es"). Loads the page through Google Translate (translate.goog), so the
//              capture shows the real page translated. Use it for languages the audience can't read.
//              With top: true the Google Translate bar ("chino → español") stays visible: honest signal.
//   top:       capture the top of the page (header, title, date) instead of a block; height = width * 1.1
//   width:     CSS viewport width. 440 (phone) with dpr 3 gives big readable text in a reel; default 440.
// Pop-ups, cookie banners, sticky bars and gallery arrows are hidden before the shot. Never edit the text.
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const [outdir, jobsPath] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
fs.mkdirSync(outdir, {recursive: true});
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--hide-scrollbars'],
});

const viaTranslate = (url, tl) => {
  const u = new URL(url);
  const host = u.hostname.replace(/-/g, '--').replace(/\./g, '-') + '.translate.goog';
  const q = new URLSearchParams(u.search);
  q.set('_x_tr_sl', 'auto'); q.set('_x_tr_tl', tl); q.set('_x_tr_hl', tl);
  return `https://${host}${u.pathname}?${q}`;
};

for (const j of jobs) {
  const page = await browser.newPage();
  const width = j.width || 440;
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36');
  await page.setViewport({width, height: 1600, deviceScaleFactor: j.dpr || 3});
  try {
    await page.goto(j.translate ? viaTranslate(j.url, j.translate) : j.url, {waitUntil: 'domcontentloaded', timeout: 45000});
    await new Promise((r) => setTimeout(r, j.wait || (j.translate ? 9000 : 4000)));
    if (j.top) {
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({path: `${outdir}/${j.name}.png`, clip: {x: 0, y: 0, width, height: Math.round(width * 1.1)}});
      console.log('OK', j.name, '(top)');
      await page.close();
      continue;
    }
    const box = await page.evaluate((j) => {
      const keep = (e) => e !== document.body && e !== document.documentElement;
      document.querySelectorAll('[id*=didomi],[class*=didomi],[role=dialog],[aria-modal=true],[id*=consent],[class*=consent]')
        .forEach((e) => { if (keep(e) && !e.contains(document.querySelector('h1'))) e.remove(); });
      document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
      // fixed/sticky bars and gallery arrows; !important because some sites re-show them on scroll
      const hideFixed = () => { for (const el of document.querySelectorAll('body *')) {
        const s = getComputedStyle(el);
        if (s.position === 'fixed' || s.position === 'sticky') el.style.setProperty('visibility', 'hidden', 'important');
      } };
      hideFixed();
      let best = null;
      if (j.selector) best = document.querySelector(j.selector);
      else {
        const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        while (w.nextNode()) { const el = w.currentNode; if (el.offsetHeight && (el.innerText || '').includes(j.find)) best = el; }
      }
      if (!best) return null;
      if (j.highlight) {
        // works even when the text is split across many nodes (Google Translate <font>s)
        const tw = document.createTreeWalker(best, NodeFilter.SHOW_TEXT); const nodes = []; let all = '';
        while (tw.nextNode()) { nodes.push([tw.currentNode, all.length]); all += tw.currentNode.data; }
        const i0 = all.indexOf(j.highlight), i1 = i0 + j.highlight.length;
        const at = (i) => { for (let k = nodes.length - 1; k >= 0; k--) if (nodes[k][1] <= i) return [nodes[k][0], i - nodes[k][1]]; };
        if (i0 >= 0) {
          const r = document.createRange(); r.setStart(...at(i0)); const [en, eo] = at(i1 - 1); r.setEnd(en, eo + 1);
          // CSS Custom Highlight: follows the text even if the page reflows (lazy ads), unlike drawn boxes
          CSS.highlights.set('src-mark', new Highlight(r));
          const st = document.createElement('style'); st.textContent = '::highlight(src-mark){background-color:#fff27a;color:inherit}';
          document.head.appendChild(st);
        } else console.log('highlight not found');
      }
      let el = best; for (let k = 0; k < (j.up || 0); k++) el = el.parentElement;
      el.scrollIntoView({block: 'center'});
      let b = el.getBoundingClientRect();
      for (const px of [4, 12, 20, 30, innerWidth - 4, innerWidth - 20]) for (const py of [b.top + 2, b.top + b.height / 2, b.bottom - 2])
        for (const o of document.elementsFromPoint(px, py)) if (!o.contains(el) && !el.contains(o)) o.style.visibility = 'hidden';
      hideFixed();
      b = el.getBoundingClientRect();
      return {x: b.x + scrollX, y: b.y + scrollY, w: b.width, h: b.height};
    }, j);
    if (!box) { console.log('NOT FOUND', j.name); await page.close(); continue; }
    const pad = j.pad ?? 16;
    const clip = {x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: Math.min(box.w + pad * 2, width), height: Math.min(box.h + pad * 2, 1800)};
    await new Promise((r) => setTimeout(r, 400));
    await page.evaluate(() => { for (const el of document.querySelectorAll('body *')) { const p = getComputedStyle(el).position; if (p === 'fixed' || p === 'sticky') el.style.setProperty('visibility', 'hidden', 'important'); } });
    await page.screenshot({path: `${outdir}/${j.name}.png`, clip, captureBeyondViewport: true});
    console.log('OK', j.name);
  } catch (e) { console.log('FAIL', j.name, e.message); }
  await page.close();
}
await browser.close();
