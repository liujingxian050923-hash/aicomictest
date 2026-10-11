"""Extend this registry for Runway, local models, or other providers.
Never mark a remote submission as completed before polling and downloading its output.
"""
from abc import ABC, abstractmethod

class GenerationProvider(ABC):
    @abstractmethod
    def submit(self,kind,prompt,references):
        """Return an actual provider task id; references are local paths."""
    @abstractmethod
    def poll(self,task_id):
        """Return {status, progress, error, output_url} from the real service."""

PROVIDERS = {} # Register tested adapters here; no fake video generation.
