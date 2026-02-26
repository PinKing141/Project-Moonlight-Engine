INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Crown', 'the_crown', 'lawful', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'the_crown');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Thieves Guild', 'thieves_guild', 'chaotic', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'thieves_guild');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Arcane Syndicate', 'arcane_syndicate', 'neutral', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'arcane_syndicate');
