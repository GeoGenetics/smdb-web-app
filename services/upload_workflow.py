"""Upload orchestration boundary.

This module will coordinate parsed uploads, reference-data lookup, and
preflight validation. It must not import or access Flask request, session,
redirect, flash, or template globals.
"""
