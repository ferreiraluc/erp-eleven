import test from 'node:test';
import assert from 'node:assert/strict';
import { suppressDependencyConsole } from '../src/privacy.mjs';

test('raw dependency diagnostics cannot print Signal sessions or messages', () => {
  const leaked = [];
  const fake = Object.fromEntries(['log', 'info', 'warn', 'error', 'debug', 'trace', 'dir', 'table', 'assert'].map(name => [name, (...args) => leaked.push(args)]));
  suppressDependencyConsole(fake);
  fake.warn('Session already closed', { privateKey: 'secret' });
  fake.error({ message: 'customer data' });
  fake.log('QR', 'pairing secret');
  assert.deepEqual(leaked, []);
});
