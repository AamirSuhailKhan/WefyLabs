import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

let totalSuites = 0;
let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
let currentSuite = '';

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (typeof a !== 'object' || a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  for (const key of keysA) {
    if (!keysB.includes(key) || !deepEqual(a[key], b[key])) return false;
  }
  return true;
}

globalThis.describe = function(name, fn) {
  totalSuites++;
  currentSuite = name;
  try {
    fn();
  } catch (err) {
    console.error(`Suite error in "${name}":`, err);
  }
};

globalThis.it = async function(name, fn) {
  totalTests++;
  try {
    const res = fn();
    if (res instanceof Promise) {
      await res;
    }
    passedTests++;
  } catch (err) {
    failedTests++;
    console.error(`  FAIL: [${currentSuite}] > ${name}`);
    console.error(`    ${err.message}`);
  }
};

globalThis.expect = function(actual) {
  return {
    toBe(expected) {
      if (actual !== expected) {
        throw new Error(`Expected ${JSON.stringify(actual)} to be ${JSON.stringify(expected)}`);
      }
    },
    toEqual(expected) {
      if (!deepEqual(actual, expected)) {
        throw new Error(`Expected ${JSON.stringify(actual)} to deeply equal ${JSON.stringify(expected)}`);
      }
    },
    toBeDefined() {
      if (actual === undefined) {
        throw new Error(`Expected value to be defined, got undefined`);
      }
    },
    toBeUndefined() {
      if (actual !== undefined) {
        throw new Error(`Expected value to be undefined, got ${JSON.stringify(actual)}`);
      }
    },
    toBeNull() {
      if (actual !== null) {
        throw new Error(`Expected null, got ${JSON.stringify(actual)}`);
      }
    },
    toContain(expected) {
      if (Array.isArray(actual) || typeof actual === 'string') {
        if (!actual.includes(expected)) {
          throw new Error(`Expected ${JSON.stringify(actual)} to contain ${JSON.stringify(expected)}`);
        }
      } else {
        throw new Error(`Cannot call toContain on non-iterable`);
      }
    },
    toMatch(expected) {
      const reg = expected instanceof RegExp ? expected : new RegExp(expected);
      if (!reg.test(String(actual))) {
        throw new Error(`Expected "${actual}" to match ${expected}`);
      }
    },
    toBeGreaterThan(expected) {
      if (!(actual > expected)) {
        throw new Error(`Expected ${actual} > ${expected}`);
      }
    },
    toBeGreaterThanOrEqual(expected) {
      if (!(actual >= expected)) {
        throw new Error(`Expected ${actual} >= ${expected}`);
      }
    },
    toBeLessThan(expected) {
      if (!(actual < expected)) {
        throw new Error(`Expected ${actual} < ${expected}`);
      }
    },
    toBeLessThanOrEqual(expected) {
      if (!(actual <= expected)) {
        throw new Error(`Expected ${actual} <= ${expected}`);
      }
    },
    not: {
      toBe(expected) {
        if (actual === expected) {
          throw new Error(`Expected ${JSON.stringify(actual)} NOT to be ${JSON.stringify(expected)}`);
        }
      },
      toEqual(expected) {
        if (deepEqual(actual, expected)) {
          throw new Error(`Expected ${JSON.stringify(actual)} NOT to deeply equal ${JSON.stringify(expected)}`);
        }
      },
      toContain(expected) {
        if (Array.isArray(actual) || typeof actual === 'string') {
          if (actual.includes(expected)) {
            throw new Error(`Expected ${JSON.stringify(actual)} NOT to contain ${JSON.stringify(expected)}`);
          }
        }
      },
      toBeNull() {
        if (actual === null) {
          throw new Error(`Expected value NOT to be null`);
        }
      },
      toBeUndefined() {
        if (actual === undefined) {
          throw new Error(`Expected value NOT to be undefined`);
        }
      }
    }
  };
};

// Discover all .spec.ts files across tests/
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const testsDir = path.join(__dirname, 'tests');

function findSpecFiles(dir) {
  let files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files = files.concat(findSpecFiles(fullPath));
    } else if (entry.name.endsWith('.spec.ts')) {
      files.push(fullPath);
    }
  }
  return files;
}

const specFiles = findSpecFiles(testsDir);
console.log(`Discovered ${specFiles.length} spec files in ${testsDir}`);

for (const file of specFiles) {
  const rel = path.relative(__dirname, file);
  try {
    await import(`file://${file.replace(/\\/g, '/')}`);
  } catch (err) {
    console.error(`Error loading ${rel}:`, err);
  }
}

console.log(`\n============================================================`);
console.log(`FRONTEND SPEC EXECUTION COMPLETE`);
console.log(`Suites: ${totalSuites}`);
console.log(`Total Specs: ${totalTests}`);
console.log(`Passed: ${passedTests}`);
console.log(`Failed: ${failedTests}`);
console.log(`============================================================`);

if (failedTests > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
