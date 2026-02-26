ALTER TABLE `character`
    ADD COLUMN `armour_class` INT NULL,
    ADD COLUMN `armor` INT NULL,
    ADD COLUMN `attack_bonus` INT NULL,
    ADD COLUMN `damage_die` VARCHAR(16) NULL,
    ADD COLUMN `speed` INT NULL;

ALTER TABLE `h_character`
    ADD COLUMN `armour_class` INT NULL,
    ADD COLUMN `armor` INT NULL,
    ADD COLUMN `attack_bonus` INT NULL,
    ADD COLUMN `damage_die` VARCHAR(16) NULL,
    ADD COLUMN `speed` INT NULL;
