#!/usr/bin/env python3
"""
Comprehensive accuracy testing tool for Pokemon card scanner.

This tool processes all test images through the scanner API and generates
detailed accuracy reports with statistics and visualizations.

Usage:
    uv run tests/accuracy_tester.py [options]
    
Options:
    --images-dir PATH        Directory containing test images (default: ../test-images-kortly)
    --output-dir PATH        Directory for reports and results (default: test_results)
    --api-url URL           API base URL (default: http://localhost:8000)
    --max-concurrent N      Maximum concurrent requests (default: 3)
    --resume                Resume from previous run using saved state
    --save-raw              Save raw API responses to JSON file
    --sample-only N         Test only first N images for quick validation
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import signal

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import Progress, TaskID
from rich.panel import Panel
from rich.table import Table

# Import our testing utilities
from tests.utils.image_processor import ImageProcessor
from tests.utils.api_client import ScannerAPIClient
from tests.utils.stats_analyzer import StatsAnalyzer
from tests.utils.report_generator import ReportGenerator

console = Console()


class AccuracyTester:
    """Main accuracy testing orchestrator."""
    
    def __init__(
        self,
        images_dir: Path,
        output_dir: Path,
        api_url: str = "http://localhost:8000",
        max_concurrent: int = 3,
        save_raw: bool = False
    ):
        self.images_dir = Path(images_dir)
        self.output_dir = Path(output_dir)
        self.api_url = api_url
        self.max_concurrent = max_concurrent
        self.save_raw = save_raw
        
        # Initialize components
        self.image_processor = ImageProcessor()
        self.api_client = ScannerAPIClient(api_url)
        self.stats_analyzer = StatsAnalyzer()
        self.report_generator = ReportGenerator(output_dir)
        
        # State management
        self.results: List[Dict[str, Any]] = []
        self.processed_files: set = set()
        self.state_file = output_dir / "test_state.json"
        self.raw_results_file = output_dir / "raw_results.json"
        
        # Progress tracking
        self.total_images = 0
        self.completed_images = 0
        self.failed_images = 0
        
        # Graceful shutdown
        self.should_stop = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown on SIGINT/SIGTERM."""
        console.print("\n[yellow]Received shutdown signal. Saving progress...[/yellow]")
        self.should_stop = True
    
    async def run(self, resume: bool = False, sample_only: Optional[int] = None) -> Path:
        """
        Run the complete accuracy testing process.
        
        Args:
            resume: Resume from previous run
            sample_only: Test only first N images
            
        Returns:
            Path to generated report
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check API health
        if not await self._check_api_health():
            console.print("[red]❌ API server not responding. Please start the server first.[/red]")
            sys.exit(1)
        
        # Load previous state if resuming
        if resume and self.state_file.exists():
            self._load_state()
            console.print(f"[green]📁 Resumed from previous run. Already processed: {len(self.processed_files)} images[/green]")
        
        # Discover images
        image_files = self._discover_images(sample_only)
        
        if not image_files:
            console.print("[red]❌ No valid image files found![/red]")
            sys.exit(1)
        
        self.total_images = len(image_files)
        remaining_files = [f for f in image_files if f.name not in self.processed_files]
        
        console.print(Panel(
            f"🃏 Pokemon Card Scanner Accuracy Test\n\n"
            f"📁 Images Directory: {self.images_dir}\n"
            f"🔗 API URL: {self.api_url}\n"
            f"🖼️  Total Images: {self.total_images}\n"
            f"⏭️  Remaining: {len(remaining_files)}\n"
            f"🔄 Concurrency: {self.max_concurrent}\n"
            f"💾 Save Raw Results: {'Yes' if self.save_raw else 'No'}",
            title="Test Configuration",
            border_style="blue"
        ))
        
        if not remaining_files:
            console.print("[green]✅ All images already processed! Generating report...[/green]")
        else:
            # Process remaining images
            await self._process_images(remaining_files)
        
        if self.should_stop:
            console.print("[yellow]⚠️  Testing interrupted. Generating report with current progress...[/yellow]")
        
        # Generate final report
        return await self._generate_report()
    
    async def _check_api_health(self) -> bool:
        """Check if the API server is healthy."""
        console.print("🔍 Checking API health...")
        try:
            healthy = await self.api_client.check_health()
            if healthy:
                console.print("[green]✅ API server is healthy[/green]")
                return True
            else:
                return False
        except Exception as e:
            console.print(f"[red]❌ API health check failed: {e}[/red]")
            return False
    
    def _discover_images(self, sample_only: Optional[int] = None) -> List[Path]:
        """Discover all valid image files in the images directory."""
        console.print("🔍 Discovering image files...")
        
        # Supported image extensions
        extensions = {'.heic', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}
        
        image_files = []
        for ext in extensions:
            image_files.extend(self.images_dir.glob(f"*{ext}"))
            image_files.extend(self.images_dir.glob(f"*{ext.upper()}"))
        
        # Sort for consistent ordering
        image_files.sort()
        
        # Apply sample limit if specified
        if sample_only and sample_only > 0:
            image_files = image_files[:sample_only]
            console.print(f"[yellow]🔬 Sample mode: Testing only first {len(image_files)} images[/yellow]")
        
        console.print(f"[green]📸 Found {len(image_files)} valid image files[/green]")
        return image_files
    
    async def _process_images(self, image_files: List[Path]):
        """Process all images through the scanner API."""
        with Progress() as progress:
            task = progress.add_task(
                f"[cyan]Processing {len(image_files)} images...", 
                total=len(image_files)
            )
            
            # Process in batches for better memory management
            batch_size = min(self.max_concurrent * 2, 10)
            
            for i in range(0, len(image_files), batch_size):
                if self.should_stop:
                    break
                
                batch = image_files[i:i + batch_size]
                batch_results = await self._process_batch(batch, progress, task)
                
                # Add results to analyzer
                for result, filename in batch_results:
                    if result:
                        self.stats_analyzer.add_result(result, filename)
                        self.results.append({**result, "filename": filename})
                        
                        if result.get("success", False):
                            self.completed_images += 1
                        else:
                            self.failed_images += 1
                    
                    self.processed_files.add(filename)
                
                # Save state periodically
                self._save_state()
                
                # Save raw results if enabled
                if self.save_raw:
                    self._save_raw_results()
        
        console.print(f"\n[green]✅ Processing complete! Success: {self.completed_images}, Failed: {self.failed_images}[/green]")
    
    async def _process_batch(
        self, 
        batch_files: List[Path], 
        progress: Progress, 
        task: TaskID
    ) -> List[tuple]:
        """Process a batch of images concurrently."""
        # Prepare image data
        image_data = []
        for image_path in batch_files:
            base64_data = self.image_processor.image_to_base64(image_path)
            if base64_data:
                image_data.append((base64_data, image_path.name))
            else:
                # Add failed conversion result
                failed_result = {
                    "success": False,
                    "error": "Failed to convert image to base64",
                    "_test_metadata": {
                        "request_time_ms": 0,
                        "status_code": 0,
                        "success": False
                    }
                }
                image_data.append((None, image_path.name))
        
        # Process batch through API
        batch_results = []
        
        if image_data:
            valid_data = [(data, name) for data, name in image_data if data is not None]
            
            if valid_data:
                api_results = await self.api_client.scan_multiple(
                    valid_data, 
                    max_concurrent=self.max_concurrent
                )
                
                # Combine results
                data_idx = 0
                for i, (data, filename) in enumerate(image_data):
                    if data is not None:
                        result = api_results[data_idx]
                        data_idx += 1
                    else:
                        result = {
                            "success": False,
                            "error": "Failed to process image",
                            "_test_metadata": {
                                "request_time_ms": 0,
                                "status_code": 0,
                                "success": False
                            }
                        }
                    
                    batch_results.append((result, filename))
                    progress.update(task, advance=1)
        
        return batch_results
    
    def _save_state(self):
        """Save current testing state for resume capability."""
        state = {
            "processed_files": list(self.processed_files),
            "completed_images": self.completed_images,
            "failed_images": self.failed_images,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _load_state(self):
        """Load previous testing state."""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                
            self.processed_files = set(state.get("processed_files", []))
            self.completed_images = state.get("completed_images", 0)
            self.failed_images = state.get("failed_images", 0)
            
            # Reload results for analyzer
            if self.raw_results_file.exists():
                with open(self.raw_results_file, 'r') as f:
                    self.results = json.load(f)
                    
                for result in self.results:
                    filename = result.get("filename", "unknown")
                    self.stats_analyzer.add_result(result, filename)
                    
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not load previous state: {e}[/yellow]")
    
    def _save_raw_results(self):
        """Save raw API results to JSON file."""
        if self.raw_results_file and self.results:
            try:
                with open(self.raw_results_file, 'w') as f:
                    json.dump(self.results, f, indent=2, default=str)
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not save raw results: {e}[/yellow]")
    
    async def _generate_report(self) -> Path:
        """Generate the final HTML report."""
        console.print("📊 Generating comprehensive report...")
        
        # Get detailed analysis
        analysis = self.stats_analyzer.get_detailed_analysis()
        
        # Generate HTML report
        report_path = self.report_generator.generate_report(
            analysis=analysis,
            results=self.results,
            test_images_dir=self.images_dir
        )
        
        # Display summary
        self._display_summary(analysis)
        
        console.print(f"\n[green]🎉 Report generated: {report_path}[/green]")
        console.print(f"[cyan]Open the report in your browser to view detailed results.[/cyan]")
        
        return report_path
    
    def _display_summary(self, analysis: Dict[str, Any]):
        """Display a summary table of key metrics."""
        metrics = analysis["overall_metrics"]
        
        table = Table(title="🏆 Test Results Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Images", str(metrics.total_images))
        table.add_row("Success Rate", f"{metrics.success_rate:.1f}%")
        table.add_row("Successful Scans", str(metrics.successful_scans))
        table.add_row("Failed Scans", str(metrics.failed_scans))
        table.add_row("Avg Processing Time", f"{metrics.avg_processing_time:.0f}ms")
        table.add_row("Total API Cost", f"${metrics.total_cost:.4f}")
        table.add_row("Avg Cost Per Scan", f"${metrics.avg_cost_per_scan:.6f}")
        table.add_row("TCG Match Rate", f"{analysis['tcg_analysis']['match_success_rate']:.1f}%")
        table.add_row("Translations", f"{analysis['language_analysis']['translations_performed']} ({analysis['language_analysis']['translation_rate']:.1f}%)")
        
        console.print(table)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pokemon Card Scanner Accuracy Tester")
    parser.add_argument(
        "--images-dir", 
        type=Path, 
        default="../test-images-kortly",
        help="Directory containing test images"
    )
    parser.add_argument(
        "--output-dir", 
        type=Path, 
        default="test_results",
        help="Directory for reports and results"
    )
    parser.add_argument(
        "--api-url", 
        default="http://localhost:8000",
        help="API base URL"
    )
    parser.add_argument(
        "--max-concurrent", 
        type=int, 
        default=3,
        help="Maximum concurrent requests"
    )
    parser.add_argument(
        "--resume", 
        action="store_true",
        help="Resume from previous run"
    )
    parser.add_argument(
        "--save-raw", 
        action="store_true",
        help="Save raw API responses to JSON"
    )
    parser.add_argument(
        "--sample-only", 
        type=int,
        help="Test only first N images for quick validation"
    )
    
    args = parser.parse_args()
    
    # Validate images directory
    if not args.images_dir.exists():
        console.print(f"[red]❌ Images directory not found: {args.images_dir}[/red]")
        sys.exit(1)
    
    # Create tester
    tester = AccuracyTester(
        images_dir=args.images_dir,
        output_dir=args.output_dir,
        api_url=args.api_url,
        max_concurrent=args.max_concurrent,
        save_raw=args.save_raw
    )
    
    try:
        # Run the test
        report_path = await tester.run(
            resume=args.resume,
            sample_only=args.sample_only
        )
        
        console.print(f"\n[bold green]✅ Testing completed successfully![/bold green]")
        console.print(f"[cyan]Report: {report_path}[/cyan]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Testing interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Testing failed: {e}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())