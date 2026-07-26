import {
  cp,
  mkdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourceDirectory = path.resolve(
  process.env.ARMADA_CONTROLLER_THEME_SOURCE ??
    path.join(scriptDirectory, "../../themes/handheld-controller-glyphs"),
);
const outputDirectory = path.resolve(
  process.env.ARMADA_CONTROLLER_THEME_OUTPUT ??
    path.join(scriptDirectory, "../dist/controller-theme"),
);

const stylesheets = [
  "themes/armada/ayn-retroid-buttons.css",
  "themes/ayn/odin-3.css",
  "themes/ayn/odin-3-colored-face-buttons.css",
];
const assetDirectory = "assets/ayn/odin-3";
const themeUrlPrefix = "/themes_custom/handheld-controller-glyphs/";

function resolveInside(root, relativePath) {
  const resolved = path.resolve(root, relativePath);
  const relative = path.relative(root, resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Theme path escapes its source directory: ${relativePath}`);
  }
  return resolved;
}

function rewriteThemeUrls(css, stylesheet) {
  const stylesheetDirectory = path.posix.dirname(stylesheet);
  const expression =
    /url\(\s*(['"]?)\/themes_custom\/handheld-controller-glyphs\/([^'")]+)\1\s*\)/g;
  return css.replace(expression, (_match, _quote, encodedAsset) => {
    const asset = decodeURIComponent(encodedAsset);
    if (
      asset !== assetDirectory &&
      !asset.startsWith(`${assetDirectory}/`)
    ) {
      throw new Error(
        `Unexpected non-Odin 3 asset in ${stylesheet}: ${asset}`,
      );
    }
    return `url("${path.posix.relative(stylesheetDirectory, asset)}")`;
  });
}

await rm(outputDirectory, { recursive: true, force: true });
await mkdir(outputDirectory, { recursive: true });

await cp(
  resolveInside(sourceDirectory, "LICENSE"),
  resolveInside(outputDirectory, "LICENSE"),
);
await mkdir(
  path.dirname(resolveInside(outputDirectory, assetDirectory)),
  { recursive: true },
);
await cp(
  resolveInside(sourceDirectory, assetDirectory),
  resolveInside(outputDirectory, assetDirectory),
  { recursive: true },
);

for (const stylesheet of stylesheets) {
  const source = resolveInside(sourceDirectory, stylesheet);
  const destination = resolveInside(outputDirectory, stylesheet);
  const css = await readFile(source, "utf8");
  const rewritten = rewriteThemeUrls(css, stylesheet);
  if (rewritten.includes(themeUrlPrefix)) {
    throw new Error(`Unrewritten theme URL remains in ${stylesheet}`);
  }
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, rewritten, "utf8");
}

console.log(
  `Built Armada Control AYN Odin 3 controller theme: ${stylesheets.length} stylesheets`,
);
