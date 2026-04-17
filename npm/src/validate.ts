import Ajv from 'ajv';
import type { Monster } from './generated/monster';
import { MONSTER_SCHEMA } from './generated/monster-schema';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ajv = new Ajv({ allErrors: true });
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _validate = ajv.compile(MONSTER_SCHEMA as any);

/**
 * Type guard — returns true when `data` conforms to the Monster schema.
 */
export function validateMonster(data: unknown): data is Monster {
  return _validate(data) as boolean;
}

/**
 * Type guard — returns true when `data` is an array of valid Monster objects.
 */
export function validateMonsters(data: unknown): data is Monster[] {
  if (!Array.isArray(data)) return false;
  return data.every((item) => validateMonster(item));
}

/**
 * Validates `data` against the Monster schema and returns a list of human-
 * readable error strings, or null when validation passes.
 */
export function getValidationErrors(data: unknown): string[] | null {
  _validate(data);
  if (!_validate.errors || _validate.errors.length === 0) return null;
  return _validate.errors.map(
    (e) => `${e.instancePath || '(root)'}: ${e.message ?? 'unknown error'}`
  );
}
