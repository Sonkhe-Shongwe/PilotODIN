// C5 source-only npm lock/readiness guard. No package manager, network, or writes.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MAX_JSON = 2 * 1024 * 1024;
const NAME = /^(?:@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*$/;
const VERSION = /^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;
const WINDOWS_NATIVE = [
  ["esbuild", "@esbuild/win32-x64"],
  ["rollup", "@rollup/rollup-win32-x64-msvc"],
  ["@tauri-apps/cli", "@tauri-apps/cli-win32-x64-msvc"],
];
const fail = reason => { throw new Error(reason); };
const object = v => v !== null && typeof v === "object" && !Array.isArray(v);

function directory(p) {
  const s = fs.lstatSync(p);
  if (!s.isDirectory() || s.isSymbolicLink()) fail("UNSAFE_DIRECTORY");
}

function file(p, limit = MAX_JSON) {
  const before = fs.lstatSync(p);
  if (!before.isFile() || before.isSymbolicLink() || before.size < 1 || before.size > limit)
    fail("UNSAFE_OR_OVERSIZE_FILE");
  const fd = fs.openSync(p, "r");
  try {
    const opened = fs.fstatSync(fd);
    if (opened.dev !== before.dev || opened.ino !== before.ino || opened.size !== before.size ||
        opened.mtimeMs !== before.mtimeMs) fail("FILE_CHANGED");
    const bytes = Buffer.alloc(before.size);
    let offset = 0;
    while (offset < bytes.length) {
      const n = fs.readSync(fd, bytes, offset, bytes.length - offset, null);
      if (!n) fail("SHORT_READ");
      offset += n;
    }
    const after = fs.lstatSync(p);
    const end = fs.fstatSync(fd);
    if (after.isSymbolicLink() || after.dev !== opened.dev || after.ino !== opened.ino ||
        end.size !== opened.size || end.mtimeMs !== opened.mtimeMs ||
        after.size !== opened.size || after.mtimeMs !== opened.mtimeMs) fail("FILE_CHANGED");
    return bytes;
  } finally { fs.closeSync(fd); }
}

// JSON.parse validates the grammar; the bounded token walk rejects duplicate keys,
// including escaped spellings. No external parser/dependency is needed.
function strictJSON(bytes) {
  const source = new TextDecoder("utf-8", {fatal:true}).decode(bytes);
  const value = JSON.parse(source);
  const tokens = source.match(/"(?:\\[\s\S]|[^"\\])*"|[{}\[\]:,]|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) || [];
  let i = 0;
  function visit(depth) {
    if (depth > 64) fail("JSON_DEPTH");
    const token = tokens[i++];
    if (token === "{") {
      const seen = new Set();
      if (tokens[i] !== "}") {
        for (;;) {
          const key = JSON.parse(tokens[i++]);
          if (seen.has(key)) fail("DUPLICATE_JSON_KEY");
          seen.add(key);
          if (tokens[i++] !== ":") fail("JSON_STRUCTURE");
          visit(depth + 1);
          if (tokens[i] !== ",") break;
          i++;
        }
      }
      if (tokens[i++] !== "}") fail("JSON_STRUCTURE");
    } else if (token === "[") {
      if (tokens[i] !== "]") {
        for (;;) {
          visit(depth + 1);
          if (tokens[i] !== ",") break;
          i++;
        }
      }
      if (tokens[i++] !== "]") fail("JSON_STRUCTURE");
    } else if (token === undefined) fail("JSON_STRUCTURE");
  }
  visit(0);
  if (i !== tokens.length || !object(value)) fail("JSON_STRUCTURE");
  return value;
}

function dependencies(v) {
  if (v === undefined) return {};
  if (!object(v)) fail("INVALID_DEPENDENCY_MAP");
  for (const [name, range] of Object.entries(v)) {
    if (!NAME.test(name) || typeof range !== "string" || !range ||
        !/^[0-9a-zA-Z.*^~<>=| +,-]+$/.test(range)) fail("INVALID_DEPENDENCY_DECLARATION");
  }
  return v;
}
function sameMap(a,b) {
  a = dependencies(a); b = dependencies(b);
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(k => Object.hasOwn(b,k) && a[k] === b[k]);
}

function integrity(s) {
  if (typeof s !== "string" || !/^sha512-[A-Za-z0-9+/]{86}==$/.test(s)) return false;
  const encoded = s.slice(7);
  const decoded = Buffer.from(encoded,"base64");
  return decoded.length === 64 && decoded.toString("base64") === encoded;
}

export function verifyLock(frontend = FRONTEND) {
  directory(frontend);
  const manifest = strictJSON(file(path.join(frontend,"package.json")));
  const lock = strictJSON(file(path.join(frontend,"package-lock.json")));
  const packages = lock.packages;
  if (lock.lockfileVersion !== 3 || !object(packages) || !object(packages[""]) ||
      Object.keys(packages).length < 2 || Object.keys(packages).length > 4096)
    fail("UNSUPPORTED_LOCK_FORMAT");
  const root = packages[""];
  if (manifest.name !== root.name || manifest.version !== root.version ||
      lock.name !== root.name || lock.version !== root.version) fail("ROOT_IDENTITY_MISMATCH");
  for (const key of ["workspaces","overrides","optionalDependencies","peerDependencies"]) {
    if (Object.hasOwn(manifest,key) || Object.hasOwn(root,key)) fail("UNREVIEWED_ROOT_CONFIGURATION");
  }
  for (const key of ["dependencies","devDependencies"]) {
    if (!sameMap(manifest[key],root[key])) fail("ROOT_DEPENDENCY_MISMATCH");
  }
  for (const [key, entry] of Object.entries(packages)) {
    if (!object(entry)) fail("INVALID_LOCK_ENTRY");
    if (key) {
      const name = key.slice("node_modules/".length);
      if (!key.startsWith("node_modules/") || !NAME.test(name) ||
          typeof entry.version !== "string" || !VERSION.test(entry.version) ||
          entry.link !== undefined || entry.inBundle !== undefined ||
          !integrity(entry.integrity)) fail("INVALID_PACKAGE_IDENTITY");
      const expected = "https://registry.npmjs.org/" + name + "/-/" +
        name.split("/").at(-1) + "-" + entry.version + ".tgz";
      if (entry.resolved !== expected) fail("UNREVIEWED_PACKAGE_SOURCE");
      for (const field of ["os","cpu","libc"]) {
        if (entry[field] !== undefined && (!Array.isArray(entry[field]) || !entry[field].length ||
            entry[field].some(v => typeof v !== "string" || !/^[a-z0-9_-]+$/.test(v))))
          fail("INVALID_PLATFORM_SELECTOR");
      }
    }
    for (const field of ["dependencies","devDependencies","optionalDependencies"]) {
      for (const name of Object.keys(dependencies(entry[field]))) {
        if (!Object.hasOwn(packages,"node_modules/"+name)) fail("MISSING_LOCK_DEPENDENCY");
      }
    }
  }
  for (const [parent, child] of WINDOWS_NATIVE) {
    const p = packages["node_modules/"+parent];
    const c = packages["node_modules/"+child];
    if (!p || !c || c.optional !== true || c.version !== p.version ||
        p.optionalDependencies?.[child] !== c.version ||
        !Array.isArray(c.os) || c.os.length !== 1 || c.os[0] !== "win32" ||
        !Array.isArray(c.cpu) || c.cpu.length !== 1 || c.cpu[0] !== "x64")
      fail("WINDOWS_NATIVE_LOCK_MISMATCH");
  }
  return packages;
}

// This checks installed package metadata and required launch files, not every
// installed byte or a release provenance chain. It is Windows x64 dev-only.
export function verifyInstalled(frontend = FRONTEND, platform = process.platform, arch = process.arch) {
  if (platform !== "win32" || arch !== "x64") fail("UNSUPPORTED_DEV_PLATFORM");
  const packages = verifyLock(frontend);
  const modules = path.join(frontend,"node_modules");
  directory(modules);
  const requiredNative = new Set(WINDOWS_NATIVE.map(([,c]) => "node_modules/"+c));
  for (const [key, entry] of Object.entries(packages)) {
    if (!key) continue;
    const required = entry.optional !== true || requiredNative.has(key);
    const dir = path.join(frontend,...key.split("/"));
    if (!required && !fs.existsSync(dir)) continue;
    if ((entry.os && !entry.os.includes(platform)) ||
        (entry.cpu && !entry.cpu.includes(arch)) || entry.libc) fail("WRONG_INSTALLED_PLATFORM");
    let parent = frontend;
    for (const part of key.split("/")) {
      parent = path.join(parent,part);
      directory(parent);
    }
    const doc = strictJSON(file(path.join(dir,"package.json")));
    if (doc.name !== key.slice("node_modules/".length) || doc.version !== entry.version)
      fail("INSTALLED_PACKAGE_VERSION_MISMATCH");
  }
  directory(path.join(modules,".bin"));
  file(path.join(modules,".bin","vite.cmd"));
  return packages;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2);
    if (args.length === 0) verifyLock();
    else if (args.length === 1 && args[0] === "--installed") verifyInstalled();
    else fail("UNSUPPORTED_ARGUMENT");
    console.log(args.length ? "NPM_EXISTING_DEV_METADATA_READY (not production provenance)" : "NPM_LOCK_STRUCTURE_READY");
  } catch (error) {
    // Never print arbitrary local paths or untrusted manifest data.
    const reason = /^[A-Z_]+$/.test(error.message) ? error.message : "MISSING_OR_INVALID_INPUT";
    console.error("C5_NPM_PREFLIGHT_BLOCKED: " + reason);
    process.exitCode = 2;
  }
}
