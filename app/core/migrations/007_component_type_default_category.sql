ALTER TABLE component_types ADD COLUMN default_category_id INTEGER NULL;

UPDATE component_types
SET default_category_id = (
    SELECT id FROM categories
    WHERE name = 'Faiz gideri' AND nature = 'expense' AND deleted_at IS NULL
    LIMIT 1
)
WHERE code IN ('interest', 'kkdf', 'bsmv', 'fund', 'tax', 'fee')
  AND nature = 'expense'
  AND deleted_at IS NULL;

UPDATE component_types
SET default_category_id = (
    SELECT id FROM categories
    WHERE name = 'Sigorta' AND nature = 'expense' AND deleted_at IS NULL
    LIMIT 1
)
WHERE code = 'life_ins'
  AND nature = 'expense'
  AND deleted_at IS NULL;
