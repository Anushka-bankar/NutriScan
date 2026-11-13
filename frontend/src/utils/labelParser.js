function parseNumber(value) {
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function firstValueAfter(line, pattern) {
  const label = pattern.exec(line);
  if (!label) return null;
  const value = line
    .slice(label.index + label[0].length)
    .match(/(\d+(?:[.,]\d+)?)/);
  return value ? parseNumber(value[1]) : null;
}

function valueForLine(lines, pattern, skipPattern) {
  for (const line of lines) {
    if (pattern.test(line) && !(skipPattern && skipPattern.test(line))) {
      const value = firstValueAfter(line, pattern);
      if (value !== null) return { line, value };
    }
  }
  return null;
}

function parseIngredients(text) {
  const lines = text.split(/\r?\n/);
  const headingIndex = lines.findIndex((line) => /\bingredients?\b/i.test(line));
  if (headingIndex < 0) return '';
  const heading = lines[headingIndex];
  const headingMatch = /\bingredients?\b\s*[:\-]?/i.exec(heading);
  const collected = [
    heading.slice(headingMatch.index + headingMatch[0].length),
    ...lines.slice(headingIndex + 1),
  ];
  return collected
    .join(' ')
    .split(/\b(?:allergens?|may contain|nutrition facts|nutrition information|storage instructions)\b/i)[0]
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 10000);
}

export function parseNutritionLabel(text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const result = {
    ingredients: parseIngredients(text),
    serving_size_g: '',
    basis: /\bper\s+serving\b/i.test(text) && !/\bper\s*100\s*g\b/i.test(text)
      ? 'serving'
      : '100g',
    energy_kj: '',
    calories_kcal: '',
    carbohydrates_g: '',
    sugars_g: '',
    protein_g: '',
    total_fat_g: '',
    saturated_fat_g: '',
    fibre_g: '',
    sodium_mg: '',
  };

  const servingLine = lines.find((line) => /\bserving size\b/i.test(line));
  if (servingLine) {
    const serving = servingLine.match(/(\d+(?:[.,]\d+)?)\s*g\b/i);
    if (serving) {
      result.serving_size_g = String(parseNumber(serving[1]));
    }
  }

  for (const line of lines) {
    if (!/\benergy\b/i.test(line)) continue;
    for (const match of line.matchAll(/(\d+(?:[.,]\d+)?)\s*(kJ|kcal)\b/gi)) {
      const value = parseNumber(match[1]);
      if (value === null) continue;
      if (match[2].toLowerCase() === 'kj' && !result.energy_kj) {
        result.energy_kj = String(value);
      } else if (match[2].toLowerCase() === 'kcal' && !result.calories_kcal) {
        result.calories_kcal = String(value);
      }
    }
  }

  const fields = [
    ['carbohydrates_g', /\b(?:carbohydrates?|carbs?)\b/i, /\bsugars?\b/i],
    ['sugars_g', /\b(?:sugars?|of which sugars?)\b/i],
    ['protein_g', /\bproteins?\b/i],
    ['total_fat_g', /\b(?:total\s+fat|fat)\b/i, /\b(?:saturated|trans)\s+fat\b/i],
    ['saturated_fat_g', /\b(?:saturated|sat\.?)\s+fat\b/i],
    ['fibre_g', /\b(?:fibre|fiber)\b/i],
  ];
  for (const [field, pattern, skip] of fields) {
    const found = valueForLine(lines, pattern, skip);
    if (found) result[field] = String(found.value);
  }

  const sodium = valueForLine(lines, /\bsodium\b/i);
  if (sodium) {
    const amount = firstValueAfter(sodium.line, /\bsodium\b/i);
    if (amount !== null) {
      result.sodium_mg = String(/\bmg\b/i.test(sodium.line) ? amount : amount * 1000);
    }
  } else {
    const salt = valueForLine(lines, /\bsalt\b/i);
    if (salt) {
      const amount = firstValueAfter(salt.line, /\bsalt\b/i);
      if (amount !== null) {
        result.sodium_mg = String(
          /\bmg\b/i.test(salt.line) ? amount * 0.4 : amount * 400,
        );
      }
    }
  }

  return result;
}
