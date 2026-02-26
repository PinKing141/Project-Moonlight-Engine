CREATE TABLE quest_definition (
    quest_definition_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    quest_slug VARCHAR(128) NOT NULL,
    title VARCHAR(255) NOT NULL,
    objective_kind VARCHAR(64) NOT NULL,
    target_count INT NOT NULL DEFAULT 1,
    reward_xp INT NOT NULL DEFAULT 0,
    reward_money INT NOT NULL DEFAULT 0,
    faction_id INT(11) UNSIGNED NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'seed',
    PRIMARY KEY (quest_definition_id),
    CONSTRAINT uk_quest_definition_slug UNIQUE (quest_slug),
    CONSTRAINT fk_quest_definition_faction_id FOREIGN KEY (faction_id) REFERENCES faction(faction_id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE character_active_quest (
    character_active_quest_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    character_id INT(11) UNSIGNED NOT NULL,
    quest_definition_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) NOT NULL,
    progress INT NOT NULL DEFAULT 0,
    target_count INT NOT NULL DEFAULT 1,
    accepted_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    completed_turn BIGINT UNSIGNED NULL,
    seed_key VARCHAR(255) NULL,
    PRIMARY KEY (character_active_quest_id),
    CONSTRAINT uk_character_active_quest UNIQUE (character_id, quest_definition_id),
    CONSTRAINT fk_character_active_quest_character_id FOREIGN KEY (character_id) REFERENCES `character`(character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_character_active_quest_definition_id FOREIGN KEY (quest_definition_id) REFERENCES quest_definition(quest_definition_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE quest_history (
    quest_history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    character_id INT(11) UNSIGNED NOT NULL,
    quest_definition_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(32) NOT NULL,
    action_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    payload_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quest_history_id),
    CONSTRAINT fk_quest_history_character_id FOREIGN KEY (character_id) REFERENCES `character`(character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_quest_history_definition_id FOREIGN KEY (quest_definition_id) REFERENCES quest_definition(quest_definition_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE rumour_projection (
    rumour_projection_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    world_id INT UNSIGNED NOT NULL,
    location_id INT(11) UNSIGNED NOT NULL,
    world_turn BIGINT UNSIGNED NOT NULL,
    seed_namespace VARCHAR(128) NOT NULL,
    seed_context_hash VARCHAR(64) NOT NULL,
    rumour_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rumour_projection_id),
    CONSTRAINT uk_rumour_projection_deterministic UNIQUE (world_id, location_id, world_turn, seed_namespace, seed_context_hash),
    CONSTRAINT fk_rumour_projection_world_id FOREIGN KEY (world_id) REFERENCES world(world_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_rumour_projection_location_id FOREIGN KEY (location_id) REFERENCES location(location_id) ON DELETE CASCADE ON UPDATE CASCADE
);