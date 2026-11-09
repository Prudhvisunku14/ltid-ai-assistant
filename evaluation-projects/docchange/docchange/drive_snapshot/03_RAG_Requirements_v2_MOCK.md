# Scenario 03 — Company-Document RAG System

Fictional company: Northstar Services | Text files + Drive documents | MOCK REVISION (test data, not in Drive)

# Project outcome

Build a document-question-answering system for fictional company policies and project information.

The system must use GPT for answer generation; use the provided documents as the sole authority for factual claims.

# Functional requirements

Ingestion — Read at least 10 files from the supplied Drive knowledge base, or an export of that Drive folder.

Search — Retrieve relevant document passages for a natural-language question. A vector database is required.

Answer — Return clear answers containing document filenames and evidence excerpts or location references.

Unknowns — When the documents do not support an answer, explicitly state that the answer is not found in the available documents.

Interface — Provide a CLI or web interface and explain the role of all selected tools.

Security — The system shall not send document text to third-party APIs without user consent.

# Acceptance evidence

Demonstrate questions about expense submissions, hotel reimbursement limits, leave notice and deployment approval.

Show the relevant document filename for every supported answer.
