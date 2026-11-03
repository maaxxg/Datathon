import re

p = 'frontend/src/routes/+page.svelte'
content = open(p, 'r', encoding='utf-8').read()

# Replace Petrinja default coords with Zagreb uz Savu
content = content.replace("selectedLabel = $state('Petrinja');", "selectedLabel = $state('Zagreb uz Savu');")
content = content.replace("lat = $state(45.4375);", "lat = $state(45.793);")
content = content.replace("lon = $state(16.2739);", "lon = $state(15.96);")

# Update initial map center zoom
content = content.replace("center: [lon, lat],\n\t\t\tzoom: 12", "center: [lon, lat],\n\t\t\tzoom: 13")

# Add derived filters
derived_code = """\tlet debounceTimer;

\t// Opasnosti s podacima za odabranu lokaciju vs. opasnosti bez podataka
\tlet availableHazards = $derived(report?.hazards?.filter((h) => h.level !== 'nema_podataka') || []);
\tlet noDataHazards = $derived(report?.hazards?.filter((h) => h.level === 'nema_podataka') || []);"""

content = content.replace("\tlet debounceTimer;", derived_code)

open(p, 'w', encoding='utf-8', newline='\n').write(content)
print("Updated basic settings!")

