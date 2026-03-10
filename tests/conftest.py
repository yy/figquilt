"""Pytest configuration for stable headless plotting tests."""

import matplotlib


# Force a non-interactive backend so tests don't require a GUI session.
matplotlib.use("Agg")
