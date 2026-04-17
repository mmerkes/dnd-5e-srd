// Types — re-exported from the generated interfaces.
export type {
  Monster,
  ArmorClass,
  HitPoints,
  Speed,
  AbilityScoreEntry,
  AbilityScores,
  Skills,
  Senses,
  Challenge,
  DamageRoll,
  AttackRoll,
  SavingThrow,
  UsesPerDay,
  AttackPattern,
  SpellList,
  SpecialAbility,
  Action,
  LegendaryActionEntry,
  LegendaryActions,
} from './generated/monster';

// Validation utilities.
export { validateMonster, validateMonsters, getValidationErrors } from './validate';

// Raw JSON Schema (useful for documentation, further tooling, or custom validators).
export { MONSTER_SCHEMA } from './generated/monster-schema';

// Monster data — 330 stat blocks from SRD 5.2.1, typed as Monster[].
// Loaded at runtime from the bundled data file; zero parse overhead at import.
import type { Monster } from './generated/monster';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const _monstersData: unknown[] = require('./data/monsters.json');
export const monsters = _monstersData as Monster[];
