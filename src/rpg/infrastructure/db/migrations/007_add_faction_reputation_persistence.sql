ALTER TABLE faction
    ADD COLUMN slug VARCHAR(128) NULL,
    ADD COLUMN alignment VARCHAR(32) NOT NULL DEFAULT 'neutral',
    ADD COLUMN influence INT NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX uk_faction_slug ON faction (slug);

UPDATE faction
SET slug = LOWER(REPLACE(name, ' ', '_'))
WHERE slug IS NULL OR slug = '';

CREATE TABLE faction_relationship (
    faction_relationship_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    faction_id INT(11) UNSIGNED NOT NULL,
    other_faction_id INT(11) UNSIGNED NOT NULL,
    alignment_score INT NOT NULL DEFAULT 0,
    updated_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (faction_relationship_id),
    CONSTRAINT uk_faction_relationship_pair UNIQUE (faction_id, other_faction_id),
    CONSTRAINT fk_faction_relationship_faction_id FOREIGN KEY (faction_id) REFERENCES faction(faction_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_faction_relationship_other_faction_id FOREIGN KEY (other_faction_id) REFERENCES faction(faction_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE character_reputation (
    character_reputation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    character_id INT(11) UNSIGNED NOT NULL,
    faction_id INT(11) UNSIGNED NOT NULL,
    reputation_score INT NOT NULL DEFAULT 0,
    updated_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (character_reputation_id),
    CONSTRAINT uk_character_reputation_character_faction UNIQUE (character_id, faction_id),
    CONSTRAINT fk_character_reputation_character_id FOREIGN KEY (character_id) REFERENCES `character`(character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_character_reputation_faction_id FOREIGN KEY (faction_id) REFERENCES faction(faction_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE reputation_history (
    reputation_history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    character_id INT(11) UNSIGNED NOT NULL,
    faction_id INT(11) UNSIGNED NOT NULL,
    delta INT NOT NULL,
    score_before INT NOT NULL,
    score_after INT NOT NULL,
    reason VARCHAR(255) NULL,
    changed_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (reputation_history_id),
    CONSTRAINT fk_reputation_history_character_id FOREIGN KEY (character_id) REFERENCES `character`(character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_reputation_history_faction_id FOREIGN KEY (faction_id) REFERENCES faction(faction_id) ON DELETE CASCADE ON UPDATE CASCADE
);