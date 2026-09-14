# Closed-Loop Formally-Verified RTL Refactoring Agent

> **Submission for NEBULA @ BITS-Goa × Astera Labs Track**  
> *Constraint Optimization through RTL Enhancement Using Generative AI*

An automated, closed-loop pipeline that ingests digital RTL, extracts synthesis and static timing analysis (STA) metrics, scans for structural clock-domain crossings (CDC), diagnoses root-cause bottlenecks into structured JSON, and executes verified refactoring passes with zero human decision points in the loop[cite: 5].

---

## Submission Deliverables & Links

* **Video Walkthrough (4:00–4:30 min):** [Watch the Demo Video](https://youtu.be/r2A-gAfU5VM)[cite: 3]
* **Full Round 1 Written Report:** [View Report Document](https://docs.google.com/document/d/1g_TCKdcMKnTxyXpBRympHMub7IjtT3Or/edit?usp=drive_link&ouid=103739974885456130013&rtpof=true&sd=true)[cite: 5]
* **Target DUT & Constraints Repository:** [External Design-Under-Test & Constraints Repo](https://github.com/vsssanjay48-hub/multi_domain_rtl_soc.git)  
  *(Hosts the complete 5-domain asynchronous fabric, generated clock dividers, domain handshakes, exhaustive testbenches, and SDC constraint files)[cite: 5].*

---

## System Architecture

The pipeline operates via a headless Python orchestrator where every stage writes a structured, auditable artifact consumed by the next[cite: 5]:
