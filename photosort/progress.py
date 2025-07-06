"""Progress tracking context for photosort operations."""

from typing import Optional
from rich.progress import Progress, TaskID


class ProgressContext:
    """Encapsulates progress tracking state for cleaner parameter passing."""
    
    def __init__(self, progress: Optional[Progress] = None, task: Optional[TaskID] = None):
        self.progress = progress
        self.task = task
    
    @property
    def is_active(self) -> bool:
        """Check if progress tracking is active."""
        return self.progress is not None and self.task is not None
    
    def update(self, description: str) -> None:
        """Update progress description if tracking is active."""
        if self.is_active:
            self.progress.update(self.task, description=description)
    
    def advance(self, steps: int = 1) -> None:
        """Advance progress by given number of steps."""
        if self.is_active:
            self.progress.advance(self.task, steps)