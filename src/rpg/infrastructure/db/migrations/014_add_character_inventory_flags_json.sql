SET @has_inventory_json := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'character'
      AND COLUMN_NAME = 'inventory_json'
);

SET @inventory_sql := IF(
    @has_inventory_json = 0,
    'ALTER TABLE `character` ADD COLUMN inventory_json JSON NULL',
    'SELECT 1'
);
PREPARE stmt_inventory FROM @inventory_sql;
EXECUTE stmt_inventory;
DEALLOCATE PREPARE stmt_inventory;

SET @has_flags_json := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'character'
      AND COLUMN_NAME = 'flags_json'
);

SET @flags_sql := IF(
    @has_flags_json = 0,
    'ALTER TABLE `character` ADD COLUMN flags_json JSON NULL',
    'SELECT 1'
);
PREPARE stmt_flags FROM @flags_sql;
EXECUTE stmt_flags;
DEALLOCATE PREPARE stmt_flags;
