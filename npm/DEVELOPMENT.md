# dnd-5e-srd — Publishing Guide

## Prerequisites

- Node.js 18+
- An [npmjs.com](https://www.npmjs.com) account with publish rights to `dnd-5e-srd`
- 2FA enabled on your npm account (required by npm's security policy)

---

## First-time setup

```bash
cd npm/
npm install
npm login        # authenticates your local npm CLI with your account
```

---

## Workflow

### 1. Regenerate types and data from source

Run this whenever `schemas/monster.schema.json` or `output/monsters.json` has changed:

```bash
npm run codegen
```

This does three things:
- Reads `../schemas/monster.schema.json` and generates `src/generated/monster.ts` (TypeScript interfaces)
- Inlines the schema as a TypeScript const in `src/generated/monster-schema.ts` (so `dist/` is self-contained)
- Copies `../output/monsters.json` → `src/data/monsters.json`

`src/generated/` and `src/data/` are gitignored — they are always derived from the canonical sources.

### 2. Build

```bash
npm run build
```

Compiles TypeScript to `dist/` and copies `src/data/monsters.json` to `dist/data/`.
`dist/` is gitignored; it is rebuilt from source before every publish.

### 3. Bump the version

Edit `package.json` and increment the version following [semver](https://semver.org):

| Change type | Example | Version bump |
|---|---|---|
| New monsters or spells added | 330 → 340 monsters | `minor` (0.1.0 → 0.2.0) |
| Bug fix in data or types | fix a wrong CR value | `patch` (0.1.0 → 0.1.1) |
| Breaking type change | rename a field | `major` (0.1.0 → 1.0.0) |

Or use the npm CLI:
```bash
npm version patch   # 0.1.0 → 0.1.1
npm version minor   # 0.1.0 → 0.2.0
npm version major   # 0.1.0 → 1.0.0
```

### 4. Publish

`prepublishOnly` runs `codegen` and `build` automatically before publishing, so you only need:

```bash
npm publish --otp=<6-digit-code>
```

Use the current code from your authenticator app. The code is valid for ~30 seconds; if it expires mid-publish, just run the command again with a fresh code.

---

## Alternative: publish with a granular access token

If you want to publish without entering an OTP each time (e.g. from a script):

1. On npmjs.com: avatar → **Access Tokens** → **Generate New Token** → **Granular Access Token**
2. Grant **publish** permission on `dnd-5e-srd` and enable **Bypass 2FA**
3. Store the token in your npm config:
   ```bash
   npm config set //registry.npmjs.org/:_authToken <your-token>
   ```
4. Then publish without `--otp`:
   ```bash
   npm publish
   ```

---

## Adding a new content type (spells, magic items, etc.)

When a new output file (e.g. `output/spells.json`) is ready:

1. Add `../schemas/spell.schema.json` at the project root
2. Update `codegen.mjs` to compile the new schema and copy the data file
3. Add `src/validate-spell.ts` and update `src/index.ts` to export the new types and data
4. Bump the minor version and publish

---

## Verifying the package before publish

```bash
npm pack --dry-run     # lists every file that would be included in the tarball
```

The published package should contain only `dist/` — compiled JS, `.d.ts` type declarations, and `dist/data/monsters.json`.
