CREATE TABLE IF NOT EXISTS spell (
  slug            VARCHAR(128) PRIMARY KEY,
  name            VARCHAR(255) NOT NULL,
  level_int       INT NOT NULL,
  school          VARCHAR(64) NULL,
  casting_time    VARCHAR(128) NULL,
  range_text      VARCHAR(128) NULL,
  duration        VARCHAR(128) NULL,
  components      VARCHAR(64) NULL,
  concentration   TINYINT(1) NOT NULL DEFAULT 0,
  ritual          TINYINT(1) NOT NULL DEFAULT 0,
  desc_text       MEDIUMTEXT NULL,
  higher_level    MEDIUMTEXT NULL,
  classes_json    JSON NULL,
  updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_spell_level ON spell (level_int);
CREATE INDEX idx_spell_name  ON spell (name);
