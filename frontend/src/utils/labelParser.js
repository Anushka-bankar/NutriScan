const CATEGORY_RULES = [
  ['grains_cereals', /\b(?:oats?|cereal|granola|muesli|rice|pasta|noodles?|wheat|flour|cornflakes?)\b/i],
  ['snacks', /\b(?:chips?|crisps?|crackers?|popcorn|snack|cookies?|biscuits?|chocolate|candy)\b/i],
  ['beverages', /\b(?:juice|soda|drink|beverage|water|tea|coffee|milkshake)\b/i],
  ['dairy_alternatives', /\b(?:oat milk|soy milk|soya milk|almond milk|plant milk|coconut milk)\b/i],
  ['dairy', /\b(?:yogurt|yoghurt|cheese|butter|cream|dairy|milk)\b/i],
  ['meat_poultry', /\b(?:chicken|beef|pork|turkey|meat|sausage)\b/i],
  ['seafood', /\b(?:fish|salmon|tuna|shrimp|prawn|seafood)\b/i],
  ['plant_protein', /\b(?:tofu|tempeh|seitan|plant protein|protein powder)\b/i],
  ['fruits_vegetables', /\b(?:fruit|vegetable|apple|banana|tomato|beans|lentils?)\b/i],
  ['condiments_sauces', /\b(?:sauce|ketchup|mustard|mayonnaise|dressing|condiment)\b/i],
  ['prepared_meals', /\b(?:soup|meal|ready.to.eat|prepared|pizza|curry)\b/i],
  ['bakery', /\b(?:bread|bun|roll|cake|pastry|bakery)\b/i],
  ['other', /\b(?:coco(?:a)?|cacao)\s+powder\b/i],
];

const NUTRIENTS = [
  ['energy_kj', /\benergy\b/i, /\b(kj)\b/i, 3766],
  ['calories_kcal', /\b(?:energy|calories?)\b/i, /\b(kcal|calories?)\b/i, 900],
  ['carbohydrates_g', /\b(?:carbohydrates?|carbs?)\b/i, /\bg\b/i, 100, /\bsugars?\b/i],
  ['sugars_g', /\b(?:of which\s+)?sugars?\b/i, /\bg\b/i],
  ['protein_g', /\bproteins?\b/i, /\bg\b/i],
  ['total_fat_g', /\b(?:total\s+fat|fat)\b/i, /\bg\b/i, 100, /\b(?:saturated|trans)\s+fat\b/i],
  ['saturated_fat_g', /\b(?:saturated|sat\.?)\s+fat\b/i, /\bg\b/i],
  ['fibre_g', /\b(?:fibre|fiber)\b/i, /\bg\b/i],
];

function parseNumber(value) {
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function findLabelValue(line, labelPattern, unitPattern) {
  const match = labelPattern.exec(line);
  if (!match) return null;
  const tail = line.slice(match.index + match[0].length);
  const value = tail.match(/(\d+(?:[.,]\d+)?)/);
  if (!value) return null;
  const parsed = parseNumber(value[1]);
  if (parsed === null) return null;
  const suffix = tail.slice(value.index + value[0].length);
  if (!unitPattern.test(suffix)) return null;
  return parsed;
}

function valueForLine(lines, labelPattern, unitPattern, skipPattern, allowImplicitUnit = false) {
  for (const line of lines) {
    if (!labelPattern.test(line) || (skipPattern && skipPattern.test(line))) continue;
    const value = findLabelValue(line, labelPattern, unitPattern);
    if (value !== null) return { line, value };
    if (allowImplicitUnit) {
      const match = labelPattern.exec(line);
      const numericValue = match
        ? line.slice(match.index + match[0].length).match(/^\s*[:\-]?\s*(\d+(?:[.,]\d+)?)(?:\s|$)/)
        : null;
      const parsed = numericValue ? parseNumber(numericValue[1]) : null;
      if (parsed !== null) return { line, value: parsed, implicitUnit: true };
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
    .join('\n')
    .split(/\b(?:use\s*:|allergens?\b|may\s+contain\b|nutrition facts\b|nutrition information\b|nutritional facts\b|store in\b|packed\s*(?:&|and)\s*marketed by\b|storage instructions\b|best before\b)/i)[0]
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 10000);
}

function parseCategory(lines, name, ingredients) {
  const explicit = lines.find((line) => /\bcategory\b\s*[:\-]/i.test(line));
  if (explicit) {
    const value = explicit.replace(/^.*?\bcategory\b\s*[:\-]\s*/i, '').trim().toLowerCase();
    const match = CATEGORY_RULES.find(([, pattern]) => pattern.test(value));
    if (match) return { value: match[0], confidence: 'medium' };
  }
  const evidence = `${name} ${ingredients}`;
  const match = CATEGORY_RULES.find(([, pattern]) => pattern.test(evidence));
  return match
    ? { value: match[0], confidence: 'low' }
    : { value: '', confidence: 'none' };
}

function extractIdentity(lines, text) {
  const explicitName = lines.find((line) => /^\s*(?:product\s+)?name\s*[:\-]/i.test(line));
  const explicitBrand = lines.find((line) => /^\s*brand\s*[:\-]/i.test(line));
  const marketedByIndex = lines.findIndex((line) =>
    /\bpacked\s*(?:&|and)\s*marketed\s*by\b/i.test(line),
  );
  const marketedByLine = marketedByIndex >= 0 ? lines[marketedByIndex] : '';
  const named = explicitName
    ? explicitName.replace(/^\s*(?:product\s+)?name\s*[:\-]\s*/i, '').trim()
    : '';
  const explicitBrandValue = explicitBrand
    ? explicitBrand.replace(/^\s*brand\s*[:\-]\s*/i, '').trim()
    : '';
  const marketedByInline = marketedByLine
    .replace(/^.*?\bpacked\s*(?:&|and)\s*marketed\s*by\b\s*[:\-]?\s*/i, '')
    .trim();
  const marketedBy = marketedByInline
    || (marketedByIndex >= 0 ? lines[marketedByIndex + 1] || '' : '');
  const brand = explicitBrandValue || marketedBy.replace(/[:\s]+$/, '').trim();
  const sectionStart = lines.findIndex((line) =>
    /\b(?:nutrition facts|nutrition information|nutrition values|ingredients?)\b/i.test(line),
  );
  const header = lines.slice(0, sectionStart < 0 ? Math.min(lines.length, 6) : sectionStart);
  const candidate = header.find((line) => {
    const cleaned = line.replace(/[^a-zA-Z0-9&' -]/g, '').trim();
    return cleaned.length >= 3
      && cleaned.length <= 100
      && !/^(?:per\s+|serving size|barcode|brand|product name|ingredients?)/i.test(cleaned)
      && !/\b\d+(?:[.,]\d+)?\s*(?:kcal|kj|g|mg)\b/i.test(line);
  });
  const fallbackName = named || candidate || '';
  const inferredBrand = !brand && candidate && named && candidate !== named
    ? candidate
    : '';
  return {
    name: fallbackName.slice(0, 160),
    brand: (brand || inferredBrand).slice(0, 120),
    nameConfidence: named ? 'high' : candidate ? 'low' : 'none',
    brandConfidence: explicitBrandValue ? 'high' : brand ? 'low' : inferredBrand ? 'low' : 'none',
    containsServingBasis: /\bper\s+serving\b/i.test(text),
    containsHundredGramBasis: /\bper\s*100\s*g\b/i.test(text),
  };
}

export function parseNutritionLabel(text, { confidence = null } = {}) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const identity = extractIdentity(lines, text);
  const ingredients = parseIngredients(text);
  const category = parseCategory(lines, identity.name, '');
  const servingLine = lines.find((line) => /\bserving size\b/i.test(line));
  const servingMatch = servingLine?.match(/(\d+(?:[.,]\d+)?)\s*g\b/i);
  const servingSize = servingMatch ? parseNumber(servingMatch[1]) : null;
  const basis = identity.containsServingBasis && !identity.containsHundredGramBasis
    ? 'serving'
    : '100g';
  const result = {
    name: identity.name,
    brand: identity.brand,
    ingredients,
    category: category.value,
    categoryConfidence: category.confidence,
    nameConfidence: identity.nameConfidence,
    brandConfidence: identity.brandConfidence,
    serving_size_g: servingSize !== null && servingSize > 0 && servingSize <= 5000
      ? String(servingSize)
      : '',
    basis,
    warnings: [],
    uncertainFields: [],
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

  if (!result.name) result.warnings.push('Product name was not found on the scanned label.');
  else if (result.nameConfidence === 'low') {
    result.uncertainFields.push('name');
    result.warnings.push('Product name was inferred from the top of the label; verify it.');
  }
  if (!result.brand) {
    result.uncertainFields.push('brand');
    result.warnings.push('Brand was not clearly labelled; leave blank if it is not shown.');
  } else if (result.brandConfidence === 'low') {
    result.uncertainFields.push('brand');
    result.warnings.push('Brand was inferred from nearby text; verify it.');
  }
  if (!result.ingredients) {
    result.uncertainFields.push('ingredients');
    result.warnings.push('Ingredients were not found; check whether this label includes an ingredients panel.');
  }
  if (!result.category) {
    result.uncertainFields.push('category');
    result.warnings.push('Food category was not identifiable; select it if known.');
  } else if (result.categoryConfidence === 'low') {
    result.uncertainFields.push('category');
    result.warnings.push('Food category was inferred from product text; verify it.');
  }
  if (!result.serving_size_g) {
    result.uncertainFields.push('serving_size_g');
    result.warnings.push('Serving size in grams was not clearly identified.');
  } else if (servingSize < 1 || servingSize > 1000) {
    result.uncertainFields.push('serving_size_g');
    result.warnings.push('Serving size looks unusual; verify the number and unit.');
  }
  if (identity.containsServingBasis && identity.containsHundredGramBasis) {
    result.uncertainFields.push('basis');
    result.warnings.push('Both per-serving and per-100 g text were found; verify which column was read.');
  } else if (basis === 'serving' && !result.serving_size_g) {
    result.uncertainFields.push('basis');
    result.warnings.push('Values appear to be per serving, but serving weight is unavailable; they cannot be normalized yet.');
  }

  for (const [field, labelPattern, unitPattern, maximum, skipPattern] of NUTRIENTS) {
    let value = null;
    if (field === 'energy_kj' || field === 'calories_kcal') {
      for (const line of lines) {
        if (!labelPattern.test(line)) continue;
        const matches = [...line.matchAll(/(\d+(?:[.,]\d+)?)\s*(kJ|kcal|calories?)\b/gi)];
        const unit = field === 'energy_kj' ? /^kj$/i : /^(?:kcal|calories?)$/i;
        const match = matches.find((entry) => unit.test(entry[2]));
        if (match) value = parseNumber(match[1]);
        if (value !== null) break;
      }
    } else {
      const found = valueForLine(
        lines,
        labelPattern,
        unitPattern,
        skipPattern,
        /\bper\s*100\s*g\b/i.test(text),
      );
      value = found?.value ?? null;
      if (found?.implicitUnit) {
        result.uncertainFields.push(field);
        result.warnings.push(`${field.replaceAll('_', ' ')} had no unit printed beside its value; verify it.`);
      }
    }

    if (value === null) continue;
    const normalized = basis === 'serving' && result.serving_size_g
      ? (value * 100) / Number(result.serving_size_g)
      : value;
    const looksInvalid = normalized > maximum
      || (basis === 'serving' && !result.serving_size_g);
    if (looksInvalid) {
      result.uncertainFields.push(field);
      result.warnings.push(`${field.replaceAll('_', ' ')} looks suspicious or could not be normalized; verify it against the label.`);
      continue;
    }
    result[field] = String(value);
  }

  const sodium = valueForLine(lines, /\bsodium\b/i, /\b(?:mg|g)\b/i);
  if (sodium) {
    const unitMatch = sodium.line.match(/\bsodium\b.*?\b(mg|g)\b/i);
    const amountMg = unitMatch?.[1].toLowerCase() === 'g'
      ? sodium.value * 1000
      : sodium.value;
    const normalized = basis === 'serving' && result.serving_size_g
      ? amountMg * 100 / Number(result.serving_size_g)
      : amountMg;
    if (normalized <= 100000 && !(basis === 'serving' && !result.serving_size_g)) {
      result.sodium_mg = String(amountMg);
    } else {
      result.uncertainFields.push('sodium_mg');
      result.warnings.push('Sodium amount looks suspicious or could not be normalized; verify it against the label.');
    }
  } else {
    const salt = valueForLine(lines, /\bsalt\b/i, /\b(?:mg|g)\b/i);
    if (salt) {
      const unitMatch = salt.line.match(/\bsalt\b.*?\b(mg|g)\b/i);
      const saltMg = unitMatch?.[1].toLowerCase() === 'mg'
        ? salt.value
        : salt.value * 1000;
      const normalized = basis === 'serving' && result.serving_size_g
        ? saltMg * 0.4 * 100 / Number(result.serving_size_g)
        : saltMg * 0.4;
      if (normalized <= 100000 && !(basis === 'serving' && !result.serving_size_g)) {
        result.sodium_mg = String(Number((saltMg * 0.4).toFixed(2)));
      } else {
        result.uncertainFields.push('sodium_mg');
        result.warnings.push('Sodium estimated from salt looks suspicious or could not be normalized; verify it.');
      }
    }
  }

  for (const [field] of NUTRIENTS) {
    if (result[field] === '') {
      result.uncertainFields.push(field);
      result.warnings.push(`${field.replaceAll('_', ' ')} was not detected and remains unavailable.`);
    }
  }
  if (result.sodium_mg === '') {
    result.uncertainFields.push('sodium_mg');
    result.warnings.push('sodium mg was not detected and remains unavailable.');
  }

  if (result.sugars_g && result.carbohydrates_g
    && Number(result.sugars_g) > Number(result.carbohydrates_g)) {
    result.uncertainFields.push('sugars_g', 'carbohydrates_g');
    result.warnings.push('Sugar exceeds carbohydrates; review both recognized values.');
  }
  if (result.saturated_fat_g && result.total_fat_g
    && Number(result.saturated_fat_g) > Number(result.total_fat_g)) {
    result.uncertainFields.push('saturated_fat_g', 'total_fat_g');
    result.warnings.push('Saturated fat exceeds total fat; review both recognized values.');
  }
  if (result.energy_kj && result.calories_kcal) {
    const expectedKcal = Number(result.energy_kj) / 4.184;
    const observedKcal = Number(result.calories_kcal);
    if (Math.abs(expectedKcal - observedKcal) / Math.max(expectedKcal, observedKcal) > 0.25) {
      result.uncertainFields.push('energy_kj', 'calories_kcal');
      result.warnings.push('Energy in kJ and kcal does not appear consistent; review both values.');
    }
  }
  if (typeof confidence === 'number' && confidence < 75) {
    result.uncertainFields.push(
      'name',
      'brand',
      'category',
      'ingredients',
      'serving_size_g',
      'sodium_mg',
      ...NUTRIENTS.map(([field]) => field),
    );
    result.warnings.unshift('OCR confidence is low. Carefully compare every extracted value with the package.');
  }
  result.uncertainFields = [...new Set(result.uncertainFields)];
  result.warnings = [...new Set(result.warnings)];
  return result;
}
