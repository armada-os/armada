import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "./worker.mjs";

function build(version = "20260909.249e21d") {
  const filename = `armada-${version}.img.gz`;
  const key = `preview/${filename}`;
  return {
    version,
    published_at: "2026-09-09T14:17:22Z",
    build_commit: "249e21d2eb8be0241d73513fc8b97ec89a756eda",
    build_commit_title: "fix(ci): publish Preview images",
    image: { filename, key, size: 6267990432, sha256: "a".repeat(64) },
    checksum: { key: `${key}.sha256` },
  };
}

function manifest(version = "20260909.249e21d") {
  return { channel: "preview", latest: version, builds: [build(version)] };
}

function bucket(index = manifest()) {
  return { DOWNLOADS: { async get(key) {
    assert.equal(key, "preview/builds.json");
    return index === null ? null : { json: async () => index };
  }, list() { throw new Error("The page must only read builds.json"); } } };
}

function request(path, method = "GET") {
  return new Request(`https://downloads.armadaos.dev${path}`, { method });
}

test("stable image link redirects to the current dated file", async () => {
  for (const path of ["/preview/latest", "/preview/latest?download=1"]) {
    const response = await worker.fetch(request(path), bucket());
    assert.equal(response.status, 302);
    assert.equal(response.headers.get("Location"),
      "https://downloads.armadaos.dev/preview/armada-20260909.249e21d.img.gz");
    assert.equal(response.headers.get("Cache-Control"), "no-store");
  }
});

test("the next request sees an updated manifest", async () => {
  let latest = manifest();
  const env = { DOWNLOADS: { get: async () => ({ json: async () => latest }) } };
  const first = await worker.fetch(request("/preview/latest"), env);
  latest = manifest("20260910.abcdef0");
  const second = await worker.fetch(request("/preview/latest"), env);
  assert.notEqual(first.headers.get("Location"), second.headers.get("Location"));
  assert.ok(second.headers.get("Location").endsWith("armada-20260910.abcdef0.img.gz"));
});

test("index renders the published image, checksum, date, and size without client scripts", async () => {
  for (const path of ["/", "/preview", "/preview/"]) {
    const response = await worker.fetch(request(path), bucket());
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("Cache-Control"), "no-store");
    assert.equal(response.headers.get("Content-Security-Policy"), "default-src 'none'; style-src 'unsafe-inline'");
    const html = await response.text();
    assert.match(html, /20260909\.249e21d/);
    assert.match(html, /6\.27 GB/);
    assert.match(html, /September 9, 2026/);
    assert.ok(html.includes(build().image.key));
    assert.ok(html.includes(build().checksum.key));
    assert.ok(!html.includes("<script"));
    assert.ok(html.includes('href="/preview/latest"'));
  }
});

test("display metadata is escaped", async () => {
  const latest = manifest();
  latest.builds[0].version = '<img src=x onerror="alert(1)">';
  latest.latest = latest.builds[0].version;
  latest.builds[0].build_commit_title = 'fix: <markup> & "quotes" — café 🚀';
  const response = await worker.fetch(request("/"), bucket(latest));
  const html = await response.text();
  assert.ok(!html.includes(latest.builds[0].version));
  assert.ok(html.includes("&lt;img"));
  assert.ok(html.includes('fix: &lt;markup&gt; &amp; &quot;quotes&quot; — café 🚀'));
  assert.ok(html.includes(`href="https://github.com/armada-os/armada/commit/${latest.builds[0].build_commit}"`));
});

test("the page reads latest and history entirely from builds.json", async () => {
  const index = manifest();
  const older = build("20260907.abcdef0");
  const newer = build("20260908.abcdef1");
  newer.build_commit = "abcdef1" + "b".repeat(33);
  newer.build_commit_title = 'fix: <screen> & brightness — café 🚀';
  index.builds = [newer, index.builds[0], older];
  const response = await worker.fetch(request("/"), bucket(index));
  const html = await response.text();
  assert.equal(response.status, 200);
  assert.match(html, /class="label">Latest</);
  assert.deepEqual([...html.matchAll(/<span class="version">(.*?)<\/span>/g)].map(match => match[1]),
    [index.latest, newer.version, older.version]);
  assert.ok(html.includes(`https://github.com/armada-os/armada/commit/${newer.build_commit}`));
  assert.ok(html.includes('fix: &lt;screen&gt; &amp; brightness — café 🚀'));
  for (const item of [older, newer]) {
    assert.ok(html.includes(`href="https://downloads.armadaos.dev/${item.image.key}"`));
    assert.ok(html.includes(`href="https://downloads.armadaos.dev/${item.checksum.key}"`));
  }
});

test("an empty history is explained, and redirects never need a bucket listing", async () => {
  const env = bucket();
  assert.match(await (await worker.fetch(request("/"), env)).text(), /No previous Preview builds/);
  env.DOWNLOADS.list = () => { throw new Error("Listing should not be called"); };
  assert.equal((await worker.fetch(request("/preview/latest"), env)).status, 302);
});

test("HEAD has no response body; writes to managed paths are rejected", async () => {
  for (const path of ["/", "/preview/latest"]) {
    const head = await worker.fetch(request(path, "HEAD"), bucket());
    assert.equal(await head.text(), "");
    const post = await worker.fetch(request(path, "POST"), {});
    assert.equal(post.status, 405);
    assert.equal(post.headers.get("Allow"), "GET, HEAD");
  }
});

test("missing, unreadable, or invalid manifests do not advertise a download", async t => {
  t.mock.method(console, "error", () => {});
  const invalid = manifest();
  invalid.builds[0].image.key = "//external.example/file.img.gz";
  const missingLatest = manifest();
  missingLatest.latest = "not-present";
  for (const env of [bucket(null), bucket(invalid), bucket(missingLatest),
    { DOWNLOADS: { get: async () => { throw new Error("R2 unavailable"); } } }]) {
    const response = await worker.fetch(request("/preview/latest"), env);
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("Location"), null);
    assert.equal(response.headers.get("Cache-Control"), "no-store");
  }
});

test("existing R2 paths preserve range requests and origin responses", async t => {
  for (const path of ["/release/armada.img.gz", "/testing/other.zip", "/preview/builds.json",
    "/preview/armada-20260909.249e21d.img.gz", "/armada-preview.img.gz",
    "/armada-preview.img.gz.sha256", "/preview/latest.sha256"]) {
    const origin = new Response("partial", { status: 206, headers: { "Content-Range": "bytes 0-6/100" } });
    const fetchMock = t.mock.method(globalThis, "fetch", async req => {
      assert.equal(req.url, `https://downloads.armadaos.dev${path}`);
      assert.equal(req.headers.get("Range"), "bytes=0-6");
      return origin;
    });
    const response = await worker.fetch(new Request(`https://downloads.armadaos.dev${path}`, {
      headers: { Range: "bytes=0-6" },
    }), {});
    assert.equal(response, origin);
    fetchMock.mock.restore();
  }
});
