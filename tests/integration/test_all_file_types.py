"""
Integration tests for processing all supported file types.

This test module verifies that the TextCleaner can correctly handle
all supported file types from end to end.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from textcleaner.core.processor import TextProcessor, ProcessingResult
from textcleaner.core.factories import TextProcessorFactory
from textcleaner.utils.security import TestingSecurityUtils
from textcleaner.core.directory_processor import DirectoryProcessor
from textcleaner.utils.parallel import parallel_processor


@pytest.fixture(scope="module")
def test_files_dir():
    """Create a temporary directory with test files of all supported types."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a directory structure for sample files
        root_dir = Path(temp_dir)
        
        # Plain text samples
        txt_dir = root_dir / "text"
        txt_dir.mkdir()
        
        # Create a simple text file
        simple_txt = txt_dir / "simple.txt"
        with open(simple_txt, "w") as f:
            f.write("This is a simple text file.\n")
            f.write("It has multiple lines.\n")
            f.write("For testing purposes.\n")
        
        # Markdown samples
        md_dir = root_dir / "markdown"
        md_dir.mkdir()
        
        # Create a simple markdown file
        markdown_file = md_dir / "sample.md"
        with open(markdown_file, "w") as f:
            f.write("# Sample Markdown\n\n")
            f.write("This is a *markdown* file with **formatting**.\n\n")
            f.write("## Section 1\n\n")
            f.write("- List item 1\n")
            f.write("- List item 2\n\n")
            f.write("## Section 2\n\n")
            f.write("Some more content here.\n")
        
        # HTML samples
        html_dir = root_dir / "html"
        html_dir.mkdir()
        
        # Create a simple HTML file
        html_file = html_dir / "simple.html"
        with open(html_file, "w") as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html>\n")
            f.write("<head>\n")
            f.write("  <title>Sample HTML Page</title>\n")
            f.write("  <meta name='author' content='Test Author'>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("  <h1>Sample HTML Page</h1>\n")
            f.write("  <p>This is a paragraph with <b>bold</b> and <i>italic</i> text.</p>\n")
            f.write("  <ul>\n")
            f.write("    <li>List item 1</li>\n")
            f.write("    <li>List item 2</li>\n")
            f.write("  </ul>\n")
            f.write("  <script>console.log('This should be removed');</script>\n")
            f.write("</body>\n")
            f.write("</html>\n")
        
        # XML samples
        xml_dir = root_dir / "xml"
        xml_dir.mkdir()
        
        # Create a simple XML file
        xml_file = xml_dir / "sample.xml"
        with open(xml_file, "w") as f:
            f.write("<?xml version='1.0' encoding='UTF-8'?>\n")
            f.write("<root>\n")
            f.write("  <title>Sample XML Document</title>\n")
            f.write("  <metadata>\n")
            f.write("    <author>Test Author</author>\n")
            f.write("    <date>2025-04-08</date>\n")
            f.write("  </metadata>\n")
            f.write("  <content>\n")
            f.write("    <section>\n")
            f.write("      <heading>Section 1</heading>\n")
            f.write("      <paragraph>This is the first section content.</paragraph>\n")
            f.write("    </section>\n")
            f.write("    <section>\n")
            f.write("      <heading>Section 2</heading>\n")
            f.write("      <paragraph>This is the second section content.</paragraph>\n")
            f.write("    </section>\n")
            f.write("  </content>\n")
            f.write("</root>\n")
        
        # Create output directory
        output_dir = root_dir / "output"
        output_dir.mkdir()
        
        yield root_dir
        
        # Clean up is handled automatically by the tempfile context manager


@pytest.fixture(scope="module")
def directory_processor():
    """Create a DirectoryProcessor instance for testing."""
    factory = TextProcessorFactory()
    # Add override for lxml parser
    overrides = {"converters": {"html": {"parser": "lxml"}}}
    single_file_processor = factory.create_processor(config_type="standard", custom_overrides=overrides)
    # Instantiate DirectoryProcessor with necessary components
    return DirectoryProcessor(
        config=single_file_processor.config,
        security_utils=TestingSecurityUtils(), # Use relaxed security for temp dirs
        parallel_processor=parallel_processor, # Use the singleton
        single_file_processor=single_file_processor
    )


def test_process_all_file_types(test_files_dir, directory_processor):
    """Test processing all supported file types."""
    # Get the underlying single file processor for direct file processing test
    processor = directory_processor.single_file_processor
    
    # Define the output directory
    output_dir = test_files_dir / "output"
    
    # Process each file type - map format names to directory names
    format_to_dir = {
        "txt": "text",
        "md": "markdown",
        "html": "html",
        "xml": "xml"
    }
    processed_files = []
    
    for format_name, dir_name in format_to_dir.items():
        format_dir = test_files_dir / dir_name
        assert format_dir.exists(), f"Test directory for {format_name} (directory: {dir_name}) not found"
        
        # Find files of this type
        files = list(format_dir.glob(f"*.{format_name}"))
        assert files, f"No {format_name} files found in {format_dir}"
        
        for file_path in files:
            # Define output path with a unique name based on format to avoid conflicts
            output_path = output_dir / f"{file_path.stem}_{format_name}_processed.md"
            
            # Process the file with overwrite flag set to force file overwrite
            # Access the config dictionary directly since it's not a nested object
            # processor.config.set('general.overwrite_existing', True) # Use set method
            
            # The process_file method doesn't automatically create the output directory structure
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            result = processor.process_file(
                input_path=file_path,
                output_path=output_path,
                output_format="markdown"
            )
            
            # Verify processing succeeded
            assert result.success, f"Failed to process {file_path}: {result.error}"
            
            # Verify output file exists
            assert output_path.exists(), f"Output file {output_path} was not created"
            
            # Verify output file has content
            assert output_path.stat().st_size > 0, f"Output file {output_path} is empty"
            
            processed_files.append(output_path)
    
    # Verify all formats were processed
    assert len(processed_files) >= len(format_to_dir), \
        f"Not all formats were processed: {len(processed_files)} < {len(format_to_dir)}"


def test_process_directory_recursive(test_files_dir, directory_processor):
    """Test processing an entire directory recursively."""
    # Define the output directory
    output_dir = test_files_dir / "output" / "recursive"
    
    # Process the entire directory using DirectoryProcessor
    results = directory_processor.process_directory(
        input_dir=test_files_dir,
        output_dir=output_dir,
        output_format="markdown",
        recursive=True
    )
    
    # Verify all files were processed
    successful_results = [r for r in results if r.success]
    assert len(successful_results) > 0, "No files were successfully processed"
    
    # Verify output directory structure matches input
    for result in successful_results:
        assert result.output_path.exists(), f"Output file {result.output_path} was not created"
        assert result.output_path.stat().st_size > 0, f"Output file {result.output_path} is empty"


def test_process_directory_with_filter(test_files_dir, directory_processor):
    """Test processing a directory with file extension filtering."""
    # Define the output directory
    output_dir = test_files_dir / "output" / "filtered"
    
    # Process only HTML files using DirectoryProcessor
    html_extensions = [".html"]
    results = directory_processor.process_directory(
        input_dir=test_files_dir,
        output_dir=output_dir,
        output_format="markdown",
        recursive=True,
        file_extensions=html_extensions
    )
    
    # Verify only HTML files were processed
    processed_count = 0
    for result in results:
        if result.success:
            processed_count += 1
            assert result.input_path.suffix.lower() == ".html", \
                f"Non-HTML file was processed: {result.input_path}"
    
    # Check that at least one HTML file was successfully processed
    assert processed_count > 0, "No HTML files were successfully processed"
