// No framework, no remote dependencies. Product data enters the DOM only after fetch.
const $ = (selector) => document.querySelector(selector);
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const artificialDelay = () => wait(300 + Math.floor(Math.random() * 1701));
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));
const numberPL = new Intl.NumberFormat('pl-PL', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const price = (p) => `${numberPL.format(p.cena)} ${p.waluta === 'PLN' ? 'zł' : '€'}`;
let schema;

async function fetchJSON(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(url, {signal: controller.signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function facts(p, fields) {
  return `<dl class="product-facts">${Object.entries(fields).map(([key, label]) =>
    `<div><dt>${escape(label)}</dt><dd data-pole="${key}">${escape(p[key])}</dd></div>`
  ).join('')}</dl>`;
}

function basicFacts() {
  return Object.fromEntries(Object.entries(schema.lista).filter(([key]) =>
    !['id', 'nazwa', 'cena', 'waluta', 'kategoria', 'url'].includes(key)));
}

function card(p) {
  return `<article class="produkt product-card" data-id="${escape(p.id)}">
    <div class="product-visual" aria-hidden="true"><span>${escape(p.kategoria)}</span><strong>↗</strong><small>${escape(p.id)}</small></div>
    <div class="product-body"><span class="category" data-pole="kategoria">${escape(p.kategoria)}</span>
    <h3 data-pole="nazwa">${escape(p.nazwa)}</h3><p class="price" data-pole="cena" data-waluta="${escape(p.waluta)}">${price(p)}</p>
    ${facts(p, basicFacts())}<a class="product-link" data-pole="url" href="${escape(p.url)}">Zobacz produkt <span aria-hidden="true">↗</span></a></div></article>`;
}

function row(p) {
  return `<tr class="produkt" data-id="${escape(p.id)}">${Object.keys(schema.lista).filter((key) => !['id', 'waluta'].includes(key)).map((key) => {
    const content = key === 'cena' ? price(p) : key === 'url' ? `<a href="${escape(p.url)}">Zobacz ↗</a>` : escape(p[key]);
    const currency = key === 'cena' ? ` data-waluta="${escape(p.waluta)}"` : '';
    return `<td data-pole="${key}"${currency}>${content}</td>`;
  }).join('')}</tr>`;
}

async function initCatalogue() {
  const section = $('#katalog');
  const button = $('#wczytaj-wiecej');
  const error = $('#blad');
  const loading = $('#stan-ladowania');
  const state = {records: [], manifest: null, next: 0, busy: false};
  $('#filtry').addEventListener('submit', (event) => event.preventDefault());

  function render() {
    const term = $('#szukaj').value.trim().toLocaleLowerCase('pl-PL');
    const category = $('#kategoria').value;
    const sort = $('#sortowanie').value;
    const visible = state.records.filter((p) =>
      (!category || p.kategoria === category) &&
      `${p.nazwa} ${p.producent ?? ''} ${p.id}`.toLocaleLowerCase('pl-PL').includes(term));
    const pricePLN = (p) => p.cena * (p.waluta === 'EUR' ? 4.35 : 1);
    if (sort === 'nazwa') visible.sort((a, b) => a.nazwa.localeCompare(b.nazwa, 'pl'));
    if (sort === 'ocena') visible.sort((a, b) => b.ocena - a.ocena);
    if (sort === 'cena-rosnaco') visible.sort((a, b) => pricePLN(a) - pricePLN(b));
    if (sort === 'cena-malejaco') visible.sort((a, b) => pricePLN(b) - pricePLN(a));
    const middle = Math.ceil(visible.length / 2);
    $('#karty-produktow').innerHTML = visible.slice(0, middle).map(card).join('');
    $('#wiersze-produktow').innerHTML = visible.slice(middle).map(row).join('');
    $('#brak-wynikow').hidden = visible.length > 0;
    const total = state.manifest.liczba_rekordow;
    $('#licznik').textContent = `Wczytano ${state.records.length} z ${total} pozycji · Widocznych: ${visible.length}`;
    $('#postep').style.width = `${state.records.length / total * 100}%`;
    const done = state.next === state.manifest.porcje.length;
    button.hidden = done;
    $('#koniec').hidden = !done;
  }

  async function loadMore() {
    if (state.busy || (state.manifest && state.next === state.manifest.porcje.length)) return;
    state.busy = true;
    button.disabled = true;
    button.textContent = 'Wczytywanie…';
    loading.hidden = false;
    error.hidden = true;
    $('#wyniki').setAttribute('aria-busy', 'true');
    try {
      if (!state.manifest) {
        [schema, state.manifest] = await Promise.all([
          fetchJSON('/data/schema.json'), fetchJSON(`/data/strona-${section.dataset.strona}.json`)
        ]);
        const categories = ['Plecaki', 'Namioty', 'Śpiwory', 'Oświetlenie', 'Nawigacja', 'Kuchnia', 'Odzież', 'Akcesoria'];
        $('#kategoria').innerHTML = '<option value="">Wszystkie kategorie</option>' +
          categories.map((name) => `<option value="${escape(name)}">${escape(name)}</option>`).join('');
      }
      // Every portion, including the first, waits 300–2000 ms before being requested.
      await artificialDelay();
      const portion = await fetchJSON(state.manifest.porcje[state.next]);
      state.records.push(...portion);
      state.next += 1;
      render();
    } catch (failure) {
      error.textContent = 'Nie udało się wczytać produktów. Sprawdź połączenie i spróbuj ponownie przyciskiem poniżej.';
      error.hidden = false;
      console.error('Wczytywanie katalogu:', failure);
    } finally {
      state.busy = false;
      button.disabled = false;
      button.textContent = error.hidden ? 'Wczytaj więcej ↓' : 'Spróbuj ponownie ↻';
      loading.hidden = true;
      $('#wyniki').setAttribute('aria-busy', 'false');
    }
  }

  for (const selector of ['#szukaj', '#kategoria', '#sortowanie']) {
    $(selector).addEventListener('input', () => { if (state.manifest) render(); });
  }
  $('#filtry').addEventListener('reset', () => setTimeout(() => { if (state.manifest) render(); }, 0));
  button.addEventListener('click', loadMore);
  await loadMore();
}

async function initDetail() {
  const container = $('#produkt-szczegoly');
  const retry = $('#ponow-szczegoly');
  let busy = false;
  async function load() {
    if (busy) return;
    busy = true;
    retry.hidden = true;
    $('#blad').hidden = true;
    $('#stan-ladowania').hidden = false;
    container.setAttribute('aria-busy', 'true');
    try {
      await artificialDelay();
      const [fields, p] = await Promise.all([
        fetchJSON('/data/schema.json'), fetchJSON(`/data/produkty/${$('#szczegoly').dataset.id}.json`)
      ]);
      schema = fields;
      document.title = `${p.nazwa} · Północ`;
      container.innerHTML = `<article class="produkt product-detail" data-id="${escape(p.id)}">
        <div class="detail-lead"><div><p class="eyebrow" data-pole="kategoria">${escape(p.kategoria)}</p>
        <h1 data-pole="nazwa">${escape(p.nazwa)}</h1><p class="price" data-pole="cena" data-waluta="${escape(p.waluta)}">${price(p)}</p>
        <a class="permalink" data-pole="url" href="${escape(p.url)}">Stały link do produktu ↗</a></div>
        <div class="detail-visual" aria-hidden="true"><span>↗</span><small>${escape(p.id)}</small></div></div>
        <div class="detail-columns"><section><h2>Informacje o produkcie</h2>${facts(p, basicFacts())}</section>
        <section><h2>Specyfikacja techniczna</h2>${facts(p, schema.szczegoly)}</section></div>
        <details class="extra-details" id="dodatkowe-informacje"><summary>Materiały, zasilanie i dostawa</summary><div id="dodatkowe-pola"></div></details></article>`;
      const details = $('#dodatkowe-informacje');
      details.addEventListener('toggle', () => {
        if (details.open && !details.dataset.loaded) {
          // These four attributes do not exist in the DOM before interaction.
          $('#dodatkowe-pola').innerHTML = facts(p, schema.interakcja);
          details.dataset.loaded = 'true';
        }
      });
    } catch (failure) {
      $('#blad').textContent = 'Nie udało się wczytać szczegółów produktu. Sprawdź połączenie i spróbuj ponownie.';
      $('#blad').hidden = false;
      retry.hidden = false;
      console.error('Szczegóły produktu:', failure);
    } finally {
      busy = false;
      $('#stan-ladowania').hidden = true;
      container.setAttribute('aria-busy', 'false');
    }
  }
  retry.addEventListener('click', load);
  await load();
}

if ($('#katalog')) initCatalogue();
if ($('#szczegoly')) initDetail();
