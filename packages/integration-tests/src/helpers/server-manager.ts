import { fork, type ChildProcess } from 'child_process';
import { resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..');

export interface ManagedServer {
  process: ChildProcess;
  port: number;
  baseUrl: string;
  kill: () => void;
}

export async function startServer(
  packageName: string,
  port: number,
  extraEnv?: Record<string, string>,
): Promise<ManagedServer> {
  const scriptPath = resolve(ROOT, 'packages', packageName, 'dist', 'index.js');

  const child = fork(scriptPath, [], {
    env: { ...process.env, PORT: String(port), ...extraEnv },
    stdio: 'pipe',
  });

  const baseUrl = `http://localhost:${port}`;

  // Wait for server to respond to health check
  await new Promise<void>((resolvePromise, reject) => {
    const timeout = setTimeout(() => {
      clearInterval(poll);
      child.kill();
      reject(new Error(`Server ${packageName} failed to start on port ${port} within 10s`));
    }, 10000);

    const poll = setInterval(async () => {
      try {
        const res = await fetch(`${baseUrl}/health`);
        if (res.ok) {
          clearInterval(poll);
          clearTimeout(timeout);
          resolvePromise();
        }
      } catch {
        // not ready yet
      }
    }, 200);
  });

  return {
    process: child,
    port,
    baseUrl,
    kill: () => {
      child.kill('SIGTERM');
    },
  };
}

export async function startMasters(port = 3001): Promise<ManagedServer> {
  return startServer('mock-masters', port);
}

export async function startPatient(port = 3002): Promise<ManagedServer> {
  return startServer('mock-patient', port);
}

export async function startMastersB(port = 3003): Promise<ManagedServer> {
  return startServer('mock-masters-b', port);
}
