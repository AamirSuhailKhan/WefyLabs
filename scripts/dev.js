#!/usr/bin/env node

/**
 * BeetleLabs Enterprise Development Server Orchestrator
 * =======================================================
 * Cross-platform process lifecycle manager for FastAPI & Next.js.
 * 
 * Features:
 * - Pre-flight port availability verification (ports 8000 and 3000).
 * - Automatic detection and cleanup of stale/orphaned processes from previous sessions.
 * - Clean recursive process-tree termination on SIGINT (Ctrl+C), SIGTERM, and unexpected exits.
 * - Cross-platform compatibility (Windows, macOS, Linux).
 */

const { spawn, execSync } = require('child_process');
const net = require('net');
const path = require('path');
const os = require('os');

const IS_WIN = process.platform === 'win32';
const API_PORT = 8000;
const WEB_PORT = 3000;

function isPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        resolve(true);
      } else {
        resolve(false);
      }
    });
    server.once('listening', () => {
      server.close(() => resolve(false));
    });
    server.listen(port, '0.0.0.0');
  });
}

function killProcessTree(pid) {
  if (!pid) return;
  try {
    if (IS_WIN) {
      execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
    } else {
      process.kill(-pid, 'SIGTERM');
    }
  } catch (e) {
    // Process might already be dead
  }
}

function freePort(port) {
  try {
    if (IS_WIN) {
      try {
        const stdout = execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`, { encoding: 'utf-8' });
        const pids = stdout.trim().split(/\r?\n/).map(s => s.trim()).filter(s => /^\d+$/.test(s) && s !== '0' && s !== String(process.pid));
        for (const pid of new Set(pids)) {
          console.log(`[BeetleLabs Dev] Freeing port ${port} held by PID ${pid}...`);
          try {
            execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
          } catch (e) {}
        }
      } catch (err) {
        const stdout = execSync(`netstat -ano`, { encoding: 'utf-8' });
        const lines = stdout.split(/\r?\n/);
        for (const line of lines) {
          if (line.includes(`:${port}`) && line.includes('LISTENING')) {
            const parts = line.trim().split(/\s+/);
            const pid = parts[parts.length - 1];
            if (pid && /^\d+$/.test(pid) && pid !== '0' && pid !== String(process.pid)) {
              console.log(`[BeetleLabs Dev] Freeing port ${port} held by PID ${pid}...`);
              try {
                execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
              } catch (e) {}
            }
          }
        }
      }
    } else {
      execSync(`lsof -ti:${port} | xargs kill -9`, { stdio: 'ignore' });
    }
  } catch (e) {
    // Port was likely already free
  }
}

async function start() {
  console.log('\x1b[36m%s\x1b[0m', '═════════════════════════════════════════════════════════════════════');
  console.log('\x1b[36m%s\x1b[0m', '           BEETLELABS ENTERPRISE DEV SERVER ORCHESTRATOR             ');
  console.log('\x1b[36m%s\x1b[0m', '═════════════════════════════════════════════════════════════════════');

  // Pre-flight port availability check
  const apiPortBusy = await isPortInUse(API_PORT);
  const webPortBusy = await isPortInUse(WEB_PORT);

  if (apiPortBusy) {
    console.log(`\x1b[33m[BeetleLabs Dev] Port ${API_PORT} is currently busy. Cleaning up stale process...\x1b[0m`);
    freePort(API_PORT);
  }

  if (webPortBusy) {
    console.log(`\x1b[33m[BeetleLabs Dev] Port ${WEB_PORT} is currently busy. Cleaning up stale process...\x1b[0m`);
    freePort(WEB_PORT);
  }

  // Small pause to ensure OS releases socket handles
  await new Promise((r) => setTimeout(r, 600));

  const rootDir = path.resolve(__dirname, '..');
  const webDir = path.resolve(rootDir, 'apps/web');

  const processes = [];

  // 1. Spawn FastAPI Backend (Python Uvicorn)
  const pythonCmd = IS_WIN ? 'python' : 'python3';
  const apiArgs = [
    '-m',
    'uvicorn',
    'app.main:app',
    '--app-dir',
    'apps/api',
    '--host',
    '0.0.0.0',
    '--port',
    String(API_PORT),
    '--reload',
  ];

  console.log(`\x1b[34m[api]\x1b[0m Starting FastAPI backend on http://0.0.0.0:${API_PORT}...`);
  const apiProc = spawn(pythonCmd, apiArgs, {
    cwd: rootDir,
    stdio: 'inherit',
    shell: true,
  });
  processes.push(apiProc);

  // 2. Spawn Next.js Frontend
  const npxCmd = IS_WIN ? 'npx.cmd' : 'npx';
  const webArgs = ['next', 'dev', '-p', String(WEB_PORT)];

  console.log(`\x1b[35m[web]\x1b[0m Starting Next.js frontend on http://localhost:${WEB_PORT}...`);
  const webProc = spawn(npxCmd, webArgs, {
    cwd: webDir,
    stdio: 'inherit',
    shell: true,
  });
  processes.push(webProc);

  let isShuttingDown = false;

  function shutdown(signal) {
    if (isShuttingDown) return;
    isShuttingDown = true;

    console.log(`\n\x1b[33m[BeetleLabs Dev] Clean shutdown initiated (${signal || 'exit'}), terminating processes...\x1b[0m`);

    for (const proc of processes) {
      if (proc && proc.pid) {
        killProcessTree(proc.pid);
      }
    }

    freePort(API_PORT);
    freePort(WEB_PORT);

    setTimeout(() => {
      process.exit(0);
    }, 500);
  }

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGHUP', () => shutdown('SIGHUP'));

  apiProc.on('exit', (code) => {
    if (!isShuttingDown && code !== 0) {
      console.log(`\x1b[31m[api] FastAPI exited with code ${code}\x1b[0m`);
      shutdown('API exit');
    }
  });

  webProc.on('exit', (code) => {
    if (!isShuttingDown && code !== 0) {
      console.log(`\x1b[31m[web] Next.js exited with code ${code}\x1b[0m`);
      shutdown('Web exit');
    }
  });
}

start().catch((err) => {
  console.error('[BeetleLabs Dev] Fatal startup error:', err);
  process.exit(1);
});
