<script>
	import { onMount } from 'svelte';

	const FALLBACK_LAYERS = {
		flood_hv: {
			title: 'Karte opasnosti od poplava 2019.',
			publisher: 'Hrvatske vode',
			licence: 'Bez ograničenja pristupa (WMS AccessConstraints NONE)',
			url: 'https://servisi.voda.hr/wms',
			info_url: 'https://www.voda.hr/hr/karte-opasnosti-od-poplava-karte-rizika-od-poplava-2019',
			year: 2019,
			resolution: 'Render WMS-a (GetMap), dubina vode u 5 razreda',
			coverage: 'croatia'
		},
		flood_efas: {
			title: 'EFAS river flood hazard maps v3.1.1',
			publisher: 'Europska komisija, JRC (Copernicus EMS)',
			licence: 'ODbL 1.0',
			url: 'https://jeodpp.jrc.ec.europa.eu/ftp/public/JRC-OpenData/CEMS-EFAS/flood_hazard/',
			info_url: 'https://doi.org/10.2905/1D128B6C-A4EE-4858-9E34-6210707F3C81',
			year: 2024,
			resolution: '90 m (GeoTIFF)',
			coverage: 'croatia',
			note: 'Koristi se samo gdje karta Hrvatskih voda nema podatka'
		},
		seismic: {
			title: 'Europski model potresne opasnosti ESHM20 (PGA, 475 god.)',
			publisher: 'EFEHR / ETH Zürich (Danciu et al.)',
			licence: 'CC BY 4.0',
			url: 'https://efehr-services.ethz.ch/hazard/api/v1',
			info_url: 'https://doi.org/10.12686/a15',
			year: 2021,
			resolution: 'Mreža ~0,1° (~10 km), referentna stijena Vs30 = 760 m/s',
			coverage: 'croatia'
		},
		landslide: {
			title: 'Podložnost klizištima',
			publisher: 'Ministarstvo prostornoga uređenja, graditeljstva i državne imovine (MPGI)',
			licence: 'Otvorena dozvola RH',
			url: 'https://data.gov.hr/ckan/hr/dataset/geohazardi',
			year: 2021,
			resolution: 'Poligoni studije (preliminarna identifikacija)',
			coverage: 'banovina'
		},
		liquefaction: {
			title: 'Podložnost likvefakciji',
			publisher: 'Ministarstvo prostornoga uređenja, graditeljstva i državne imovine (MPGI)',
			licence: 'Otvorena dozvola RH',
			url: 'https://data.gov.hr/ckan/hr/dataset/geohazardi',
			year: 2021,
			resolution: 'Poligoni studije (preliminarna identifikacija)',
			coverage: 'banovina'
		},
		sinkhole: {
			title: 'Podložnost vrtačama',
			publisher: 'Ministarstvo prostornoga uređenja, graditeljstva i državne imovine (MPGI)',
			licence: 'Otvorena dozvola RH',
			url: 'https://data.gov.hr/ckan/hr/dataset/geohazardi',
			year: 2021,
			resolution: 'Poligoni studije (preliminarna identifikacija)',
			coverage: 'banovina'
		},
		unfavourable: {
			title: 'Područja nepovoljna za gradnju',
			publisher: 'Ministarstvo prostornoga uređenja, graditeljstva i državne imovine (MPGI)',
			licence: 'Otvorena dozvola RH',
			url: 'https://data.gov.hr/ckan/hr/dataset/geohazardi',
			year: 2021,
			resolution: 'Poligoni studije',
			coverage: 'banovina'
		},
		groundwater: {
			title: 'Dubina podzemne vode',
			publisher: 'Ministarstvo prostornoga uređenja, graditeljstva i državne imovine (MPGI)',
			licence: 'Otvorena dozvola RH',
			url: 'https://data.gov.hr/ckan/hr/dataset/geohazardi',
			year: 2021,
			resolution: 'Točkasta mjerenja (611 točaka, atribut dubina_do u m, radijus 1 km)',
			coverage: 'banovina'
		},
		addresses: {
			title: 'Adrese INSPIRE',
			publisher: 'Državna geodetska uprava (DGU)',
			licence: 'Otvorena dozvola RH',
			url: 'https://data.gov.hr/ckan/hr/dataset/adrese-inspire',
			info_url: 'https://geoportal.dgu.hr/services/atom/INSPIRE_Addresses_(AD).zip',
			year: 2026,
			resolution: 'Točke kućnih brojeva (~1,68 mil. adresa u RH)',
			coverage: 'croatia'
		}
	};

	let layers = $state(FALLBACK_LAYERS);

	onMount(async () => {
		try {
			const res = await fetch('/api/sources');
			if (res.ok) {
				const data = await res.json();
				if (data && data.layers) {
					layers = { ...FALLBACK_LAYERS, ...data.layers };
				}
			}
		} catch {
			// Keep fallback catalogue
		}
	});
</script>

<svelte:head>
	<title>Izvori podataka i metodologija — Geo-rizik</title>
</svelte:head>

<section class="page-intro">
	<h1>Izvori otvorenih podataka i metodologija izračuna</h1>
	<p>
		Aplikacija <strong>Geo-rizik</strong> povezuje službene skupove otvorenih podataka tijela javnog sektora Republike Hrvatske
		(<a href="https://data.gov.hr/" target="_blank" rel="noopener noreferrer">Portal otvorenih podataka RH</a>, NIPP/INSPIRE servisi)
		i europskih znanstvenih servisa (Copernicus EFAS, EFEHR ESHM20). Razine opasnosti računaju se <strong>isključivo deterministički</strong>
		prema javnoj tablici pravila u nastavku — bez proizvoljnih težina i bez procjene umjetnom inteligencijom.
	</p>
</section>

<section class="section-block" aria-labelledby="sources-heading">
	<h2 id="sources-heading">1. Katalog skupova podataka (`layers.yaml`)</h2>
	<div class="sources-grid">
		{#each Object.entries(layers) as [key, item]}
			<article class="source-card">
				<div class="source-header">
					<h3>{item.title}</h3>
					<span class="coverage-chip {item.coverage === 'croatia' ? 'cov-hr' : 'cov-ban'}">
						{item.coverage === 'croatia' ? 'Cijela Hrvatska' : 'Banovina (SMŽ)'}
					</span>
				</div>
				<dl class="meta-list">
					<div>
						<dt>Izdavač:</dt>
						<dd>{item.publisher}</dd>
					</div>
					<div>
						<dt>Licenca:</dt>
						<dd>{item.licence}</dd>
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
	<h2 id="rules-heading">2. Javna tablica pravila za određivanje razina</h2>
	<p>
		Sustav strogo razlikuje stanje <strong>„nema rizika prema karti”</strong> (izvor pokriva točku i pokazuje da opasnosti nema)
		od stanja <strong>„nema podataka”</strong> (izvor ne pokriva područje ili servis nije dostupan).
		Kod odabira „najznačajnijeg rizika” na vrhu izvještaja uspoređuje se utvrđena razina, a kod iste razine redoslijed prioriteta je:
		<em>poplave → potres → klizišta → likvefakcija → vrtače → nepovoljno za gradnju → podzemna voda</em>.
	</p>

	<div class="table-wrap">
		<table class="rules-table">
			<thead>
				<tr>
					<th>Opasnost</th>
					<th>Izvor podataka</th>
					<th>Determinističko pravilo mapiranja u razinu</th>
				</tr>
			</thead>
			<tbody>
				<tr>
					<td><strong>Poplave (nacionalno)</strong></td>
					<td>Hrvatske vode (karte opasnosti 2019.)</td>
					<td>
						<strong>Visoko:</strong> stalna vodena površina, ili velika vjerojatnost (RP 25 god., bilo koja dubina), ili srednja vjerojatnost (RP 100 god.) s dubinom &gt; 1,5 m.<br />
						<strong>Srednje:</strong> srednja vjerojatnost (RP 100 god.) s dubinom ≤ 1,5 m.<br />
						<strong>Nisko:</strong> samo mala vjerojatnost (ekstremni scenarij).<br />
						<strong>Nema prema karti:</strong> točka izvan poplavnih zona za sva tri scenarija.
					</td>
				</tr>
				<tr>
					<td><strong>Poplave (rezerva)</strong></td>
					<td>Copernicus EFAS v3.1.1 (90 m)</td>
					<td>
						Koristi se isključivo kada servis Hrvatskih voda nema podatka za točku.<br />
						<strong>Visoko:</strong> dubina &gt; 0 m za RP 10 god. ·
						<strong>Srednje:</strong> dubina &gt; 0 m za RP 100 god. ·
						<strong>Nisko:</strong> dubina &gt; 0 m za RP 500 god. ·
						<strong>Nema prema karti:</strong> 0 m za sve scenarije.
					</td>
				</tr>
				<tr>
					<td><strong>Potresna opasnost</strong></td>
					<td>ESHM20 (EFEHR, 475 god., Eurokod 8)</td>
					<td>
						Razredi prema normi <strong>HRN EN 1998-1 (Eurokod 8, točka 3.2.1)</strong> za referentno vršno ubrzanje tla na stijeni (<em>a</em><sub>g</sub>):<br />
						<strong>Vrlo niska seizmičnost:</strong> <em>a</em><sub>g</sub> ≤ 0,04 g ·
						<strong>Niska seizmičnost:</strong> 0,04 g &lt; <em>a</em><sub>g</sub> ≤ 0,08 g ·
						<strong>Iznad praga niske seizmičnosti:</strong> <em>a</em><sub>g</sub> &gt; 0,08 g (uz prikaz točne vrijednosti u <em>g</em>).
					</td>
				</tr>
				<tr>
					<td><strong>Klizišta, likvefakcija, vrtače</strong></td>
					<td>MPGI Geohazardi (Banovina, 2021.)</td>
					<td>
						Preuzima se izvorni razred podložnosti iz poligona studije: <strong>niska</strong> → nisko, <strong>srednja</strong> → srednje, <strong>visoka</strong> → visoko. Izvan obuhvata studije → <strong>nema podataka</strong>.
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
						Najbliža točka mjerenja (`dubina_do`) u radijusu do 1 km: <strong>&lt; 1,5 m</strong> → visoko, <strong>1,5 – 3,0 m</strong> → srednje, <strong>&gt; 3,0 m</strong> → nisko; bez mjerenja unutar 1 km → <strong>nema podataka</strong>.
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</section>

<section class="section-block disclaimer-box" aria-labelledby="legal-heading">
	<h2 id="legal-heading">3. Odricanje od odgovornosti, privatnost i licence</h2>
	<ul>
		<li>
			<strong>Informativni karakter:</strong> Podaci prikazani u aplikaciji služe isključivo za informiranje građana i ne predstavljaju službeno uvjerenje, lokacijsku informaciju niti geotehničko ili građevinsko stručno mišljenje. Za sve zahvate u prostoru i kupoprodajne odluke obratite se nadležnim javnopravnim tijelima i ovlaštenim inženjerima.
		</li>
		<li>
			<strong>Privatnost korisnika:</strong> Aplikacija ne sprema unesene kućne adrese niti koristi analitičke servise trećih strana. Upiti prema servisu Hrvatskih voda zaokružuju se na fiksnu mrežu pločica od 0,01° (~1,1 km), čime se u privremenoj memoriji nikada ne pohranjuje točna lokacija korisnika.
		</li>
		<li>
			<strong>Otvoreni kod i licence:</strong> Izvorni kod aplikacije objavljen je pod <strong>MIT licencom</strong>. Izvedena mreža s EFAS vrijednostima poplava objavljuje se pod licencom <strong>Open Database License (ODbL 1.0)</strong>, a podaci modela ESHM20 pod licencom <strong>CC BY 4.0</strong> (Danciu et al., 2021, DOI: 10.12686/a15).
		</li>
	</ul>
</section>

<style>
	.page-intro {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 1.35rem 1.5rem;
		margin-bottom: 1.5rem;
	}
	.page-intro h1 {
		margin: 0 0 0.5rem 0;
		font-size: 1.5rem;
	}
	.page-intro p {
		margin: 0;
		color: var(--muted);
	}
	.section-block {
		margin-bottom: 2rem;
	}
	.section-block h2 {
		font-size: 1.25rem;
		margin: 0 0 0.85rem 0;
	}
	.sources-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
		gap: 1rem;
	}
	.source-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.65rem;
		padding: 1rem 1.15rem;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
	}
	.source-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
		margin-bottom: 0.65rem;
	}
	.source-header h3 {
		margin: 0;
		font-size: 1rem;
	}
	.coverage-chip {
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		white-space: nowrap;
	}
	.cov-hr {
		background: #dbeafe;
		color: #1e3a8a;
	}
	.cov-ban {
		background: #fef3c7;
		color: #78350f;
	}
	.meta-list {
		margin: 0 0 0.75rem 0;
		font-size: 0.88rem;
		display: grid;
		gap: 0.3rem;
	}
	.meta-list div {
		display: grid;
		grid-template-columns: 120px 1fr;
		gap: 0.4rem;
	}
	.meta-list dt {
		color: var(--muted);
		font-weight: 600;
	}
	.meta-list dd {
		margin: 0;
	}
	.source-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		padding-top: 0.55rem;
		border-top: 1px solid #e2e8f0;
		font-size: 0.85rem;
		font-weight: 600;
	}
	.table-wrap {
		overflow-x: auto;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.65rem;
	}
	.rules-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	.rules-table th,
	.rules-table td {
		padding: 0.75rem 1rem;
		text-align: left;
		border-bottom: 1px solid #e2e8f0;
		vertical-align: top;
	}
	.rules-table th {
		background: #f1f5f9;
		font-weight: 700;
	}
	.disclaimer-box {
		background: var(--surface);
		border: 1px solid var(--border);
		border-left: 6px solid #2563eb;
		border-radius: 0.65rem;
		padding: 1.15rem 1.35rem;
	}
	.disclaimer-box ul {
		margin: 0;
		padding-left: 1.25rem;
		display: grid;
		gap: 0.6rem;
		font-size: 0.92rem;
	}
</style>
