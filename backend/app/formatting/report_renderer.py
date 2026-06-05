"""
Report formatting: turn retrieval + generation results into markdown or text.
"""
from typing import List, Dict


def _format_document_label(document: Dict) -> str:
    title = str(document.get("report_title") or "").strip()
    year = document.get("year")

    if title and year:
        return f"{title} ({year})"
    if title:
        return title
    if year:
        return f"Report ({year})"
    return f"Doc {document.get('id', '?')}"


def format_report_markdown(
    company: str,
    criterion: str,
    query: str,
    retrieved_docs: List[Dict],
    assessment: str
) -> str:
    """
    Format evaluation results as markdown.
    """
    if retrieved_docs:
        retrieved_md = "\n".join(
            [
                f"{i+1}. ({_format_document_label(r)}, similarity {(float(r['similarity'])*100):.1f}%) "
                f"{str(r['content'])[:300]}{'...' if len(str(r['content'])) > 300 else ''}"
                for i, r in enumerate(retrieved_docs)
            ]
        )
    else:
        retrieved_md = "(No relevant documents found in the database.)"

    report = "\n".join(
        [
            "# ESG Evaluation Report",
            f"**Company:** {company}",
            f"**Criterion:** {criterion}",
            "",
            "## Request",
            query,
            "",
            "## Retrieved Context",
            retrieved_md,
            "",
            "## Evaluation",
            assessment,
        ]
    )
    return report


def format_report_text(
    company: str,
    criterion: str,
    query: str,
    retrieved_docs: List[Dict],
    assessment: str
) -> str:
    """
    Format evaluation results as plain text.
    """
    if retrieved_docs:
        retrieved_text = "\n".join(
            [
                f"{i+1}. ({_format_document_label(r)}, similarity {(float(r['similarity'])*100):.1f}%) "
                f"{str(r['content'])[:300]}{'...' if len(str(r['content'])) > 300 else ''}"
                for i, r in enumerate(retrieved_docs)
            ]
        )
    else:
        retrieved_text = "(No relevant documents found in the database.)"

    report = "\n".join(
        [
            "ESG Evaluation Report",
            f"Company: {company}",
            f"Criterion: {criterion}",
            "",
            "Request:",
            query,
            "",
            "Retrieved Context:",
            retrieved_text,
            "",
            "Evaluation:",
            assessment,
        ]
    )
    return report
