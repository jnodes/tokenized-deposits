"""
StableArch Council - Crew Assembly
=====================================
Assembles the CrewAI hierarchical crew with the Orchestrator as manager_agent.
Context: the Issuing Bank Cari deposit platform on the Cari Network / ZKsync Prividium.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.
"""

from __future__ import annotations

import os
from crewai import Crew, Process

from agents.orchestrator import create_orchestrator_agent
from agents.cari_deposit_platform import create_cari_deposit_platform_agent
from agents.tech_stack import create_tech_stack_agent
from agents.security_guardian import create_security_guardian_agent
from agents.strategic_advisory import create_strategic_advisory_agent
from tasks import (
    create_platform_architecture_task,
    create_tech_stack_evaluation_task,
    create_security_compliance_task,
    create_strategic_advisory_task,
    create_arb_synthesis_task,
)
from guardrails import run_guardrail_checks


def build_crew(llm=None, verbose: bool = True) -> Crew:
    """Build and return the StableArch Council crew.

    Args:
        llm: Optional LLM instance to pass to all agents.
             If None, agents will use CrewAI's default LLM
             (set via OPENAI_API_KEY or OPENAI_MODEL_NAME env vars).
        verbose: Whether to enable verbose logging.

    Returns:
        A configured CrewAI Crew instance ready to kickoff.
    """
    # -- Create Agents --
    orchestrator = create_orchestrator_agent(llm=llm)
    cari_architect = create_cari_deposit_platform_agent(llm=llm)
    tech_stack_expert = create_tech_stack_agent(llm=llm)
    security_guardian = create_security_guardian_agent(llm=llm)
    strategic_advisor = create_strategic_advisory_agent(llm=llm)

    # -- Create Tasks --
    platform_task = create_platform_architecture_task(cari_architect)
    tech_task = create_tech_stack_evaluation_task(tech_stack_expert)
    security_task = create_security_compliance_task(security_guardian)
    strategy_task = create_strategic_advisory_task(strategic_advisor)

    # The synthesis task receives context from all specialist tasks
    synthesis_task = create_arb_synthesis_task(
        agent=orchestrator,
        context_tasks=[platform_task, tech_task, security_task, strategy_task],
    )

    # -- Assemble Crew --
    crew = Crew(
        agents=[
            cari_architect,
            tech_stack_expert,
            security_guardian,
            strategic_advisor,
        ],
        tasks=[
            platform_task,
            tech_task,
            security_task,
            strategy_task,
            synthesis_task,
        ],
        process=Process.hierarchical,
        manager_agent=orchestrator,
        verbose=verbose,
    )

    return crew


def run_council(
    topic: str | None = None,
    llm=None,
    verbose: bool = True,
    output_file: str | None = None,
) -> str:
    """Run the StableArch Council and return the ARB package.

    Args:
        topic: Optional topic/scenario to append to the kickoff inputs.
        llm: Optional LLM instance.
        verbose: Enable verbose output.
        output_file: If set, write the ARB package and guardrail report here.

    Returns:
        The final ARB package text.
    """
    crew = build_crew(llm=llm, verbose=verbose)

    inputs = {
        "bank": "the Issuing Bank",
        "network": "Cari Network",
        "l2": "ZKsync Prividium",
    }
    if topic:
        inputs["topic"] = topic

    result = crew.kickoff(inputs=inputs)
    arb_output = str(result)

    # -- Run regulatory guardrail checks --
    report = run_guardrail_checks(arb_output)
    guardrail_text = report.summary()

    full_output = f"{arb_output}\n\n{guardrail_text}"

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_output)
        if verbose:
            print(f"\nARB package written to: {output_file}")

    if not report.passed:
        print("\n*** GUARDRAIL FAILURES DETECTED ***")
        print(guardrail_text)
    else:
        print("\nAll regulatory guardrails passed.")

    return full_output
