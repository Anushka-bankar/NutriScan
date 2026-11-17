export const CATALOG_PAGE_SIZE = 20;

export const CATALOG_FILTER_RANGES = [
  { key: 'calories', label: 'Calories', unit: 'kcal' },
  { key: 'sugar', label: 'Sugar', unit: 'g' },
  { key: 'fat', label: 'Total fat', unit: 'g' },
  { key: 'protein', label: 'Protein', unit: 'g' },
  { key: 'sodium', label: 'Sodium', unit: 'mg' },
];

export const CATALOG_NUTRIENTS = [
  ['calories_kcal', 'Calories', 'kcal'],
  ['carbohydrates_g', 'Carbohydrates', 'g'],
  ['protein_g', 'Protein', 'g'],
  ['total_fat_g', 'Total fat', 'g'],
  ['saturated_fat_g', 'Saturated fat', 'g'],
  ['trans_fat_g', 'Trans fat', 'g'],
  ['sugar_g', 'Sugar', 'g'],
  ['sodium_mg', 'Sodium', 'mg'],
  ['dietary_fiber_g', 'Dietary fiber', 'g'],
  ['cholesterol_mg', 'Cholesterol', 'mg'],
  ['calcium_mg', 'Calcium', 'mg'],
  ['iron_mg', 'Iron', 'mg'],
];

export function formatCatalogValue(value, unit = '') {
  if (value == null || value === '') return 'Not available';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'Not available';
  const formatted = numeric.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
  return unit ? `${formatted} ${unit}` : formatted;
}

export function buildCatalogFilterParams(filters) {
  const params = {};
  const category = filters.category?.trim();
  if (category) params.category = category;

  for (const { key } of CATALOG_FILTER_RANGES) {
    for (const bound of ['min', 'max']) {
      const field = `${key}_${bound}`;
      const value = filters[field]?.trim();
      if (value) params[field] = value;
    }
  }
  return params;
}

export function hasCatalogFilterCriteria(params) {
  return Object.values(params).some((value) => value !== '' && value != null);
}

export function filterCatalogItems(products, { q = '', brand = '' } = {}) {
  const nameQuery = q.trim().toLocaleLowerCase();
  const brandQuery = brand.trim().toLocaleLowerCase();
  return products.filter((product) => {
    const nameMatches = !nameQuery
      || product.name.toLocaleLowerCase().includes(nameQuery);
    const brandMatches = !brandQuery
      || (product.brand || '').toLocaleLowerCase().includes(brandQuery);
    return nameMatches && brandMatches;
  });
}

export function paginateCatalogItems(items, page, pageSize = CATALOG_PAGE_SIZE) {
  const total = items.length;
  const pages = Math.ceil(total / pageSize);
  const currentPage = pages === 0 ? 1 : Math.min(Math.max(1, page), pages);
  const start = (currentPage - 1) * pageSize;
  return {
    products: items.slice(start, start + pageSize),
    pagination: {
      page: currentPage,
      per_page: pageSize,
      total,
      pages,
    },
  };
}

export function catalogErrorMessage(error, fallback) {
  return error.response?.data?.message || fallback;
}
