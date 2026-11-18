/** Real Chromium/IndexedDB fixture, entirely local. No app login or production API.
 * CHROME_BIN=/path/to/chrome node frontend/scripts/check-offline-worker.mjs */
import { createServer } from 'vite'
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const profile = await mkdtemp(join(tmpdir(), 'eleven-offline-chrome-'))
const chromePath = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const fixture = String.raw`<!doctype html><meta charset="utf-8"><title>Offline catalog isolated fixture</title><script type="module">
const assert = (value, message) => { if (!value) throw new Error(message) }
let worker, sequence = 0; const waiting = new Map()
function openWorker() {
  worker = new Worker('/__offline-qa-worker.js', { type: 'module' })
  worker.onmessage = ({data}) => { const waiter = waiting.get(data.id); if (!waiter) return; waiting.delete(data.id); data.error ? waiter.reject(new Error(data.error)) : waiter.resolve(data.result) }
  worker.onerror = event => { for (const waiter of waiting.values()) waiter.reject(new Error(event.message)); waiting.clear() }
}
const rpc = (type, data={}) => new Promise((resolve,reject) => { window.__offlineStep=type; const id=++sequence, timeout=setTimeout(()=>{waiting.delete(id);reject(new Error('Worker timeout: '+type))},30000);waiting.set(id,{resolve:value=>{clearTimeout(timeout);resolve(value)},reject:error=>{clearTimeout(timeout);reject(error)}});worker.postMessage({id,type,data}) })
const row = i => ({ id:String(i), name:'Camiseta '+i, sku_internal:'QA-'+i, inventory_code:'INV-'+String(i).padStart(6,'0'),
  description:'Fixture local',brand:'Boss',category:'Roupas',size:'M',color:'Branco',unit:'un',sale_price:80,sale_currency:'USD',is_active:true,
  has_image:i<12,created_at:i===0?null:'2026-11-17',updated_at:'2026-11-17',current_stock:i===100?99:5,stock_loja:2,stock_deposito:3,
  reserved_loja:1,reserved_deposito:0,stock_confirmed:true,snapshot_at:'2026-11-17T12:00:00Z',min_stock:1,max_stock:10 })
const dbRequest = request => new Promise((resolve,reject) => { request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error) })
const committed = tx => new Promise((resolve,reject) => { tx.oncomplete=resolve;tx.onabort=tx.onerror=()=>reject(tx.error) })
try {
  await dbRequest(indexedDB.deleteDatabase('eleven-offline-catalog-v1'))
  openWorker();await rpc('init',{scope:'qa-a'});await rpc('begin',{generation:'complete'})
  const start=performance.now()
  for(let from=0;from<50000;from+=500)await rpc('put',{rows:Array.from({length:500},(_,i)=>row(from+i))})
  const meta=await rpc('finish',{startedAt:Date.now(),syncedAt:Date.now()})
  assert(meta.count===50000,'complete snapshot count')
  const page=await rpc('search',{query:'',filters:{},limit:100,offset:49900})
  assert(page.total===50000&&page.items.length===100,'last pagination page')
  assert((await rpc('search',{query:'INV-049999',filters:{}})).items[0]?.id==='49999','QR beyond first page')
  assert((await rpc('item',{id:'100'})).stock_loja===null,'inconsistent stock not invented')
  assert((await rpc('item',{id:'0'})).created_at==='','nullable legacy date normalized')
  const image='data:image/jpeg;base64,/9j/AA=='
  await rpc('thumbnail-put',{id:'0',version:'2026-11-17',image})
  assert(await rpc('thumbnail',{id:'0',version:'2026-11-17'})===image,'preview persisted')
  await rpc('thumbnail-put',{id:'1',version:'2026-11-17',image:'https://example.com/private.jpg'})
  assert(await rpc('thumbnail',{id:'1',version:'2026-11-17'})===null,'remote image rejected')
  await rpc('begin',{generation:'interrupted'});await rpc('put',{rows:[{...row(0),name:'Incomplete replacement'}]})
  let failed=false;try{await rpc('put',{rows:[{...row(2),id:'QUOTA'}]})}catch{failed=true}
  assert(failed,'quota fault injected')
  assert((await rpc('item',{id:'0'})).name==='Camiseta 0','quota preserves active generation')
  worker.terminate();openWorker();const reopened=await rpc('init',{scope:'qa-a'})
  assert(reopened.count===50000,'reopen last complete generation')
  assert(await rpc('thumbnail',{id:'0',version:'2026-11-17'})===image,'reopen thumbnail')
  worker.terminate();openWorker();const other=await rpc('init',{scope:'qa-b'})
  assert(other.count===0&&(await rpc('search',{query:'',filters:{}})).total===0,'different user isolated')
  worker.terminate()
  // Fixture-only metadata at the cap checks the worker refuses further preview
  // prefetch without creating an unnecessary 128 MiB test image on disk.
  const db=await dbRequest(indexedDB.open('eleven-offline-catalog-v1',1));const tx=db.transaction('thumbnailInfo','readwrite')
  tx.objectStore('thumbnailInfo').put({key:'qa-a:budget',scope:'qa-a',id:'budget',version:'fixture',bytes:128*1024*1024,checkedAt:Date.now()})
  await committed(tx);db.close();openWorker();await rpc('init',{scope:'qa-a'})
  assert((await rpc('thumbnail-candidates')).length===0,'preview budget respected')
  worker.terminate();await dbRequest(indexedDB.deleteDatabase('eleven-offline-catalog-v1'))
  window.__offlineResult={ok:true,count:50000,bytes:meta.bytes,durationMs:Math.round(performance.now()-start),checks:['pagination','QR','unknown-stock','legacy-date','thumbnail-validation','quota-rollback','reopen','user-isolation','thumbnail-budget','logout-delete']}
}catch(error){worker?.terminate();window.__offlineResult={ok:false,error:String(error.stack||error)}}
</script>`
const server = await createServer({ root, configFile: false, logLevel: 'error', optimizeDeps: { noDiscovery: true, entries: [] }, server: { host: '127.0.0.1', port: 0 }, plugins: [{
  name: 'isolated-offline-fixture', configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url === '/__offline-qa') { res.setHeader('Content-Type', 'text/html'); res.end(fixture) }
      else if (req.url === '/__offline-qa-worker.js') {
        res.setHeader('Content-Type', 'text/javascript')
        res.end(`import '/src/services/offlineCatalog.worker.ts';const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(value,...args){if(this.name==='entries'&&value?.row?.id==='QUOTA')throw new DOMException('Fixture quota','QuotaExceededError');return put.call(this,value,...args)};`)
      } else next()
    })
  },
}] })
let chrome, socket
try {
  await server.listen()
  const address = server.httpServer.address(), origin = `http://127.0.0.1:${address.port}`
  chrome = spawn(chromePath, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-default-apps', `--user-data-dir=${profile}`, '--remote-debugging-port=0', 'about:blank'], { stdio: 'ignore' })
  let port
  for (let attempt = 0; attempt < 100; attempt++) {
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break } catch { await new Promise(resolve => setTimeout(resolve, 100)) }
  }
  if (!port) throw new Error('Isolated Chromium did not start')
  const page = await (await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(origin + '/__offline-qa')}`, { method: 'PUT' })).json()
  socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let sequence = 0; const pending = new Map()
  socket.onmessage = event => { const data = JSON.parse(event.data); const waiter = pending.get(data.id); if (waiter) { pending.delete(data.id); data.error ? waiter.reject(new Error(JSON.stringify(data.error))) : waiter.resolve(data.result) } }
  const send = (method, params) => new Promise((resolve, reject) => { const id=++sequence, timeout=setTimeout(()=>{pending.delete(id);reject(new Error('Chrome command timeout'))},100000);pending.set(id,{resolve:value=>{clearTimeout(timeout);resolve(value)},reject:error=>{clearTimeout(timeout);reject(error)}});socket.send(JSON.stringify({id,method,params})) })
  let result
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      result = await send('Runtime.evaluate', { expression: `new Promise((resolve,reject)=>{const deadline=Date.now()+90000;const tick=()=>{if(window.__offlineResult)resolve(window.__offlineResult);else if(Date.now()>deadline)reject(new Error('Fixture timed out'));else setTimeout(tick,100)};tick()})`, awaitPromise: true, returnByValue: true })
      break
    } catch (error) {
      if (!String(error).includes('Execution context was destroyed') || attempt === 4) throw error
      await new Promise(resolve => setTimeout(resolve, 200))
    }
  }
  const report = result.result?.value
  if (!report?.ok) throw new Error(JSON.stringify(report || result))
  console.log(JSON.stringify(report, null, 2))
} finally {
  socket?.close(); chrome?.kill('SIGTERM'); await server.close()
  if (chrome && chrome.exitCode === null) await new Promise(resolve => { chrome.once('exit', resolve); setTimeout(resolve, 3000) })
  await rm(profile, { recursive: true, force: true, maxRetries: 3 }).catch(() => {})
}
