let activeTypingTimer = null;

const themeToggle = document.getElementById('themeToggle');

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    themeToggle.textContent = isDark ? 'Light Mode' : 'Dark Mode';
})


function renderMarkdownInto(element, markdownText) {
    // Render markdown and sanitize (important if content comes from a backend)
    const html = window.marked ? window.marked.parse(markdownText, { breaks: true }) : markdownText;
    element.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
}

function typeMarkdownInto(element, markdownText, options = {}) {
    const charsPerSecond = options.charsPerSecond ?? 10; // Adjust this value to make typing faster or slower
    const intervalMs = options.intervalMs ?? 30;
    const minCharsPerTick = options.minCharsPerTick ?? 2;
    const renderEveryTicks = options.renderEveryTicks ?? 1;

    if (activeTypingTimer) {
        clearInterval(activeTypingTimer);
        activeTypingTimer = null;
    }

    const charsPerTick = Math.max(minCharsPerTick, Math.round((charsPerSecond * intervalMs) / 1000));
    let index = 0;
    let tick = 0;

    renderMarkdownInto(element, '');

    activeTypingTimer = setInterval(() => {
        index = Math.min(markdownText.length, index + charsPerTick);
        tick += 1;

        if (tick % renderEveryTicks === 0 || index >= markdownText.length) {
            renderMarkdownInto(element, markdownText.slice(0, index));
            element.scrollTop = element.scrollHeight;
        }

        if (index >= markdownText.length) {
            clearInterval(activeTypingTimer);
            activeTypingTimer = null;
        }
    }, intervalMs);
}

document.getElementById('esgEvalForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const companySelect = document.getElementById('companySelect');
    const criteriaSelect = document.getElementById('criteriaSelect');
    const reportOutput = document.getElementById('reportOutput');

    const companyLabel = companySelect.options[companySelect.selectedIndex]?.text ?? '';
    const criteriaLabel = criteriaSelect.options[criteriaSelect.selectedIndex]?.text ?? '';
    const company = companySelect.value;
    const criterion = criteriaSelect.value;

    const query = `Evaluate ${companyLabel}'s ${criteriaLabel}. Provide a structured ESG report with key findings.`;

    typeMarkdownInto(reportOutput, `Generating report for **${companyLabel}** (${criteriaLabel})...`, { charsPerSecond: 60 });

    try {
        // Detect if we're behind Nuvolos proxy and adjust API path accordingly
        const basePath = window.location.pathname.startsWith('/proxy/') 
            ? '/proxy/3000' 
            : '';
        
        const response = await fetch(basePath + '/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                company,
                criterion,
                query,
                top_k: 3,
                format: 'markdown'
            })
        });

        const data = await response.json();
        if (!response.ok) {
            const detail = data?.detail ?? 'Unknown error';
            typeMarkdownInto(reportOutput, `# Error\n\n${detail}`);
            return;
        }

        const report = data?.report ?? '# Error\n\nBackend response missing `report`.';
        typeMarkdownInto(reportOutput, report);
    } catch (err) {
        typeMarkdownInto(reportOutput, `# Network Error\n\n${err?.message ?? String(err)}`);
    }
});