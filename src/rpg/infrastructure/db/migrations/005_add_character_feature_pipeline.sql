ALTER TABLE ability
    ADD COLUMN slug VARCHAR(128) NULL,
    ADD COLUMN trigger_key VARCHAR(64) NULL,
    ADD COLUMN effect_kind VARCHAR(64) NULL,
    ADD COLUMN effect_value INT NULL,
    ADD COLUMN source VARCHAR(32) NULL;

CREATE UNIQUE INDEX uk_ability_slug ON ability (slug);

CREATE TABLE character_feature (
    character_feature_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    character_id INT(11) UNSIGNED NOT NULL,
    ability_id INT(11) UNSIGNED NOT NULL,
    PRIMARY KEY (character_feature_id),
    CONSTRAINT uk_character_id_ability_id UNIQUE (character_id, ability_id),
    CONSTRAINT fk_character_feature_character_id FOREIGN KEY (character_id) REFERENCES `character`(character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_character_feature_ability_id FOREIGN KEY (ability_id) REFERENCES ability(ability_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE h_character_feature (
    h_character_feature_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    character_feature_id BIGINT UNSIGNED NOT NULL,
    character_id INT(11) UNSIGNED NOT NULL,
    ability_id INT(11) UNSIGNED NOT NULL,
    PRIMARY KEY (h_character_feature_id)
);

INSERT INTO ability_type (name, `desc`)
SELECT 'passive', 'Persistent passive feature'
WHERE NOT EXISTS (SELECT 1 FROM ability_type WHERE LOWER(name) = 'passive');

INSERT INTO ability (name, ability_type_id, required_level, slug, trigger_key, effect_kind, effect_value, source)
SELECT 'Sneak Attack', at.ability_type_id, 1, 'feature.sneak_attack', 'on_attack_hit', 'bonus_damage', 2, 'seed'
FROM ability_type at
WHERE LOWER(at.name) = 'passive'
  AND NOT EXISTS (SELECT 1 FROM ability WHERE slug = 'feature.sneak_attack');

INSERT INTO class_ability (class_id, ability_id)
SELECT cls.class_id, ab.ability_id
FROM class cls
INNER JOIN ability ab ON ab.slug = 'feature.sneak_attack'
WHERE LOWER(COALESCE(cls.open5e_slug, cls.name)) = 'rogue'
  AND NOT EXISTS (
      SELECT 1
      FROM class_ability ca
      WHERE ca.class_id = cls.class_id AND ca.ability_id = ab.ability_id
  );

INSERT INTO ability (name, ability_type_id, required_level, slug, trigger_key, effect_kind, effect_value, source)
SELECT 'Darkvision', at.ability_type_id, 1, 'feature.darkvision', 'on_initiative', 'initiative_bonus', 2, 'seed'
FROM ability_type at
WHERE LOWER(at.name) = 'passive'
  AND NOT EXISTS (SELECT 1 FROM ability WHERE slug = 'feature.darkvision');

INSERT INTO ability (name, ability_type_id, required_level, slug, trigger_key, effect_kind, effect_value, source)
SELECT 'Martial Precision', at.ability_type_id, 1, 'feature.martial_precision', 'on_attack_roll', 'attack_bonus', 2, 'seed'
FROM ability_type at
WHERE LOWER(at.name) = 'passive'
  AND NOT EXISTS (SELECT 1 FROM ability WHERE slug = 'feature.martial_precision');

INSERT INTO class_ability (class_id, ability_id)
SELECT cls.class_id, ab.ability_id
FROM class cls
INNER JOIN ability ab ON ab.slug = 'feature.martial_precision'
WHERE LOWER(COALESCE(cls.open5e_slug, cls.name)) = 'fighter'
  AND NOT EXISTS (
      SELECT 1
      FROM class_ability ca
      WHERE ca.class_id = cls.class_id AND ca.ability_id = ab.ability_id
  );
