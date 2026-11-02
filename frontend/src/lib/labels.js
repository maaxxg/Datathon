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
	{ name: 'Petrinja (Matije Gupca 12)', lat: 45.4410, lon: 16.2718, address: 'Ulica Matije Gupca 12, 44250 Petrinja' },
	{ name: 'Petrinja — centar', lat: 45.4375, lon: 16.2739, address: 'Petrinja (središte)' },
	{ name: 'Sisak (Rimska 19)', lat: 45.4896, lon: 16.3713, address: 'Rimska ulica 19, 44000 Sisak' },
	{ name: 'Karlovac (uz Kupu)', lat: 45.4870, lon: 15.5480, address: 'Karlovac' },
	{ name: 'Gunja', lat: 44.8810, lon: 18.8450, address: 'Gunja' },
	{ name: 'Zagreb (uz Savu)', lat: 45.7930, lon: 15.9600, address: 'Zagreb — priobalje Save' },
	{ name: 'Split', lat: 43.5081, lon: 16.4402, address: 'Split' }
];
