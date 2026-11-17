export const ADULT_BMI_CATEGORIES = [
  { key: 'underweight', range: 'Below 18.5', label: 'Underweight' },
  { key: 'healthy', range: '18.5–24.9', label: 'Normal weight' },
  { key: 'overweight', range: '25–29.9', label: 'Overweight' },
  { key: 'obesity', range: '30 or above', label: 'Obese' },
];

export function getBmiCategoryLabel(category) {
  return ADULT_BMI_CATEGORIES.find((item) => item.key === category)?.label;
}
