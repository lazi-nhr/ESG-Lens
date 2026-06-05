"""
Configuration and environment variables.
"""
import os

# Load environment variables from .env file (if it exists)
from dotenv import load_dotenv
load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "nv-service-b48efcd4fbe8cf4a875a2ccb70e0e21b")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nuvolos")
DB_USER = os.getenv("DB_USER", "nuvolos")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nuvolos")

# Server
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8500"))
# BACKEND_HOST: address for server binding (0.0.0.0 = all interfaces)
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
# BACKEND_URL: address for client connections (what the frontend uses to call the backend)
BACKEND_URL = os.getenv("BACKEND_URL", "localhost")

# Retrieval
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "10"))
MAX_TOP_K = int(os.getenv("MAX_TOP_K", "100"))

# Chunking
SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.5"))
MIN_CHUNK_TOKENS = int(os.getenv("MIN_CHUNK_TOKENS", "100"))
MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", "800"))

# LLM / Generation
DEFAULT_FORMAT = "markdown"  # "markdown" | "text"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface")

# Local model for inference (runs on Tesla T4)
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B")
# Fallback API model for inference (if local model fails)
HF_API_MODEL = os.getenv("HF_API_MODEL", "Qwen/Qwen2.5-7B-Instruct")
# Hugging Face API authentication (for embeddings and fallback inference)
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_HOME = os.getenv("HF_HOME", "/files/.hf_cache")

# Evaluation Criteria
# Structured definition of available ESG evaluation criteria
EVALUATION_CRITERIA = [
    {
        "id": "overall",
        "name": "Overall ESG Assessment",
        "description": "Comprehensive evaluation of Environmental, Social, and Governance practices",
        "category": "composite",
        "question": "Provide a comprehensive ESG assessment covering all three pillars: environmental, social, and governance performance. Include key achievements, gaps, and recommendations.",
        "context_instructions": "Synthesize insights from all three ESG dimensions. Focus on material issues and strategic importance.",
        "output_format": "narrative",
        "required_fields": ["environmental_score", "social_score", "governance_score", "overall_trends", "key_risks"],
        "retrieval_bias": ["ESG", "sustainability", "corporate responsibility", "material issues"]
    },
    {
        "id": "environment",
        "name": "Environment (E) Summary",
        "description": "Environmental sustainability initiatives, climate action, and resource management",
        "category": "pillar",
        "question": "What are the company's key environmental initiatives and climate commitments? Include emissions reduction targets, renewable energy use, waste management, and environmental compliance.",
        "context_instructions": "Emphasize quantifiable metrics, science-based targets, and progress against commitments. Highlight both achievements and areas needing improvement.",
        "output_format": "structured",
        "required_fields": ["emissions_targets", "renewable_energy_percent", "waste_reduction", "water_usage", "climate_risks"],
        "retrieval_bias": ["emissions", "carbon", "renewable energy", "climate change", "environmental risk", "sustainability"]
    },
    {
        "id": "social",
        "name": "Social (S) Summary",
        "description": "Social responsibility, employee welfare, community impact, and human rights",
        "category": "pillar",
        "question": "What is the company's approach to social responsibility including employee welfare, diversity and inclusion, community engagement, and human rights? Include key programs and their impact.",
        "context_instructions": "Focus on employee satisfaction, diversity metrics, community investment, and social impact measurement. Address labor practices and supply chain responsibility.",
        "output_format": "structured",
        "required_fields": ["employee_diversity", "compensation_equity", "community_investment", "labor_practices", "supply_chain_responsibility"],
        "retrieval_bias": ["diversity", "inclusion", "employee welfare", "community", "human rights", "labor practices", "supply chain"]
    },
    {
        "id": "governance",
        "name": "Governance (G) Summary",
        "description": "Board composition, executive compensation, ethics, and corporate transparency",
        "category": "pillar",
        "question": "What is the company's governance structure and approach to ethics? Include board composition, executive compensation philosophy, ethics programs, and transparency practices.",
        "context_instructions": "Evaluate board diversity, independence, compensation alignment with performance, and governance best practices. Address ethics and compliance frameworks.",
        "output_format": "structured",
        "required_fields": ["board_diversity", "board_independence", "ceo_pay_ratio", "ethics_program", "audit_committee"],
        "retrieval_bias": ["board composition", "executive compensation", "ethics", "compliance", "governance", "transparency", "audit"]
    },
    {
        "id": "climate_risk",
        "name": "Climate Risk Management",
        "description": "Identification, assessment and management of physical and transition climate risks.",
        "category": "environment",
        "question": "How does the company identify, assess, and mitigate climate-related physical and transition risks? Describe scenario analysis, integration into strategy, and financial exposure.",
        "context_instructions": "Prioritize quantified scenario analysis, governance oversight, and alignment with TCFD-style disclosures.",
        "output_format": "structured",
        "required_fields": ["risk_assessment_method", "scenario_results", "financial_impacts", "mitigation_measures"],
        "retrieval_bias": ["climate risk", "physical risk", "transition risk", "scenario analysis", "TCFD"]
    },
    {
        "id": "ghg_emissions",
        "name": "GHG Emissions & Metrics",
        "description": "Emissions accounting, scopes 1-3, reduction targets, and progress reporting.",
        "category": "environment",
        "question": "What are the company's Scope 1, 2, and 3 emissions, targets and recent progress? Explain methodologies and key emissions drivers.",
        "context_instructions": "Look for absolute/normalized emissions, third‑party verification, and SBTi alignment where available.",
        "output_format": "structured",
        "required_fields": ["scope1", "scope2", "scope3", "targets", "verification"],
        "retrieval_bias": ["Scope 1", "Scope 2", "Scope 3", "SBTi", "carbon footprint", "emissions intensity"]
    },
    {
        "id": "energy_transition",
        "name": "Energy Transition & Renewables",
        "description": "Strategy and progress toward low‑carbon energy sources and energy efficiency.",
        "category": "environment",
        "question": "Describe the company's approach to energy transition: renewable procurement, energy efficiency programs, and capital allocation for low‑carbon technologies.",
        "context_instructions": "Favor quantitative metrics (renewable % of consumption, efficiency gains) and CAPEX commitments.",
        "output_format": "structured",
        "required_fields": ["renewable_share", "efficiency_measures", "capex_commitments"],
        "retrieval_bias": ["renewable energy", "energy efficiency", "power purchase agreement", "renewables"]
    },
    {
        "id": "water_biodiversity",
        "name": "Water & Biodiversity Stewardship",
        "description": "Management of water use, impacts on ecosystems, and biodiversity protection.",
        "category": "environment",
        "question": "How does the company manage water risks and biodiversity impacts across operations and supply chains? Note targets, site-level actions, and partnerships.",
        "context_instructions": "Highlight watershed-level risks, water intensity metrics, biodiversity assessments, and mitigation/restoration programs.",
        "output_format": "structured",
        "required_fields": ["water_intensity", "biodiversity_assessments", "mitigation_actions"],
        "retrieval_bias": ["water risk", "biodiversity", "ecosystem", "freshwater", "species", "habitat"]
    },
    {
        "id": "supply_chain",
        "name": "Supply Chain Sustainability",
        "description": "Due diligence, supplier standards, and monitoring across suppliers and tiers.",
        "category": "social",
        "question": "Describe supply chain due diligence processes, key supplier risks, and remediation/monitoring approaches (including audits and KPIs).",
        "context_instructions": "Prioritize multi-tier coverage, audit frequency, corrective actions, and supplier engagement programs.",
        "output_format": "structured",
        "required_fields": ["due_diligence_process", "audit_coverage", "supplier_kpis"],
        "retrieval_bias": ["supply chain", "supplier audit", "supplier due diligence", "tier 2", "procurement"]
    },
    {
        "id": "labor_practices",
        "name": "Labor Practices & Worker Rights",
        "description": "Workplace safety, fair labor, collective bargaining, and grievance mechanisms.",
        "category": "social",
        "question": "What policies and performance metrics relate to worker health & safety, living wages, collective bargaining and grievance mechanisms?",
        "context_instructions": "Seek incident rates, corrective measures, union engagement, and remediation examples.",
        "output_format": "structured",
        "required_fields": ["injury_rate", "wage_practices", "grievance_mechanism", "collective_bargaining"],
        "retrieval_bias": ["health and safety", "injury rate", "wages", "collective bargaining", "grievance"]
    },
    {
        "id": "dei",
        "name": "Diversity, Equity & Inclusion",
        "description": "Workforce diversity metrics, inclusion programs, and equitable practices.",
        "category": "social",
        "question": "Provide workforce diversity statistics, advancement programs, pay equity efforts, and measurable inclusion outcomes.",
        "context_instructions": "Prefer disaggregated data (gender, race/ethnicity, seniority) and time-series trends.",
        "output_format": "structured",
        "required_fields": ["diversity_metrics", "pay_equity", "promotion_rates", "inclusion_programs"],
        "retrieval_bias": ["diversity", "inclusion", "pay equity", "gender split", "underrepresented"]
    },
    {
        "id": "data_privacy_security",
        "name": "Data Privacy & Cybersecurity",
        "description": "Policies, incident history, and controls for data protection and cyber resilience.",
        "category": "governance",
        "question": "How does the company manage data privacy and cybersecurity risks? Include governance, incident history, and security controls.",
        "context_instructions": "Look for breach disclosures, third-party audits (SOC2), incident response plans, and board-level oversight.",
        "output_format": "structured",
        "required_fields": ["incident_history", "security_controls", "governance_owner"],
        "retrieval_bias": ["cybersecurity", "data breach", "privacy policy", "SOC2", "incident response"]
    },
    {
        "id": "anti_corruption",
        "name": "Anti-Corruption & Business Ethics",
        "description": "Anti-bribery controls, whistleblower programs, and ethical conduct enforcement.",
        "category": "governance",
        "question": "Describe policies and performance on anti-corruption, third-party risk management, whistleblowing, and enforcement actions.",
        "context_instructions": "Prioritize incident disclosures, training coverage, and remediation outcomes.",
        "output_format": "structured",
        "required_fields": ["policy_coverage", "training_rates", "investigations", "third_party_screening"],
        "retrieval_bias": ["anti corruption", "bribery", "whistleblower", "ethics", "compliance"]
    },
    {
        "id": "disclosure_reporting",
        "name": "Disclosure, Targets & Reporting Quality",
        "description": "Transparency, quality of reporting, assurance and alignment with reporting standards.",
        "category": "governance",
        "question": "Assess the quality and completeness of the company's ESG disclosures, target clarity, and external assurance.",
        "context_instructions": "Look for standard alignment (GRI, SASB, TCFD/ISSB), third‑party assurance and granular KPIs.",
        "output_format": "structured",
        "required_fields": ["reporting_standards", "assurance", "kpi_coverage", "disclosure_gaps"],
        "retrieval_bias": ["GRI", "SASB", "TCFD", "ISSB", "assurance", "disclosure"]
    }
]