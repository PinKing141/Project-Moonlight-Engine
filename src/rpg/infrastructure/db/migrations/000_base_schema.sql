-- Baseline schema migration generated from deprecated create_tables.sql/create_history_tables.sql.
-- This file is the canonical bootstrap source for fresh databases in strict linear mode.

CREATE TABLE `conf` (
    `conf_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `value` varchar(255),
    PRIMARY KEY (`conf_id`),
    CONSTRAINT `uk_name` UNIQUE (`name`)
);

CREATE TABLE `user_type` (
    `user_type_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`user_type_id`)
);


CREATE TABLE `user` (
    `user_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_type_id` int(11) UNSIGNED NOT NULL,
    `first_name` varchar(255) NOT NULL,
    `last_name` varchar(255) NOT NULL,
    `email` varchar(255) NOT NULL,
    `password` varchar(255) NOT NULL,
    PRIMARY KEY (`user_id`),
    CONSTRAINT `fk_user_user_type_id` FOREIGN KEY (`user_type_id`) REFERENCES `user_type`(`user_type_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `character_type` (
    `character_type_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`character_type_id`)
);


CREATE TABLE `character` (
    `character_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `alive` tinyint NOT NULL,
    `level` smallint NOT NULL,
    `xp` bigint NOT NULL,
    `money` bigint NOT NULL,
    `inventory_json` JSON NULL,
    `flags_json` JSON NULL,
    PRIMARY KEY (`character_id`),
    CONSTRAINT `fk_character_character_type_id` FOREIGN KEY (`character_type_id`) REFERENCES `character_type`(`character_type_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `user_character` (
    `user_character_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`user_character_id`),
    CONSTRAINT `uk_user_id_character_id` UNIQUE (`user_id`, `character_id`),
    CONSTRAINT `fk_user_character_user_id` FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_user_character_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `attribute` (
    `attribute_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`attribute_id`)
);


CREATE TABLE `character_attribute` (
    `character_attribute_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `value` bigint NOT NULL,
    PRIMARY KEY (`character_attribute_id`),
    CONSTRAINT `uk_character_id_attribute_id` UNIQUE (`character_id`, `attribute_id`),
    CONSTRAINT `fk_character_attribute_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_attribute_attribute_id` FOREIGN KEY (`attribute_id`) REFERENCES `attribute`(`attribute_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `place` (
    `place_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`place_id`)
);

CREATE TABLE `location` (
    `location_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `x` bigint NOT NULL,
    `y` bigint NOT NULL,
    `place_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`location_id`),
    CONSTRAINT `uk_x_y` UNIQUE (`x`, `y`),
    CONSTRAINT `fk_location_place_id` FOREIGN KEY (`place_id`) REFERENCES `place`(`place_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `character_location` (
    `character_location_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `location_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_location_id`),
    CONSTRAINT `uk_character_id` UNIQUE (`character_id`),
    CONSTRAINT `fk_character_location_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_location_location_id` FOREIGN KEY (`location_id`) REFERENCES `location`(`location_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `item_type` (
    `item_type_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`item_type_id`)
);

CREATE TABLE `item` (
    `item_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `item_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `required_level` smallint,
    `durability` tinyint  NOT NULL,
    PRIMARY KEY (`item_id`),
    CONSTRAINT `fk_item_item_type_id` FOREIGN KEY (`item_type_id`) REFERENCES `item_type`(`item_type_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `item_attribute` (
    `item_attribute_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `item_id` int(11) UNSIGNED NOT NULL,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `value` bigint NOT NULL,
    PRIMARY KEY (`item_attribute_id`),
    CONSTRAINT `uk_item_id_attribute_id` UNIQUE (`item_id`, `attribute_id`),
    CONSTRAINT `fk_item_attribute_item_id` FOREIGN KEY (`item_id`) REFERENCES `item`(`item_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_item_attribute_attribute_id` FOREIGN KEY (`attribute_id`) REFERENCES `attribute`(`attribute_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `item_location` (
    `item_location_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `item_id` int(11) UNSIGNED NOT NULL,
    `location_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`item_location_id`),
    CONSTRAINT `uk_item_id` UNIQUE (`item_id`),
    CONSTRAINT `fk_item_location_item_id` FOREIGN KEY (`item_id`) REFERENCES `item`(`item_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_item_location_location_id` FOREIGN KEY (`location_id`) REFERENCES `location`(`location_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `character_item` (
    `character_item_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_item_id`),
    CONSTRAINT `uk_character_id_item_id` UNIQUE (`character_id`, `item_id`),
    CONSTRAINT `fk_character_item_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_item_item_id` FOREIGN KEY (`item_id`) REFERENCES `item`(`item_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `equipment_slot` (
    `equipment_slot_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`equipment_slot_id`),
    CONSTRAINT `uk_name` UNIQUE (`name`)
);


CREATE TABLE `character_equipment` (
    `character_equipment_id` int(11) UNSIGNED NOT NULL,
    `equipment_slot_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`equipment_slot_id`),
    CONSTRAINT `uk_equipment_slot_id_character_id` UNIQUE (`equipment_slot_id`, `character_id`),
    CONSTRAINT `fk_character_equipment_equipment_slot_id` FOREIGN KEY (`equipment_slot_id`) REFERENCES `equipment_slot`(`equipment_slot_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_equipment_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_equipment_item_id` FOREIGN KEY (`item_id`) REFERENCES `item`(`item_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `class` (
    `class_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `hit_die` varchar(8),
    `primary_ability` varchar(32),
    `source` varchar(32),
    `open5e_slug` varchar(128),
    PRIMARY KEY (`class_id`),
    CONSTRAINT `uk_name` UNIQUE (`name`),
    CONSTRAINT `uk_open5e_slug` UNIQUE (`open5e_slug`)
);

CREATE TABLE `character_class` (
    `character_class_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `class_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_class_id`),
    CONSTRAINT `uk_character_id` UNIQUE (`character_id`),
    CONSTRAINT `fk_character_class_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_class_class_id` FOREIGN KEY (`class_id`) REFERENCES `class`(`class_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `ability_type` (
    `ability_type_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`ability_type_id`)
);

CREATE TABLE `ability` (
    `ability_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `ability_type_id` int(11) UNSIGNED NOT NULL,
    `required_level` smallint,
    PRIMARY KEY (`ability_id`),
    CONSTRAINT `fk_ability_ability_type_id` FOREIGN KEY (`ability_type_id`) REFERENCES `ability_type`(`ability_type_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `class_ability` (
    `class_ability_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `class_id` int(11) UNSIGNED NOT NULL,
    `ability_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`class_ability_id`),
    CONSTRAINT `uk_class_id_ability_id` UNIQUE (`class_id`, `ability_id`),
    CONSTRAINT `fk_class_ability_class_id` FOREIGN KEY (`class_id`) REFERENCES `class`(`class_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_class_ability_ability_id` FOREIGN KEY (`ability_id`) REFERENCES `ability`(`ability_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `effect_type` (
    `effect_type_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`effect_type_id`)
);


CREATE TABLE `status_effect` (
    `status_effect_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `effect_type_id` int(11) UNSIGNED NOT NULL,
    `duration` bigint,
    `desc` varchar(255),
    PRIMARY KEY (`status_effect_id`),
    CONSTRAINT `fk_status_effect_effect_type_id` FOREIGN KEY (`effect_type_id`) REFERENCES `effect_type`(`effect_type_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `character_status_effect` (
    `character_status_effect_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `status_effect_id` int(11) UNSIGNED NOT NULL,
    `date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`character_status_effect_id`),
    CONSTRAINT `fk_character_status_effect_status_effect_id` FOREIGN KEY (`status_effect_id`) REFERENCES `status_effect`(`status_effect_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_status_effect_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `loot` (
    `loot_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `xp` bigint,
    `money` bigint,
    PRIMARY KEY (`loot_id`)
);

CREATE TABLE `character_loot` (
    `character_loot_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_loot_id`),
    CONSTRAINT `fk_character_loot_loot_id` FOREIGN KEY (`loot_id`) REFERENCES `loot`(`loot_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_loot_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `item_loot` (
    `item_loot_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    `drop_chance` FLOAT(4,4),
    PRIMARY KEY (`item_loot_id`),
    CONSTRAINT `fk_item_loot_loot_id` FOREIGN KEY (`loot_id`) REFERENCES `loot`(`loot_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_item_loot_item_id` FOREIGN KEY (`item_id`) REFERENCES `item`(`item_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_type` (
    `entity_type_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`entity_type_id`)
);

CREATE TABLE `entity` (
    `entity_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `entity_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `level` smallint,
    PRIMARY KEY (`entity_id`),
    CONSTRAINT `fk_entity_entity_type_id` FOREIGN KEY (`entity_type_id`) REFERENCES `entity_type`(`entity_type_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_attribute` (
    `entity_attribute_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `value` bigint NOT NULL,
    PRIMARY KEY (`entity_attribute_id`),
    CONSTRAINT `uk_entity_id_attribute_id` UNIQUE (`entity_id`, `attribute_id`),
    CONSTRAINT `fk_entity_attribute_entity_id` FOREIGN KEY (`entity_id`) REFERENCES `entity`(`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_entity_attribute_attribute_id` FOREIGN KEY (`attribute_id`) REFERENCES `attribute`(`attribute_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_location` (
    `entity_location_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `location_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`entity_location_id`),
    CONSTRAINT `uk_entity_id` UNIQUE (`entity_id`),
    CONSTRAINT `fk_entity_location_entity_id` FOREIGN KEY (`entity_id`) REFERENCES `entity`(`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_entity_location_location_id` FOREIGN KEY (`location_id`) REFERENCES `location`(`location_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_class` (
    `entity_class_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `class_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`entity_class_id`),
    CONSTRAINT `uk_entity_id` UNIQUE (`entity_id`),
    CONSTRAINT `fk_entity_class_entity_id` FOREIGN KEY (`entity_id`) REFERENCES `entity`(`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_entity_class_class_id` FOREIGN KEY (`class_id`) REFERENCES `class`(`class_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_status_effect` (
    `entity_status_effect_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `status_effect_id` int(11) UNSIGNED NOT NULL,
    `date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`entity_status_effect_id`),
    CONSTRAINT `fk_entity_status_effect_status_effect_id` FOREIGN KEY (`status_effect_id`) REFERENCES `status_effect`(`status_effect_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_entity_status_effect_entity_id` FOREIGN KEY (`entity_id`) REFERENCES `entity`(`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_loot` (
    `entity_loot_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`entity_loot_id`),
    CONSTRAINT `fk_entity_loot_loot_id` FOREIGN KEY (`loot_id`) REFERENCES `loot`(`loot_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_entity_loot_entity_id` FOREIGN KEY (`entity_id`) REFERENCES `entity`(`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `faction` (
    `faction_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`faction_id`)
);

CREATE TABLE `character_faction` (
    `character_faction_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `faction_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_faction_id`),
    CONSTRAINT `fk_character_faction_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_faction_faction_id` FOREIGN KEY (`faction_id`) REFERENCES `faction`(`faction_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `entity_faction` (
    `entity_faction_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `faction_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`entity_faction_id`),
    CONSTRAINT `fk_entity_faction_entity_id` FOREIGN KEY (`entity_id`) REFERENCES `entity`(`entity_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_entity_faction_faction_id` FOREIGN KEY (`faction_id`) REFERENCES `faction`(`faction_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `rank` (
    `rank_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`rank_id`)
);

CREATE TABLE `guild` (
    `guild_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`guild_id`)
);

CREATE TABLE `guild_rank` (
    `guild_rank_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `guild_id` int(11) UNSIGNED NOT NULL,
    `rank_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`guild_rank_id`),
    CONSTRAINT `uk_guild_id_rank_id` UNIQUE (`guild_id`, `rank_id`),
    CONSTRAINT `fk_guild_rank_guild_id` FOREIGN KEY (`guild_id`) REFERENCES `guild`(`guild_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_guild_rank_rank_id` FOREIGN KEY (`rank_id`) REFERENCES `rank`(`rank_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `character_guild` (
    `character_guild_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `guild_id` int(11) UNSIGNED NOT NULL,
    `guild_leader` tinyint,
    PRIMARY KEY (`character_guild_id`),
    CONSTRAINT `uk_guild_id_guild_leader` UNIQUE (`guild_id`, `guild_leader`),
    CONSTRAINT `fk_character_guild_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_guild_guild_id` FOREIGN KEY (`guild_id`) REFERENCES `guild`(`guild_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `character_guild_rank` (
    `character_guild_rank_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `guild_rank_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_guild_rank_id`),
    CONSTRAINT `uk_character_id_guild_rank_id` UNIQUE (`character_id`, `guild_rank_id`),
    CONSTRAINT `fk_character_guild_rank_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_guild_rank_guild_rank_id` FOREIGN KEY (`guild_rank_id`) REFERENCES `guild_rank`(`guild_rank_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `party` (
    `party_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    PRIMARY KEY (`party_id`)
);

CREATE TABLE `character_party` (
    `character_party_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `party_id` int(11) UNSIGNED NOT NULL,
    `party_leader` tinyint,
    PRIMARY KEY (`character_party_id`),
    CONSTRAINT `uk_character_id` UNIQUE (`character_id`),
    CONSTRAINT `uk_party_id_party_leader` UNIQUE (`party_id`, `party_leader`),
    CONSTRAINT `fk_character_party_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_party_party_id` FOREIGN KEY (`party_id`) REFERENCES `party`(`party_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE `title` (
    `title_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`title_id`)
);

CREATE TABLE `character_title` (
    `character_title_id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `character_id` int(11) UNSIGNED NOT NULL,
    `title_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`character_title_id`),
    CONSTRAINT `fk_character_title_character_id` FOREIGN KEY (`character_id`) REFERENCES `character`(`character_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_character_title_title_id` FOREIGN KEY (`title_id`) REFERENCES `title`(`title_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

-- History/audit schema tables

CREATE TABLE `h_conf` (
    h_conf_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `conf_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `value` varchar(255),
    PRIMARY KEY (`h_conf_id`)
);

CREATE TABLE `h_user_type` (
    h_user_type_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `user_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_user_type_id`)
);

CREATE TABLE `h_user` (
    h_user_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `user_id` int(11) UNSIGNED NOT NULL,
    `user_type_id` int(11) UNSIGNED NOT NULL,
    `first_name` varchar(255) NOT NULL,
    `last_name` varchar(255) NOT NULL,
    `email` varchar(255) NOT NULL,
    `password` varchar(255) NOT NULL,
    PRIMARY KEY (`h_user_id`)
);

CREATE TABLE `h_character_type` (
    h_character_type_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_character_type_id`)
);

CREATE TABLE `h_character` (
    h_character_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_id` int(11) UNSIGNED NOT NULL,
    `character_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `alive` tinyint NOT NULL,
    `level` smallint NOT NULL,
    `xp` bigint NOT NULL,
    `money` bigint NOT NULL,
    PRIMARY KEY (`h_character_id`)
);

CREATE TABLE `h_user_character` (
    h_user_character_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `user_character_id` int(11) UNSIGNED NOT NULL,
    `user_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_user_character_id`)
);

CREATE TABLE `h_attribute` (
    h_attribute_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`h_attribute_id`)
);

CREATE TABLE `h_character_attribute` (
    h_character_attribute_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_attribute_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `value` bigint NOT NULL,
    PRIMARY KEY (`h_character_attribute_id`)
);

CREATE TABLE `h_place` (
    h_place_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `place_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_place_id`)
);

CREATE TABLE `h_location` (
    h_location_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `location_id` int(11) UNSIGNED NOT NULL,
    `x` bigint NOT NULL,
    `y` bigint NOT NULL,
    `place_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_location_id`)
);

CREATE TABLE `h_character_location` (
    h_character_location_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_location_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `location_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_location_id`)
);

CREATE TABLE `h_item_type` (
    h_item_type_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `item_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`h_item_type_id`)
);

CREATE TABLE `h_item` (
    h_item_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `item_id` int(11) UNSIGNED NOT NULL,
    `item_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `required_level` smallint,
    `durability` tinyint  NOT NULL,
    PRIMARY KEY (`h_item_id`)
);

CREATE TABLE `h_item_attribute` (
    h_item_attribute_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `item_attribute_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `value` bigint NOT NULL,
    PRIMARY KEY (`h_item_attribute_id`)
);

CREATE TABLE `h_item_location` (
    h_item_location_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `item_location_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    `location_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_item_location_id`)
);

CREATE TABLE `h_character_item` (
    h_character_item_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_item_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_item_id`)
);

CREATE TABLE `h_equipment_slot` (
    h_equipment_slot_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `equipment_slot_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_equipment_slot_id`)
);

CREATE TABLE `h_character_equipment` (
    h_character_equipment_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_equipment_id` int(11) UNSIGNED NOT NULL,
    `equipment_slot_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_equipment_id`)
);

CREATE TABLE `h_class` (
    h_class_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `class_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_class_id`)
);

CREATE TABLE `h_character_class` (
    h_character_class_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_class_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `class_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_class_id`)
);

CREATE TABLE `h_ability_type` (
    h_ability_type_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `ability_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`h_ability_type_id`)
);

CREATE TABLE `h_ability` (
    h_ability_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `ability_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `ability_type_id` int(11) UNSIGNED NOT NULL,
    `required_level` smallint,
    PRIMARY KEY (`h_ability_id`)
);

CREATE TABLE `h_class_ability` (
    h_class_ability_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `class_ability_id` int(11) UNSIGNED NOT NULL,
    `class_id` int(11) UNSIGNED NOT NULL,
    `ability_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_class_ability_id`)
);

CREATE TABLE `h_effect_type` (
    h_effect_type_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `effect_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `desc` varchar(255),
    PRIMARY KEY (`h_effect_type_id`)
);

CREATE TABLE `h_status_effect` (
    h_status_effect_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `status_effect_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `effect_type_id` int(11) UNSIGNED NOT NULL,
    `duration` bigint,
    `desc` varchar(255),
    PRIMARY KEY (`h_status_effect_id`)
);

CREATE TABLE `h_character_status_effect` (
    h_character_status_effect_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_status_effect_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `status_effect_id` int(11) UNSIGNED NOT NULL,
    `date` TIMESTAMP,
    PRIMARY KEY (`h_character_status_effect_id`)
);

CREATE TABLE `h_loot` (
    h_loot_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `xp` bigint,
    `money` bigint,
    PRIMARY KEY (`h_loot_id`)
);

CREATE TABLE `h_character_loot` (
    h_character_loot_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_loot_id` int(11) UNSIGNED NOT NULL,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_loot_id`)
);

CREATE TABLE `h_item_loot` (
    h_item_loot_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `item_loot_id` int(11) UNSIGNED NOT NULL,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `item_id` int(11) UNSIGNED NOT NULL,
    `drop_chance` FLOAT(4,4),
    PRIMARY KEY (`h_item_loot_id`)
);

CREATE TABLE `h_entity_type` (
    h_entity_type_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_entity_type_id`)
);

CREATE TABLE `h_entity` (
    h_entity_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `entity_type_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    `level` smallint,
    PRIMARY KEY (`h_entity_id`)
);

CREATE TABLE `h_entity_attribute` (
    h_entity_attribute_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_attribute_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `attribute_id` int(11) UNSIGNED NOT NULL,
    `value` bigint NOT NULL,
    PRIMARY KEY (`h_entity_attribute_id`)
);

CREATE TABLE `h_entity_location` (
    h_entity_location_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_location_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `location_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_entity_location_id`)
);

CREATE TABLE `h_entity_class` (
    h_entity_class_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_class_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `class_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_entity_class_id`)
);

CREATE TABLE `h_entity_status_effect` (
    h_entity_status_effect_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_status_effect_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `status_effect_id` int(11) UNSIGNED NOT NULL,
    `date` TIMESTAMP,
    PRIMARY KEY (`h_entity_status_effect_id`)
);

CREATE TABLE `h_entity_loot` (
    h_entity_loot_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_loot_id` int(11) UNSIGNED NOT NULL,
    `loot_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_entity_loot_id`)
);

CREATE TABLE `h_faction` (
    h_faction_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `faction_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_faction_id`)
);

CREATE TABLE `h_character_faction` (
    h_character_faction_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_faction_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `faction_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_faction_id`)
);

CREATE TABLE `h_entity_faction` (
    h_entity_faction_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `entity_faction_id` int(11) UNSIGNED NOT NULL,
    `entity_id` int(11) UNSIGNED NOT NULL,
    `faction_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_entity_faction_id`)
);

CREATE TABLE `h_rank` (
    h_rank_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `guild_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_rank_id`)
);

CREATE TABLE `h_guild` (
    h_guild_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `guild_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_guild_id`)
);

CREATE TABLE `h_guild_rank` (
    h_guild_rank_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `guild_rank_id` int(11) UNSIGNED NOT NULL,
    `guild_id` int(11) UNSIGNED NOT NULL,
    `rank_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_guild_rank_id`)
);

CREATE TABLE `h_character_guild` (
    h_character_guild_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_guild_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `guild_id` int(11) UNSIGNED NOT NULL,
    `guild_leader` tinyint,
    PRIMARY KEY (`h_character_guild_id`)
);

CREATE TABLE `h_character_guild_rank` (
    h_character_guild_rank_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_guild_rank_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `guild_rank_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_guild_rank_id`)
);

CREATE TABLE `h_party` (
    h_party_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `party_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_party_id`)
);

CREATE TABLE `h_character_party` (
    h_character_party_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_party_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `party_id` int(11) UNSIGNED NOT NULL,
    `party_leader` tinyint,
    PRIMARY KEY (`h_character_party_id`)
);

CREATE TABLE `h_title` (
    h_title_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `title_id` int(11) UNSIGNED NOT NULL,
    `name` varchar(255) NOT NULL,
    PRIMARY KEY (`h_title_id`)
);

CREATE TABLE `h_character_title` (
    h_character_title_id bigint UNSIGNED NOT NULL AUTO_INCREMENT,
    h_action ENUM('create', 'update', 'delete'),
    h_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `character_title_id` int(11) UNSIGNED NOT NULL,
    `character_id` int(11) UNSIGNED NOT NULL,
    `title_id` int(11) UNSIGNED NOT NULL,
    PRIMARY KEY (`h_character_title_id`)
);
