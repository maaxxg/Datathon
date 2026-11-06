<script>
	import { onMount } from 'svelte';

	let layers = $state({});
	let loadFailed = $state(false);

	const COVERAGE = {
		croatia: { label: 'Cijela Hrvatska', cls: 'cov-hr' },
		banovina: { label: 'Banovina (studija MPGI)', cls: 'cov-ban' }
	};

	onMount(async () => {
		try {
			const res = await fetch('/api/sources');
			if (!res.ok) throw new Error('bad status');
			const data = await res.json();
			if (!data || !data.layers) throw new Error('bad payload');
			layers = data.layers;
		} catch {
			loadFailed = true;
		}
	});
</script>

<svelte:head>
	<title>Izvori podataka i metodologija — Geo-rizik</title>
</svelte:head>

<section class="page-intro">
	<p class="label">List 02 — Izvori i metodologija</p>
	<h1>Izvori otvorenih podataka i metodologija izračuna</h1>
	<p class="intro-body">
		Aplikacija <strong>Geo-rizik</strong> povezuje službene skupove otvorenih podataka tijela javnog sektora Republike Hrvatske
		(<a href="https://data.gov.hr/" target="_blank" rel="noopener noreferrer">Portal otvorenih podataka RH</a>, NIPP/INSPIRE servisi)
		i europskih znanstvenih servisa (Copernicus EFAS, EFEHR ESHM20). Razine opasnosti računaju se <strong>isključivo deterministički</strong>
		prema javnoj tablici pravila u nastavku — bez proizvoljnih težina. Jezični model (AI) koristi se samo za prevođenje pretrage prirodnim jezikom
		u provjerljive filtere i dodatno pojašnjenje već izračunatog izvještaja, nikada za procjenu razine rizika.
	</p>
</section>

<section class="section-block" aria-labelledby="sources-heading">
	<div class="section-head">
		<h2 id="sources-heading">1. Katalog korištenih skupova podataka</h2>
		<span class="section-count">{Object.keys(layers).length ? String(Object.keys(layers).length).padStart(2, '0') : ''}</span>
	</div>
	{#if loadFailed}
		<div class="load-error" role="alert">Popis izvora trenutno nije dostupan. Pokušajte ponovno.</div>
	{/if}
	<div class="sources-grid">
		{#each Object.entries(layers) as [key, item], idx}
			<article class="source-card">
				<div class="source-header">
					<div class="source-title-row">
						<span class="source-num" aria-hidden="true">{String(idx + 1).padStart(2, '0')}</span>
						<h3>{item.title}</h3>
					</div>
					{#if COVERAGE[item.coverage]}
						<span class="coverage-chip {COVERAGE[item.coverage].cls}">[{COVERAGE[item.coverage].label}]</span>
					{/if}
				</div>
				<dl class="meta-list">
					<div>
						<dt>Izdavač:</dt>
						<dd>{item.publisher}</dd>
					</div>
					<div>
						<dt>Licenca:</dt>
						<dd>
							{item.licence}
							{#if item.licence_note}<br /><span class="licence-note">{item.licence_note}</span>{/if}
						</dd>
					</div>
					{#if item.year && item.year !== 'TBD'}
						<div>
							<dt>Godina:</dt>
							<dd>{item.year}.</dd>
						</div>
					{/if}
					{#if item.resolution && item.resolution !== 'TBD'}
						<div>
							<dt>Rezolucija / oblik:</dt>
							<dd>{item.resolution}</dd>
						</div>
					{/if}
					{#if item.note}
						<div>
							<dt>Napomena:</dt>
							<dd>{item.note}</dd>
						</div>
					{/if}
				</dl>
				<div class="source-links">
					{#if item.url && item.url !== 'TBD'}
						<a href={item.url} target="_blank" rel="noopener noreferrer">Izvor / servis ↗</a>
					{/if}
					{#if item.info_url}
						<a href={item.info_url} target="_blank" rel="noopener noreferrer">Dokumentacija / DOI ↗</a>
					{/if}
					{#if item.download}
						<a href={item.download} target="_blank" rel="noopener noreferrer">ATOM preuzimanje ↗</a>
					{/if}
				</div>
			</article>
		{/each}
	</div>
</section>

<section class="section-block" aria-labelledby="rules-heading">
	<div class="section-head">
		<h2 id="rules-heading">2. Javna tablica pravila za određivanje razina</h2>
	</div>
	<p class="rules-lede">
		Sustav strogo razlikuje stanje <strong>„nema rizika prema karti”</strong> (izvor pokriva točku i pokazuje da opasnosti nema)
		od stanja <strong>„nema podataka”</strong> (izvor ne pokriva područje ili servis nije dostupan).
		Kod odabira „najznačajnijeg rizika” na vrhu izvještaja uspoređuje se utvrđena razina, a kod iste razine redoslijed prioriteta je:
		<em>poplave → potres → klizišta → likvefakcija → vrtače → nepovoljno za gradnju → podzemna voda</em>.
	</p>

	<div class="table-wrap" role="region" aria-label="Tablica pravila">
		<table class="rules-table">
			<thead>
				<tr>
					<th scope="col" style="width: 22%;">Opasnost</th>
					<th scope="col" style="width: 28%;">Izvor podataka</th>
					<th scope="col">Determinističko pravilo mapiranja u razinu</th>
				</tr>
			</thead>
			<tbody>
				<tr>
					<td><strong>Poplave (nacionalno)</strong></td>
					<td>Hrvatske vode (karte opasnosti 2019.)</td>
					<td>
						<strong>Visoko:</strong> velika vjerojatnost (bilo koja dubina) ili srednja vjerojatnost s dubinom &gt; 1,5 m; stalna vodena površina → visoko (posebna napomena).<br />
						<strong>Srednje:</strong> srednja vjerojatnost s dubinom ≤ 1,5 m.<br />
						<strong>Nisko:</strong> samo mala vjerojatnost.<br />
						<strong>Nema prema karti:</strong> točka izvan svih zona unutar obuhvata karte.<br />
						<strong>Nema podataka:</strong> servis Hrvatskih voda trenutačno ne odgovara za barem jedan od scenarija (privremeni ispad).
					</td>
				</tr>
				<tr>
					<td><strong>Poplave (rezerva)</strong></td>
					<td>Copernicus EFAS v3.1.1 (90 m)</td>
					<td>
						Koristi se isključivo kada podatak Hrvatskih voda nije dostupan (privremeni ispad servisa); ispad se tada izričito navodi u izvještaju.<br />
						<strong>Visoko:</strong> dubina &gt; 0 m za povratno razdoblje 10 god. ·
						<strong>Srednje:</strong> dubina &gt; 0 m za povratno razdoblje 100 god. ·
						<strong>Nisko:</strong> dubina &gt; 0 m za povratno razdoblje 500 god. ·
						<strong>Nema prema karti:</strong> stvarna vrijednost 0 m za sve scenarije.<br />
						Bez podatka (nodata) ili izvan rastera → <strong>nema podataka</strong>. Europski model, rezolucija 90 m, okvirna procjena.
					</td>
				</tr>
				<tr>
					<td><strong>Potresna opasnost</strong></td>
					<td>ESHM20 (EFEHR, 475 god., Eurokod 8)</td>
					<td>
						Razredi prema normi <strong>HRN EN 1998-1 (Eurokod 8, točka 3.2.1)</strong> za referentno vršno ubrzanje tla na stijeni (<em>a</em><sub>g</sub>):<br />
						<strong>Vrlo niska seizmičnost:</strong> <em>a</em><sub>g</sub> ≤ 0,04 g ·
						<strong>Niska seizmičnost:</strong> 0,04 g &lt; <em>a</em><sub>g</sub> ≤ 0,08 g ·
						<strong>Iznad praga niske seizmičnosti:</strong> <em>a</em><sub>g</sub> &gt; 0,08 g (uz prikaz točne vrijednosti u <em>g</em>).<br />
						Okvirna procjena; mreža ~10 km; referentna stijena Vs30 = 760 m/s; izvor nije objavljen na data.gov.hr.
					</td>
				</tr>
				<tr>
					<td><strong>Klizišta, likvefakcija, vrtače</strong></td>
					<td>MPGI Geohazardi (Banovina, 2021.)</td>
					<td>
						Preuzima se izvorni razred podložnosti iz poligona studije: <strong>niska</strong> → nisko, <strong>srednja</strong> → srednje, <strong>visoka</strong> → visoko. Točka izvan poligona studije → <strong>nema podataka</strong>; izvan obuhvata (Banovina) → <strong>nema podataka</strong>.
					</td>
				</tr>
				<tr>
					<td><strong>Nepovoljno za gradnju</strong></td>
					<td>MPGI Geohazardi (Banovina, 2021.)</td>
					<td>
						Unutar izdvojenog poligona → <strong>visoko</strong>; unutar obuhvata studije ali izvan poligona → <strong>nema prema karti</strong>; izvan Banovine → <strong>nema podataka</strong>.
					</td>
				</tr>
				<tr>
					<td><strong>Dubina podzemne vode</strong></td>
					<td>MPGI Geohazardi (Banovina, 2021.)</td>
					<td>
						Najbliža točka mjerenja (dubina_do) u radijusu do 1 km: <strong>&lt; 1,5 m</strong> → visoko, <strong>1,5 – 3,0 m</strong> → srednje, <strong>&gt; 3,0 m</strong> → nisko; bez mjerenja unutar 1 km → <strong>nema podataka</strong>.<br />
						Jedno mjerenje (veljača–ožujak 2021.); prikazuju se datum i udaljenost bušotine.
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</section>

<section class="section-block" aria-labelledby="basemap-heading">
	<div class="section-head">
		<h2 id="basemap-heading">3. Podloga karte</h2>
	</div>
	<p class="basemap-text">
		Pozadinska karta je © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">suradnici OpenStreetMapa</a>
		(licenca ODbL), a pločice poslužuje tile.openstreetmap.org prema
		<a href="https://operations.osmfoundation.org/policies/tiles/" target="_blank" rel="noopener noreferrer">pravilima korištenja pločica</a>.
		Preglednik pločice karte dohvaća izravno s OpenStreetMap poslužitelja, pa oni vide vašu IP adresu i prikazano područje karte.
		OpenStreetMap ne koristimo kao izvor podataka o opasnostima, samo kao pozadinu.
	</p>
</section>

<section class="section-block disclaimer-box" aria-labelledby="legal-heading">
	<div class="section-head">
		<h2 id="legal-heading">4. Odricanje od odgovornosti, privatnost i licence</h2>
	</div>
	<ul class="disclaimer-list">
		<li>
			<strong>Informativni karakter:</strong> Podaci prikazani u aplikaciji služe isključivo za informiranje građana i ne predstavljaju službeno uvjerenje, lokacijsku informaciju niti geotehničko ili građevinsko stručno mišljenje. Za sve zahvate u prostoru i kupoprodajne odluke obratite se nadležnim javnopravnim tijelima i ovlaštenim inženjerima.
		</li>
		<li>
			<strong>Privatnost korisnika:</strong> Aplikacija ne sprema unesene kućne adrese niti koristi analitičke servise trećih strana. Upiti prema servisu Hrvatskih voda zaokružuju se na fiksnu mrežu pločica od 0,02° (~2,2 km), čime se u privremenoj memoriji nikada ne pohranjuje točna lokacija korisnika. Pozadinska karta učitava se s poslužitelja OpenStreetMap, a uključivi sloj poplava izravno sa servisa Hrvatskih voda; ti poslužitelji vide koje se pločice karte učitavaju.
		</li>
		<li>
			<strong>Otvoreni kod i licence:</strong> Izvorni kod aplikacije objavljen je pod <strong>MIT licencom</strong>. Skupovi podataka tijela javnog sektora RH (DGU Adrese INSPIRE, MPGI Geohazardi) koriste se pod <strong>Otvorenom dozvolom RH</strong>. Izvedena mreža s EFAS vrijednostima poplava objavljuje se pod licencom <strong>Open Database License (ODbL 1.0)</strong>, a podaci modela ESHM20 pod licencom <strong>CC BY 4.0</strong> (Danciu et al., 2021, DOI: 10.12686/a15).
		</li>
	</ul>
</section>

<style>
	.page-intro {
		padding-bottom: 1.5rem;
		margin-bottom: 1.75rem;
		border-bottom: 1px solid var(--rule);
	}
	.page-intro .label {
		margin: 0 0 0.5rem 0;
		color: var(--accent-ink);
	}
	.page-intro h1 {
		margin: 0 0 0.75rem 0;
		font-size: clamp(1.7rem, 1.2rem + 1.8vw, 2.5rem);
		line-height: 1.1;
		max-width: 24ch;
	}
	.intro-body {
		margin: 0;
		color: var(--ink-2);
		max-width: 78ch;
		font-size: 1.02rem;
		line-height: 1.6;
	}
	.section-block {
		margin-bottom: 2.75rem;
	}
	.section-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		border-bottom: 1px solid var(--rule);
		padding-bottom: 0.35rem;
		margin-bottom: 1.1rem;
	}
	.section-head h2 {
		font-size: 1.25rem;
		margin: 0;
	}
	.section-count {
		font-family: var(--mono);
		font-size: 0.85rem;
		color: var(--muted);
	}
	.sources-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(360px, 100%), 1fr));
		gap: 1.25rem;
	}
	.source-card {
		background: var(--surface);
		border: 1.5px solid var(--ink);
		padding: 1.1rem 1.25rem;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		box-shadow: 4px 4px 0 var(--paper-2);
	}
	.source-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem;
		margin-bottom: 0.85rem;
		border-bottom: 1px solid var(--hair);
		padding-bottom: 0.65rem;
	}
	.source-title-row {
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
		flex: 1;
	}
	.source-num {
		font-family: var(--mono);
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--accent);
		flex: none;
	}
	.source-header h3 {
		margin: 0;
		font-size: 1.05rem;
		line-height: 1.25;
	}
	.coverage-chip {
		font-family: var(--mono);
		font-size: 0.72rem;
		padding: 0.1rem 0.45rem;
		border: 1px solid currentColor;
		white-space: nowrap;
		flex: none;
	}
	.cov-hr {
		color: var(--none-text);
		background: var(--none-bg);
	}
	.cov-ban {
		color: var(--med-text);
		background: var(--med-bg);
	}
	.load-error {
		padding: 1rem 1.25rem;
		margin-bottom: 1rem;
		background: var(--high-bg);
		border: 1.5px solid var(--high-border);
		color: var(--high-text);
	}
	.meta-list {
		margin: 0 0 0.85rem 0;
		font-size: 0.86rem;
		display: grid;
		gap: 0.35rem;
	}
	.meta-list div {
		display: grid;
		grid-template-columns: 110px 1fr;
		gap: 0.4rem;
	}
	.meta-list dt {
		color: var(--muted);
		font-family: var(--sans);
		font-weight: 600;
		font-size: 0.82rem;
	}
	.meta-list dd {
		margin: 0;
		color: var(--ink);
	}
	.licence-note {
		color: var(--muted);
		font-size: 0.78rem;
	}
	.source-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.25rem;
		padding-top: 0.65rem;
		border-top: 1px solid var(--hair);
		font-size: 0.84rem;
		font-weight: 600;
	}
	.rules-lede {
		margin: 0 0 1rem 0;
		max-width: 78ch;
		color: var(--ink-2);
		font-size: 0.95rem;
		line-height: 1.55;
	}
	.table-wrap {
		overflow-x: auto;
		background: var(--surface);
		border: 1.5px solid var(--ink);
	}
	.rules-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.88rem;
		text-align: left;
	}
	.rules-table th,
	.rules-table td {
		padding: 0.85rem 1.1rem;
		border-bottom: 1px solid var(--hair);
		vertical-align: top;
		line-height: 1.5;
	}
	.rules-table th {
		background: var(--paper-2);
		font-family: var(--sans);
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink);
		border-bottom: 1.5px solid var(--ink);
	}
	.rules-table tr:last-child td {
		border-bottom: none;
	}
	.rules-table tr:hover td {
		background: rgba(235, 229, 214, 0.4);
	}
	.basemap-text {
		margin: 0;
		max-width: 78ch;
		color: var(--ink-2);
		font-size: 0.95rem;
		line-height: 1.55;
	}
	.disclaimer-box {
		padding: 1.25rem 1.5rem;
		background: var(--surface);
		border: 1.5px solid var(--ink);
		border-left: 6px solid var(--ink);
	}
	.disclaimer-box .section-head {
		margin-bottom: 0.9rem;
	}
	.disclaimer-list {
		margin: 0;
		padding-left: 1.25rem;
		display: grid;
		gap: 0.75rem;
		font-size: 0.92rem;
		line-height: 1.6;
		color: var(--ink-2);
	}
	.disclaimer-list li::marker {
		color: var(--accent);
	}
</style>
