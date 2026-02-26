ALTER TABLE location
    ADD COLUMN biome_key VARCHAR(32) NOT NULL DEFAULT 'wilderness',
    ADD COLUMN hazard_profile_key VARCHAR(32) NOT NULL DEFAULT 'standard',
    ADD COLUMN environmental_flags JSON NULL;

CREATE TABLE location_history (
    location_history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    location_id INT(11) UNSIGNED NOT NULL,
    changed_turn BIGINT UNSIGNED NOT NULL DEFAULT 0,
    flag_key VARCHAR(128) NOT NULL,
    old_value VARCHAR(255) NULL,
    new_value VARCHAR(255) NULL,
    reason VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (location_history_id),
    CONSTRAINT fk_location_history_location_id FOREIGN KEY (location_id) REFERENCES location(location_id) ON DELETE CASCADE ON UPDATE CASCADE
);