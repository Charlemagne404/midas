import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const gitValue = (...args) => {
  try {
    return execFileSync('git', ['-C', repositoryRoot, ...args], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return 'unavailable';
  }
};

export const integratedIdentity = Object.freeze({
  branch: gitValue('branch', '--show-current'),
  commit: gitValue('rev-parse', 'HEAD'),
  dirty: gitValue('status', '--porcelain').length > 0,
});
