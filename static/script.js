const API_BASE = '';  

const classifyBtn = document.getElementById('classifyBtn');
const statsBtn = document.getElementById('statsBtn');
const referenceBtn = document.getElementById('referenceBtn');
const jobInput = document.getElementById('jobInput');
const resultsDiv = document.getElementById('results');

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    if (!response.ok) {
        throw new Error(`Ошибка ${response.status}: ${response.statusText}`);
    }
    return response.json();
}

function renderClassifyResult(data) {
    if (!data.results || data.results.length === 0) {
        resultsDiv.innerHTML = '<p>Нет результатов.</p>';
        return;
    }

    let html = `
        <h3>Результаты классификации</h3>
        <table>
            <thead>
                <tr>
                    <th>Исходная</th>
                    <th>Нормализованная</th>
                    <th>Эталон</th>
                    <th>Уверенность</th>
                    <th>Статус</th>
                </tr>
            </thead>
            <tbody>
    `;

    data.results.forEach(item => {
        const statusClass = item.success ? 'status-success' : 'status-fail';
        const statusText = item.success ? '✅ Найдено' : (item.message || '❌ Не найдено');
        const refTitle = item.reference_title || '—';
        const normalized = item.normalized || '—';
        const confidence = item.confidence ? (item.confidence * 100).toFixed(1) + '%' : '—';

        html += `
            <tr>
                <td>${escapeHtml(item.original)}</td>
                <td>${escapeHtml(normalized)}</td>
                <td>${escapeHtml(refTitle)}</td>
                <td>${confidence}</td>
                <td class="${statusClass}">${statusText}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    resultsDiv.innerHTML = html;
}

function renderStats(data) {
    const cards = `
        <div class="stat-cards">
            <div class="stat-card"><div class="number">${data.total_records}</div><div class="label">Всего записей</div></div>
            <div class="stat-card"><div class="number">${data.with_reference}</div><div class="label">С эталоном</div></div>
            <div class="stat-card"><div class="number">${data.llm_processed}</div><div class="label">Обработано LLM</div></div>
            <div class="stat-card"><div class="number">${data.algorithm_processed}</div><div class="label">Алгоритмически</div></div>
            <div class="stat-card"><div class="number">${data.manual_verified}</div><div class="label">Проверено вручную</div></div>
        </div>
    `;
    resultsDiv.innerHTML = `<h3>Статистика</h3>${cards}`;
}

function renderReference(data) {
    if (!data || data.length === 0) {
        resultsDiv.innerHTML = '<p>Эталонный справочник пуст.</p>';
        return;
    }
    let html = `<h3>Эталонный справочник (${data.length} записей)</h3><div class="reference-list">`;
    data.forEach(item => {
        html += `<div class="reference-item">ID ${item.id} — ${escapeHtml(item.canonical_title)} (кластер ${item.cluster_id}, размер ${item.cluster_size})</div>`;
    });
    html += '</div>';
    resultsDiv.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function classify() {
    const text = jobInput.value.trim();
    if (!text) {
        resultsDiv.innerHTML = '<p style="color:#dc2626;">Введите хотя бы одну должность.</p>';
        return;
    }
    const titles = text.split('\n').map(s => s.trim()).filter(s => s);
    if (titles.length === 0) {
        resultsDiv.innerHTML = '<p style="color:#dc2626;">Введите хотя бы одну должность.</p>';
        return;
    }

    resultsDiv.innerHTML = '<p>⏳ Загрузка...</p>';
    try {
        const data = await apiCall('/classify', 'POST', { titles });
        renderClassifyResult(data);
    } catch (err) {
        resultsDiv.innerHTML = `<p style="color:#dc2626;">Ошибка: ${err.message}</p>`;
    }
}

async function loadStats() {
    resultsDiv.innerHTML = '<p>⏳ Загрузка...</p>';
    try {
        const data = await apiCall('/stats');
        renderStats(data);
    } catch (err) {
        resultsDiv.innerHTML = `<p style="color:#dc2626;">Ошибка: ${err.message}</p>`;
    }
}

async function loadReference() {
    resultsDiv.innerHTML = '<p>⏳ Загрузка...</p>';
    try {
        const data = await apiCall('/reference');
        renderReference(data);
    } catch (err) {
        resultsDiv.innerHTML = `<p style="color:#dc2626;">Ошибка: ${err.message}</p>`;
    }
}

classifyBtn.addEventListener('click', classify);
statsBtn.addEventListener('click', loadStats);
referenceBtn.addEventListener('click', loadReference);

jobInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        classify();
    }
});