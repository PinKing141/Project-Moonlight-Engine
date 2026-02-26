INSERT INTO item_type (name, `desc`)
SELECT 'consumable', 'Combat and utility consumables'
WHERE NOT EXISTS (
    SELECT 1
    FROM item_type
    WHERE LOWER(name) = 'consumable'
);

INSERT INTO item (item_type_id, name, required_level, durability)
SELECT
    (
        SELECT item_type_id
        FROM item_type
        WHERE LOWER(name) = 'consumable'
        ORDER BY item_type_id
        LIMIT 1
    ),
    'Focus Potion',
    1,
    1
WHERE NOT EXISTS (
    SELECT 1
    FROM item
    WHERE LOWER(name) = 'focus potion'
);

INSERT INTO item (item_type_id, name, required_level, durability)
SELECT
    (
        SELECT item_type_id
        FROM item_type
        WHERE LOWER(name) = 'consumable'
        ORDER BY item_type_id
        LIMIT 1
    ),
    'Whetstone',
    1,
    1
WHERE NOT EXISTS (
    SELECT 1
    FROM item
    WHERE LOWER(name) = 'whetstone'
);
