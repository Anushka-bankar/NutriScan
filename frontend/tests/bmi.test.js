import test from 'node:test';
import assert from 'node:assert/strict';
import { ADULT_BMI_CATEGORIES, getBmiCategoryLabel } from '../src/utils/bmi.js';

test('provides adult BMI ranges and readable category names', () => {
  assert.deepEqual(
    ADULT_BMI_CATEGORIES.map(({ range, label }) => [range, label]),
    [
      ['Below 18.5', 'Underweight'],
      ['18.5–24.9', 'Normal weight'],
      ['25–29.9', 'Overweight'],
      ['30 or above', 'Obese'],
    ],
  );
  assert.equal(getBmiCategoryLabel('healthy'), 'Normal weight');
  assert.equal(getBmiCategoryLabel('not_classified'), undefined);
});
