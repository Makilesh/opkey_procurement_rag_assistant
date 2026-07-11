# Evaluation Results

- **Hit Rate:** 93%
- **Answer Relevance (1–5, strict judge):** 4.67
- **Faithfulness (1–5, strict judge):** 4.8
- **Keyword Coverage (objective):** 100%
- **LLM calls:** 35  ·  **Duration:** 558.0s

| # | Question | Multi-turn | Hit | Relevance | Faithfulness | Keywords | Notes |
|---|----------|------------|-----|-----------|--------------|----------|-------|
| richmond-thresholds | What are the competitive bidding thresholds at the University of Richmond? |  | ✅ | 5 | 5 | 100% |  |
| richmond-capital-equipment | What qualifies as capital equipment in the Richmond procurement policy and what is its minimum purchase price? |  | ✅ | 5 | 5 | 100% |  |
| richmond-card-invoice | Can a University of Richmond purchase card be used to pay an invoice? |  | ✅ | 5 | 5 | 100% |  |
| richmond-tech-purchases | Which department manages technology purchases such as hardware and software at the University of Richmond? |  | ✅ | 5 | 5 | 100% |  |
| oracle-order-vs-requisition | What is the difference between an order and a requisition in Oracle Procurement? |  | ✅ | 5 | 5 | 100% |  |
| oracle-po-types | What purchase order types does Oracle Purchasing provide? |  | ✅ | 5 | 5 | 100% |  |
| oracle-requisition-lifecycle | What does the requisition life cycle refer to in Oracle Procurement? |  | ✅ | 5 | 5 | 100% |  |
| oracle-reassign-requisition | Can I reassign a requisition that was created by someone else in Oracle Procurement? |  | ✅ | 5 | 5 | 100% |  |
| richmond-sole-vs-single-source | What is the difference between sole source and single source in the University of Richmond procurement policy? |  | ✅ | 5 | 5 | 100% |  |
| oracle-blanket-purchase-agreement | What is a blanket purchase agreement in Oracle Purchasing and when would you use one? |  | ✅ | 5 | 5 | 100% |  |
| oracle-supplier-registration | How does the supplier registration process work in Oracle Procurement? |  | ✅ | 5 | 5 | 100% |  |
| multiturn-oracle-requisition | What statuses can it have during approval? | yes | ✅ | 5 | 5 | 100% |  |
| multiturn-richmond-thresholds | What is required for purchases above the highest threshold? | yes | ✅ | 3 | 4 | 100% | unsupported: individuals must contact the Procurement Office as early as possible |
| cross-doc-approval-limit | What is the approval limit for purchases? |  | ❌ | 5 | 5 | — |  |
| out-of-scope-refusal | What is the capital of France? |  | — | 2 | 3 | — | refused correctly; unsupported: I can only answer from the Oracle Fusion Procurement guide and the University of Richmond procurement policy. |
