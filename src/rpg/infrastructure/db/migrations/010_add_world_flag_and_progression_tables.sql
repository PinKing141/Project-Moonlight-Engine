CREATE TABLE world_flag (
    world_flag_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    world_id INT UNSIGNED NOT NULL,
    flag_key VARCHAR(191) NOT NULL,
    flag_value VARCHAR(255) NULL,
    changed_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    reason VARCHAR(255) NOT NULL DEFAULT 'system',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (world_flag_id),
    CONSTRAINT uk_world_flag_world_key UNIQUE (world_id, flag_key),
    CONSTRAINT fk_world_flag_world_id FOREIGN KEY (world_id) REFERENCES world(world_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE world_history (
    world_history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    world_id INT UNSIGNED NOT NULL,
    changed_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    flag_key VARCHAR(191) NOT NULL,
    old_value VARCHAR(255) NULL,
    new_value VARCHAR(255) NULL,
    reason VARCHAR(255) NOT NULL DEFAULT 'system',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (world_history_id),
    CONSTRAINT fk_world_history_world_id FOREIGN KEY (world_id) REFERENCES world(world_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_world_history_world_turn ON world_history (world_id, changed_turn);

CREATE TABLE character_progression_unlock (
    character_progression_unlock_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    character_id INT(11) UNSIGNED NOT NULL,
    unlock_kind VARCHAR(32) NOT NULL,
    unlock_key VARCHAR(191) NOT NULL,
    unlocked_level SMALLINT NOT NULL,
    created_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (character_progression_unlock_id),
    CONSTRAINT uk_character_progression_unlock UNIQUE (character_id, unlock_kind, unlock_key),
    CONSTRAINT fk_character_progression_unlock_character_id FOREIGN KEY (character_id) REFERENCES `character`(character_id) ON DELETE CASCADE ON UPDATE CASCADE
);
