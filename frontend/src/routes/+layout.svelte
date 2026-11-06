<script>
	import '../app.css';
	import { page } from '$app/state';
	let { children } = $props();

	const NAV = [
		{ href: '/', label: 'Izvještaj po lokaciji' },
		{ href: '/izvori', label: 'Izvori i metodologija' }
	];
</script>

<a class="skip-link" href="#sadrzaj">Preskoči na sadržaj</a>

<header class="site-header no-print">
	<div class="meta-strip">
		<div class="container meta-inner">
			<span>Republika Hrvatska</span>
			<span aria-hidden="true">/</span>
			<span>otvoreni podaci javnog sektora</span>
			<span class="meta-right">WGS84 · EPSG:4326</span>
		</div>
	</div>
	<div class="container header-inner">
		<a href="/" class="brand" aria-label="Geo-rizik, početna">
			<svg class="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
				<path d="M20 3.5c10 0 17.2 7.4 16.4 16.8-.8 9.3-8 16-17.2 15.3C9.8 34.9 3.6 27.6 4.4 18.4 5.2 9.9 11.6 3.5 20 3.5z" />
				<path d="M20.4 9.6c6.3-.2 10.7 4.4 10.1 10.4-.6 6.2-5.3 9.9-11 9.3-5.6-.6-8.9-4.7-8.3-10.4.6-5.3 4.3-9.1 9.2-9.3z" />
				<path d="M20.2 15.2c3.2-.1 5.2 2.2 4.9 5.1-.3 3-2.6 4.6-5.3 4.3-2.6-.3-4.2-2.3-3.9-4.9.3-2.6 2-4.4 4.3-4.5z" />
				<path class="trig" d="M20 17.4l2.6 4.5h-5.2z" />
			</svg>
			<span class="brand-text">
				<span class="brand-name">Geo-rizik</span>
				<span class="brand-sub">Prirodne opasnosti iz otvorenih podataka javnog sektora</span>
			</span>
		</a>
		<nav aria-label="Glavna navigacija" class="nav-links">
			{#each NAV as item}
				<a href={item.href} aria-current={page.url.pathname === item.href ? 'page' : undefined}>
					{item.label}
				</a>
			{/each}
		</nav>
	</div>
</header>

<main id="sadrzaj" class="container main-content">
	{@render children()}
</main>

<footer class="site-footer">
	<div class="container footer-grid">
		<div class="footer-brand">
			<span class="footer-name">Geo-rizik</span>
			<span class="footer-small">Otvoreni kod · MIT licenca</span>
		</div>
		<p class="footer-legal">
			<strong>Pravna napomena (Disclaimer):</strong> Informativni prikaz iz javnih podataka (DGU, MPGI, Hrvatske vode, Copernicus EFAS, EFEHR ESHM20).
			Izvještaj nije stručno mišljenje ni službena potvrda. Unesene adrese se ne spremaju.
		</p>
		<nav class="footer-nav no-print" aria-label="Podnožje">
			<a href="/izvori">Izvori podataka</a>
			<a href="/izvori#rules-heading">Tablica pravila</a>
			<a href="/izvori#legal-heading">Privatnost</a>
		</nav>
	</div>
</footer>

<style>
	.skip-link {
		position: absolute;
		left: 0.75rem;
		top: -3rem;
		z-index: 100;
		padding: 0.5rem 0.9rem;
		background: var(--ink);
		color: var(--paper);
		font-weight: 700;
	}
	.skip-link:focus {
		top: 0.75rem;
		color: var(--paper);
	}
	.site-header {
		background: var(--paper);
		border-bottom: 3px solid var(--rule);
		box-shadow: 0 3px 0 var(--paper), 0 4px 0 var(--rule);
		margin-bottom: 4px;
	}
	.meta-strip {
		background: var(--ink);
		color: #d9d2c2;
		font-family: var(--mono);
		font-size: 0.7rem;
		letter-spacing: 0.04em;
	}
	.meta-inner {
		display: flex;
		gap: 0.6rem;
		padding-top: 0.3rem;
		padding-bottom: 0.3rem;
	}
	.meta-right {
		margin-left: auto;
	}
	@media (max-width: 640px) {
		.meta-right {
			display: none;
		}
	}
	.header-inner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem 2rem;
		padding-top: 0.9rem;
		padding-bottom: 0.9rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		color: var(--ink);
		text-decoration: none;
	}
	.brand:hover {
		color: var(--ink);
	}
	.brand:hover .brand-mark path:not(.trig) {
		stroke: var(--accent);
	}
	.brand-mark {
		width: 2.6rem;
		height: 2.6rem;
		flex: none;
	}
	.brand-mark path {
		fill: none;
		stroke: var(--ink);
		stroke-width: 1.6;
		transition: stroke 0.15s ease;
	}
	.brand-mark .trig {
		fill: var(--accent);
		stroke: none;
	}
	.brand-text {
		display: flex;
		flex-direction: column;
	}
	.brand-name {
		font-family: var(--serif);
		font-size: 1.6rem;
		font-weight: 700;
		line-height: 1;
		letter-spacing: -0.01em;
	}
	.brand-sub {
		margin-top: 0.25rem;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.nav-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1.5rem;
	}
	.nav-links a {
		position: relative;
		padding: 0.35rem 0;
		color: var(--ink);
		font-weight: 600;
		text-decoration: none;
	}
	.nav-links a::after {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 2px;
		background: var(--accent);
		transform: scaleX(0);
		transform-origin: left;
		transition: transform 0.18s ease;
	}
	.nav-links a:hover::after,
	.nav-links a[aria-current='page']::after {
		transform: scaleX(1);
	}
	.nav-links a[aria-current='page'] {
		color: var(--accent-ink);
	}
	.main-content {
		padding-top: 1.75rem;
		padding-bottom: 3rem;
	}
	.site-footer {
		border-top: 1px solid var(--rule);
		background: var(--paper-2);
		padding: 1.25rem 0 1.5rem;
		font-size: 0.85rem;
		color: var(--ink-2);
	}
	.footer-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.9rem;
	}
	@media (min-width: 860px) {
		.footer-grid {
			grid-template-columns: 12rem 1fr auto;
			gap: 2rem;
			align-items: start;
		}
	}
	.footer-brand {
		display: flex;
		flex-direction: column;
	}
	.footer-name {
		font-family: var(--serif);
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--ink);
	}
	.footer-small {
		font-family: var(--mono);
		font-size: 0.72rem;
		color: var(--muted);
	}
	.footer-legal {
		margin: 0;
		max-width: 68ch;
	}
	.footer-nav {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.footer-nav a {
		color: var(--ink);
	}
</style>
