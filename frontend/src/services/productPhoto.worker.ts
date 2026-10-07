import * as ort from 'onnxruntime-web/wasm'
import wasmUrl from 'onnxruntime-web/ort-wasm-simd-threaded.wasm?url'
import wasmMjsUrl from 'onnxruntime-web/ort-wasm-simd-threaded.mjs?url'

const scope = self as unknown as {
  onmessage: (event: MessageEvent<{ input: Float32Array }>) => void
  postMessage: (message: unknown, transfer?: Transferable[]) => void
}
ort.env.wasm.numThreads = 1
ort.env.wasm.wasmPaths = { wasm: wasmUrl, mjs: wasmMjsUrl }
scope.onmessage = async event => {
  try {
    const session = await ort.InferenceSession.create('/models/u2netp/model.onnx', { executionProviders: ['wasm'] })
    const input = new ort.Tensor('float32', event.data.input, [1, 3, 320, 320])
    const outputs = await session.run({ [session.inputNames[0]]: input })
    const mask = Float32Array.from(outputs[session.outputNames[0]].data as Float32Array)
    let min = Infinity, max = -Infinity
    for (const value of mask) { min = Math.min(min, value); max = Math.max(max, value) }
    if (!Number.isFinite(min) || !Number.isFinite(max) || max - min < 1e-6) throw new Error('Empty mask')
    for (let i = 0; i < mask.length; i++) mask[i] = (mask[i] - min) / (max - min)
    for (const output of Object.values(outputs)) output.dispose()
    input.dispose(); await session.release()
    scope.postMessage({ mask }, [mask.buffer])
  } catch { scope.postMessage({ error: true }) }
}
