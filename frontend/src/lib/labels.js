export const HAZARD_META = {
	flood: {
		title: 'Poplave',
		subtitle: 'Riječne i površinske poplave po scenarijima vjerojatnosti',
		icon: '🌊'
	},
	seismic: {
		title: 'Potresna opasnost',
		subtitle: 'Referentno vršno ubrzanje tla (povratno razdoblje 475 godina, Eurokod 8)',
		icon: '🫨'
	},
	landslide: {
		title: 'Podložnost klizištima',
		subtitle: 'Stabilnost padina i mogućnost klizanja tla (studija Banovina)',
		icon: '⛰️'
	},
	liquefaction: {
		title: 'Podložnost likvefakciji',
		subtitle: 'Gubitak nosivosti zasićenog pjeskovitog tla pri potresu (Banovina)',
		icon: '💧'
	},
	sinkhole: {
		title: 'Podložnost vrtačama',
		subtitle: 'Mogućnost urušnih ponikvi u krškom i pokrivenom krškom terenu (Banovina)',
		icon: '🕳️'
	},
	unfavourable: {
		title: 'Nepovoljno za gradnju',
		subtitle: 'Izdvojene zone nepovoljnih geotehničkih uvjeta (Banovina)',
		icon: '⚠️'
	},
	groundwater: {
		title: 'Dubina podzemne vode',
		subtitle: 'Najbliže točkasto mjerenje razine podzemne vode (Banovina)',
		icon: '🚰'
	}
};

export const LEVEL_META = {
	visoko: {
		label: 'VISOKA OPASNOST',
		icon: '▲',
		tone: 'high'
	},
	iznad_praga_niske_seizmicnosti: {
		label: 'IZNAD PRAGA NISKE SEIZMIČNOSTI (> 0,08 g)',
		icon: '◆',
		tone: 'med'
	},
	srednje: {
		label: 'SREDNJA OPASNOST',
		icon: '◆',
		tone: 'med'
	},
	nisko: {
		label: 'NISKA OPASNOST',
		icon: '●',
		tone: 'low'
	},
	niska_seizmicnost: {
		label: 'NISKA SEIZMIČNOST (0,04 – 0,08 g)',
		icon: '●',
		tone: 'low'
	},
	vrlo_niska_seizmicnost: {
		label: 'VRLO NISKA SEIZMIČNOST (≤ 0,04 g)',
		icon: '○',
		tone: 'none'
	},
	nema_prema_karti: {
		label: 'NEMA RIZIKA PREMA KARTI',
		icon: '✓',
		tone: 'none'
	},
	nema_podataka: {
		label: 'NEMA PODATAKA ZA LOKACIJU',
		icon: '—',
		tone: 'nodata'
	}
};

export const FLOOD_DEPTH_TEXT = {
	outside: 'izvan poplavne zone',
	none: 'izvan poplavne zone',
	d_lt_0_5: 'dubina < 0,5 m',
	d_0_5_1_5: 'dubina 0,5 – 1,5 m',
	d_1_5_2_5: 'dubina 1,5 – 2,5 m',
	d_gt_2_5: 'dubina > 2,5 m',
	permanent_water: 'stalna vodena površina'
};

export const PRESET_LOCATIONS = [
	{ name: 'Petrinja', lat: 45.4375, lon: 16.2739 },
	{ name: 'Sisak', lat: 45.484, lon: 16.374 },
	{ name: 'Karlovac', lat: 45.487, lon: 15.548 },
	{ name: 'Gunja', lat: 44.881, lon: 18.845 },
	{ name: 'Zagreb uz Savu', lat: 45.793, lon: 15.96 },
	{ name: 'Split', lat: 43.5081, lon: 16.4402 }
];

// Decimal comma for every number shown to the user.
export function fmt(n, digits) {
	if (n === null || n === undefined || Number.isNaN(Number(n))) return null;
	const v = digits === undefined ? String(n) : Number(n).toFixed(digits);
	return v.replace('.', ',');
}

// Map legend texts (Croatian). Colours here match the map paint; swatches are decorative, text carries the meaning.
export const MAP_LEGEND = {
	hv: {
		rows: [
			{ colour: '#BEE8FF', text: '< 0,5 m' },
			{ colour: '#73DFFF', text: '0,5–1,5 m' },
			{ colour: '#73B2FF', text: '1,5–2,5 m' },
			{ colour: '#7A8EF5', text: '> 2,5 m' },
			{ colour: '#004DA8', text: 'Stalne vodene površine' }
		],
		note: 'Dubina vode po scenariju vjerojatnosti. Sloj je vidljiv samo pri zumu 12–14.'
	},
	geo: {
		susceptibility: [
			{ colour: '#facc15', text: 'Niska podložnost' },
			{ colour: '#f97316', text: 'Srednja podložnost' },
			{ colour: '#b91c1c', text: 'Visoka podložnost' }
		],
		unfavourable: { colour: '#4c1d95', text: 'Nepovoljno za gradnju' },
		coverage: { colour: '#0f766e', text: 'Obuhvat studije (samo Banovina)' },
		coverageNote: 'Obuhvat geohazarda: samo Banovina (Sisačko-moslavačka)',
		note: 'Pojednostavljeni prikaz: rubovi većinom unutar ~20 m (klizišta ~40 m, ponegdje i više); manji dijelovi izostavljeni (klizišta do ~2 ha, ostali slojevi do ~0,4 ha). Razred za odabranu točku daje izvještaj iz izvornih podataka.'
	},
	efas: {
		rows: [
			{ colour: '#D8B4FE', text: '< 0,5 m' },
			{ colour: '#A855F7', text: '0,5–1,5 m' },
			{ colour: '#7E22CE', text: '1,5–2,5 m' },
			{ colour: '#3B0764', text: '> 2,5 m' }
		],
		note: 'Europski model, 90 m, prikaz ~180 m (najveća dubina u bloku); u izvještaju se koristi samo kad podatak Hrvatskih voda nije dostupan. Prikazuje samo poplave uz veće rijeke. Prozirno znači da model ne prikazuje poplavu ili da za to područje nema podatka. Izvedeno iz EFAS v3.1.1, ODbL 1.0.'
	}
};

export const MAP_UNAVAILABLE = 'Sloj trenutačno nije dostupan.';
