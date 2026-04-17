/**
 * Codegen script — run with `npm run codegen` from the npm/ directory.
 *
 * 1. Reads ../schemas/monster.schema.json (canonical, language-agnostic)
 * 2. Generates src/generated/monster.ts  — TypeScript interfaces
 * 3. Generates src/generated/monster-schema.ts — schema inlined as a TS const
 *    (keeps dist/ self-contained; no external JSON required at runtime)
 * 4. Copies ../output/monsters.json → src/data/monsters.json
 */

import { compile } from 'json-schema-to-typescript';
import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '..');

const schemaPath = join(rootDir, 'schemas', 'monster.schema.json');
const monstersDataPath = join(rootDir, 'output', 'monsters.json');
const generatedDir = join(__dirname, 'src', 'generated');
const dataDir = join(__dirname, 'src', 'data');

mkdirSync(generatedDir, { recursive: true });
mkdirSync(dataDir, { recursive: true });

// ── 1 & 2. Generate TypeScript interfaces ──────────────────────────────────
const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));

const interfaceTs = await compile(schema, 'Monster', {
  bannerComment:
    '/* Auto-generated. Do not edit manually.\n' +
    ' * Run `npm run codegen` from the npm/ directory to regenerate. */',
  additionalProperties: false,
  unknownAny: false,
});

writeFileSync(join(generatedDir, 'monster.ts'), interfaceTs);
console.log('✓ Generated src/generated/monster.ts');

// ── 3. Inline schema as a TypeScript const ─────────────────────────────────
const schemaTs =
  `/* Auto-generated. Do not edit manually.\n` +
  ` * Run \`npm run codegen\` from the npm/ directory to regenerate. */\n` +
  `\n` +
  `// eslint-disable-next-line @typescript-eslint/no-explicit-any\n` +
  `export const MONSTER_SCHEMA: Record<string, any> = ${JSON.stringify(schema, null, 2)};\n`;

writeFileSync(join(generatedDir, 'monster-schema.ts'), schemaTs);
console.log('✓ Generated src/generated/monster-schema.ts');

// ── 4. Copy monster data ───────────────────────────────────────────────────
copyFileSync(monstersDataPath, join(dataDir, 'monsters.json'));
console.log('✓ Copied output/monsters.json → src/data/monsters.json');
