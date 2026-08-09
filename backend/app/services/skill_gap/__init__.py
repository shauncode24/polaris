# backend/app/services/skill_gap/__init__.py
# app/services/skill_gap package — the Comparison Engine (design doc §5 /
# revision "Comparison Engine (Current Skill Gap Analyzer)"). Pure
# comparison: Engineering Identity evidence + a TargetProfile in,
# GapAnalysisResult out. Knows nothing about parsing job descriptions,
# extracting companies, or understanding resumes — see comparison.py.