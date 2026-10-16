// Tiny fetch mock shared by the edge-function tests (node:test, no deps).
export function mockFetch(routes) {
  const calls = [];
  const fn = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init.method || "GET").toUpperCase();
    calls.push({ url, method, init });
    for (const route of routes) {
      if (route.match(url, method, init)) {
        const res = await route.respond(url, method, init);
        return res;
      }
    }
    throw new Error(`unexpected fetch ${method} ${url}`);
  };
  fn.calls = calls;
  return fn;
}

export function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
