-- World table to persist world state
CREATE TABLE IF NOT EXISTS world (
    world_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    current_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    threat_level INT NOT NULL DEFAULT 0,
    flags JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (world_id)
);

-- Seed a default world row if none exists
INSERT INTO world (name)
SELECT 'Default World'
WHERE NOT EXISTS (SELECT 1 FROM world);

-- HP persistence on character
ALTER TABLE `character`
    ADD COLUMN hp_current INT NOT NULL DEFAULT 10;

ALTER TABLE `character`
    ADD COLUMN hp_max INT NOT NULL DEFAULT 10;
