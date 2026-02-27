INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Grand Conclave', 'conclave_council', 'lawful', 5
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'conclave_council');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Crimson Spire', 'tower_crimson', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tower_crimson');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Cobalt Ward', 'tower_cobalt', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tower_cobalt');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Emerald Circle', 'tower_emerald', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tower_emerald');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Aurelian Order', 'tower_aurelian', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tower_aurelian');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Obsidian Cabal', 'tower_obsidian', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tower_obsidian');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Alabaster Sanctum', 'tower_alabaster', 'lawful', 5
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tower_alabaster');

INSERT INTO faction_relationship (faction_id, other_faction_id, alignment_score, updated_turn)
SELECT council.faction_id, tower.faction_id, 35, 0
FROM faction AS council
JOIN faction AS tower
WHERE council.slug = 'conclave_council'
  AND tower.slug IN ('tower_crimson', 'tower_cobalt', 'tower_emerald', 'tower_aurelian', 'tower_obsidian', 'tower_alabaster')
  AND NOT EXISTS (
    SELECT 1
    FROM faction_relationship rel
    WHERE rel.faction_id = council.faction_id
      AND rel.other_faction_id = tower.faction_id
  );

INSERT INTO faction_relationship (faction_id, other_faction_id, alignment_score, updated_turn)
SELECT tower.faction_id, council.faction_id, 35, 0
FROM faction AS council
JOIN faction AS tower
WHERE council.slug = 'conclave_council'
  AND tower.slug IN ('tower_crimson', 'tower_cobalt', 'tower_emerald', 'tower_aurelian', 'tower_obsidian', 'tower_alabaster')
  AND NOT EXISTS (
    SELECT 1
    FROM faction_relationship rel
    WHERE rel.faction_id = tower.faction_id
      AND rel.other_faction_id = council.faction_id
  );

INSERT INTO faction_relationship (faction_id, other_faction_id, alignment_score, updated_turn)
SELECT src.faction_id, dst.faction_id, 5, 0
FROM faction AS src
JOIN faction AS dst
WHERE src.slug IN ('tower_crimson', 'tower_cobalt', 'tower_emerald', 'tower_aurelian', 'tower_obsidian', 'tower_alabaster')
  AND dst.slug IN ('tower_crimson', 'tower_cobalt', 'tower_emerald', 'tower_aurelian', 'tower_obsidian', 'tower_alabaster')
  AND src.faction_id <> dst.faction_id
  AND NOT EXISTS (
    SELECT 1
    FROM faction_relationship rel
    WHERE rel.faction_id = src.faction_id
      AND rel.other_faction_id = dst.faction_id
  );