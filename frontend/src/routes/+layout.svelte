<script>
	import '../app.css';
	import '$lib/print.css';
	let { children } = $props();
</script>

<header class="site-header no-print">
	<div class="container header-inner">
		<a href="/" class="brand">
			<span class="brand-badge" aria-hidden="true">HR</span>
			<div>
				<strong>Geo-rizik</strong>
				<span class="brand-sub">Prirodne opasnosti iz otvorenih podataka javnog sektora</span>
			</div>
		</a>
		<nav aria-label="Glavna navigacija" class="nav-links">
			<a href="/">Izvještaj po lokaciji</a>
			<a href="/izvori">Izvori podataka</a>
		</nav>
	</div>
</header>

<main class="container main-content">
	{@render children()}
</main>

<footer class="site-footer">
	<div class="container">
		<p>
			<strong>Pravna napomena (Disclaimer):</strong> Informativni prikaz iz javnih podataka (DGU, MPGI, Hrvatske vode, Copernicus EFAS, EFEHR ESHM20).
			Izvještaj nije stručno mišljenje ni službena potvrda. Unesene adrese se ne spremaju.
		</p>
	</div>
</footer>

<style>
	.site-header {
		background: #0f172a;
		color: #f8fafc;
		border-bottom: 3px solid #2563eb;
		padding: 0.75rem 0;
	}
	.header-inner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		color: #ffffff;
		text-decoration: none;
	}
	.brand:hover {
		color: #dbeafe;
	}
	.brand-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border-radius: 0.5rem;
		background: #2563eb;
		font-weight: 800;
		font-size: 0.9rem;
	}
	.brand-sub {
		display: block;
		font-size: 0.8rem;
		color: #cbd5e1;
	}
	.nav-links {
		display: flex;
		gap: 1.25rem;
	}
	.nav-links a {
		color: #f8fafc;
		font-weight: 600;
		text-decoration: none;
		padding: 0.35rem 0.65rem;
		border-radius: 0.375rem;
	}
	.nav-links a:hover {
		background: #1e293b;
		color: #93c5fd;
	}
	.main-content {
		padding-top: 1.25rem;
		padding-bottom: 2.5rem;
	}
	.site-footer {
		border-top: 1px solid var(--border);
		background: #ffffff;
		padding: 1rem 0;
		font-size: 0.85rem;
		color: var(--muted);
	}
</style>
