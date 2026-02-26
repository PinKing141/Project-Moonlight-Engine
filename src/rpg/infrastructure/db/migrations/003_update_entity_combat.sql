ALTER TABLE entity
    ADD COLUMN armour_class INT NULL,
    ADD COLUMN attack_bonus INT NULL,
    ADD COLUMN damage_dice VARCHAR(32) NULL,
    ADD COLUMN hp_max INT NULL,
    ADD COLUMN kind VARCHAR(64) NULL;
