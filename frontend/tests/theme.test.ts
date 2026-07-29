import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const sourceRoot = path.join(frontendRoot, 'src');
const styles = fs.readFileSync(path.join(sourceRoot, 'styles.css'), 'utf8');
const shell = fs.readFileSync(path.join(sourceRoot, 'components/layout/DashboardShell.tsx'), 'utf8');
const authLayout = fs.readFileSync(path.join(sourceRoot, 'components/layout/AuthLayout.tsx'), 'utf8');
const styleConstants = fs.readFileSync(path.join(sourceRoot, 'constants/styles.ts'), 'utf8');

function sourceFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(fullPath);
    return /\.(css|ts|tsx)$/.test(entry.name) ? [fullPath] : [];
  });
}

test('FeedHive green design tokens are the frontend source of truth', () => {
  const requiredTokens = {
    '--color-green-canvas': '#f3faf5',
    '--color-card-white': '#ffffff',
    '--color-ink': '#18261d',
    '--color-muted-green': '#708078',
    '--color-border-mist': '#e1ebe4',
    '--color-soft-green-wash': '#e4f5e9',
    '--color-brand-green': '#15803d',
    '--color-brand-green-light': '#4fbf73',
  };

  for (const [token, value] of Object.entries(requiredTokens)) {
    assert.match(styles, new RegExp(`${token}:\\s*${value}`, 'i'), `${token} must be ${value}`);
  }
  assert.match(styles, /--brand-action-gradient:\s*linear-gradient\(to right,\s*#15803d,\s*#4fbf73\)/i);
});

test('workspace uses one geometric sans and FeedHive pill/card geometry', () => {
  assert.match(styles, /--font-thicccboi:\s*['"]DM Sans['"]/);
  assert.match(styles, /h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6[\s\S]*font-family:\s*var\(--font-thicccboi\)/);
  assert.match(styles, /--radius-cards:\s*24px/);
  assert.match(styles, /--radius-buttons:\s*9999px/);
  assert.match(styleConstants, /rounded-\[24px\]/);
  assert.match(styleConstants, /rounded-full/);
});

test('workspace uses a top bar rather than the old sidebar', () => {
  assert.match(shell, /<header/);
  assert.match(shell, /Workspace navigation/);
  assert.doesNotMatch(shell, /<motion\.aside|sidebar/i);
});

test('official Codev logo is used in auth, header, and footer', () => {
  const logoPath = path.join(sourceRoot, 'assets/codev-logo.png');
  assert.equal(fs.existsSync(logoPath), true);
  assert.match(authLayout, /import codevLogo/);
  assert.match(authLayout, /src=\{codevLogo\}/);
  assert.match(shell, /import codevLogo/);
  assert.match(shell, /<header[\s\S]*src=\{codevLogo\}/);
  assert.match(shell, /<footer[\s\S]*src=\{codevLogo\}/);
});

test('frontend contains no blue-violet theme or ordinary card shadows', () => {
  const contents = sourceFiles(sourceRoot).map((file) => fs.readFileSync(file, 'utf8')).join('\n');
  const forbiddenColors = [
    '#4457ff', '#7583fd', '#dbeafe', '#f3f5ff', '#c7c8e2',
    '#145aff', '#3b82f6', '#020520', '#696a72', '#e2e4e9', '#f0f4fe', '#fcfcfc',
    '#b6ced5', '#0a66c2',
  ];

  for (const color of forbiddenColors) {
    assert.doesNotMatch(contents, new RegExp(color, 'i'), `${color} does not belong to the green visual system`);
  }
  assert.doesNotMatch(contents, /(?:text|bg|border|ring|from|to)-(?:blue|cyan|sky|indigo|violet|purple|fuchsia)-/i);
  assert.doesNotMatch(contents, /rgba?\(\s*20\s*,\s*90\s*,\s*255/i);
  assert.doesNotMatch(contents, /\bbox-shadow\s*:/i);
  assert.doesNotMatch(contents, /(?:^|\s)(?:hover:)?shadow(?:-\[[^\]]+\]|-(?:sm|md|lg|xl|2xl))?(?=\s|["'`])/m);
});
