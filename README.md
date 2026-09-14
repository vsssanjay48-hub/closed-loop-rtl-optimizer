# Closed-Loop Formally-Verified RTL Refactoring Agent

> **Submission for NEBULA @ BITS-Goa × Astera Labs Track**  
> *Constraint Optimization through RTL Enhancement Using Generative AI*

An automated, closed-loop pipeline that ingests digital RTL, extracts synthesis and static timing analysis (STA) metrics, scans for structural clock-domain crossings (CDC), diagnoses root-cause bottlenecks into structured JSON, and executes verified refactoring passes with zero human decision points in the loop[cite: 5].

---

## Submission Deliverables & Links

* **Video Walkthrough (4:00–4:30 min):** [Watch the Demo Video](PASTE_YOUR_YOUTUBE_OR_DRIVE_VIDEO_LINK_HERE)[cite: 3]
* **Full Round 1 Written Report:** [View Report Document](./Nebula_Round1_Report.docx)[cite: 5]
* **Target DUT & Constraints Repository:** [External Design-Under-Test & Constraints Repo](PASTE_YOUR_EXTERNAL_DUT_REPO_LINK_HERE)  
  *(Hosts the complete 5-domain asynchronous fabric, generated clock dividers, domain handshakes, exhaustive testbenches, and SDC constraint files)[cite: 5].*

---

## System Architecture

The pipeline operates via a headless Python orchestrator where every stage writes a structured, auditable artifact consumed by the next[cite: 5]:
