"""Phase 5 specialist agent tools — Cipher, Forge, Shield, Ledger, Pulse.

These agents have domain-specific tools for cloud infrastructure, DevOps,
security, finance, and product management respectively.
"""

import asyncio
import logging
import uuid
from datetime import date

logger = logging.getLogger(__name__)


# ── Shared LLM utility (imported from agent_tools at runtime) ─────────────

async def _llm_analyze(prompt: str, system: str, model: str = "claude-haiku-4-5-20251001",
                        max_tokens: int = 300) -> str:
    from gneva.services import llm_analyze
    return await llm_analyze(prompt, system, model=model, max_tokens=max_tokens)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CIPHER — Cloud & Infrastructure Expert (30 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _cloud_tool(name: str, desc: str, props: dict | None = None, required: list | None = None) -> dict:
    """Helper to create a cloud tool definition concisely."""
    schema = {"type": "object", "properties": props or {}, "required": required or []}
    if not props:
        schema["properties"] = {"query": {"type": "string", "description": "What to analyze."}}
        schema["required"] = ["query"]
    return {"name": name, "description": desc, "input_schema": schema}


CIPHER_TOOLS = [
    # AWS (20)
    _cloud_tool("ec2_describe", "Describe EC2 instances: state, type, region, tags, utilization.",
                {"instance_id": {"type": "string", "description": "Instance ID or filter."}}),
    _cloud_tool("ec2_troubleshoot", "Troubleshoot an EC2 issue: connectivity, performance, state.",
                {"issue": {"type": "string", "description": "What's wrong."}}, ["issue"]),
    _cloud_tool("lambda_logs", "Check Lambda function logs for errors, cold starts, duration.",
                {"function_name": {"type": "string", "description": "Lambda function name."}}, ["function_name"]),
    _cloud_tool("lambda_optimize", "Optimize a Lambda function: memory, timeout, concurrency, cost.",
                {"function_name": {"type": "string", "description": "Lambda function name."}}, ["function_name"]),
    _cloud_tool("ecs_service_status", "Check ECS service health: task count, deployments, events.",
                {"service": {"type": "string", "description": "ECS service name."}}, ["service"]),
    _cloud_tool("eks_cluster_health", "EKS cluster health: nodes, pods, control plane, networking.",
                {"cluster": {"type": "string", "description": "Cluster name."}}, ["cluster"]),
    _cloud_tool("s3_analysis", "Analyze S3 bucket: size, cost, access patterns, lifecycle.",
                {"bucket": {"type": "string", "description": "Bucket name."}}, ["bucket"]),
    _cloud_tool("rds_performance", "RDS performance: CPU, connections, slow queries, storage.",
                {"instance": {"type": "string", "description": "RDS instance identifier."}}, ["instance"]),
    _cloud_tool("dynamodb_capacity", "DynamoDB table capacity, throttling, hot partitions.",
                {"table": {"type": "string", "description": "Table name."}}, ["table"]),
    _cloud_tool("vpc_debug", "Debug VPC networking: routes, NACLs, security groups, DNS.",
                {"issue": {"type": "string", "description": "Networking issue description."}}, ["issue"]),
    _cloud_tool("security_group_audit", "Audit security groups for overly permissive rules.",
                {"scope": {"type": "string", "description": "VPC or security group ID."}}),
    _cloud_tool("cloudfront_analysis", "CloudFront distribution analysis: cache hit ratio, origins, errors.",
                {"distribution": {"type": "string", "description": "Distribution ID or domain."}}),
    _cloud_tool("alb_analysis", "ALB health: target groups, error rates, latency, rules.",
                {"alb": {"type": "string", "description": "ALB name or ARN."}}),
    _cloud_tool("cost_explorer_query", "AWS cost breakdown by service, tag, time period.",
                {"query": {"type": "string", "description": "Cost question."},
                 "period": {"type": "string", "description": "Time period (e.g. 'last 30 days')."}},
                ["query"]),
    _cloud_tool("iam_analyzer", "Analyze IAM policies: overprivileged roles, unused permissions.",
                {"scope": {"type": "string", "description": "Role, user, or 'all'."}}),
    _cloud_tool("cloudwatch_query", "Query CloudWatch metrics or logs.",
                {"query": {"type": "string", "description": "What to look for."},
                 "log_group": {"type": "string", "description": "Log group (optional)."}},
                ["query"]),
    _cloud_tool("xray_trace", "Analyze X-Ray traces for latency bottlenecks.",
                {"service": {"type": "string", "description": "Service to trace."}}),
    _cloud_tool("cloudformation_drift", "Check CloudFormation stack for drift from template.",
                {"stack": {"type": "string", "description": "Stack name."}}, ["stack"]),
    _cloud_tool("reserved_instance_advisor", "RI/Savings Plan recommendations based on usage.",
                {"scope": {"type": "string", "description": "Service or account scope."}}),
    _cloud_tool("resource_waste", "Find wasted resources: idle instances, unattached volumes, unused EIPs.",
                {"scope": {"type": "string", "description": "Account or region scope."}}),
    # Azure (5)
    _cloud_tool("aks_health", "Azure AKS cluster health: nodes, pods, networking, upgrades.",
                {"cluster": {"type": "string", "description": "AKS cluster name."}}, ["cluster"]),
    _cloud_tool("azure_cost", "Azure cost analysis by service, resource group, tag.",
                {"query": {"type": "string", "description": "Cost question."}}, ["query"]),
    _cloud_tool("arm_review", "Review ARM template or Bicep for issues and improvements.",
                {"template": {"type": "string", "description": "Template name or description."}}, ["template"]),
    _cloud_tool("azure_monitor", "Query Azure Monitor metrics and alerts.",
                {"query": {"type": "string", "description": "What to check."}}, ["query"]),
    _cloud_tool("azure_security", "Azure Security Center findings and recommendations.",
                {"scope": {"type": "string", "description": "Resource group or subscription."}}),
    # GCP (5)
    _cloud_tool("gke_health", "GKE cluster health: nodes, workloads, networking.",
                {"cluster": {"type": "string", "description": "GKE cluster name."}}, ["cluster"]),
    _cloud_tool("bigquery_optimize", "BigQuery optimization: query cost, slot usage, partitioning.",
                {"query": {"type": "string", "description": "Query or dataset to optimize."}}, ["query"]),
    _cloud_tool("gcp_cost", "GCP billing analysis by project, service, label.",
                {"query": {"type": "string", "description": "Cost question."}}, ["query"]),
    _cloud_tool("cloud_run_analyze", "Cloud Run service analysis: instances, latency, cold starts.",
                {"service": {"type": "string", "description": "Cloud Run service name."}}, ["service"]),
    _cloud_tool("gcp_security", "GCP Security Command Center findings.",
                {"scope": {"type": "string", "description": "Project or org scope."}}),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FORGE — DevOps & Platform Engineer (14 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORGE_TOOLS = [
    _cloud_tool("github_pr_review", "Review a GitHub PR: code quality, risk, test coverage.",
                {"pr": {"type": "string", "description": "PR number or URL."},
                 "concerns": {"type": "string", "description": "Specific concerns."}},
                ["pr"]),
    _cloud_tool("github_actions_status", "Check GitHub Actions: recent runs, failures, duration.",
                {"repo": {"type": "string", "description": "Repository name."}}, ["repo"]),
    _cloud_tool("terraform_plan_review", "Review Terraform plan for risks, cost impact, best practices.",
                {"plan_summary": {"type": "string", "description": "Plan summary or resource changes."}},
                ["plan_summary"]),
    _cloud_tool("docker_analyze", "Analyze Dockerfile or container: image size, layers, security, optimization.",
                {"target": {"type": "string", "description": "Image name or Dockerfile description."}},
                ["target"]),
    _cloud_tool("k8s_troubleshoot", "Troubleshoot Kubernetes: pods, services, networking, storage.",
                {"issue": {"type": "string", "description": "What's wrong."}}, ["issue"]),
    _cloud_tool("deployment_risk_score", "Score deployment risk: change size, time of day, service criticality.",
                {"deployment": {"type": "string", "description": "What's being deployed."}},
                ["deployment"]),
    _cloud_tool("pipeline_optimize", "Optimize CI/CD pipeline: build time, caching, parallelism.",
                {"pipeline": {"type": "string", "description": "Pipeline description."}}, ["pipeline"]),
    _cloud_tool("dependency_audit", "Audit dependencies: vulnerabilities, outdated packages, license issues.",
                {"project": {"type": "string", "description": "Project or package manager."}}, ["project"]),
    _cloud_tool("incident_timeline", "Build incident timeline from events, logs, and changes.",
                {"incident": {"type": "string", "description": "Incident description."}}, ["incident"]),
    _cloud_tool("sla_monitor", "Check SLA compliance: uptime, error budget, burn rate.",
                {"service": {"type": "string", "description": "Service to check."}}, ["service"]),
    _cloud_tool("rollback_plan", "Generate a rollback plan for a deployment or change.",
                {"change": {"type": "string", "description": "What was changed."}}, ["change"]),
    _cloud_tool("post_mortem_generate", "Generate a post-mortem from incident details.",
                {"incident": {"type": "string", "description": "Incident summary."}}, ["incident"]),
    _cloud_tool("migration_plan", "Plan a migration: steps, risks, rollback, timeline.",
                {"migration": {"type": "string", "description": "What's being migrated."}}, ["migration"]),
    _cloud_tool("infrastructure_cost", "Estimate infrastructure cost for a proposed architecture.",
                {"architecture": {"type": "string", "description": "Proposed architecture."}},
                ["architecture"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHIELD — Security & Compliance Expert (13 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SHIELD_TOOLS = [
    _cloud_tool("cve_lookup", "Look up a CVE: severity, affected systems, patches, exploitability.",
                {"cve_id": {"type": "string", "description": "CVE ID or vulnerability description."}},
                ["cve_id"]),
    _cloud_tool("threat_model", "Generate a threat model for a system or feature.",
                {"system": {"type": "string", "description": "System or feature to model."}}, ["system"]),
    _cloud_tool("compliance_check", "Check compliance status against a framework (SOC2, HIPAA, GDPR, PCI).",
                {"framework": {"type": "string", "description": "Compliance framework."},
                 "scope": {"type": "string", "description": "What to check."}},
                ["framework"]),
    _cloud_tool("security_architecture_review", "Review architecture for security: auth, encryption, network, data.",
                {"architecture": {"type": "string", "description": "Architecture to review."}},
                ["architecture"]),
    _cloud_tool("vendor_risk_assessment", "Assess third-party vendor security risk.",
                {"vendor": {"type": "string", "description": "Vendor name or type."}}, ["vendor"]),
    _cloud_tool("incident_response_playbook", "Generate incident response playbook for a scenario.",
                {"scenario": {"type": "string", "description": "Incident type."}}, ["scenario"]),
    _cloud_tool("access_review", "Review access patterns: who has access to what, any anomalies.",
                {"scope": {"type": "string", "description": "System or resource scope."}}, ["scope"]),
    _cloud_tool("data_flow_analysis", "Map data flows for privacy/security: where PII goes, encryption points.",
                {"system": {"type": "string", "description": "System to analyze."}}, ["system"]),
    _cloud_tool("privacy_impact_assessment", "Privacy impact assessment for a feature or data change.",
                {"feature": {"type": "string", "description": "Feature or change."}}, ["feature"]),
    _cloud_tool("pentest_findings_review", "Review and prioritize penetration test findings.",
                {"findings": {"type": "string", "description": "Summary of findings."}}, ["findings"]),
    _cloud_tool("supply_chain_risk", "Assess software supply chain risk: dependencies, build pipeline, signing.",
                {"target": {"type": "string", "description": "Project or component."}}, ["target"]),
    _cloud_tool("regulatory_radar", "Check upcoming regulatory changes that may affect us.",
                {"domain": {"type": "string", "description": "Industry or regulatory domain."}}, ["domain"]),
    _cloud_tool("security_budget_roi", "Calculate ROI of a security investment or initiative.",
                {"initiative": {"type": "string", "description": "Security initiative."}}, ["initiative"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEDGER — Finance & Business Operations (12 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEDGER_TOOLS = [
    _cloud_tool("financial_model", "Build or analyze a financial model.",
                {"model_type": {"type": "string", "description": "Type: P&L, unit economics, DCF, etc."},
                 "inputs": {"type": "string", "description": "Key inputs and assumptions."}},
                ["model_type"]),
    _cloud_tool("budget_tracker", "Check budget status: spent vs planned, variance, forecast.",
                {"department": {"type": "string", "description": "Department or project."}}, ["department"]),
    _cloud_tool("unit_economics", "Calculate unit economics: CAC, LTV, payback period, margins.",
                {"product": {"type": "string", "description": "Product or service."}}, ["product"]),
    _cloud_tool("revenue_forecast", "Revenue forecast with assumptions and scenarios.",
                {"period": {"type": "string", "description": "Forecast period."},
                 "model": {"type": "string", "description": "Model type: bottom-up, top-down, etc."}},
                ["period"]),
    _cloud_tool("burn_rate", "Calculate burn rate, runway, and cash-out date.",
                {"inputs": {"type": "string", "description": "Current cash, monthly expenses."}}),
    _cloud_tool("scenario_planning", "Financial scenario planning: best/likely/worst with key levers.",
                {"scenario": {"type": "string", "description": "What to model."}}, ["scenario"]),
    _cloud_tool("vendor_comparison", "Compare vendor pricing and total cost of ownership.",
                {"vendors": {"type": "string", "description": "Vendors to compare."},
                 "criteria": {"type": "string", "description": "Comparison criteria."}},
                ["vendors"]),
    _cloud_tool("contract_analysis", "Analyze contract financial terms: pricing, SLAs, penalties.",
                {"contract": {"type": "string", "description": "Contract description."}}, ["contract"]),
    _cloud_tool("headcount_planning", "Headcount plan: roles needed, cost, timeline, alternatives.",
                {"plan": {"type": "string", "description": "Hiring needs."}}, ["plan"]),
    _cloud_tool("roi_calculator", "Calculate ROI for an investment or initiative.",
                {"initiative": {"type": "string", "description": "What to evaluate."},
                 "cost": {"type": "string", "description": "Estimated cost."},
                 "benefit": {"type": "string", "description": "Expected benefit."}},
                ["initiative"]),
    _cloud_tool("pricing_analysis", "Pricing strategy analysis: competitive, value-based, cost-plus.",
                {"product": {"type": "string", "description": "Product to price."}}, ["product"]),
    _cloud_tool("fundraising_prep", "Fundraising preparation: metrics, narrative, valuation inputs.",
                {"stage": {"type": "string", "description": "Funding stage (seed, A, B, etc)."}}, ["stage"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PULSE — Product Manager (10 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PULSE_TOOLS = [
    _cloud_tool("user_feedback_search", "Search user feedback and feature requests.",
                {"query": {"type": "string", "description": "What to search for."}}, ["query"]),
    _cloud_tool("feature_prioritization", "Prioritize features using RICE, ICE, or value/effort.",
                {"features": {"type": "string", "description": "Features to prioritize (comma-separated)."},
                 "method": {"type": "string", "description": "RICE, ICE, or value_effort."}},
                ["features"]),
    _cloud_tool("roadmap_status", "Check roadmap status: what's shipped, in progress, planned.",
                {"quarter": {"type": "string", "description": "Quarter to check (e.g., 'Q1 2026')."}}),
    _cloud_tool("usage_analytics", "Product usage analytics: feature adoption, DAU/MAU, retention.",
                {"feature": {"type": "string", "description": "Feature or product area."}}),
    _cloud_tool("a_b_test_results", "Get A/B test results and recommendation.",
                {"test": {"type": "string", "description": "Test name or description."}}, ["test"]),
    _cloud_tool("competitive_feature_matrix", "Feature comparison matrix vs competitors.",
                {"competitors": {"type": "string", "description": "Competitors to compare."},
                 "features": {"type": "string", "description": "Features to compare."}},
                ["competitors"]),
    _cloud_tool("prd_generator", "Generate a PRD outline from a feature description.",
                {"feature": {"type": "string", "description": "Feature to spec."}}, ["feature"]),
    _cloud_tool("user_story_writer", "Write user stories with acceptance criteria.",
                {"feature": {"type": "string", "description": "Feature to write stories for."}}, ["feature"]),
    _cloud_tool("sprint_planning", "Sprint planning helper: scope, capacity, risk assessment.",
                {"goals": {"type": "string", "description": "Sprint goals."}}, ["goals"]),
    _cloud_tool("tech_debt_tracker", "Track and prioritize technical debt items.",
                {"area": {"type": "string", "description": "Area to check (optional)."}}),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ATLAS — Legal & Contracts (10 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ATLAS_TOOLS = [
    _cloud_tool("contract_review", "Review a contract for key terms, risks, and negotiation points.",
                {"contract": {"type": "string", "description": "Contract description or key terms."},
                 "concerns": {"type": "string", "description": "Specific areas of concern."}},
                ["contract"]),
    _cloud_tool("clause_comparison", "Compare specific clauses against market standard or prior agreements.",
                {"clause": {"type": "string", "description": "Clause text or description."},
                 "benchmark": {"type": "string", "description": "What to compare against."}},
                ["clause"]),
    _cloud_tool("legal_risk_assessment", "Assess legal risks for an initiative, deal, or product feature.",
                {"subject": {"type": "string", "description": "What to assess."}}, ["subject"]),
    _cloud_tool("ip_search", "Search for intellectual property: patents, trademarks, prior art.",
                {"query": {"type": "string", "description": "IP to search for."}}, ["query"]),
    _cloud_tool("regulatory_lookup", "Look up regulations relevant to a product, feature, or market.",
                {"topic": {"type": "string", "description": "Regulatory area."},
                 "jurisdiction": {"type": "string", "description": "Country or region."}},
                ["topic"]),
    _cloud_tool("nda_generator", "Generate NDA outline with key terms and considerations.",
                {"parties": {"type": "string", "description": "Parties involved."},
                 "scope": {"type": "string", "description": "What's covered."}},
                ["parties"]),
    _cloud_tool("terms_of_service_audit", "Audit terms of service for compliance, risk, and user-friendliness.",
                {"service": {"type": "string", "description": "Service or product."}}, ["service"]),
    _cloud_tool("employment_law_check", "Check employment law implications for a policy or action.",
                {"question": {"type": "string", "description": "Employment law question."},
                 "jurisdiction": {"type": "string", "description": "State/country."}},
                ["question"]),
    _cloud_tool("data_processing_agreement", "Review or generate DPA terms for data handling.",
                {"context": {"type": "string", "description": "Data processing context."}}, ["context"]),
    _cloud_tool("open_source_license_audit", "Audit open source licenses for compatibility and risk.",
                {"project": {"type": "string", "description": "Project or dependency list."}}, ["project"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELIX — Engineering Architect (12 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HELIX_TOOLS = [
    _cloud_tool("architecture_review", "Review system architecture: patterns, coupling, scalability, failure modes.",
                {"architecture": {"type": "string", "description": "Architecture to review."}},
                ["architecture"]),
    _cloud_tool("code_complexity", "Analyze code complexity: cyclomatic, cognitive, coupling metrics.",
                {"component": {"type": "string", "description": "Component or module."}}, ["component"]),
    _cloud_tool("api_design_review", "Review API design: REST/GraphQL conventions, versioning, error handling.",
                {"api": {"type": "string", "description": "API to review."}}, ["api"]),
    _cloud_tool("database_schema_review", "Review database schema: normalization, indexes, query patterns.",
                {"schema": {"type": "string", "description": "Schema or table descriptions."}}, ["schema"]),
    _cloud_tool("performance_bottleneck", "Identify performance bottlenecks in a system or component.",
                {"system": {"type": "string", "description": "System to analyze."},
                 "symptoms": {"type": "string", "description": "Observed symptoms."}},
                ["system"]),
    _cloud_tool("migration_planner", "Plan a technical migration: steps, risks, rollback, timeline.",
                {"from_system": {"type": "string", "description": "Current system."},
                 "to_system": {"type": "string", "description": "Target system."}},
                ["from_system", "to_system"]),
    _cloud_tool("tech_stack_comparison", "Compare technology options with trade-offs matrix.",
                {"options": {"type": "string", "description": "Technologies to compare."},
                 "criteria": {"type": "string", "description": "Evaluation criteria."}},
                ["options"]),
    _cloud_tool("scalability_assessment", "Assess how a system will handle 10x, 100x scale.",
                {"system": {"type": "string", "description": "System to assess."},
                 "target_scale": {"type": "string", "description": "Target scale (e.g., '10x users')."}},
                ["system"]),
    _cloud_tool("adr_generate", "Generate an Architecture Decision Record for a technical decision.",
                {"decision": {"type": "string", "description": "Decision to document."},
                 "context": {"type": "string", "description": "Why this decision was needed."}},
                ["decision"]),
    _cloud_tool("effort_estimate", "Estimate engineering effort: t-shirt size, risks, dependencies.",
                {"task": {"type": "string", "description": "What to estimate."}}, ["task"]),
    _cloud_tool("tech_debt_inventory", "Inventory technical debt: categorize, prioritize, estimate payoff.",
                {"area": {"type": "string", "description": "Codebase area or system."}}),
    _cloud_tool("system_design_interview", "Walk through a system design: requirements, components, trade-offs.",
                {"system": {"type": "string", "description": "System to design."}}, ["system"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ORBIT — Customer Success (10 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ORBIT_TOOLS = [
    _cloud_tool("customer_health_score", "Calculate customer health score from usage, engagement, support data.",
                {"customer": {"type": "string", "description": "Customer name."}}, ["customer"]),
    _cloud_tool("churn_risk_analysis", "Analyze churn risk: signals, probability, recommended actions.",
                {"customer": {"type": "string", "description": "Customer to assess."}}, ["customer"]),
    _cloud_tool("ticket_history", "Get support ticket history: volume, categories, resolution times.",
                {"customer": {"type": "string", "description": "Customer name."}}, ["customer"]),
    _cloud_tool("nps_analysis", "Analyze NPS data: score trends, verbatim themes, segment breakdown.",
                {"scope": {"type": "string", "description": "Customer, segment, or 'all'."}}),
    _cloud_tool("escalation_playbook", "Generate escalation playbook for a customer situation.",
                {"situation": {"type": "string", "description": "Customer situation."}}, ["situation"]),
    _cloud_tool("renewal_forecast", "Forecast renewal probability and revenue by customer or cohort.",
                {"scope": {"type": "string", "description": "Customer or segment."}}),
    _cloud_tool("success_plan_generator", "Generate a customer success plan with milestones and metrics.",
                {"customer": {"type": "string", "description": "Customer name."},
                 "goals": {"type": "string", "description": "Customer's goals."}},
                ["customer"]),
    _cloud_tool("onboarding_tracker", "Track customer onboarding progress and blockers.",
                {"customer": {"type": "string", "description": "Customer name."}}, ["customer"]),
    _cloud_tool("customer_usage_analytics", "Analyze product usage for a customer: features, frequency, trends.",
                {"customer": {"type": "string", "description": "Customer name."}}),
    _cloud_tool("customer_comparison", "Compare two customers on health, usage, and engagement.",
                {"customer_a": {"type": "string", "description": "First customer."},
                 "customer_b": {"type": "string", "description": "Second customer."}},
                ["customer_a", "customer_b"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SPARK — Creative & Communications (10 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPARK_TOOLS = [
    _cloud_tool("message_framework", "Create a messaging framework: value prop, proof points, key messages.",
                {"product": {"type": "string", "description": "Product or initiative."},
                 "audience": {"type": "string", "description": "Target audience."}},
                ["product"]),
    _cloud_tool("press_release_draft", "Draft a press release for an announcement.",
                {"announcement": {"type": "string", "description": "What's being announced."}},
                ["announcement"]),
    _cloud_tool("blog_post_draft", "Draft a blog post outline or intro.",
                {"topic": {"type": "string", "description": "Blog topic."},
                 "audience": {"type": "string", "description": "Target readers."}},
                ["topic"]),
    _cloud_tool("presentation_outline", "Create a presentation outline with key slides and talking points.",
                {"topic": {"type": "string", "description": "Presentation topic."},
                 "audience": {"type": "string", "description": "Who it's for."},
                 "duration": {"type": "string", "description": "Length (e.g., '10 minutes')."}},
                ["topic"]),
    _cloud_tool("brand_voice_check", "Check if content matches brand voice guidelines.",
                {"content": {"type": "string", "description": "Content to check."}}, ["content"]),
    _cloud_tool("audience_analysis", "Analyze target audience: demographics, needs, channels, messaging.",
                {"audience": {"type": "string", "description": "Audience to analyze."}}, ["audience"]),
    _cloud_tool("content_calendar", "Generate a content calendar with topics, formats, and timing.",
                {"theme": {"type": "string", "description": "Campaign or theme."},
                 "duration": {"type": "string", "description": "Calendar duration."}},
                ["theme"]),
    _cloud_tool("crisis_communication", "Draft crisis communication: statement, Q&A, internal messaging.",
                {"crisis": {"type": "string", "description": "Crisis situation."}}, ["crisis"]),
    _cloud_tool("internal_announcement", "Draft an internal announcement for the team.",
                {"news": {"type": "string", "description": "What to announce."},
                 "tone": {"type": "string", "description": "Tone: celebratory, neutral, sensitive."}},
                ["news"]),
    _cloud_tool("social_campaign", "Design a social media campaign: platforms, content types, cadence.",
                {"campaign": {"type": "string", "description": "Campaign objective."},
                 "platforms": {"type": "string", "description": "Social platforms."}},
                ["campaign"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# QUANTUM — AI/ML Specialist (12 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUANTUM_TOOLS = [
    _cloud_tool("model_comparison", "Compare ML/AI models: accuracy, cost, latency, capabilities.",
                {"models": {"type": "string", "description": "Models to compare."},
                 "use_case": {"type": "string", "description": "Intended use case."}},
                ["models"]),
    _cloud_tool("dataset_analysis", "Analyze a dataset: quality, bias, size, distribution, suitability.",
                {"dataset": {"type": "string", "description": "Dataset description."}}, ["dataset"]),
    _cloud_tool("training_cost_estimate", "Estimate ML training costs: compute, data, time, total.",
                {"model": {"type": "string", "description": "Model type and size."},
                 "data_size": {"type": "string", "description": "Training data size."}},
                ["model"]),
    _cloud_tool("inference_optimization", "Optimize inference: latency, throughput, cost, quantization.",
                {"model": {"type": "string", "description": "Model to optimize."},
                 "constraints": {"type": "string", "description": "Latency/cost constraints."}},
                ["model"]),
    _cloud_tool("prompt_engineering", "Optimize a prompt: structure, few-shot examples, guardrails.",
                {"task": {"type": "string", "description": "What the prompt does."},
                 "current_prompt": {"type": "string", "description": "Current prompt (if any)."}},
                ["task"]),
    _cloud_tool("eval_framework", "Design an evaluation framework for an AI system.",
                {"system": {"type": "string", "description": "AI system to evaluate."},
                 "metrics": {"type": "string", "description": "Key metrics."}},
                ["system"]),
    _cloud_tool("bias_detection", "Detect and assess bias in a model or dataset.",
                {"target": {"type": "string", "description": "Model or dataset to check."}}, ["target"]),
    _cloud_tool("ml_pipeline_review", "Review ML pipeline: data flow, training, deployment, monitoring.",
                {"pipeline": {"type": "string", "description": "Pipeline to review."}}, ["pipeline"]),
    _cloud_tool("gpu_cost_optimizer", "Optimize GPU costs: instance types, spot pricing, scheduling.",
                {"workload": {"type": "string", "description": "GPU workload description."}}, ["workload"]),
    _cloud_tool("ai_strategy", "AI strategy assessment: build vs buy, use cases, roadmap.",
                {"question": {"type": "string", "description": "Strategy question."}}, ["question"]),
    _cloud_tool("rag_architecture", "Design or review a RAG system: retrieval, chunking, embedding, generation.",
                {"use_case": {"type": "string", "description": "RAG use case."}}, ["use_case"]),
    _cloud_tool("agent_architecture", "Design or review an AI agent system: tools, memory, planning, safety.",
                {"system": {"type": "string", "description": "Agent system description."}}, ["system"]),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool registries
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPECIALIST_TOOLS: dict[str, list[dict]] = {
    # Phase 5
    "cipher": CIPHER_TOOLS,
    "forge": FORGE_TOOLS,
    "shield": SHIELD_TOOLS,
    "ledger": LEDGER_TOOLS,
    "pulse": PULSE_TOOLS,
    # Phase 6
    "atlas": ATLAS_TOOLS,
    "helix": HELIX_TOOLS,
    "orbit": ORBIT_TOOLS,
    "spark": SPARK_TOOLS,
    "quantum": QUANTUM_TOOLS,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Executors — domain-specific LLM-powered analysis
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Agent system prompts for tool execution context
_AGENT_SYSTEMS = {
    "cipher": (
        "You are Cipher, a cloud infrastructure expert with deep AWS/Azure/GCP knowledge. "
        "You're calm during incidents, explain complex infra in metaphors, and always think about cost. "
        "Be specific with service names, metrics, and thresholds. Spoken format, 3-5 sentences."
    ),
    "forge": (
        "You are Forge, a DevOps and platform engineer. Automation-obsessed. "
        "Opinionated about CI/CD, pragmatic about trade-offs. "
        "Every answer should consider: reliability, speed, cost, and maintainability. "
        "Spoken format, 3-5 sentences."
    ),
    "shield": (
        "You are Shield, a security and compliance expert. Pragmatic, not paranoid. "
        "Rank risks by actual impact, not theoretical severity. "
        "Translate security to business language. Never use FUD. "
        "Spoken format, 3-5 sentences."
    ),
    "ledger": (
        "You are Ledger, a finance and business operations expert. "
        "You speak numbers fluently and always connect them to the business story. "
        "Every dollar here is a dollar not there. Be specific with numbers. "
        "Spoken format, 3-5 sentences."
    ),
    "pulse": (
        "You are Pulse, a product manager. You think in terms of user problems, not features. "
        "Data-informed but not data-paralyzed. Ship fast, learn fast. "
        "Ask 'what problem are we solving?' before anything else. "
        "Spoken format, 3-5 sentences."
    ),
    "atlas": (
        "You are Atlas, a legal and contracts expert. You translate legal to plain English. "
        "Risk-calibrated — not everything is a five-alarm fire. "
        "Always note when something needs actual legal counsel vs your analysis. "
        "NEVER say 'this is legal advice'. Spoken format, 3-5 sentences."
    ),
    "helix": (
        "You are Helix, an engineering architect. You think in trade-offs, not best practices. "
        "Who maintains this at 2 AM? The simplest thing that works is usually the right answer. "
        "Be specific about complexity costs. Spoken format, 3-5 sentences."
    ),
    "orbit": (
        "You are Orbit, a customer success expert. You genuinely care about customer outcomes. "
        "The customer's real goal is often different from what they asked for. "
        "Their usage tells a different story than their words. Spoken format, 3-5 sentences."
    ),
    "spark": (
        "You are Spark, a creative and communications expert. You think visually and pitch by painting pictures. "
        "Nobody cares about features — they care about outcomes. Frame everything as a story. "
        "Spoken format, 3-5 sentences."
    ),
    "quantum": (
        "You are Quantum, an AI/ML specialist. Pragmatic about AI, skeptical of hype. "
        "Before reaching for deep learning, have we baselined this? The bottleneck is rarely the model. "
        "Be specific about trade-offs between accuracy, cost, and latency. Spoken format, 3-5 sentences."
    ),
}


async def execute_specialist_tool(
    agent_name: str,
    tool_name: str,
    tool_input: dict,
    org_id: str | None = None,
    meeting_id: str | None = None,
    transcript_buffer: list[dict] | None = None,
) -> str:
    """Execute a Phase 5 specialist tool.

    All specialist tools use LLM-powered analysis since they depend on
    external integrations (cloud APIs, CRMs, etc.) that aren't connected yet.
    The LLM provides expert-level analysis based on the agent's domain knowledge.
    When real integrations are added, the LLM analysis will be augmented with live data.
    """
    try:
        system = _AGENT_SYSTEMS.get(agent_name, "You are a domain specialist. Be concise and specific.")

        # Build prompt from tool input
        prompt_parts = [f"Tool: {tool_name}"]
        for key, value in tool_input.items():
            if value:
                prompt_parts.append(f"{key}: {value}")

        # Add transcript context for meeting-aware tools
        if transcript_buffer and tool_name in _TRANSCRIPT_AWARE_TOOLS:
            recent = transcript_buffer[-10:]
            context = "\n".join(f"{s['speaker']}: {s['text']}" for s in recent)
            prompt_parts.append(f"\nRecent meeting context:\n{context}")

        prompt = "\n".join(prompt_parts)

        return await _llm_analyze(prompt, system=system)

    except Exception as e:
        logger.error(f"Specialist tool failed [{agent_name}/{tool_name}]: {e}", exc_info=True)
        return f"Sorry, that tool didn't work right now. Please try again."


# Tools that benefit from meeting transcript context
_TRANSCRIPT_AWARE_TOOLS = {
    "deployment_risk_score", "incident_timeline", "post_mortem_generate",
    "threat_model", "incident_response_playbook",
    "sprint_planning", "feature_prioritization",
    # Phase 6
    "architecture_review", "effort_estimate", "crisis_communication",
    "escalation_playbook", "prompt_engineering", "ai_strategy",
}
