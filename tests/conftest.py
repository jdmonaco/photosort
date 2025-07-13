"""
pytest configuration and fixtures for photosort tests.
"""

import io
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pytest


@dataclass
class CliResult:
    """Result from running CLI command."""
    exit_code: int
    output: str
    error: str


@pytest.fixture(scope="session")
def example_media_dir():
    """Path to the example media directory with real files.

    This directory should be created by running:
        python tests/create_test_media.py /path/to/media/collection
    """
    media_dir = Path(__file__).parent / "example_media"
    if not media_dir.exists():
        pytest.skip(
            f"Example media directory not found at {media_dir}. "
            "Run 'python tests/create_test_media.py /path/to/media' to create it."
        )
    return media_dir


@pytest.fixture
def temp_source_folder(example_media_dir, tmp_path):
    """Create a temporary copy of example media for each test."""
    temp_source = tmp_path / "source"
    shutil.copytree(example_media_dir, temp_source)
    return temp_source


@pytest.fixture(scope="session")
def test_config_base(tmp_path_factory):
    """Shared test config directory for all tests."""
    return tmp_path_factory.mktemp("photosort_test_config")


@pytest.fixture
def test_config_path(test_config_base):
    """Test-specific config path with clean state guarantee."""
    config_path = test_config_base / "config.yml"

    # Ensure clean state - remove config if it exists
    if config_path.exists():
        config_path.unlink()

    # Also clean any residual history or import logs
    history_dir = test_config_base / "history"
    imports_log = test_config_base / "imports.log"

    if history_dir.exists():
        shutil.rmtree(history_dir)
    if imports_log.exists():
        imports_log.unlink()

    return config_path


@pytest.fixture
def cli_runner(monkeypatch):
    """Create a CLI runner that captures output and uses test config."""

    def run_cli(*args, config_path=None):
        """Run photosort CLI with given arguments.

        Args:
            *args: Command line arguments (source, dest, --flags, etc)
            config_path: Optional config path for test isolation

        Returns:
            CliResult with exit_code, output, and error
        """
        from photosort.cli import main

        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout = io.StringIO()
        stderr = io.StringIO()

        # Store original argv
        old_argv = sys.argv
        
        # Store original console.input for restoration
        original_input = None

        try:
            sys.stdout = stdout
            sys.stderr = stderr

            # Mock console.input to avoid hanging on confirmation prompts
            def mock_input(prompt=""):
                # Default to "no" for confirmation prompts to avoid hanging
                return "n"
            
            # Apply the mock
            from photosort.constants import get_console
            console = get_console()
            original_input = getattr(console, 'input', None)
            console.input = mock_input

            # Set up argv
            sys.argv = ['photosort'] + [str(a) for a in args]

            # Run main with config_path
            exit_code = main(config_path=config_path)

            return CliResult(
                exit_code=exit_code,
                output=stdout.getvalue(),
                error=stderr.getvalue()
            )
        except SystemExit as e:
            # Handle sys.exit() calls
            return CliResult(
                exit_code=e.code if e.code is not None else 0,
                output=stdout.getvalue(),
                error=stderr.getvalue()
            )
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.argv = old_argv
            
            # Restore original console.input if it existed
            try:
                from photosort.constants import get_console
                console = get_console()
                if original_input:
                    console.input = original_input
                elif hasattr(console, 'input'):
                    delattr(console, 'input')
            except:
                pass  # Ignore cleanup errors

    return run_cli


@pytest.fixture
def mock_external_tools(monkeypatch):
    """Mock external tool availability for testing."""

    def mock_tools(tools_available: dict):
        """Mock specific tools as available or not.

        Args:
            tools_available: Dict of tool_name -> bool
                e.g., {"exiftool": False, "ffmpeg": True}
        """
        original_check = None

        def mock_check_tool(cmd: str, version_flag: str = "-h") -> bool:
            if cmd in tools_available:
                return tools_available[cmd]
            # Fall back to original for unmocked tools
            if original_check:
                return original_check(cmd, version_flag)
            return True

        # Import and store original
        from photosort.constants import check_tool_availability
        original_check = check_tool_availability

        # Apply mock
        monkeypatch.setattr("photosort.constants.check_tool_availability", mock_check_tool)

    return mock_tools


@pytest.fixture
def create_test_files(tmp_path):
    """Helper to create test files with specific properties."""

    def create_files(file_specs: List[dict]) -> Path:
        """Create test files based on specifications.

        Args:
            file_specs: List of dicts with keys:
                - name: filename
                - content: file content (optional)
                - mtime: modification time as datetime (optional)

        Returns:
            Path to directory containing created files
        """
        test_dir = tmp_path / "test_files"
        test_dir.mkdir(exist_ok=True)

        for spec in file_specs:
            file_path = test_dir / spec['name']

            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            content = spec.get('content', b'test file content')
            if isinstance(content, str):
                file_path.write_text(content)
            else:
                file_path.write_bytes(content)

            # Set modification time if specified
            if 'mtime' in spec:
                import os
                mtime = spec['mtime'].timestamp()
                os.utime(file_path, (mtime, mtime))

        return test_dir

    return create_files


@pytest.fixture
def assert_file_structure():
    """Helper to assert expected file structure."""

    def check_structure(base_path: Path, expected_structure: dict):
        """Assert that directory has expected structure.

        Args:
            base_path: Root directory to check
            expected_structure: Dict describing expected structure
                e.g., {
                    "2024": {
                        "01": ["file1.jpg", "file2.jpg"],
                        "02": ["file3.jpg"]
                    }
                }
        """
        def check_level(path: Path, structure: dict):
            for name, value in structure.items():
                item_path = path / name
                assert item_path.exists(), f"Expected {item_path} to exist"

                if isinstance(value, dict):
                    # It's a directory, recurse
                    assert item_path.is_dir(), f"Expected {item_path} to be a directory"
                    check_level(item_path, value)
                elif isinstance(value, list):
                    # It's a directory with expected files
                    assert item_path.is_dir(), f"Expected {item_path} to be a directory"
                    actual_files = sorted([f.name for f in item_path.iterdir() if f.is_file()])
                    expected_files = sorted(value)
                    assert actual_files == expected_files, \
                        f"Expected files {expected_files} in {item_path}, got {actual_files}"

        check_level(base_path, expected_structure)

    return check_structure


@pytest.fixture
def assert_history_structure():
    """Helper to assert history folder structure."""

    def check_history(config_path: Path, dest_name: str):
        """Assert that history folder was created with expected structure.

        Args:
            config_path: Path to test config
            dest_name: Expected destination name in history folder

        Returns:
            Path to the history folder for further inspection
        """
        history_root = config_path.parent / "history"
        assert history_root.exists(), f"History root {history_root} should exist"

        # Find folder containing dest_name
        history_folders = list(history_root.glob("*"))
        matching = [f for f in history_folders if dest_name in f.name]

        assert len(matching) == 1, \
            f"Expected exactly one history folder with '{dest_name}', found {len(matching)}"

        history_folder = matching[0]

        # Check expected subdirectories
        expected_dirs = ["LegacyVideos", "Metadata", "UnknownFiles", "Unsorted"]
        for dir_name in expected_dirs:
            dir_path = history_folder / dir_name
            assert dir_path.exists(), f"Expected {dir_path} to exist"
            assert dir_path.is_dir(), f"Expected {dir_path} to be a directory"

        # Check import.log exists
        import_log = history_folder / "import.log"
        assert import_log.exists(), f"Expected {import_log} to exist"

        return history_folder

    return check_history
