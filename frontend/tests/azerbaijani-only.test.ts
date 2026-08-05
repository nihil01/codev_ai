import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import test from 'node:test';

function sourceFiles(directory: URL): URL[] {
  return readdirSync(directory).flatMap((name) => {
    const entry = new URL(`${name}${statSync(new URL(name, directory)).isDirectory() ? '/' : ''}`, directory);
    return statSync(entry).isDirectory()
      ? sourceFiles(entry)
      : /\.(ts|tsx)$/.test(name) ? [entry] : [];
  });
}

test('frontend source contains no Russian Cyrillic copy and exposes only Azerbaijani locale', () => {
  const root = new URL('../src/', import.meta.url);
  const offenders = sourceFiles(root)
    .filter((file) => /[А-Яа-яЁё]/.test(readFileSync(file, 'utf8')))
    .map((file) => file.pathname);

  assert.deepEqual(offenders, []);
  assert.match(readFileSync(new URL('services/locale.ts', root), 'utf8'), /SUPPORTED_LOCALES = \['az'\]/);
});
