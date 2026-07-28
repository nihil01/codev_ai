import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const sourceRoot = path.join(frontendRoot, 'src');
const styles = fs.readFileSync(path.join(sourceRoot, 'styles.css'), 'utf8');

function sourceFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(fullPath);
    return /\.(css|ts|tsx)$/.test(entry.name) ? [fullPath] : [];
  });
}

test('Ease Health botanical design tokens are the frontend source of truth', () => {
  const requiredTokens = {
    '--color-forest-ink': '#0f3e17',
    '--color-sage-mist': '#b1dbb8',
    '--color-keylime-wash': '#e1f4df',
    '--color-mint-veil': '#cfe7d3',
    '--color-slate-hush': '#b6ced5',
    '--color-cream-paper': '#fffefc',
    '--color-charcoal': '#222222',
    '--color-border-mist': '#efeeeb',
    '--color-forest-shadow': '#0c2f10',
  };

  for (const [token, value] of Object.entries(requiredTokens)) {
    assert.match(styles, new RegExp(`${token}:\\s*${value}`, 'i'), `${token} must be ${value}`);
  }
});

test('display headings use the light editorial serif', () => {
  assert.match(styles, /--font-faire-octave:\s*['"]Cormorant Garamond['"]/);
  assert.match(styles, /h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6[\s\S]*font-family:\s*var\(--font-faire-octave\)/);
  assert.match(styles, /h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6[\s\S]*font-weight:\s*300/);
});

test('frontend contains no legacy blue theme or elevated card shadows', () => {
  const contents = sourceFiles(sourceRoot).map((file) => fs.readFileSync(file, 'utf8')).join('\n');
  const legacyColors = ['#145aff', '#3b82f6', '#020520', '#696a72', '#e2e4e9', '#f0f4fe', '#fcfcfc'];

  for (const color of legacyColors) {
    assert.doesNotMatch(contents, new RegExp(color, 'i'), `${color} belongs to the old visual system`);
  }
  assert.doesNotMatch(contents, /\bbox-shadow\s*:/i);
  assert.doesNotMatch(contents, /(?:^|\s)(?:hover:)?shadow(?:-\[[^\]]+\]|-(?:sm|md|lg|xl|2xl))?(?=\s|["'`])/m);
});
