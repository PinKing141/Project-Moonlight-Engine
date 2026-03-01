INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Emerald Wardens', 'wardens', 'neutral', 2
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'wardens');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Wild Tribes', 'wild', 'chaotic', 2
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'wild');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Restless Dead', 'undead', 'evil', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'undead');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Crown', 'the_crown', 'lawful', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'the_crown');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Thieves Guild', 'thieves_guild', 'chaotic', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'thieves_guild');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'The Arcane Syndicate', 'arcane_syndicate', 'neutral', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'arcane_syndicate');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Tozan Empire', 'tozan_empire', 'lawful', 5
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'tozan_empire');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Sarprakelian Khaganate', 'sarprakelian_khaganate', 'lawful', 5
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'sarprakelian_khaganate');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Kingdom of Onimydrait', 'kingdom_of_onimydrait', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'kingdom_of_onimydrait');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Kingdom of Staglenia', 'kingdom_of_staglenia', 'lawful', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'kingdom_of_staglenia');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Vuyurt Khaganate', 'vuyurt_khaganate', 'chaotic', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'vuyurt_khaganate');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Republic of Pudrock', 'republic_of_pudrock', 'neutral', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'republic_of_pudrock');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Witnesses of Elloragh', 'witnesses_of_elloragh', 'lawful', 5
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'witnesses_of_elloragh');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Neverchist Synod', 'neverchist_synod', 'lawful', 5
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'neverchist_synod');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Ironcoin Syndicate', 'ironcoin_syndicate', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'ironcoin_syndicate');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Shrouded Athenaeum', 'shrouded_athenaeum', 'neutral', 4
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'shrouded_athenaeum');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Golden Banner Company', 'golden_banner_company', 'neutral', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'golden_banner_company');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Blond Spirit Cult', 'blond_spirit_cult', 'evil', 2
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'blond_spirit_cult');

INSERT INTO faction (name, slug, alignment, influence)
SELECT 'Crimson Corsairs', 'crimson_corsairs', 'chaotic', 3
WHERE NOT EXISTS (SELECT 1 FROM faction WHERE LOWER(COALESCE(slug, '')) = 'crimson_corsairs');