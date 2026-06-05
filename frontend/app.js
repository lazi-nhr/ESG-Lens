// --- Theme Toggle Logic ---
const themeToggle = document.getElementById('themeToggle');

function getApiBasePath() {
    return window.location.pathname.startsWith('/proxy/') ? '/proxy/3000' : '';
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    themeToggle.textContent = isDark ? 'Light Mode' : 'Dark Mode';
});

// --- Dynamic Dropdown Builder ---
async function loadCompanies() {
    const companySelect = document.getElementById('companySelect');

    try {
        const response = await fetch(getApiBasePath() + '/companies');
        
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

async function loadCriteria() {
    const criteriaSelect = document.getElementById('criteriaSelect');

    try {
        const response = await fetch(getApiBasePath() + '/criteria');

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const criteria = await response.json();

        criteria.forEach(criterion => {
            const option = document.createElement('option');
            option.value = criterion.id;
            option.textContent = criterion.name;
            criteriaSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading criteria from backend:', error);
        criteriaSelect.innerHTML = '<option value="" disabled selected>Error loading criteria</option>';
    }
}

// Fire the function immediately when the script loads!
loadCompanies();
loadCriteria();

let currentMarkdownReport = ""; // Stores the raw text for the PDF

// --- Report Rendering Logic ---
let activeTypingTimer = null;

function renderMarkdownInto(element, markdownText) {
    try {
        const html = window.marked ? window.marked.parse(markdownText, { breaks: true }) : markdownText;
        element.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
    } catch (err) {
        console.error("Error rendering markdown:", err);
    }
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
    console.log(`[Animation Start] Text length: ${markdownText.length}, charsPerTick: ${charsPerTick}`);

    activeTypingTimer = setInterval(() => {
        try {
            index = Math.min(markdownText.length, index + charsPerTick);
            tick += 1;

            if (tick % renderEveryTicks === 0 || index >= markdownText.length) {
                renderMarkdownInto(element, markdownText.slice(0, index));
                if (tick % 10 === 0) {
                    console.log(`[Animation Progress] ${index}/${markdownText.length} chars`);
                }
            }

            if (index >= markdownText.length) {
                clearInterval(activeTypingTimer);
                activeTypingTimer = null;
                console.log('[Animation Complete]');
            }
        } catch (err) {
            console.error("Error in animation loop:", err);
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
        const response = await fetch(getApiBasePath() + '/evaluate', {
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
    if (!currentMarkdownReport) {
        alert("Please generate a complete report before downloading.");
        return;
    }

    // 1. Frontend Text Fix: Safely force a new line without breaking Markdown bold tags!
    // This looks for "Criterion:" (with or without bold asterisks) and safely drops a <br> before it.
    let fixedMarkdown = currentMarkdownReport.replace(/(\*\*Criterion:\*\*|Criterion:)/g, '<br>$1');

    const printDocument = document.createElement('div');
    
    // 2. Basic document styling
    printDocument.style.color = 'black';
    printDocument.style.backgroundColor = 'white';
    printDocument.style.fontFamily = 'Arial, sans-serif';
    printDocument.style.fontSize = '14px';
    printDocument.style.lineHeight = '1.6';
    printDocument.style.paddingBottom = '24px';

    // 3. Add Spacing CSS (Fixed for stacked headers)
    const styleBlock = document.createElement('style');
    styleBlock.innerHTML = `
        .section-box { margin-top: 30px; }
        .section-box:first-child { margin-top: 0; }
        .report-content { clear: both; }
        
        /* Only remove the top margin if the header is the very first item in the box */
        .section-box > h1:first-child,
        .section-box > h2:first-child,
        .section-box > h3:first-child { margin-top: 0; }
        
        h2 { margin-bottom: 10px; }
        h3 { margin-top: 15px; margin-bottom: 8px; }
    `;
    printDocument.appendChild(styleBlock);

    // 4. Add Your Logo
    const logoHtml = `<div style="text-align: right; margin-bottom: 20px;"><img src="logo_pdf.png" style="display: inline-block; max-width: 150px;" /></div>`;

    // 5. Parse the Markdown into a TEMPORARY container
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = window.DOMPurify.sanitize(window.marked.parse(fixedMarkdown));

    // 6. Group sections into unbreakable boxes (Smarter Logic!)
    const groupedContent = document.createElement('div');
    groupedContent.className = 'report-content';
    let currentSection = document.createElement('div');
    
    currentSection.className = 'section-box';
    currentSection.style.pageBreakInside = 'avoid'; 

    let hasBodyContent = false; // Tracks if we actually have paragraphs/lists in the box

    Array.from(tempDiv.children).forEach(child => {
        const isHeader = child.tagName === 'H1' || child.tagName === 'H2' || child.tagName === 'H3';
        
        if (isHeader) {
            // ONLY split into a new box if the current box actually has body text in it.
            // This forces stacked headers (like H2 immediately followed by H3) to stay together!
            if (currentSection.hasChildNodes() && hasBodyContent) {
                groupedContent.appendChild(currentSection);
                currentSection = document.createElement('div');
                currentSection.className = 'section-box';
                currentSection.style.pageBreakInside = 'avoid'; 
                hasBodyContent = false; // Reset for the new box
            }
        } else {
            hasBodyContent = true; // We hit a paragraph, list, or code block!
        }
        
        currentSection.appendChild(child);
    });
    
    // Catch the final section
    if (currentSection.hasChildNodes()) {
        groupedContent.appendChild(currentSection);
    }

    // 7. Combine the logo and grouped HTML
    printDocument.innerHTML += logoHtml + groupedContent.outerHTML;

    // 8. Configure html2pdf 
    const opt = {
        margin:       20, 
        filename:     'ESG_Evaluation_Report.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true }, 
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    html2pdf().set(opt).from(printDocument).save();
});