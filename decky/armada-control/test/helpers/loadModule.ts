import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const compiled = new Map<string, string>();

export function loadModule(file: string, dependencies: Record<string, any> | ((id: string) => any), globals: Record<string, any> = {}): any {
  let code = compiled.get(file);
  if (!code) {
    const source = readFileSync(new URL(`../../src/${file}`, import.meta.url), "utf8");
    code = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    compiled.set(file, code);
  }
  const element = (type: any, props: any, key?: string) => ({ type, props, key });
  const modules = { "react/jsx-runtime": { jsx: element, jsxs: element, Fragment: "Fragment" }, ...(typeof dependencies === "function" ? {} : dependencies) };
  const exports = {};
  runInNewContext(code, { ...globals, exports, require: (id: string) => {
    if (Object.prototype.hasOwnProperty.call(modules, id)) return modules[id];
    if (typeof dependencies === "function") {
      const resolved = dependencies(id);
      if (resolved !== undefined) return resolved;
    }
    throw Error(`Unexpected import in ${file}: ${id}`);
  } });
  return exports;
}
