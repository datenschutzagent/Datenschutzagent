"""Quality-evaluation harness for document extraction and LLM checks.

Run with::

    python -m evals.run            # offline evals (extraction structure + grounding)
    python -m evals.run --llm      # additionally run VVT/check evals against the configured LLM

The offline evals require no LLM provider and are suitable for CI regression gating.
"""
