// --- Theme Toggle Logic ---
const themeToggle = document.getElementById('themeToggle');

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    themeToggle.textContent = isDark ? 'Light Mode' : 'Dark Mode';
});

// --- Dynamic Dropdown Builder ---
async function loadCompanies() {
    const companySelect = document.getElementById('companySelect');
    
    // Check if we need the Nuvolos proxy path, just like in your evaluate function
    const basePath = window.location.pathname.startsWith('/proxy/') ? '/proxy/3000' : '';

    try {
        // 1. Fetch the data from the proxy
        const response = await fetch(basePath + '/companies');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // 2. Parse the JSON
        const companies = await response.json();
        
        // 3. Loop through the array and create the HTML options
        companies.forEach(company => {
            const option = document.createElement('option');
            option.value = company.id;        // The backend ID (e.g., 'apple')
            option.textContent = company.name; // The display name (e.g., 'Apple')
            companySelect.appendChild(option);
        });
        
    } catch (error) {
        console.error("Error loading companies from backend:", error);
        // Fallback so the user knows something went wrong
        companySelect.innerHTML = '<option value="" disabled selected>Error loading companies</option>';
    }
}

// Fire the function immediately when the script loads!
loadCompanies();

let currentMarkdownReport = ""; // Stores the raw text for the PDF

// --- Report Rendering Logic ---
let activeTypingTimer = null;

function renderMarkdownInto(element, markdownText) {
    const html = window.marked ? window.marked.parse(markdownText, { breaks: true }) : markdownText;
    element.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
}

function typeMarkdownInto(element, markdownText, options = {}) {
    const charsPerSecond = options.charsPerSecond ?? 200; 
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

// --- Form Submission Logic ---
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
        const basePath = window.location.pathname.startsWith('/proxy/') ? '/proxy/3000' : '';
        
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

        // Intercept the raw markdown and save it for the PDF button
        currentMarkdownReport = report;

        typeMarkdownInto(reportOutput, report);
    } catch (err) {
        typeMarkdownInto(reportOutput, `# Network Error\n\n${err?.message ?? String(err)}`);
    }
});

// --- Clean PDF Generation Logic ---
document.getElementById('downloadPdfBtn').addEventListener('click', () => {
    // 1. Check if we actually have a report intercepted from the backend
    if (!currentMarkdownReport) {
        alert("Please generate a complete report before downloading.");
        return;
    }

    // 2. Create an INVISIBLE "piece of paper" in the computer's memory
    const printDocument = document.createElement('div');
    
    // 3. Style it like a real printed document, ignoring the website's dark mode
    // We add padding here to act as the margins of the PDF page
    printDocument.style.padding = '20mm'; 
    printDocument.style.color = 'black';
    printDocument.style.backgroundColor = 'white';
    printDocument.style.fontFamily = 'Arial, sans-serif';
    printDocument.style.fontSize = '14px';
    printDocument.style.lineHeight = '1.6';

    // 4. Convert the raw Markdown into clean HTML (bolding, lists, etc.) 
    // We use the exact same libraries your UI uses!
    const formattedHtml = window.DOMPurify.sanitize(window.marked.parse(currentMarkdownReport));
    printDocument.innerHTML = formattedHtml;

    // 5. Configure the PDF settings
    const opt = {
        margin:       0, // Set to 0 because we handle margins using CSS padding above
        filename:     'ESG_Evaluation_Report.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2 }, // High scale ensures crisp, readable text
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    // 6. Generate the PDF directly from the INVISIBLE document!
    html2pdf().set(opt).from(printDocument).save();
});