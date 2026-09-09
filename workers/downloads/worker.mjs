const DOWNLOAD_ORIGIN = "https://downloads.armadaos.dev";
const MANIFEST_KEY = "preview/builds.json";
const INDEX_PATHS = new Set(["/", "/preview", "/preview/"]);
const IMAGE_ALIAS = "/preview/latest";
const IMAGE_KEY = /^preview\/armada-\d{8}(?:\.[a-f0-9]{7,40})?\.img\.gz$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const index = INDEX_PATHS.has(url.pathname);
    const alias = url.pathname === IMAGE_ALIAS;
    if (!index && !alias) {
      // A Worker route forwards these requests to the existing R2 custom domain.
      return fetch(new Request(new URL(url.pathname + url.search, DOWNLOAD_ORIGIN), request));
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD", "Cache-Control": "no-store" },
      });
    }

    try {
      const object = await env.DOWNLOADS.get(MANIFEST_KEY);
      if (!object) throw new Error("Preview manifest is missing");
      const manifest = await object.json();
      if (manifest.channel !== "preview" ||
          !Array.isArray(manifest.builds) || !manifest.builds.length ||
          !manifest.builds.every(build =>
            /^[a-f0-9]{40}$/.test(build.build_commit) &&
            typeof build.build_commit_title === "string" &&
            IMAGE_KEY.test(build.image?.key) &&
            build.image.filename === build.image.key.slice("preview/".length) &&
            build.checksum?.key === `${build.image.key}.sha256` &&
            /^[a-f0-9]{64}$/.test(build.image.sha256) &&
            Number.isSafeInteger(build.image.size) && build.image.size > 0)) {
        throw new Error("Invalid Preview manifest");
      }
      const latest = manifest.builds.find(build => build.version === manifest.latest);
      if (!latest) throw new Error("Latest Preview build is missing from manifest");
      if (alias) {
        return new Response(null, {
          status: 302,
          headers: {
            Location: `${DOWNLOAD_ORIGIN}/${latest.image.key}`,
            "Cache-Control": "no-store",
          },
        });
      }
      const previous = manifest.builds.filter(build => build !== latest);
      return new Response(request.method === "HEAD" ? null : renderPage(latest, previous), {
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-store",
          "X-Content-Type-Options": "nosniff",
          "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
      });
    } catch (error) {
      console.error("Cannot read Preview download metadata", error);
      return new Response(request.method === "HEAD" ? null : "Preview downloads are temporarily unavailable. Please try again shortly.", {
        status: 503,
        headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
      });
    }
  },
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" :
    new Intl.DateTimeFormat("en", { dateStyle: "long", timeStyle: "short", timeZone: "UTC" }).format(date) + " UTC";
}

function commitLink(commit, title) {
  return `<a href="https://github.com/armada-os/armada/commit/${commit}">${escapeHtml(title)} · ${commit.slice(0, 7)} ↗</a>`;
}

function renderPage(latest, previous) {
  const rows = [latest, ...previous].map(build => {
    const current = build === latest;
    return `<tr${current ? ' class="latest"' : ""}>
      <th scope="row"><span class="version">${escapeHtml(build.version)}</span>${current ? ' <strong class="label">Latest</strong>' : ""}
        <div class="commit">${commitLink(build.build_commit, build.build_commit_title)}</div></th>
      <td class="date">${escapeHtml(formatDate(build.published_at))}</td>
      <td class="size">${(build.image.size / 1e9).toFixed(2)} GB</td>
      <td class="files"><a href="${DOWNLOAD_ORIGIN}/${build.image.key}">Image (.img.gz)</a><br><a href="${DOWNLOAD_ORIGIN}/${build.checksum.key}">SHA-256 checksum</a></td>
    </tr>`;
  }).join("\n");
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Armada Preview disk image downloads for supported ARM64 handhelds.">
  <title>Preview downloads · Armada</title>
  <link rel="icon" href="data:,">
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; background: #181818; color: #ddd; }
    * { box-sizing: border-box; }
    body { max-width: 1120px; margin: 0 auto; padding: 24px; font-size: 14px; line-height: 1.5; }
    a { color: #a9c9ee; text-underline-offset: 2px; }
    a:focus-visible, .table-wrap:focus-visible { outline: 2px solid #a9c9ee; outline-offset: 3px; }
    .intro, .date, .size { color: #aaa; }
    h1 { font-size: 24px; margin: 20px 0 8px; }
    p { margin: 8px 0 16px; }
    .table-wrap { overflow-x: auto; margin: 20px 0; }
    table { width: 100%; min-width: 680px; border-collapse: collapse; text-align: left; }
    th, td { padding: 12px 10px; border-bottom: 1px solid #383838; vertical-align: top; }
    thead th { padding-top: 8px; padding-bottom: 8px; font-size: 12px; color: #aaa; font-weight: 500; }
    tbody th { width: 48%; font-weight: 400; }
    .latest { background: #242424; }
    .version { font-family: ui-monospace, monospace; }
    .label { margin-left: 8px; font-size: 12px; }
    .commit { margin-top: 5px; font-size: 13px; overflow-wrap: anywhere; }
    .date { font-size: 13px; }
    .size, .files { white-space: nowrap; font-size: 13px; }
    @media (max-width: 600px) { body { padding: 16px; } }
  </style>
</head>
<body>
  <main>
    <h1>Preview disk images</h1>
    <p><a href="${IMAGE_ALIAS}">Download latest image</a> · <a href="https://armadaos.dev/devices/supported-devices/">Supported devices</a> · <a href="https://armadaos.dev/getting-started/flashing-to-an-sd-card/">Installation guide</a></p>
    <div class="table-wrap" role="region" aria-label="Available Preview builds" tabindex="0">
      <table aria-label="Preview disk image downloads">
        <thead><tr><th scope="col">Build / commit</th><th scope="col">Published</th><th scope="col">Size</th><th scope="col">Files</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    ${previous.length ? "" : '<p class="intro">No previous Preview builds are available yet.</p>'}
  </main>
</body>
</html>`;
}
