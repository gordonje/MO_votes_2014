-- which counties cross multiple congressional districts?
SELECT county, count(*)
FROM (
        SELECT county, race
        FROM public.results
        WHERE race_type = 'US Representative'
        GROUP BY county, race
        HAVING count(*) > 1
        ORDER BY county
) as sub
GROUP BY county
HAVING count(*) > 1
ORDER BY county;

-- which counties cross multiple state senate districts?
SELECT county, count(*)
FROM (
        SELECT county, race
        FROM public.results
        WHERE race_type = 'State Senate'
        GROUP BY county, race
        HAVING count(*) > 1
        ORDER BY county
) as sub
GROUP BY county
HAVING count(*) > 1
ORDER BY county; 

-- which counties cross multiple state house districts?
SELECT county, count(*)
FROM (
        SELECT county, race
        FROM public.results
        WHERE race_type = 'State House'
        GROUP BY county, race
        HAVING count(*) > 1
        ORDER BY county
) as sub
GROUP BY county
HAVING count(*) > 1
ORDER BY county;