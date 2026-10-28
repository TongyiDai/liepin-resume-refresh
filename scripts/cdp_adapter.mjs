// Chromium adapter: attach to an explicitly configured local debugging endpoint.
// It creates and closes its own tab; it neither starts a browser nor exports cookies.
async function taskSpace() {
  if (typeof WebSocket === "undefined") throw new Error("Node.js 22 or newer is required");
  const endpoint = new URL(input.cdpEndpoint);
  if (endpoint.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(endpoint.hostname)) {
    throw new Error("CDP endpoint must be loopback HTTP");
  }
  const created = await fetch(new URL("/json/new?about:blank", endpoint), { method: "PUT", signal: AbortSignal.timeout(10000) });
  if (!created.ok) throw new Error("CDP connection unavailable");
  const target = await created.json();
  const debuggerURL = new URL(target.webSocketDebuggerUrl);
  if (!['ws:', 'wss:'].includes(debuggerURL.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(debuggerURL.hostname)) {
    throw new Error("CDP WebSocket must be loopback");
  }
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("CDP connection timeout")), 10000);
    socket.addEventListener("open", () => { clearTimeout(timeout); resolve(); }, { once: true });
    socket.addEventListener("error", () => { clearTimeout(timeout); reject(new Error("CDP connection failed")); }, { once: true });
  });
  let sequence = 0;
  const pending = new Map();
  let buffered = [];
  socket.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (event.id) {
      const item = pending.get(event.id);
      if (item) { pending.delete(event.id); clearTimeout(item.timeout); event.error ? item.reject(new Error(event.error.message)) : item.resolve(event.result); }
    } else if (event.method === "Network.responseReceived") {
      buffered.push(event);
      if (buffered.length > 1000) buffered.shift();
    }
  });
  socket.addEventListener("close", () => {
    for (const item of pending.values()) { clearTimeout(item.timeout); item.reject(new Error("CDP disconnected")); }
    pending.clear();
  });
  function cdp(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timeout = setTimeout(() => { pending.delete(id); reject(new Error("CDP command timeout")); }, 15000);
      pending.set(id, { resolve, reject, timeout });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  await cdp("Page.enable");
  await cdp("Runtime.enable");
  async function evaluate(fn, argument) {
    const result = await cdp("Runtime.evaluate", {
      expression: `(${fn.toString()})(${JSON.stringify(argument) ?? "undefined"})`,
      returnByValue: true, awaitPromise: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Page evaluation failed");
    return result.result.value;
  }
  async function waitForFunction(fn, argument, options = {}) {
    const deadline = Date.now() + (options.timeout || 15000);
    while (Date.now() < deadline) {
      try { if (await evaluate(fn, argument)) return; }
      catch (error) { if (!/context|navigation|Cannot find/i.test(String(error))) throw error; }
      await new Promise(resolve => setTimeout(resolve, 150));
    }
    throw new Error("Page wait timeout");
  }
  const page = {
    cdp, evaluate, waitForFunction,
    async goto(url) { await cdp("Page.navigate", { url }); await waitForFunction(() => document.readyState !== "loading", undefined); },
    async events() { const events = buffered; buffered = []; return events; },
    async waitForSelector(selector, options = {}) {
      await waitForFunction(({ selector, state }) => {
        const found = [...document.querySelectorAll(selector)].some(el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden");
        return state === "hidden" ? !found : found;
      }, { selector, state: options.state }, options);
    },
    async click(selector) {
      const css = selector.replace(/^loc=css:/, "");
      const point = await evaluate((s) => {
        const matches = [...document.querySelectorAll(s)].filter(el => el.getClientRects().length > 0);
        if (matches.length !== 1) throw new Error("Ambiguous or missing click target");
        const el = matches[0];
        el.scrollIntoView({ block: "center" });
        const box = el.getBoundingClientRect();
        const x = box.x + box.width / 2, y = box.y + box.height / 2;
        const hit = document.elementFromPoint(x, y);
        if (hit !== el && !el.contains(hit)) throw new Error("Click target blocked");
        return { x, y };
      }, css);
      await cdp("Input.dispatchMouseEvent", { type: "mousePressed", ...point, button: "left", clickCount: 1 });
      await cdp("Input.dispatchMouseEvent", { type: "mouseReleased", ...point, button: "left", clickCount: 1 });
    },
  };
  return {
    page() { return page; },
    async finish() {
      try { await fetch(new URL(`/json/close/${encodeURIComponent(target.id)}`, endpoint), { signal: AbortSignal.timeout(5000) }); }
      finally { socket.close(); }
    },
  };
}
