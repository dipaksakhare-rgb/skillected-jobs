"""Crawler & ingestion architecture (§50–52, §89).

Frequency-agnostic: the pipeline is identical whether it runs every 15 minutes
or every 12 hours — only the scheduler cadence changes. API-first, RSS second,
HTML third; browser automation only where permitted (§51).
"""
