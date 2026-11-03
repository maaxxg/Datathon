p = 'frontend/src/routes/+page.svelte'
content = open(p, 'r', encoding='utf-8').read()

# Replace workspace-grid media query and heights
old_grid = """\t@media (min-width: 900px) {
\t\t.workspace-grid {
\t\t\tgrid-template-columns: 5fr 7fr;
\t\t\talign-items: start;
\t\t}
\t}"""

new_grid = """\t@media (min-width: 960px) {
\t\t.workspace-grid {
\t\t\tgrid-template-columns: minmax(0, 1fr) 420px;
\t\t\talign-items: stretch;
\t\t}
\t}"""

assert old_grid in content, "old_grid not found"
content = content.replace(old_grid, new_grid)

# Map frame height increase
old_map_frame = """\t.map-frame {
\t\twidth: 100%;
\t\theight: 440px;
\t\tborder-radius: 0.5rem;
\t\tborder: 1px solid var(--border);
\t}"""

new_map_frame = """\t.map-frame {
\t\twidth: 100%;
\t\theight: 580px;
\t\tmin-height: 480px;
\t\tborder-radius: 0.5rem;
\t\tborder: 1px solid var(--border);
\t}"""

assert old_map_frame in content, "old_map_frame not found"
content = content.replace(old_map_frame, new_map_frame)

# Add styles for bottom sections and cards grid
new_styles = """
\t.bottom-section {
\t\tmargin-top: 1.5rem;
\t\tbackground: var(--surface);
\t\tborder: 1px solid var(--border);
\t\tborder-radius: 0.75rem;
\t\tpadding: 1.25rem;
\t}
\t.no-data-section {
\t\tborder-style: dashed;
\t\tbackground: #fafbfc;
\t}
\t.section-title-wrap h3 {
\t\tmargin: 0 0 0.25rem 0;
\t\tfont-size: 1.15rem;
\t\tcolor: var(--muted);
\t}
\t.section-desc {
\t\tmargin: 0 0 1rem 0;
\t\tfont-size: 0.88rem;
\t\tcolor: var(--muted);
\t}
\t.bottom-cards-grid {
\t\tdisplay: grid;
\t\tgrid-template-columns: 1fr;
\t\tgap: 1rem;
\t}
\t@media (min-width: 768px) {
\t\t.bottom-cards-grid {
\t\t\tgrid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
\t\t}
\t}
\t.no-active-hazards {
\t\tpadding: 1rem;
\t\tbackground: #f8fafc;
\t\tborder-radius: 0.5rem;
\t\tfont-size: 0.9rem;
\t\tcolor: var(--muted);
\t\tborder: 1px dashed var(--border);
\t}
"""

content = content.replace("</style>", new_styles + "</style>")

open(p, 'w', encoding='utf-8', newline='\n').write(content)
print("CSS updated successfully!")

