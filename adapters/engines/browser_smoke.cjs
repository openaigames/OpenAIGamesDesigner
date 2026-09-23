// Real browser load check of a chosen build. This does not test game mechanics.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const root = fs.realpathSync(request.root);
const errors = [], files = {};
let browser, server;
const result = {root, success: false, errors, canvas_count: 0, served_files: files};
const types = {'.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript',
  '.css':'text/css', '.json':'application/json', '.wasm':'application/wasm',
  '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml', '.ogg':'audio/ogg',
  '.mp3':'audio/mpeg', '.woff2':'font/woff2', '.glb':'model/gltf-binary'};
function contained(p) { const relative = path.relative(root, p); return !path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..'+path.sep); }
(async () => {
  try {
    server = http.createServer((req, res) => {
      try {
        let name = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname);
        if (name === '/favicon.ico' && !fs.existsSync(path.join(root, 'favicon.ico'))) { res.writeHead(204); res.end(); return; }
        if (name.endsWith('/')) name += 'index.html';
        let target = path.resolve(root, '.'+name);
        if (!contained(target)) { res.writeHead(403); res.end(); return; }
        target = fs.realpathSync(target);
        if (!contained(target) || !fs.statSync(target).isFile()) { res.writeHead(403); res.end(); return; }
        const bytes = fs.readFileSync(target);
        files[path.relative(root,target).replaceAll('\\','/')] = crypto.createHash('sha256').update(bytes).digest('hex');
        res.writeHead(200, {'Content-Type':types[path.extname(target)] || 'application/octet-stream', 'Cache-Control':'no-store'});
        res.end(bytes);
      } catch (_) { res.writeHead(404); res.end(); }
    });
    await new Promise((resolve, reject) => { server.once('error',reject); server.listen(0,'127.0.0.1',resolve); });
    const {chromium} = require(request.module);
    browser = await chromium.launch({executablePath:request.browser, headless:true});
    const page = await browser.newPage({viewport:{width:960,height:540}});
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => { if(m.type()==='error') errors.push(m.text()); });
    page.on('requestfailed', r => errors.push(r.url()+': '+r.failure()?.errorText));
    page.on('response', r => { if(r.status()>=400) errors.push(r.status()+' '+r.url()); });
    result.url = `http://127.0.0.1:${server.address().port}/`;
    const response = await page.goto(result.url, {waitUntil:'load',timeout:30000});
    await page.waitForTimeout(request.seconds*1000);
    result.status = response.status();
    result.canvas_count = await page.locator('canvas').evaluateAll(nodes => nodes.filter(n=>n.width>0 && n.height>0 && n.getBoundingClientRect().width>0).length);
    await page.screenshot({path:path.join(request.run,'browser.png')});
    result.browser_version = browser.version();
    result.success = result.status===200 && result.canvas_count>0 && errors.length===0;
    if (!result.canvas_count) errors.push('No visible nonempty canvas');
  } catch (e) { errors.push(String(e)); }
  finally {
    if(browser) await browser.close().catch(e=>errors.push(String(e)));
    if(server) await new Promise(resolve=>server.close(resolve));
    result.success = result.success && errors.length===0;
    fs.writeFileSync(path.join(request.run,'browser-result.json'), JSON.stringify(result,null,2));
    process.exitCode = result.success ? 0 : 1;
  }
})();
