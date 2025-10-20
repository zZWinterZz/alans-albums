// Theme switcher
(function(window, document){
	const THEME_KEY = 'site_theme_scheme';

	// If the template provides a data-schemes attribute (comma-separated)
	function getSchemesFromDOM(){
		const el = document.getElementById('scheme-select');
		if(!el) return null;
		const data = el.getAttribute('data-schemes');
		if(!data) return null;
		return data.split(',').map(s=>s.trim()).filter(Boolean);
	}

	function defaultSchemes(){
		return ['Scheme-1','Scheme-2'];
	}

	function setSchemeLink(name){
		const link = document.getElementById('scheme-stylesheet');
		if(!link) return;
		// set a cache-busting query param to help during development
		// normalize incoming name (allow both Scheme1 and Scheme-1)
		const normalized = name.replace(/Scheme\s*-?\s*(\d+)/i, 'Scheme-$1');
		const href = `/static/css/schemes/${normalized}.css`;
		link.setAttribute('href', href);
	}

	function populateSelector(schemes, current){
		const sel = document.getElementById('scheme-select');
		if(!sel) return;
		sel.innerHTML = '';
		schemes.forEach(s=>{
			const opt = document.createElement('option');
			opt.value = s; opt.textContent = s;
			sel.appendChild(opt);
		});
		if(current) sel.value = current;
		sel.addEventListener('change', ()=>{
			const val = sel.value;
			setSchemeLink(val);
			localStorage.setItem(THEME_KEY, val);
		});
	}

	function init(){
		const domSchemes = getSchemesFromDOM();
		const schemes = domSchemes || defaultSchemes();
		const saved = localStorage.getItem(THEME_KEY) || schemes[0];
		populateSelector(schemes, saved);
		setSchemeLink(saved);
		// expose for console/debug
		window.ThemeSwitcher = {
			schemes,
			current: ()=> localStorage.getItem(THEME_KEY) || schemes[0],
			set: (name)=>{ if(schemes.includes(name)){ setSchemeLink(name); localStorage.setItem(THEME_KEY,name);} }
		};
	}

	document.addEventListener('DOMContentLoaded', init);
})(window, document);

